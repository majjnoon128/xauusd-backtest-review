"""Targeted confirmation filters. HTF/DXY use last CLOSED bars only (no unfinished bar)."""
from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd
from engine import Order
from indicators import ema, atr, resample_ohlc, in_session, last_closed_value


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
    dxy_close = dxy_ema = None
    if dxy is not None and not dxy.empty:
        d = dxy.copy()
        d["ema50"] = ema(d["close"], 50)
        dxy_close, dxy_ema = d["close"], d["ema50"]

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

        # ATR: last M1 bar whose close <= t (1-min left-labeled → start <= t-1m)
        atr_i = last_closed_value(m1_atr, t, 1)
        risk = abs(o.price - o.sl)
        if atr_i and atr_i > 0:
            if risk < min_sl_atr * atr_i:
                continue
            if risk > max_sl_atr * atr_i:
                continue

        if require_htf:
            c15 = last_closed_value(m15["close"], t, 15)
            e15 = last_closed_value(m15["ema50"], t, 15)
            if c15 is None or e15 is None:
                continue
            up = c15 > e15
            if o.side == "long" and not up:
                continue
            if o.side == "short" and up:
                continue

        if require_dxy and dxy_close is not None:
            # DXY series assumed 15m left-labeled (same as apply_dxy_gate)
            c = last_closed_value(dxy_close, t, 15)
            e = last_closed_value(dxy_ema, t, 15)
            if c is None or e is None:
                continue
            bear = c < e
            if o.side == "long" and not bear:
                continue
            if o.side == "short" and bear:
                continue
        out.append(o)
    return out
