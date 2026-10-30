"""Previous-day midpoint magnet: long above mid→PDH, short below→PDL. London/NY on M15 context."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, bullish_engulfing, bearish_engulfing
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before, prev_day_hl


def base_rate_stats(m1: pd.DataFrame) -> dict:
    """Given price above/below mid in London/NY, how often PDH/PDL touched before opposite."""
    pdhl = prev_day_hl(m1)
    m15 = resample_ohlc(m1, "15min")
    results = {"above_mid_pdh_first": 0, "above_mid_pdl_first": 0, "above_n": 0,
               "below_mid_pdl_first": 0, "below_mid_pdh_first": 0, "below_n": 0,
               "day_boundary": "UTC via prev_day_hl"}
    # group m15 by day
    for day, (pdh, pdl) in pdhl.items():
        mid = 0.5 * (pdh + pdl)
        # session bars 07-21 UTC
        seg = m15[(m15.index >= day) & (m15.index < day + pd.Timedelta(days=1))]
        seg = seg[(seg.index.hour >= 7) & (seg.index.hour < 21)]
        if len(seg) < 5 or pdh - pdl < 1.0:
            continue
        # first classification when inside range
        classified = None
        for ts, r in seg.iterrows():
            if not (pdl < r.close < pdh):
                continue
            if r.close > mid:
                classified = "above"; results["above_n"] += 1
            else:
                classified = "below"; results["below_n"] += 1
            # walk forward: which extreme first
            fut = seg[seg.index >= ts]
            hit = None
            for _, rr in fut.iterrows():
                if rr.high >= pdh and rr.low <= pdl:
                    # same bar both — skip
                    hit = "both"; break
                if rr.high >= pdh:
                    hit = "pdh"; break
                if rr.low <= pdl:
                    hit = "pdl"; break
            if classified == "above":
                if hit == "pdh": results["above_mid_pdh_first"] += 1
                elif hit == "pdl": results["above_mid_pdl_first"] += 1
            else:
                if hit == "pdl": results["below_mid_pdl_first"] += 1
                elif hit == "pdh": results["below_mid_pdh_first"] += 1
            break  # one per day
    for k in ("above", "below"):
        n = results[f"{k}_n"]
        if k == "above":
            results["above_pdh_rate"] = results["above_mid_pdh_first"] / n if n else None
        else:
            results["below_pdl_rate"] = results["below_mid_pdl_first"] / n if n else None
    return results


def generate_magnet(
    m1: pd.DataFrame,
    entry_tf: str = "M5",       # M5 | M15
    trigger: str = "engulf",    # engulf | sweep_mss | pullback_mid
    min_rr: float = 1.5,
    atr_buf: float = 0.1,
) -> List[Order]:
    pdhl = prev_day_hl(m1)
    bar_m = 5 if entry_tf == "M5" else 15
    df = resample_ohlc(m1, f"{bar_m}min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)
    bull_eng = bullish_engulfing(df).values
    bear_eng = bearish_engulfing(df).values

    variant = f"magnet_{entry_tf}_{trigger}_rr{min_rr}"
    orders: List[Order] = []
    used = set()

    for i in range(20, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        hr = ts.hour
        if not (7 <= hr < 21):
            continue
        day = ts.normalize()
        box = pdhl.get(day)
        if box is None:
            continue
        pdh, pdl = box
        if pdh - pdl < 1.0:
            continue
        mid = 0.5 * (pdh + pdl)
        # must be inside range
        if not (pdl < c[i] < pdh):
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue
        key = (day.date(),)
        if key in used:
            continue

        side = None
        if c[i] > mid:
            side = "long"; tp = pdh
        else:
            side = "short"; tp = pdl

        # triggers
        ok = False
        if trigger == "engulf":
            ok = (side == "long" and bull_eng[i]) or (side == "short" and bear_eng[i])
        elif trigger == "sweep_mss":
            if side == "long":
                sw = last_swing_before(sli, i)
                ok = sw is not None and l[i] < l[sw] and c[i] > o[i] and c[i] > l[sw]
            else:
                sw = last_swing_before(shi, i)
                ok = sw is not None and h[i] > h[sw] and c[i] < o[i] and c[i] < h[sw]
        elif trigger == "pullback_mid":
            # touch mid then close back on bias side
            touched = l[i] <= mid <= h[i]
            if side == "long":
                ok = touched and c[i] > mid and c[i] > o[i]
            else:
                ok = touched and c[i] < mid and c[i] < o[i]
        if not ok:
            continue

        px = float(c[i])
        buf = max(atr_buf * atr_v, 0.12)
        if side == "long":
            sw = last_swing_before(sli, i)
            sl = (float(l[sw]) - buf) if sw is not None else float(l[i]) - buf
            if sl >= px:
                continue
        else:
            sw = last_swing_before(shi, i)
            sl = (float(h[sw]) + buf) if sw is not None else float(h[i]) + buf
            if sl <= px:
                continue
        risk = abs(px - sl)
        if risk < 0.20:
            continue
        rr = abs(tp - px) / risk
        if rr < min_rr:
            continue

        arm = bar_end(ts, bar_m)
        orders.append(Order(
            arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
            strategy="MagnetPDMid", variant=variant,
            meta={"pdh": pdh, "pdl": pdl, "mid": mid},
            expire_minutes=20, max_hold_minutes=360,
        ))
        used.add(key)

    return dedupe_orders(orders, 40)


def generate_magnet_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15"):
        for trig in ("engulf", "sweep_mss", "pullback_mid"):
            for rr in (1.5, 2.0):
                print(f" magnet {tf} {trig} rr{rr}", flush=True)
                oo = generate_magnet(m1, tf, trig, rr)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
    return pools
