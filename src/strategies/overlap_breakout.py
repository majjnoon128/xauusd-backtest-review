"""overlap_breakout (abolfazl.ghariblou): London–NY overlap range break.
Pre-overlap window variants 11:00–12:30 / 12:00–13:30 UTC; M5 closed break or stop;
SL opposite/mid; TP RR4/2/3; skip SL>cap (engine).
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


def generate_overlap_breakout(
    m1: pd.DataFrame,
    pre_start: str = "11:00",   # HH:MM UTC
    pre_end: str = "12:30",
    entry_kind: str = "market", # market (closed break) | stop
    sl_mode: str = "opp",       # opp | mid
    rr: float = 4.0,
) -> List[Order]:
    m5 = resample_ohlc(m1, "5min")
    h, l, c = m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    n = len(m5)
    sh, sm = map(int, pre_start.split(":"))
    eh, em = map(int, pre_end.split(":"))
    variant = f"ovbo_{pre_start.replace(':','')}_{pre_end.replace(':','')}_{entry_kind}_sl{sl_mode}_rr{rr:g}"
    orders: List[Order] = []

    days = [d for d in m1.index.normalize().unique()
            if int(getattr(d, "day_of_week", d.dayofweek)) < 5]
    for d in days:
        d = pd.Timestamp(d)
        w0 = d + pd.Timedelta(hours=sh, minutes=sm)
        w1 = d + pd.Timedelta(hours=eh, minutes=em)
        # overlap trade window ~ until 16:00 UTC
        t0 = w1
        t1 = d + pd.Timedelta(hours=16)
        seg = m1[(m1.index >= w0) & (m1.index < w1)]
        if len(seg) < 20:
            continue
        rh, rl = float(seg["high"].max()), float(seg["low"].min())
        rng = rh - rl
        if rng < 0.5:
            continue
        mid = 0.5 * (rh + rl)
        i0 = times.searchsorted(t0, side="left")
        i1 = times.searchsorted(t1, side="left")
        fired = False
        for i in range(i0, min(i1, n - 1)):
            if fired:
                break
            # closed break
            side = None
            if c[i] > rh and c[i - 1] <= rh:
                side = "long"
            elif c[i] < rl and c[i - 1] >= rl:
                side = "short"
            if side is None:
                continue
            px = float(c[i]) if entry_kind == "market" else (rh if side == "long" else rl)
            if sl_mode == "opp":
                sl = rl - 0.05 if side == "long" else rh + 0.05
            else:
                sl = mid
            if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                continue
            risk = abs(px - sl)
            if risk < 0.25:
                continue
            tp = px + rr * risk if side == "long" else px - rr * risk
            arm = bar_end(times[i], 5)
            kind = "market" if entry_kind == "market" else "stop"
            orders.append(Order(
                arm_time=arm, side=side, kind=kind, price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="OverlapBO", variant=variant, meta={"rh": rh, "rl": rl},
                expire_minutes=90, max_hold_minutes=240,
            ))
            fired = True

    return dedupe_orders(orders, 30)


def generate_overlap_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    windows = [("11:00", "12:30"), ("12:00", "13:30")]
    for ps, pe in windows:
        for ek in ("market", "stop"):
            for slm in ("opp", "mid"):
                for rr in (4.0, 3.0, 2.0):
                    print(f" ovbo {ps}-{pe} {ek} {slm} rr{rr}", flush=True)
                    oo = generate_overlap_breakout(m1, ps, pe, ek, slm, rr)
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
    return pools
