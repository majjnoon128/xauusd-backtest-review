"""H4-open FVG: bias from previous CLOSED H4 direction (no lookahead on forming H4).
Bull: price sweeps below H4 open (of current forming H4), M15/M5 swing low swept, bullish BOS/MSS,
limit at FVG of impulse, SL at sweep, TP 1:2. Mirror bear.
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
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before


def generate_h4open_fvg(
    m1: pd.DataFrame,
    entry_tf: str = "M15",   # M15 | M5
    rr: float = 2.0,
    bias_mode: str = "prev_h4",  # prev_h4 | side_of_open
    atr_buf: float = 0.15,
) -> List[Order]:
    bar_m = 15 if entry_tf == "M15" else 5
    df = resample_ohlc(m1, f"{bar_m}min")
    h4 = resample_ohlc(m1, "4h")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)

    h4_o = h4["open"].values
    h4_c = h4["close"].values
    h4_h = h4["high"].values
    h4_l = h4["low"].values
    h4_t = h4.index

    variant = f"h4open_{entry_tf}_{bias_mode}_rr{rr}"
    orders: List[Order] = []
    used = set()

    # map each LTF bar to current forming H4 index and previous closed H4
    h4_pos = h4_t.searchsorted(times, side="right") - 1

    for i in range(30, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        hi = int(h4_pos[i])
        if hi < 1:
            continue
        # previous closed H4 = hi-1 (current forming is hi, not fully closed)
        # Confirm hi is still forming: times[i] < h4_t[hi] + 4h
        if times[i] >= h4_t[hi] + pd.Timedelta(hours=4):
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        prev = hi - 1
        cur_open = float(h4_o[hi])
        # bias
        if bias_mode == "prev_h4":
            if h4_c[prev] > h4_o[prev]:
                bias = "long"
            elif h4_c[prev] < h4_o[prev]:
                bias = "short"
            else:
                continue
        else:  # side_of_open at sweep time — still uses only closed LTF info
            # require trade on bullish side of open for long setups etc. applied below
            bias = None  # determined by sweep side relative to open

        key = (h4_t[hi],)
        if key in used:
            continue

        side = None
        swept = None
        # bull: price below H4 open, sweep swing low, close back above swept low (MSS reclaim)
        if (bias == "long" or bias_mode == "side_of_open") and l[i] < cur_open:
            sw = last_swing_before(sli, i)
            if sw is not None and l[i] < l[sw] and c[i] > l[sw] and c[i] > o[i]:
                if bias == "long" or bias_mode == "side_of_open":
                    side = "long"
                    swept = float(min(l[i], l[sw]))
        if side is None and (bias == "short" or bias_mode == "side_of_open") and h[i] > cur_open:
            sw = last_swing_before(shi, i)
            if sw is not None and h[i] > h[sw] and c[i] < h[sw] and c[i] < o[i]:
                side = "short"
                swept = float(max(h[i], h[sw]))
        if side is None or swept is None:
            continue
        # for prev_h4 bias, enforce matching direction
        if bias_mode == "prev_h4" and bias is not None and side != bias:
            continue

        # FVG of impulse (last few bars)
        fdir = "bull" if side == "long" else "bear"
        fvgs = find_fvgs(h, l, a, max(i - 8, 0), i, fdir, min_atr=0.05)
        if not fvgs:
            continue
        glo, ghi, _ = fvgs[-1]
        px = 0.5 * (glo + ghi)
        buf = max(atr_buf * atr_v, 0.12)
        if side == "long":
            sl = min(swept, glo) - buf
            if sl >= px:
                continue
        else:
            sl = max(swept, ghi) + buf
            if sl <= px:
                continue
        risk = abs(px - sl)
        if risk < 0.20:
            continue
        tp = px + rr * risk if side == "long" else px - rr * risk
        arm = bar_end(ts, bar_m)
        orders.append(Order(
            arm_time=arm, side=side, kind="limit", price=float(px),
            sl=float(sl), tp=float(tp),
            strategy="H4OpenFVG", variant=variant,
            meta={"h4_open": cur_open, "h4_start": str(h4_t[hi])},
            expire_minutes=90, max_hold_minutes=360,
        ))
        used.add(key)

    return dedupe_orders(orders, 40)


def generate_h4open_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M15", "M5"):
        for bias in ("prev_h4", "side_of_open"):
            for rr in (2.0, 1.5):
                print(f" h4open {tf} {bias} rr{rr}", flush=True)
                oo = generate_h4open_fvg(m1, entry_tf=tf, rr=rr, bias_mode=bias)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
    return pools


def overlap_with_session_box(h4_orders: List[Order], box_orders: List[Order], window_min=60) -> dict:
    """Count H4Open signals that also have a SessionBox signal within window."""
    if not h4_orders or not box_orders:
        return {"h4_n": len(h4_orders), "box_n": len(box_orders), "overlap": 0, "pct": 0.0}
    box_t = sorted([o.arm_time for o in box_orders])
    ov = 0
    for o in h4_orders:
        for bt in box_t:
            if abs((o.arm_time - bt).total_seconds()) <= window_min * 60 and o.side == "long":  # rough
                # better: same side
                pass
    # side-aware
    box_by_side = {"long": [o.arm_time for o in box_orders if o.side == "long"],
                   "short": [o.arm_time for o in box_orders if o.side == "short"]}
    ov = 0
    for o in h4_orders:
        for bt in box_by_side.get(o.side, []):
            if abs((o.arm_time - bt).total_seconds()) <= window_min * 60:
                ov += 1
                break
    return {"h4_n": len(h4_orders), "box_n": len(box_orders), "overlap": ov,
            "pct": ov / len(h4_orders) if h4_orders else 0.0}
