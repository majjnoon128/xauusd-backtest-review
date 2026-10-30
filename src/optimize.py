"""Targeted confirmation filters addressing top loss causes. OOS validation only for claims."""
from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd
from engine import Order
from indicators import ema, atr, resample_ohlc, in_session


def apply_quality_filters(
    orders: List[Order],
    m1: pd.DataFrame,
    dxy: pd.DataFrame | None,
    *,
    require_htf: bool = True,
    require_dxy: bool = False,
    min_sl_atr: float = 0.5,
    max_sl_atr: float = 2.5,
    block_asian: bool = True,
    block_london_open: bool = False,
) -> List[Order]:
    if not orders:
        return []
    m15 = resample_ohlc(m1, "15min")
    m15["ema50"] = ema(m15["close"], 50)
    m1_atr = atr(m1, 14)
    dxy_bear = None
    if dxy is not None and not dxy.empty:
        d = dxy.copy()
        d["ema50"] = ema(d["close"], 50)
        dxy_bear = d["close"] < d["ema50"]

    out = []
    for o in orders:
        t = o.arm_time
        h = t.hour
        if block_asian and (h < 7 or h >= 21):
            continue
        if block_london_open and 7 <= h < 9:
            continue
        if not in_session(t) or t.dayofweek >= 5:
            continue

        ai = m1_atr.index.searchsorted(t, side="right") - 1
        atr_i = float(m1_atr.iloc[ai]) if ai >= 0 else np.nan
        risk = abs(o.price - o.sl)
        if atr_i and atr_i > 0:
            if risk < min_sl_atr * atr_i:
                continue
            if risk > max_sl_atr * atr_i:
                continue

        if require_htf:
            mi = m15.index.searchsorted(t, side="right") - 1
            if mi < 50:
                continue
            up = float(m15["close"].iloc[mi]) > float(m15["ema50"].iloc[mi])
            if o.side == "long" and not up:
                continue
            if o.side == "short" and up:
                continue

        if require_dxy and dxy_bear is not None:
            di = dxy_bear.index.searchsorted(t, side="right") - 1
            if di < 0:
                continue
            bear = bool(dxy_bear.iloc[di])
            if o.side == "long" and not bear:
                continue
            if o.side == "short" and bear:
                continue
        out.append(o)
    return out
