"""Idris: H4 high/low (closed) + M1 RSI hidden div + Inside Bar → market after IB close."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import rsi, inside_bar, resample_ohlc, atr_prior, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders


def generate_idris(m1, dxy=None, use_dxy=False, use_vol=False, rr=3.0, vol_mult=1.3) -> List[Order]:
    h4 = resample_ohlc(m1, "4h")
    m1_rsi = rsi(m1["close"], 14).values
    ib = inside_bar(m1).values
    a = atr_prior(m1, 14).values
    high, low, close = m1["high"].values, m1["low"].values, m1["close"].values
    times = m1.index
    h4_high, h4_low, h4_idx = h4["high"].values, h4["low"].values, h4.index
    # simple pivot lows/highs left=3 right=3 — only use pivots confirmed (i-3)
    n = len(m1)
    pl = np.zeros(n, dtype=bool)
    ph = np.zeros(n, dtype=bool)
    for i in range(3, n - 3):
        if low[i] == low[i-3:i+4].min() and (low[i-3:i+4] == low[i]).sum() == 1:
            pl[i + 3] = True  # confirm at i+3 → store flag at confirm bar pointing... simplify: mark pivot bar when confirmed
        if high[i] == high[i-3:i+4].max() and (high[i-3:i+4] == high[i]).sum() == 1:
            ph[i + 3] = True
    # Better: store confirmed pivot indices
    pivot_lows, pivot_highs = [], []
    for i in range(3, n - 3):
        if low[i] == low[i-3:i+4].min() and (low[i-3:i+4] == low[i]).sum() == 1:
            pivot_lows.append(i)  # known only after i+3
        if high[i] == high[i-3:i+4].max() and (high[i-3:i+4] == high[i]).sum() == 1:
            pivot_highs.append(i)

    orders = []
    vol_ma20 = vol_ma(m1["volume"], 20) if "volume" in m1.columns else None
    pl_arr = np.array(pivot_lows) if pivot_lows else np.array([], dtype=int)
    ph_arr = np.array(pivot_highs) if pivot_highs else np.array([], dtype=int)

    for i in range(50, n - 1):
        ts = times[i]
        if not in_session(ts) or not ib[i]:
            continue
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        # last CLOSED H4: bar ending <= ts
        # H4 left-labeled; closed when start+4h <= ts → start <= ts-4h
        deadline = ts - pd.Timedelta(hours=4)
        hi = h4_idx.searchsorted(deadline, side="right") - 1
        if hi < 0:
            continue
        zh, zl = float(h4_high[hi]), float(h4_low[hi])
        tol = 0.15 * atr_i
        touched_low = low[max(0, i-5):i+1].min() <= zl + tol
        touched_high = high[max(0, i-5):i+1].max() >= zh - tol

        # pivots confirmed only if pivot_bar + 3 <= i
        side = None
        if touched_low:
            pls = pl_arr[pl_arr + 3 <= i]
            if len(pls) >= 2:
                p2, p1 = pls[-1], pls[-2]
                if low[p2] > low[p1] and m1_rsi[p2] < m1_rsi[p1]:
                    side = "long"
        if side is None and touched_high:
            phs = ph_arr[ph_arr + 3 <= i]
            if len(phs) >= 2:
                p2, p1 = phs[-1], phs[-2]
                if high[p2] < high[p1] and m1_rsi[p2] > m1_rsi[p1]:
                    side = "short"
        if side is None:
            continue

        if side == "long":
            entry = float(high[i])  # buy stop ref at IB high — use market after close at close
            entry = float(close[i])
            sl = float(low[i]) - 0.05 * atr_i
            risk = entry - sl
            if risk <= 0.05:
                continue
            tp = entry + rr * risk
        else:
            entry = float(close[i])
            sl = float(high[i]) + 0.05 * atr_i
            risk = sl - entry
            if risk <= 0.05:
                continue
            tp = entry - rr * risk

        arm = bar_end(ts, 1)
        orders.append(Order(arm, side, "market", entry, sl, tp, "Idris", f"h4_rsi_ib_rr{rr}",
                            {"signal_bar": ts}, 30))

    orders = dedupe_orders(orders, 30)
    if use_vol and vol_ma20 is not None:
        orders = apply_vol_gate(orders, m1["volume"], vol_ma20, True, vol_mult, 1)
    return apply_dxy_gate(orders, dxy, use_dxy)
