"""
Web server for Sensex / Nifty ratio monitor.
Uses Groww Trade API for live index and futures data.
Token: set GROWW_ACCESS_TOKEN in env, or use GROWW_API_KEY + GROWW_TOTP_SECRET (no expiry).
Refresh: update GROWW_ACCESS_TOKEN in env when it expires, or use /token to regenerate via API key+secret.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_socketio import SocketIO
from growwapi import GrowwAPI, GrowwFeed

from config import (
    ACCESS_TOKEN,
    INDEX_INSTRUMENTS,
    FUT_INSTRUMENTS,
    NIFTY_INDEX,
    SENSEX_INDEX,
    NIFTY_FUT_INSTRUMENT,
    SENSEX_FUT_INSTRUMENTS,
)

_current_access_token: str | None = None
_feed_thread: threading.Thread | None = None
_feed: GrowwFeed | None = None

REFRESH_SECRET = os.getenv("REFRESH_SECRET", "").strip()
GROWW_API_KEY = os.getenv("GROWW_API_KEY", "").strip()
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "").strip()

app = Flask(__name__)
app.config["SECRET_KEY"] = "sensex-nifty-secret"
# Use threading so server responds when eventlet is present; avoids monkey-patch issues
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

state: dict[str, Any] = {
    "nifty_fut": None,
    "sensex_fut": None,
    "fut_ratio": None,
    "nifty_cash": None,
    "sensex_cash": None,
    "cash_ratio": None,
}

# Google Sheets live push (optional)
_sheets_last_push: float = 0
_sheets_lock: threading.Lock = threading.Lock()
SHEETS_PUSH_INTERVAL = 2.0  # seconds between pushes to avoid rate limits


def _push_state_to_sheets() -> None:
    """Push current state to Google Sheet (if configured). Throttled, runs in background."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        return
    with _sheets_lock:
        if time.monotonic() - _sheets_last_push < SHEETS_PUSH_INTERVAL:
            return
        _sheets_last_push = time.monotonic()

    def _do_push() -> None:
        try:
            try:
                from google.oauth2.service_account import Credentials
                from googleapiclient.discovery import build
            except ImportError:
                print("Sheets push skipped: install google-auth and google-api-python-client", flush=True)
                return
            creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            if creds_json:
                creds = Credentials.from_service_account_info(json.loads(creds_json))
            elif creds_path and os.path.isfile(creds_path):
                creds = Credentials.from_service_account_file(creds_path)
            else:
                return
            service = build("sheets", "v4", credentials=creds)
            range_name = os.getenv("GOOGLE_SHEET_RANGE", "Sheet1!A1:B7").strip()
            values = [
                ["Metric", "Value"],
                ["Nifty Fut", state.get("nifty_fut") or ""],
                ["Sensex Fut", state.get("sensex_fut") or ""],
                ["Fut Ratio", state.get("fut_ratio") or ""],
                ["Nifty Cash", state.get("nifty_cash") or ""],
                ["Sensex Cash", state.get("sensex_cash") or ""],
                ["Cash Ratio", state.get("cash_ratio") or ""],
            ]
            body = {"values": values}
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
        except Exception as e:
            print(f"Sheets push error: {e}", flush=True)

    t = threading.Thread(target=_do_push, daemon=True)
    t.start()


def _broadcast_state() -> None:
    payload = {
        "nifty_fut": state["nifty_fut"],
        "sensex_fut": state["sensex_fut"],
        "fut_ratio": state["fut_ratio"],
        "nifty_cash": state["nifty_cash"],
        "sensex_cash": state["sensex_cash"],
        "cash_ratio": state["cash_ratio"],
    }
    socketio.emit("state", payload)
    _push_state_to_sheets()


def _extract_sensex_ltp(data: dict | None) -> float | None:
    """Extract Sensex LTP from first instrument that has data (NSE or BSE)."""
    if data is None:
        return None
    for inst in SENSEX_FUT_INSTRUMENTS:
        val = _extract_ltp(data, inst)
        if val is not None:
            return val
    return None


def _on_feed_data(meta: dict, feed: GrowwFeed) -> None:
    if meta is None or not isinstance(meta, dict):
        return
    feed_type = (meta.get("feed_type") or meta.get("feedType") or "").strip()

    if feed_type == "ltp":
        ltp_data = feed.get_ltp()
        if ltp_data is None:
            return
        nf = _extract_ltp(ltp_data, NIFTY_FUT_INSTRUMENT)
        sf = _extract_sensex_ltp(ltp_data)
        updated = False
        if nf is not None:
            state["nifty_fut"] = round(nf, 2)
            updated = True
        if sf is not None:
            state["sensex_fut"] = round(sf, 2)
            updated = True
        if nf is not None and sf is not None:
            state["fut_ratio"] = round(sf / nf, 4)
            updated = True
        if updated:
            _broadcast_state()

    if feed_type == "index_value":
        idx_data = feed.get_index_value()
        if idx_data is None:
            return
        nc = _extract_index_value(idx_data, NIFTY_INDEX)
        sc = _extract_index_value(idx_data, SENSEX_INDEX)
        if nc is not None and sc is not None:
            state["nifty_cash"] = round(nc, 2)
            state["sensex_cash"] = round(sc, 2)
            state["cash_ratio"] = round(sc / nc, 4)
            _broadcast_state()


def _extract_ltp(data: dict | None, instrument: dict) -> float | None:
    """Extract LTP from feed.get_ltp() result: exchange -> segment -> exchange_token -> {ltp}."""
    if data is None:
        return None
    try:
        ex = data.get(instrument["exchange"]) or {}
        seg = ex.get(instrument["segment"]) or {}
        token_key = instrument["exchange_token"]
        # SDK may key by str or int
        tok = seg.get(token_key) or seg.get(str(token_key))
        if tok is None and str(token_key).isdigit():
            tok = seg.get(int(token_key))
        if tok is None:
            return None
        # Value may be a number directly (e.g. BSE feed)
        if isinstance(tok, (int, float)):
            return float(tok)
        if not isinstance(tok, dict):
            return None
        # Proto may use ltp, lastPrice, last_price, last, close
        price = (
            tok.get("ltp")
            or tok.get("lastPrice")
            or tok.get("last_price")
            or tok.get("last")
            or tok.get("close")
        )
        return float(price) if price is not None else None
    except (TypeError, KeyError, ValueError):
        return None


def _extract_index_value(data: dict | None, instrument: dict) -> float | None:
    if data is None:
        return None
    try:
        ex = (data.get(instrument["exchange"]) or {})
        seg = ex.get(instrument["segment"]) or {}
        tok = seg.get(instrument["exchange_token"]) or {}
        return float(tok.get("value"))
    except (TypeError, KeyError, ValueError):
        return None


def _get_access_token() -> str:
    return _current_access_token if _current_access_token is not None else ACCESS_TOKEN


def _run_feed() -> None:
    global _feed
    try:
        token = _get_access_token()
        groww = GrowwAPI(token)
        feed = GrowwFeed(groww)
        _feed = feed

        def callback(meta: dict) -> None:
            try:
                _on_feed_data(meta, feed)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                print(f"Feed callback error: {e}", file=sys.stderr, flush=True)

        feed.subscribe_index_value(INDEX_INSTRUMENTS, on_data_received=callback)
        feed.subscribe_ltp(FUT_INSTRUMENTS, on_data_received=callback)
        feed.consume()
    except Exception as e:
        # Groww SDK sometimes raises/logs errors with empty message; show type and args
        msg = str(e).strip() or repr(e)
        print(f"Groww feed error: {msg}", flush=True)
        raise


def start_ticker() -> None:
    global _feed_thread
    if _feed_thread is not None and _feed_thread.is_alive():
        return
    _feed_thread = threading.Thread(target=_run_feed, daemon=True)
    _feed_thread.start()


def _restart_ticker() -> None:
    start_ticker()


@app.route("/")
def index() -> Any:
    return render_template("index.html")


@app.route("/api/state")
def api_state_json() -> Any:
    """Return current live state as JSON (for Google Sheets Apps Script, Excel Power Query, etc.)."""
    return jsonify(state)


@app.route("/api/state.csv")
def api_state_csv() -> Any:
    """Return current live state as CSV (for =IMPORTDATA in Sheets, Excel Get Data from Web)."""
    from io import StringIO
    import csv as csv_module
    buf = StringIO()
    w = csv_module.writer(buf)
    w.writerow(["metric", "value"])
    for key, val in state.items():
        w.writerow([key, val if val is not None else ""])
    return buf.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8"}


@app.route("/token", methods=["GET", "POST"])
def token_page() -> Any:
    if request.method == "POST":
        secret = request.form.get("secret", "").strip()
        if REFRESH_SECRET and secret != REFRESH_SECRET:
            return render_template(
                "token.html", error="Invalid password.", require_password=bool(REFRESH_SECRET)
            ), 403
        if not GROWW_API_KEY or not GROWW_API_SECRET:
            return render_template(
                "token.html",
                error="GROWW_API_KEY and GROWW_API_SECRET must be set to refresh token here.",
                require_password=bool(REFRESH_SECRET),
            ), 400
        try:
            new_token = GrowwAPI.get_access_token(api_key=GROWW_API_KEY, secret=GROWW_API_SECRET)
        except Exception as e:
            return render_template(
                "token.html", error=str(e), require_password=bool(REFRESH_SECRET)
            ), 400
        global _current_access_token
        _current_access_token = new_token
        _restart_ticker()
        return redirect(url_for("index") + "?token_updated=1")
    return render_template(
        "token.html",
        error=None,
        require_password=bool(REFRESH_SECRET),
    )


@app.route("/token-callback")
def token_callback() -> Any:
    return redirect(url_for("token_page"))


@socketio.on("connect")
def handle_connect() -> None:
    _broadcast_state()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8002"))
    # Start feed after a short delay so the web server binds first and responds
    def start_feed_delayed() -> None:
        time.sleep(1.5)
        start_ticker()
    threading.Thread(target=start_feed_delayed, daemon=True).start()
    print(f"\n  On this computer, open in browser: http://127.0.0.1:{port}")
    print(f"  (or http://localhost:{port})")
    print(f"  From phone (same Wi‑Fi): http://<this-PC-IP>:{port}")
    print(f"  Starting server on port {port}...\n")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
else:
    start_ticker()
