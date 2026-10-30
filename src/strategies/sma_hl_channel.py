"""sma_hl_channel (trade_ela): SMA20 high / SMA20 low channel.
Bias long only above channel; entries: fractal break or pullback-touch+close. SL swing/channel; TP RR1.5/2/3. M5/M15.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def generate_sma_hl_channel(
    m1: pd.DataFrame,
    tf: str = "M15",
    entry_mode: str = "break",  # break | pullback
    rr: float = 2.0,
    sl_mode: str = "swing",     # swing | channel
) -> List[Order]:
    bar = 5 if tf == "M5" else 15
    df = resample_ohlc(m1, f"{bar}min")
    h, l, c = df["high"], df["low"], df["close"]
    sma_h = h.rolling(20).mean().shift(1).values  # prior closed
    sma_l = l.rolling(20).mean().shift(1).values
    hv, lv, cv = h.values, l.values, c.values
    times = df.index
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(hv, lv, 2, 2)
    n = len(df)
    variant = f"smahl_{tf}_{entry_mode}_rr{rr:g}_sl{sl_mode}"
    orders: List[Order] = []
    used = set()

    for i in range(25, n - 1):
        if np.isnan(sma_h[i]) or np.isnan(a[i]) or a[i] <= 0:
            continue
        if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
            continue
        above = cv[i] > sma_h[i]
        below = cv[i] < sma_l[i]
        if not above and not below:
            continue
        side = "long" if above else "short"
        key = (times[i].normalize(), side)
        if key in used:
            continue

        signal = False
        if entry_mode == "break":
            if side == "long":
                sw = last_swing_before(shi, i)
                if sw is not None and cv[i] > hv[sw] and cv[i - 1] <= hv[sw]:
                    signal = True
            else:
                sw = last_swing_before(sli, i)
                if sw is not None and cv[i] < lv[sw] and cv[i - 1] >= lv[sw]:
                    signal = True
        else:  # pullback: touch channel then close back through
            if side == "long":
                if lv[i] <= sma_h[i] and cv[i] > sma_h[i] and cv[i] > df["open"].values[i]:
                    signal = True
            else:
                if hv[i] >= sma_l[i] and cv[i] < sma_l[i] and cv[i] < df["open"].values[i]:
                    signal = True
        if not signal:
            continue

        px = float(cv[i])
        buf = max(0.1 * a[i], 0.12)
        if sl_mode == "channel":
            sl = float(sma_l[i]) - buf if side == "long" else float(sma_h[i]) + buf
        else:
            if side == "long":
                sw = last_swing_before(sli, i)
                sl = (float(lv[sw]) - buf) if sw is not None else float(sma_l[i]) - buf
            else:
                sw = last_swing_before(shi, i)
                sl = (float(hv[sw]) + buf) if sw is not None else float(sma_h[i]) + buf
        if (side == "long" and sl >= px) or (side == "short" and sl <= px):
            continue
        risk = abs(px - sl)
        if risk < 0.2:
            continue
        tp = px + rr * risk if side == "long" else px - rr * risk
        arm = bar_end(times[i], bar)
        orders.append(Order(
            arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
            strategy="SMAHLChannel", variant=variant, meta={},
            expire_minutes=bar * 2, max_hold_minutes=bar * 80,
        ))
        used.add(key)

    return dedupe_orders(orders, bar)


def generate_smahl_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15"):
        for em in ("break", "pullback"):
            for rr in (1.5, 2.0, 3.0):
                for slm in ("swing", "channel"):
                    print(f" smahl {tf} {em} rr{rr} {slm}", flush=True)
                    oo = generate_sma_hl_channel(m1, tf, em, rr, slm)
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
    return pools
