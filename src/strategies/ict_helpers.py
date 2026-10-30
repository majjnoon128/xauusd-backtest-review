"""Shared ICT building blocks — closed-bar only (M5)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple


def find_fvgs(high, low, atr_arr, i_start: int, i_end: int, direction: str, min_atr=0.05):
    """3-candle FVG. form_i = k+2. bull: low[k+2]>high[k]; bear: high[k+2]<low[k]."""
    out = []
    for k in range(max(i_start, 0), max(i_end - 1, 0)):
        if k + 2 > i_end:
            break
        a = atr_arr[k + 2]
        if np.isnan(a) or a <= 0:
            continue
        if direction == "bull":
            gap = low[k + 2] - high[k]
            if gap >= min_atr * a:
                out.append((float(high[k]), float(low[k + 2]), k + 2))
        else:
            gap = low[k] - high[k + 2]
            if gap >= min_atr * a:
                out.append((float(high[k + 2]), float(low[k]), k + 2))
    return out


def swing_highs_lows(high, low, left: int = 2, right: int = 2):
    """Confirmed pivots: returns (shi_list, sli_list) of indices."""
    n = len(high)
    shi, sli = [], []
    for i in range(left, n - right):
        h = high[i]
        if all(h >= high[i - j] for j in range(1, left + 1)) and all(h > high[i + j] for j in range(1, right + 1)):
            shi.append(i)
        l = low[i]
        if all(l <= low[i - j] for j in range(1, left + 1)) and all(l < low[i + j] for j in range(1, right + 1)):
            sli.append(i)
    return shi, sli


def last_swing_before(swings: List[int], i: int) -> Optional[int]:
    for s in reversed(swings):
        if s < i:
            return s
    return None


def is_displacement(open_, close, atr_v, mult: float = 1.0) -> bool:
    if atr_v is None or np.isnan(atr_v) or atr_v <= 0:
        return False
    return abs(close - open_) >= mult * atr_v


def asian_ranges(m1: pd.DataFrame) -> dict:
    ranges = {}
    for d in m1.index.normalize().unique():
        if int(getattr(d, "day_of_week", d.dayofweek)) >= 5:
            continue
        seg = m1[(m1.index >= d) & (m1.index < d + pd.Timedelta(hours=7))]
        if len(seg) < 30:
            continue
        ranges[pd.Timestamp(d)] = (float(seg["high"].max()), float(seg["low"].min()),
                                   d + pd.Timedelta(hours=7))
    return ranges


def prev_day_hl(m1: pd.DataFrame) -> dict:
    """UTC calendar day high/low keyed by next day (level available at next day open)."""
    out = {}
    for d in m1.index.normalize().unique():
        seg = m1[(m1.index >= d) & (m1.index < d + pd.Timedelta(days=1))]
        if len(seg) < 60:
            continue
        out[pd.Timestamp(d) + pd.Timedelta(days=1)] = (float(seg["high"].max()), float(seg["low"].min()))
    return out


def ny_hour(ts: pd.Timestamp) -> int:
    """Hour in America/New_York."""
    return int(ts.tz_convert("America/New_York").hour)


def in_silver_bullet(ts: pd.Timestamp) -> bool:
    """NY 10:00–11:00 America/New_York (inclusive start, exclusive end of hour window on bar open)."""
    t = ts.tz_convert("America/New_York")
    return t.hour == 10


def opposing_liquidity(side: str, asian_h: float, asian_l: float, prev_h: float, prev_l: float,
                       entry: float) -> float:
    """TP toward opposing session liquidity."""
    if side == "long":
        cands = [x for x in (asian_h, prev_h) if x > entry + 0.2]
        return max(cands) if cands else entry + abs(entry) * 0  # fallback handled by caller
    cands = [x for x in (asian_l, prev_l) if x < entry - 0.2]
    return min(cands) if cands else entry
