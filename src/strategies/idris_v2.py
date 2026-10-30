"""Idris v2 (author reel): H4 level → reaction → hidden div on exec TF → IB entry.

Closed bars only. Use generate_idris_v2_grid() for multi entry/sl/tp in one scan.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import (
    atr_prior, resample_ohlc, bar_end, inside_bar, rsi, macd, stoch,
    in_tokyo_london,
)
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def _osc_series(df: pd.DataFrame, osc: str) -> np.ndarray:
    if osc == "rsi14":
        return rsi(df["close"], 14).values
    if osc == "macd":
        _, _, hist = macd(df["close"], 12, 26, 9)
        return hist.values
    if osc == "stoch":
        k, _ = stoch(df["high"], df["low"], df["close"], 14, 3, 3)
        return k.values
    raise ValueError(osc)


def _confirmed_pivots(high, low, left=3, right=3):
    n = len(high)
    pls, phs = [], []
    for i in range(left, n - right):
        w = low[i - left:i + right + 1]
        if low[i] == w.min() and (w == low[i]).sum() == 1:
            pls.append(i)
        w = high[i - left:i + right + 1]
        if high[i] == w.max() and (w == high[i]).sum() == 1:
            phs.append(i)
    return np.array(pls, dtype=int), np.array(phs, dtype=int)


def _h4_levels(h4: pd.DataFrame, mode: str):
    h, l = h4["high"].values, h4["low"].values
    n = len(h4)
    if mode == "h4_hl":
        return h.copy(), l.copy(), h4.index
    shi, sli = swing_highs_lows(h, l, 2, 2)
    zh = np.full(n, np.nan)
    zl = np.full(n, np.nan)
    last_sh = last_sl = np.nan
    si = sj = 0
    for i in range(n):
        while si < len(shi) and shi[si] + 2 <= i:
            last_sh = float(h[shi[si]]); si += 1
        while sj < len(sli) and sli[sj] + 2 <= i:
            last_sl = float(l[sli[sj]]); sj += 1
        zh[i] = last_sh
        zl[i] = last_sl
    return zh, zl, h4.index


def generate_idris_v2_grid(
    m1: pd.DataFrame,
    level: str = "h4_hl",
    osc: str = "rsi14",
    entry_tf: str = "M5",
    session: str = "tokyo_london",
    entries: Tuple[str, ...] = ("stop", "close"),
    sls: Tuple[str, ...] = ("mother", "swing"),
    tps: Tuple[str, ...] = ("rr3", "rr3_trail"),
    rr: float = 3.0,
    atr_buf: float = 0.05,
    pivot_lr: int = 3,
) -> Dict[str, List[Order]]:
    """One scan → many order-style variants."""
    bar_m = {"M1": 1, "M5": 5, "M15": 15}[entry_tf]
    rule = {1: "1min", 5: "5min", 15: "15min"}[bar_m]
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, rule)
    h4 = resample_ohlc(m1, "4h")

    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    ib = inside_bar(df).values
    osc_v = _osc_series(df, osc)
    pl_arr, ph_arr = _confirmed_pivots(h, l, pivot_lr, pivot_lr)
    shi, sli = swing_highs_lows(h, l, 2, 2)
    zh_all, zl_all, h4_idx = _h4_levels(h4, level)

    pools: Dict[str, List[Order]] = {}
    for em in entries:
        for sm in sls:
            for tm in tps:
                pools[f"idris_{level}_{osc}_{entry_tf}_{em}_{sm}_{tm}_{session}"] = []

    for i in range(60, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        if session == "tokyo_london" and not in_tokyo_london(ts):
            continue
        if not ib[i]:
            continue
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0 or np.isnan(osc_v[i]):
            continue

        deadline = ts - pd.Timedelta(hours=4)
        hi = h4_idx.searchsorted(deadline, side="right") - 1
        if hi < 0:
            continue
        zh, zl = float(zh_all[hi]), float(zl_all[hi])
        if np.isnan(zh) or np.isnan(zl):
            continue

        tol = 0.15 * atr_i
        look = max(0, i - 8)
        touched_low = float(np.min(l[look:i + 1])) <= zl + tol
        touched_high = float(np.max(h[look:i + 1])) >= zh - tol

        side = None
        if touched_low:
            pls = pl_arr[pl_arr + pivot_lr <= i]
            if len(pls) >= 2:
                p2, p1 = int(pls[-1]), int(pls[-2])
                if l[p2] > l[p1] and osc_v[p2] < osc_v[p1]:
                    side = "long"
        if side is None and touched_high:
            phs = ph_arr[ph_arr + pivot_lr <= i]
            if len(phs) >= 2:
                p2, p1 = int(phs[-1]), int(phs[-2])
                if h[p2] < h[p1] and osc_v[p2] > osc_v[p1]:
                    side = "short"
        if side is None:
            continue

        m_hi, m_lo = float(h[i - 1]), float(l[i - 1])
        buf = max(atr_buf * atr_i, 0.10)
        arm = bar_end(ts, bar_m)

        # precompute swing SL
        sw_sl = None
        if side == "long":
            sw = last_swing_before(sli, i)
            if sw is not None:
                sw_sl = min(float(l[sw]), m_lo) - buf
        else:
            sw = last_swing_before(shi, i)
            if sw is not None:
                sw_sl = max(float(h[sw]), m_hi) + buf
        mother_sl = (m_lo - buf) if side == "long" else (m_hi + buf)

        for em in entries:
            kind = "stop" if em == "stop" else "market"
            px = (m_hi if side == "long" else m_lo) if em == "stop" else float(c[i])
            for sm in sls:
                sl = mother_sl if sm == "mother" else sw_sl
                if sl is None:
                    continue
                risk = abs(px - sl)
                if risk < 0.20:
                    continue
                if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                    continue
                for tm in tps:
                    tp = px + rr * risk if side == "long" else px - rr * risk
                    meta = {"signal_bar": ts, "h4": (zh, zl)}
                    if tm == "rr3_trail":
                        meta["trail_activate_r"] = 1.5
                    v = f"idris_{level}_{osc}_{entry_tf}_{em}_{sm}_{tm}_{session}"
                    pools[v].append(Order(
                        arm_time=arm, side=side, kind=kind, price=float(px),
                        sl=float(sl), tp=float(tp),
                        strategy="IdrisV2", variant=v, meta=meta,
                        expire_minutes=60 if kind == "stop" else 20,
                        max_hold_minutes=480,
                    ))

    return {k: dedupe_orders(v, 40) for k, v in pools.items() if v}


def generate_idris_v2(m1, **kwargs) -> List[Order]:
    """Single-variant wrapper."""
    level = kwargs.pop("level", "h4_hl")
    osc = kwargs.pop("osc", "rsi14")
    entry_tf = kwargs.pop("entry_tf", "M5")
    session = kwargs.pop("session", "tokyo_london")
    entry_mode = kwargs.pop("entry_mode", "stop")
    sl_mode = kwargs.pop("sl_mode", "mother")
    tp_mode = kwargs.pop("tp_mode", "rr3")
    kwargs.pop("dxy", None)
    kwargs.pop("use_dxy", None)
    grid = generate_idris_v2_grid(
        m1, level=level, osc=osc, entry_tf=entry_tf, session=session,
        entries=(entry_mode,), sls=(sl_mode,), tps=(tp_mode,),
        **{k: kwargs[k] for k in ("rr", "atr_buf", "pivot_lr") if k in kwargs},
    )
    v = f"idris_{level}_{osc}_{entry_tf}_{entry_mode}_{sl_mode}_{tp_mode}_{session}"
    return grid.get(v, [])
