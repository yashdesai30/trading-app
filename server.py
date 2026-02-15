"""
Web server for Sensex / Nifty ratio monitor.
Uses Groww Trade API for live index and futures data.
Token: set GROWW_ACCESS_TOKEN in env, or use GROWW_API_KEY + GROWW_TOTP_SECRET (no expiry).
Refresh: update GROWW_ACCESS_TOKEN in env when it expires, or use /token to regenerate via API key+secret.
"""

from __future__ import annotations

import json
import os
import threading
import time
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
    SENSEX_FUT_INSTRUMENT,
)

_current_access_token: str | None = None
_feed_thread: threading.Thread | None = None
_feed: GrowwFeed | None = None

REFRESH_SECRET = os.getenv("REFRESH_SECRET", "").strip()
GROWW_API_KEY = os.getenv("GROWW_API_KEY", "").strip()
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "").strip()

app = Flask(__name__)
app.config["SECRET_KEY"] = "sensex-nifty-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

LOW = 3.25
HIGH = 3.26

state: dict[str, Any] = {
    "nifty_fut": None,
    "sensex_fut": None,
    "fut_ratio": None,
    "nifty_cash": None,
    "sensex_cash": None,
    "cash_ratio": None,
    "fut_below_325": 0,
    "fut_above_326": 0,
    "cash_below_325": 0,
    "cash_above_326": 0,
}

prev_fut_ratio: float | None = None
prev_cash_ratio: float | None = None

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
            range_name = os.getenv("GOOGLE_SHEET_RANGE", "Sheet1!A1:B11").strip()
            values = [
                ["Metric", "Value"],
                ["Nifty Fut", state.get("nifty_fut") or ""],
                ["Sensex Fut", state.get("sensex_fut") or ""],
                ["Fut Ratio", state.get("fut_ratio") or ""],
                ["Nifty Cash", state.get("nifty_cash") or ""],
                ["Sensex Cash", state.get("sensex_cash") or ""],
                ["Cash Ratio", state.get("cash_ratio") or ""],
                ["Fut below 3.25", state.get("fut_below_325", 0)],
                ["Fut above 3.26", state.get("fut_above_326", 0)],
                ["Cash below 3.25", state.get("cash_below_325", 0)],
                ["Cash above 3.26", state.get("cash_above_326", 0)],
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
        "fut_below_325": state["fut_below_325"],
        "fut_above_326": state["fut_above_326"],
        "cash_below_325": state["cash_below_325"],
        "cash_above_326": state["cash_above_326"],
    }
    socketio.emit("state", payload)
    _push_state_to_sheets()


def _on_feed_data(meta: dict, feed: GrowwFeed) -> None:
    global prev_fut_ratio, prev_cash_ratio
    feed_type = meta.get("feed_type", "")

    if feed_type == "ltp":
        ltp_data = feed.get_ltp()
        nf = _extract_ltp(ltp_data, NIFTY_FUT_INSTRUMENT)
        sf = _extract_ltp(ltp_data, SENSEX_FUT_INSTRUMENT)
        if nf is not None and sf is not None:
            fut_ratio = sf / nf
            state["nifty_fut"] = round(nf, 2)
            state["sensex_fut"] = round(sf, 2)
            state["fut_ratio"] = round(fut_ratio, 4)
            if prev_fut_ratio is not None:
                if prev_fut_ratio >= LOW and fut_ratio < LOW:
                    state["fut_below_325"] += 1
                if prev_fut_ratio <= HIGH and fut_ratio > HIGH:
                    state["fut_above_326"] += 1
            prev_fut_ratio = fut_ratio
            _broadcast_state()

    if feed_type == "index_value":
        idx_data = feed.get_index_value()
        nc = _extract_index_value(idx_data, NIFTY_INDEX)
        sc = _extract_index_value(idx_data, SENSEX_INDEX)
        if nc is not None and sc is not None:
            cash_ratio = sc / nc
            state["nifty_cash"] = round(nc, 2)
            state["sensex_cash"] = round(sc, 2)
            state["cash_ratio"] = round(cash_ratio, 4)
            if prev_cash_ratio is not None:
                if prev_cash_ratio >= LOW and cash_ratio < LOW:
                    state["cash_below_325"] += 1
                if prev_cash_ratio <= HIGH and cash_ratio > HIGH:
                    state["cash_above_326"] += 1
            prev_cash_ratio = cash_ratio
            _broadcast_state()


def _extract_ltp(data: dict, instrument: dict) -> float | None:
    try:
        ex = data.get("ltp", {}).get(instrument["exchange"], {})
        seg = ex.get(instrument["segment"], {})
        tok = seg.get(instrument["exchange_token"], {})
        return float(tok.get("ltp"))
    except (TypeError, KeyError, ValueError):
        return None


def _extract_index_value(data: dict, instrument: dict) -> float | None:
    try:
        ex = data.get(instrument["exchange"], {})
        seg = ex.get(instrument["segment"], {})
        tok = seg.get(instrument["exchange_token"], {})
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
            _on_feed_data(meta, feed)

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
    start_ticker()
    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  Open in browser (or on your phone, same Wi‑Fi): http://0.0.0.0:{port}")
    print(f"  On this machine: http://127.0.0.1:{port}\n")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
else:
    start_ticker()
