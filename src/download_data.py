"""Download XAU/USD M1 and FX pairs for synthetic DXY from Dukascopy."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
import pandas as pd
import dukascopy_python as d

DATA = Path("/workspace/trading/backtest/data")
DATA.mkdir(parents=True, exist_ok=True)

# Prefer ~12 months ending just before today (box date ~2026-10-30)
END = datetime(2026, 10, 28, tzinfo=timezone.utc)
START = datetime(2025, 10, 1, tzinfo=timezone.utc)

INSTRUMENTS = {
    "XAUUSD": ("XAU/USD", d.INTERVAL_MIN_1),
    "EURUSD": ("EUR/USD", d.INTERVAL_MIN_15),
    "USDJPY": ("USD/JPY", d.INTERVAL_MIN_15),
    "GBPUSD": ("GBP/USD", d.INTERVAL_MIN_15),
    "USDCAD": ("USD/CAD", d.INTERVAL_MIN_15),
    "USDCHF": ("USD/CHF", d.INTERVAL_MIN_15),
    "USDSEK": ("USD/SEK", d.INTERVAL_MIN_15),
}

# M1: ~20 trading days per chunk to stay under 30k limit
# M15: can do ~2 months per chunk


def chunk_ranges(start, end, days):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def download_instrument(name, symbol, interval, start, end, chunk_days):
    out = DATA / f"{name}.parquet"
    if out.exists():
        df = pd.read_parquet(out)
        print(f"[skip] {name} already has {len(df)} bars -> {out}")
        return df
    parts = []
    for a, b in chunk_ranges(start, end, chunk_days):
        for attempt in range(5):
            try:
                df = d.fetch(symbol, interval, d.OFFER_SIDE_BID, a, b, max_retries=3)
                if df is not None and len(df):
                    parts.append(df)
                    print(f"  {name} {a.date()} -> {b.date()}: {len(df)} bars")
                else:
                    print(f"  {name} {a.date()} -> {b.date()}: empty")
                break
            except Exception as e:
                print(f"  {name} {a.date()} attempt {attempt+1}: {e}")
                time.sleep(2 + attempt)
        time.sleep(0.3)
    if not parts:
        raise RuntimeError(f"No data for {name}")
    full = pd.concat(parts).sort_index()
    full = full[~full.index.duplicated(keep="last")]
    full.to_parquet(out)
    print(f"[ok] {name}: {len(full)} bars, {full.index.min()} .. {full.index.max()}")
    return full


def build_synthetic_dxy():
    """ICE DXY formula from 6 FX pairs (M15)."""
    pairs = {}
    for name in ["EURUSD", "USDJPY", "GBPUSD", "USDCAD", "USDCHF", "USDSEK"]:
        path = DATA / f"{name}.parquet"
        df = pd.read_parquet(path)
        pairs[name] = df["close"].rename(name)
    px = pd.concat(pairs.values(), axis=1).dropna()
    # Official ICE DXY constant & exponents
    dxy = (
        50.14348112
        * px["EURUSD"] ** (-0.576)
        * px["USDJPY"] ** (0.136)
        * px["GBPUSD"] ** (-0.119)
        * px["USDCAD"] ** (0.091)
        * px["USDSEK"] ** (0.042)
        * px["USDCHF"] ** (0.036)
    )
    out = pd.DataFrame({"close": dxy})
    out.to_parquet(DATA / "DXY_synth.parquet")
    print(f"[ok] DXY_synth: {len(out)} bars, range {dxy.min():.2f}-{dxy.max():.2f}")
    return out


def main():
    for name, (symbol, interval) in INSTRUMENTS.items():
        chunk = 14 if interval == d.INTERVAL_MIN_1 else 45
        download_instrument(name, symbol, interval, START, END, chunk)
    build_synthetic_dxy()
    print("DONE")


if __name__ == "__main__":
    main()
