"""
Helper script to generate a Groww API access token.

Usage (for API Key + Secret approval flow):

  1. Ensure your `.env` (or shell) has:
       GROWW_API_KEY=...
       GROWW_API_SECRET=...
  2. Approve the key for today at https://groww.in/trade-api/api-keys
  3. Run:
       python generate_token.py
  4. Copy the printed GROWW_ACCESS_TOKEN into your `.env`.

For TOTP (no expiry): set GROWW_API_KEY and GROWW_TOTP_SECRET; the app
generates the token at startup. No need to run this script.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required but not set. "
            "Set it in your shell or .env before running this script."
        )
    return value.strip()


def main() -> None:
    from growwapi import GrowwAPI

    api_key = _require_env("GROWW_API_KEY")
    secret = _require_env("GROWW_API_SECRET")

    access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)

    print("\nGROWW_ACCESS_TOKEN:", access_token)
    print(
        "\nAdd this line to your .env file:\n"
        f"GROWW_ACCESS_TOKEN={access_token}\n"
    )
    print("Token expires daily at 6:00 AM. Re-run after approving the key again.")


if __name__ == "__main__":
    main()
