"""
Desktop (Tkinter) Sensex / Nifty ratio monitor using Groww Trade API.
Run: python app.py
Requires GROWW_ACCESS_TOKEN or (GROWW_API_KEY + GROWW_TOTP_SECRET) in .env.
"""

import threading
import tkinter as tk
from dotenv import load_dotenv

load_dotenv()

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

root = tk.Tk()
root.title("Sensex / Nifty – Cash & Futures (Groww)")
root.geometry("420x420")

nifty_fut_var = tk.StringVar(value="--")
sensex_fut_var = tk.StringVar(value="--")
fut_ratio_var = tk.StringVar(value="--")
nifty_cash_var = tk.StringVar(value="--")
sensex_cash_var = tk.StringVar(value="--")
cash_ratio_var = tk.StringVar(value="--")

def row(label, var):
    tk.Label(root, text=label, font=("Arial", 11)).pack()
    tk.Label(root, textvariable=var, font=("Arial", 14, "bold")).pack()

row("NIFTY FUT", nifty_fut_var)
row("SENSEX FUT", sensex_fut_var)
row("FUT RATIO (SENSEX / NIFTY)", fut_ratio_var)
tk.Label(root, text="").pack()
row("NIFTY CASH", nifty_cash_var)
row("SENSEX CASH", sensex_cash_var)
row("CASH RATIO (SENSEX / NIFTY)", cash_ratio_var)

LOW = 3.25
HIGH = 3.26
fut_below_325 = 0
fut_above_326 = 0
cash_below_325 = 0
cash_above_326 = 0
prev_fut_ratio = None
prev_cash_ratio = None


def _extract_ltp(data, instrument):
    try:
        ex = data.get("ltp", {}).get(instrument["exchange"], {})
        seg = ex.get(instrument["segment"], {})
        tok = seg.get(instrument["exchange_token"], {})
        return float(tok.get("ltp"))
    except (TypeError, KeyError, ValueError):
        return None


def _extract_index_value(data, instrument):
    try:
        ex = data.get(instrument["exchange"], {})
        seg = ex.get(instrument["segment"], {})
        tok = seg.get(instrument["exchange_token"], {})
        return float(tok.get("value"))
    except (TypeError, KeyError, ValueError):
        return None


def on_feed_data(meta, feed):
    global fut_below_325, fut_above_326, cash_below_325, cash_above_326
    global prev_fut_ratio, prev_cash_ratio
    feed_type = meta.get("feed_type", "")

    if feed_type == "ltp":
        ltp_data = feed.get_ltp()
        nf = _extract_ltp(ltp_data, NIFTY_FUT_INSTRUMENT)
        sf = _extract_ltp(ltp_data, SENSEX_FUT_INSTRUMENT)
        if nf is not None and sf is not None:
            fut_ratio = sf / nf
            nifty_fut_var.set(round(nf, 2))
            sensex_fut_var.set(round(sf, 2))
            fut_ratio_var.set(round(fut_ratio, 4))
            if prev_fut_ratio is not None:
                if prev_fut_ratio >= LOW and fut_ratio < LOW:
                    fut_below_325 += 1
                    print("FUT crossed BELOW 3.25 →", fut_below_325)
                if prev_fut_ratio <= HIGH and fut_ratio > HIGH:
                    fut_above_326 += 1
                    print("FUT crossed ABOVE 3.26 →", fut_above_326)
            prev_fut_ratio = fut_ratio

    if feed_type == "index_value":
        idx_data = feed.get_index_value()
        nc = _extract_index_value(idx_data, NIFTY_INDEX)
        sc = _extract_index_value(idx_data, SENSEX_INDEX)
        if nc is not None and sc is not None:
            cash_ratio = sc / nc
            nifty_cash_var.set(round(nc, 2))
            sensex_cash_var.set(round(sc, 2))
            cash_ratio_var.set(round(cash_ratio, 4))
            if prev_cash_ratio is not None:
                if prev_cash_ratio >= LOW and cash_ratio < LOW:
                    cash_below_325 += 1
                    print("CASH crossed BELOW 3.25 →", cash_below_325)
                if prev_cash_ratio <= HIGH and cash_ratio > HIGH:
                    cash_above_326 += 1
                    print("CASH crossed ABOVE 3.26 →", cash_above_326)
            prev_cash_ratio = cash_ratio


def run_feed():
    groww = GrowwAPI(ACCESS_TOKEN)
    feed = GrowwFeed(groww)

    def callback(meta):
        on_feed_data(meta, feed)

    feed.subscribe_index_value(INDEX_INSTRUMENTS, on_data_received=callback)
    feed.subscribe_ltp(FUT_INSTRUMENTS, on_data_received=callback)
    feed.consume()


t = threading.Thread(target=run_feed, daemon=True)
t.start()

root.mainloop()
