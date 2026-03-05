import time
import os
import sys

import logging
logging.basicConfig(level=logging.DEBUG)

from dotenv import load_dotenv
load_dotenv()

from config import ACCESS_TOKEN, INDEX_INSTRUMENTS
from growwapi import GrowwAPI, GrowwFeed

print("Initializing API...")
groww = GrowwAPI(ACCESS_TOKEN)
print("Creating feed...")
feed = GrowwFeed(groww)

count = 0

from config import _load_instruments_csv
rows = _load_instruments_csv()

print("BANKNIFTY matches (NSE CASH):")
for row in rows:
    if row.get("exchange") == "NSE" and row.get("segment") == "CASH" and "BANKNIFTY" in row.get("trading_symbol", ""):
        print(row.get("trading_symbol"), row.get("exchange_token"))

print("\nBANKEX matches (BSE CASH):")
for row in rows:
    if row.get("exchange") == "BSE" and row.get("segment") == "CASH" and "BANKEX" in row.get("trading_symbol", ""):
        print(row.get("trading_symbol"), row.get("exchange_token"))

print("\nExact matches for NIFTY BANK:")
for row in rows:
    if row.get("trading_symbol") == "NIFTY BANK" or row.get("trading_symbol") == "BANKNIFTY":
        print("Found:", row.get("exchange"), row.get("segment"), row.get("trading_symbol"), row.get("exchange_token"))

os._exit(0)
