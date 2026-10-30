"""ny_close_magnet (fxshortcast, claim ~75%): stats on prior NY close (21:00/22:00 UTC) touches
in London open / London close / NY open vs random baseline; if real, trade toward it.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def _ny_close_levels(m1: pd.DataFrame, close_hour: int) -> Dict[pd.Timestamp, float]:
    """Map next calendar day → prior day's close at close_hour UTC bar."""
    m60 = resample_ohlc(m1, "1h")
    out = {}
    for ts, row in m60.iterrows():
        if ts.hour != close_hour:
            continue
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        day = ts.normalize()
        nxt = day + pd.Timedelta(days=1)
        # skip weekend → Monday
        while int(getattr(nxt, "day_of_week", nxt.dayofweek)) >= 5:
            nxt += pd.Timedelta(days=1)
        out[pd.Timestamp(nxt)] = float(row["close"])
    return out


def magnet_stats(m1: pd.DataFrame) -> dict:
    """Touch rates of prior NY close in session windows vs random same-distance levels."""
    rng = np.random.default_rng(42)
    windows = {
        "london_open": (7, 9),
        "london_close": (15, 17),  # ~London cash close UTC
        "ny_open": (12, 14),
    }
    results = {}
    for ch in (21, 22):
        levels = _ny_close_levels(m1, ch)
        for wname, (h0, h1) in windows.items():
            touches = 0
            base_touches = 0
            n = 0
            for day, lvl in levels.items():
                if int(getattr(day, "day_of_week", day.dayofweek)) >= 5:
                    continue
                seg = m1[(m1.index >= day + pd.Timedelta(hours=h0)) &
                         (m1.index < day + pd.Timedelta(hours=h1))]
                if len(seg) < 30:
                    continue
                n += 1
                if float(seg["low"].min()) <= lvl <= float(seg["high"].max()):
                    touches += 1
                # random baseline: level at same |dist from open| but flipped/random side
                day_open_seg = m1[(m1.index >= day) & (m1.index < day + pd.Timedelta(hours=1))]
                if len(day_open_seg) < 5:
                    continue
                o0 = float(day_open_seg["open"].iloc[0])
                dist = abs(o0 - lvl)
                sign = 1 if rng.random() < 0.5 else -1
                fake = o0 + sign * dist
                if float(seg["low"].min()) <= fake <= float(seg["high"].max()):
                    base_touches += 1
            results[f"ny{ch}_{wname}"] = {
                "n": n, "touch": touches, "rate": touches / n if n else 0,
                "rand_touch": base_touches, "rand_rate": base_touches / n if n else 0,
                "lift": (touches / n - base_touches / n) if n else 0,
            }
    return results


def generate_ny_close_magnet(
    m1: pd.DataFrame,
    close_hour: int = 21,
    window: str = "london_open",  # london_open | london_close | ny_open
    rr_min: float = 1.5,
) -> List[Order]:
    """M5 closed-bar reversal after moving away from NY close, TP at level, SL swing."""
    wh = {"london_open": (7, 10), "london_close": (15, 17), "ny_open": (12, 15)}[window]
    levels = _ny_close_levels(m1, close_hour)
    m5 = resample_ohlc(m1, "5min")
    o, h, l, c = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    a = atr_prior(m5, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)
    n = len(m5)
    variant = f"nymag_h{close_hour}_{window}_rr{rr_min:g}"
    orders: List[Order] = []
    used = set()

    for day, lvl in levels.items():
        if int(getattr(day, "day_of_week", day.dayofweek)) >= 5:
            continue
        if day in used:
            continue
        i0 = times.searchsorted(day + pd.Timedelta(hours=wh[0]), side="left")
        i1 = times.searchsorted(day + pd.Timedelta(hours=wh[1]), side="left")
        # need price to have moved away then reverse toward lvl
        for i in range(max(i0, 5), min(i1, n - 1)):
            atr_v = a[i]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            # away below lvl → long toward; away above → short toward
            if c[i - 1] < lvl - 0.3 * atr_v and c[i] > o[i] and c[i] > c[i - 1]:
                side = "long"
                px = float(c[i])
                if px >= lvl:
                    continue
                sw = last_swing_before(sli, i)
                sl = float(l[sw]) - 0.1 * atr_v if sw is not None else px - 1.0 * atr_v
                tp = float(lvl)
                risk = px - sl
                if risk < 0.2 or (tp - px) / risk < rr_min:
                    continue
            elif c[i - 1] > lvl + 0.3 * atr_v and c[i] < o[i] and c[i] < c[i - 1]:
                side = "short"
                px = float(c[i])
                if px <= lvl:
                    continue
                sw = last_swing_before(shi, i)
                sl = float(h[sw]) + 0.1 * atr_v if sw is not None else px + 1.0 * atr_v
                tp = float(lvl)
                risk = sl - px
                if risk < 0.2 or (px - tp) / risk < rr_min:
                    continue
            else:
                continue
            arm = bar_end(times[i], 5)
            orders.append(Order(
                arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
                strategy="NYCloseMagnet", variant=variant, meta={"lvl": lvl},
                expire_minutes=10, max_hold_minutes=180,
            ))
            used.add(day)
            break

    return dedupe_orders(orders, 30)


def generate_nymag_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for ch in (21, 22):
        for w in ("london_open", "london_close", "ny_open"):
            for rr in (1.5, 2.0):
                print(f" nymag h{ch} {w} rr{rr}", flush=True)
                oo = generate_ny_close_magnet(m1, ch, w, rr)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
    return pools
