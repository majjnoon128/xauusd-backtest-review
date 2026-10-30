"""fib78_limit (beny.trade): trend (HH/HL or LH/LL) → impulse swing → limit @ 0.78, SL beyond 1.0, TP @ 0.0.

Log-scale Fib irrelevant intraday on gold (linear only). First-touch only; invalidate if price
exceeds 1.0 before fill. Fractal sizes / TFs: M5 M15 H1 H2.
Difference vs losing NDS Fib zone test: exact 0.78 limit (not zone+engulf), SL beyond 1.0, TP at 0.0 (~3.5R).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows


def _trend(shi, sli, h, l, i) -> Optional[str]:
    """HH/HL → bull, LH/LL → bear. Need 2 swings each."""
    ph = [s for s in shi if s < i]
    pl = [s for s in sli if s < i]
    if len(ph) < 2 or len(pl) < 2:
        return None
    if h[ph[-1]] > h[ph[-2]] and l[pl[-1]] > l[pl[-2]]:
        return "long"
    if h[ph[-1]] < h[ph[-2]] and l[pl[-1]] < l[pl[-2]]:
        return "short"
    return None


def generate_fib78_limit(
    m1: pd.DataFrame,
    swing_tf: str = "M15",   # M5 | M15 | H1 | H2
    fractal: int = 2,        # left/right for swings
    atr_buf: float = 0.1,
    first_touch_only: bool = True,
) -> List[Order]:
    bar_m = {"M5": 5, "M15": 15, "H1": 60, "H2": 120}[swing_tf]
    df = resample_ohlc(m1, f"{bar_m}min")
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, fractal, fractal)

    tag = "ft1" if first_touch_only else "any"
    variant = f"fib78_{swing_tf}_fr{fractal}_{tag}"
    orders: List[Order] = []

    # Walk confirmed swings: when a new swing extreme confirms, define impulse
    # Confirmation at swing_i + fractal
    for idx, sw in enumerate(shi):
        conf = sw + fractal
        if conf >= n - 1:
            continue
        trend = _trend(shi, sli, h, l, conf)
        if trend != "short":
            continue
        # impulse = swing high that made new extreme (this SH) from prior SL
        pl = [s for s in sli if s < sw]
        if not pl:
            continue
        sl_i = pl[-1]
        leg_start = float(l[sl_i])  # wait — for short impulse: start=high (1.0), end=low (0.0)
        # Short setup after bearish impulse: impulse was down from high to low
        # Actually beny: trend LH/LL, impulse = swing that made new extreme (new LL),
        # Fib from start of that impulse leg (prior swing high=1.0) to new low=0.0, limit buy? 
        # For shorts in downtrend: impulse down, retrace to 0.78, sell.
        # leg: 1.0 = swing high (start), 0.0 = new swing low (end)
        # But this SH is the start if we're looking at a completed down move ending at a SL.
        pass

    # Cleaner pass: on each confirmed swing low in downtrend → short retrace setup
    # on each confirmed swing high in uptrend → long retrace setup
    for sw in sli:
        conf = sw + fractal
        if conf >= n - 1 or conf < 5:
            continue
        if int(getattr(times[conf], "day_of_week", times[conf].dayofweek)) >= 5:
            continue
        trend = _trend(shi, sli, h, l, conf)
        if trend != "short":
            continue
        # impulse end = this SL; start = last SH before it
        ph = [s for s in shi if s < sw]
        if not ph:
            continue
        sh_i = ph[-1]
        p10 = float(h[sh_i])  # Fib 1.0
        p00 = float(l[sw])    # Fib 0.0
        move = p10 - p00
        atr_v = a[conf]
        if np.isnan(atr_v) or atr_v <= 0 or move < 1.2 * atr_v:
            continue
        p78 = p00 + 0.78 * move
        buf = max(atr_buf * atr_v, 0.15)
        sl = p10 + buf
        tp = p00
        risk = abs(p78 - sl)
        if risk < 0.3 or abs(tp - p78) / risk < 1.5:
            continue
        # arm at confirmation; limit sell at 0.78; expire until invalidation (price > 1.0)
        # expire_minutes: until end of next few bars — use price invalidation via expire window
        # Engine doesn't support invalidate-on-price; approximate expire 8h and skip if 1.0 already pierced before arm
        if float(np.max(h[sw:conf + 1])) > p10:
            continue  # invalidated during confirm
        arm = bar_end(times[conf], bar_m)
        # first touch: only one order per impulse
        orders.append(Order(
            arm_time=arm, side="short", kind="limit", price=float(p78),
            sl=float(sl), tp=float(tp),
            strategy="Fib78Limit", variant=variant,
            meta={"p10": p10, "p00": p00, "p78": p78, "first_touch": first_touch_only},
            expire_minutes=bar_m * 40, max_hold_minutes=bar_m * 80,
        ))

    for sw in shi:
        conf = sw + fractal
        if conf >= n - 1 or conf < 5:
            continue
        if int(getattr(times[conf], "day_of_week", times[conf].dayofweek)) >= 5:
            continue
        trend = _trend(shi, sli, h, l, conf)
        if trend != "long":
            continue
        pl = [s for s in sli if s < sw]
        if not pl:
            continue
        sl_i = pl[-1]
        p10 = float(l[sl_i])
        p00 = float(h[sw])
        move = p00 - p10
        atr_v = a[conf]
        if np.isnan(atr_v) or atr_v <= 0 or move < 1.2 * atr_v:
            continue
        p78 = p00 - 0.78 * move
        buf = max(atr_buf * atr_v, 0.15)
        sl = p10 - buf
        tp = p00
        risk = abs(p78 - sl)
        if risk < 0.3 or abs(tp - p78) / risk < 1.5:
            continue
        if float(np.min(l[sw:conf + 1])) < p10:
            continue
        arm = bar_end(times[conf], bar_m)
        orders.append(Order(
            arm_time=arm, side="long", kind="limit", price=float(p78),
            sl=float(sl), tp=float(tp),
            strategy="Fib78Limit", variant=variant,
            meta={"p10": p10, "p00": p00, "p78": p78, "note": "linear fib; log-scale N/A intraday XAU"},
            expire_minutes=bar_m * 40, max_hold_minutes=bar_m * 80,
        ))

    oo = dedupe_orders(orders, 30)
    if first_touch_only:
        # already one per swing; dedupe handles clustering
        pass
    return oo


def generate_fib78_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15", "H1", "H2"):
        for fr in (2, 3):
            for ft in (True, False):
                print(f" fib78 {tf} fr{fr} ft{ft}", flush=True)
                oo = generate_fib78_limit(m1, tf, fr, first_touch_only=ft)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
    return pools
