"""
Configuration for Groww API Sensex/Nifty ratio app.

Sensitive values (access token or API key + TOTP) are read from
environment variables.

Required (one of):
  - GROWW_ACCESS_TOKEN
  - GROWW_API_KEY + GROWW_TOTP_SECRET (token generated at runtime, no expiry)
  - GROWW_API_KEY + GROWW_API_SECRET (token generated at runtime; approve key daily at Groww)

Optional overrides for futures (exchange_token from Groww instruments CSV):
  - NIFTY_FUT_EXCHANGE_TOKEN
  - SENSEX_FUT_EXCHANGE_TOKEN
"""

from __future__ import annotations

import base64
import csv
import os
import ssl
from datetime import date, datetime
from typing import Optional
from urllib.request import urlopen

import certifi

INSTRUMENT_CSV_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"

# Index identifiers for Groww Feed (fixed: Nifty = NSE NIFTY, Sensex = BSE 1)
NIFTY_INDEX = {"exchange": "NSE", "segment": "CASH", "exchange_token": "NIFTY"}
SENSEX_INDEX = {"exchange": "BSE", "segment": "CASH", "exchange_token": "1"}


def _require_env(name: str) -> str:
    """Return required environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required but not set. "
            "Set it in your shell or a .env file before running the app."
        )
    return value


def _totp_secret_for_pyotp(raw: str) -> str:
    """Return a base32 TOTP secret pyotp can use. Handles base32, hex, or base64 from Groww."""
    stripped = raw.strip().replace(" ", "")
    normalized_upper = stripped.upper()
    # Try as base32 first (pyotp expects base32)
    try:
        base64.b32decode(normalized_upper, casefold=True)
        return normalized_upper
    except Exception:
        pass
    # Try hex
    if len(stripped) % 2 == 0 and all(c in "0123456789ABCDEFabcdef" for c in stripped):
        try:
            secret_bytes = bytes.fromhex(stripped)
            return base64.b32encode(secret_bytes).decode("ascii").rstrip("=")
        except Exception:
            pass
    # Try base64 (standard or URL-safe)
    for candidate in (stripped, stripped + "=="):
        try:
            secret_bytes = base64.b64decode(candidate, validate=True)
            return base64.b32encode(secret_bytes).decode("ascii").rstrip("=")
        except Exception:
            pass
    try:
        padded = stripped + "==" if len(stripped) % 4 else stripped
        secret_bytes = base64.urlsafe_b64decode(padded)
        return base64.b32encode(secret_bytes).decode("ascii").rstrip("=")
    except Exception:
        pass
    raise ValueError(
        "GROWW_TOTP_SECRET must be base32 (A–Z, 2–7), hex, or base64. "
        "Copy the exact secret from Groww’s TOTP setup (not the 6-digit code)."
    )


def _get_access_token() -> str:
    """Resolve access token: GROWW_ACCESS_TOKEN, or generate from API_KEY + TOTP or API_KEY + SECRET."""
    token = os.getenv("GROWW_ACCESS_TOKEN", "").strip()
    if token:
        return token
    api_key = os.getenv("GROWW_API_KEY", "").strip()
    totp_secret = os.getenv("GROWW_TOTP_SECRET", "").strip()
    api_secret = os.getenv("GROWW_API_SECRET", "").strip()
    if api_key and totp_secret:
        try:
            import pyotp
            from growwapi import GrowwAPI
            secret_b32 = _totp_secret_for_pyotp(totp_secret)
            totp_code = pyotp.TOTP(secret_b32).now()
            # Ensure 6-digit string (Groww may expect this format)
            totp_str = str(totp_code).zfill(6)
            return GrowwAPI.get_access_token(api_key=api_key, totp=totp_str)
        except ValueError as e:
            raise RuntimeError(str(e)) from e
        except Exception as e:
            err_msg = str(e)
            if "400" in err_msg and "Groww API" in err_msg:
                raise RuntimeError(
                    f"{e}\n\nTOTP 400 usually means: (1) GROWW_API_KEY must be the key from "
                    "'Generate TOTP token' (not 'Generate API key'). (2) The secret must match that key. "
                    "Alternatively use GROWW_API_KEY + GROWW_API_SECRET and approve the key daily at "
                    "https://groww.in/trade-api/api-keys"
                ) from e
            raise RuntimeError(
                f"Could not generate Groww token from GROWW_API_KEY + GROWW_TOTP_SECRET: {e}"
            ) from e
    if api_key and api_secret:
        try:
            from growwapi import GrowwAPI
            return GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
        except Exception as e:
            raise RuntimeError(
                f"Could not generate Groww token from GROWW_API_KEY + GROWW_API_SECRET: {e}. "
                "Ensure you have approved the key today at https://groww.in/trade-api/api-keys"
            ) from e
    raise RuntimeError(
        "Set GROWW_ACCESS_TOKEN, or (GROWW_API_KEY and GROWW_TOTP_SECRET), "
        "or (GROWW_API_KEY and GROWW_API_SECRET) in your environment."
    )


ACCESS_TOKEN: str = _get_access_token()


def _env_str(name: str) -> Optional[str]:
    raw = os.getenv(name)
    return raw.strip() if raw else None


def _load_instruments_csv() -> list[dict]:
    """Download and parse Groww instruments CSV (public URL)."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urlopen(INSTRUMENT_CSV_URL, timeout=30, context=ctx) as resp:
        text = resp.read().decode("utf-8")
    reader = csv.DictReader(line for line in text.splitlines() if line.strip())
    return list(reader)


def _parse_expiry(exp_str: Optional[str]) -> Optional[date]:
    if not exp_str or not exp_str.strip():
        return None
    try:
        return datetime.strptime(exp_str.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_nearest_fut(
    rows: list[dict],
    symbol_prefixes: list[str],
    exchange: str = "NSE",
) -> str:
    """Return exchange_token for nearest-expiry future matching one of symbol_prefixes."""
    today = date.today()
    candidates = []
    for row in rows:
        if row.get("exchange") != exchange or row.get("segment") != "FNO":
            continue
        exp = _parse_expiry(row.get("expiry_date"))
        if exp is None or exp < today:
            continue
        sym = (row.get("trading_symbol") or "").strip()
        if not any(sym.startswith(p) for p in symbol_prefixes):
            continue
        if "FUT" not in sym.upper():
            continue
        candidates.append((exp, row.get("exchange_token", "")))
    if not candidates:
        raise RuntimeError(
            f"Could not find {symbol_prefixes} futures on {exchange}. "
            "Set NIFTY_FUT_EXCHANGE_TOKEN / SENSEX_FUT_EXCHANGE_TOKEN in your environment."
        )
    candidates.sort(key=lambda x: x[0])
    return str(candidates[0][1])


def _resolve_fut_tokens() -> tuple[str, str]:
    """Resolve Nifty and Sensex futures exchange_tokens (env override or from CSV)."""
    nifty_env = _env_str("NIFTY_FUT_EXCHANGE_TOKEN")
    sensex_env = _env_str("SENSEX_FUT_EXCHANGE_TOKEN")
    if nifty_env and sensex_env:
        return nifty_env, sensex_env

    rows = _load_instruments_csv()
    nifty = nifty_env or _resolve_nearest_fut(rows, ["NIFTY"], "NSE")
    if sensex_env:
        sensex = sensex_env
    else:
        try:
            sensex = _resolve_nearest_fut(rows, ["SENSEX", "BFSENSEX"], "NSE")
        except RuntimeError:
            try:
                sensex = _resolve_nearest_fut(rows, ["SENSEX", "BFSENSEX"], "BSE")
            except RuntimeError as e:
                raise RuntimeError(
                    "Could not resolve SENSEX futures. Set SENSEX_FUT_EXCHANGE_TOKEN in your environment."
                ) from e
    return nifty, sensex


NIFTY_FUT_EXCHANGE_TOKEN, SENSEX_FUT_EXCHANGE_TOKEN = _resolve_fut_tokens()

NIFTY_FUT_INSTRUMENT = {"exchange": "NSE", "segment": "FNO", "exchange_token": NIFTY_FUT_EXCHANGE_TOKEN}
SENSEX_FUT_INSTRUMENT = {"exchange": "NSE", "segment": "FNO", "exchange_token": SENSEX_FUT_EXCHANGE_TOKEN}
INDEX_INSTRUMENTS = [NIFTY_INDEX, SENSEX_INDEX]
FUT_INSTRUMENTS = [NIFTY_FUT_INSTRUMENT, SENSEX_FUT_INSTRUMENT]
