"""MTF SMC (reel): Daily strong bias after FVG fill → H1 FVG tap → M5 SMT? → BOS → limit at M5 FVG.

Closed bars only. DXY used for SMT (inverse) as close series (15m→M5 ffill).
Separate apply_dxy_gate is the confirmation filter (±DXY in compare), not SMT.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before


def _daily_fvgs(d_h, d_l, d_atr) -> List[Tuple[float, float, int, str]]:
    """All daily FVGs: (gap_lo, gap_hi, form_i, direction)."""
    out = []
    n = len(d_h)
    for k in range(0, n - 2):
        a = d_atr[k + 2]
        if np.isnan(a) or a <= 0:
            continue
        # bull
        gap = d_l[k + 2] - d_h[k]
        if gap >= 0.05 * a:
            out.append((float(d_h[k]), float(d_l[k + 2]), k + 2, "bull"))
        # bear
        gap = d_l[k] - d_h[k + 2]
        if gap >= 0.05 * a:
            out.append((float(d_h[k + 2]), float(d_l[k]), k + 2, "bear"))
    return out


def _strong_bias_after_fvg_fill(d: pd.DataFrame) -> dict:
    """For each CLOSED daily bar i, if strong (body>60% range) and it filled a prior
    same-direction daily FVG, set bias for the NEXT session (available at bar end of i).
    Returns map: date(normalize of day i+1 open / availability) -> 'long'|'short'.
    Bias is keyed by the calendar date when it becomes actionable (day after close).
    """
    o = d["open"].values
    h = d["high"].values
    l = d["low"].values
    c = d["close"].values
    atr = atr_prior(d, 14).values
    times = d.index
    fvgs = _daily_fvgs(h, l, atr)
    bias = {}  # date -> side (actionable starting that UTC day)
    for i in range(2, len(d)):
        rng = h[i] - l[i]
        if rng < 1e-9:
            continue
        body = abs(c[i] - o[i])
        if body / rng < 0.60:
            continue
        bull = c[i] > o[i]
        direction = "bull" if bull else "bear"
        # filled a prior same-dir FVG: bar range overlaps gap, formed before i
        filled = False
        for glo, ghi, fi, direc in fvgs:
            if fi >= i or direc != direction:
                continue
            # overlap of bar [l,h] with gap [glo,ghi]
            if l[i] <= ghi and h[i] >= glo:
                # continuation close on the right side of gap mid
                mid = 0.5 * (glo + ghi)
                if bull and c[i] >= mid:
                    filled = True
                    break
                if (not bull) and c[i] <= mid:
                    filled = True
                    break
        if not filled:
            continue
        # actionable from next calendar day 00:00 (after this daily close)
        avail = (times[i] + pd.Timedelta(days=1)).normalize()
        bias[avail.date()] = "long" if bull else "short"
    return bias


def _ext_liq(d: pd.DataFrame) -> dict:
    """Previous two daily highs/lows available at start of day t (from t-1, t-2)."""
    h = d["high"].values
    l = d["low"].values
    times = d.index
    out = {}
    for i in range(2, len(d)):
        # at open of day i, we know days i-1 and i-2 fully closed
        day = times[i].date()
        out[day] = {
            "highs": (float(h[i - 1]), float(h[i - 2])),
            "lows": (float(l[i - 1]), float(l[i - 2])),
        }
    return out


def _smt_bullish(g_l, g_h, dxy_c, i, lookback=30) -> bool:
    """Gold LL while DXY fails HH over recent window ending at i (closed)."""
    if i < lookback + 5 or dxy_c is None:
        return False
    w0 = i - lookback
    # gold: current low is LL vs prior half
    mid = w0 + lookback // 2
    cur_low = float(np.min(g_l[mid:i + 1]))
    prior_low = float(np.min(g_l[w0:mid]))
    if not (cur_low < prior_low - 1e-9):
        return False
    # DXY expected HH if inverse confirms gold weakness — fail = no HH
    cur_dxy_hi = float(np.nanmax(dxy_c[mid:i + 1]))
    prior_dxy_hi = float(np.nanmax(dxy_c[w0:mid]))
    if np.isnan(cur_dxy_hi) or np.isnan(prior_dxy_hi):
        return False
    return cur_dxy_hi <= prior_dxy_hi + 1e-9  # failed HH


def _smt_bearish(g_l, g_h, dxy_c, i, lookback=30) -> bool:
    """Gold HH while DXY fails LL."""
    if i < lookback + 5 or dxy_c is None:
        return False
    w0 = i - lookback
    mid = w0 + lookback // 2
    cur_hi = float(np.max(g_h[mid:i + 1]))
    prior_hi = float(np.max(g_h[w0:mid]))
    if not (cur_hi > prior_hi + 1e-9):
        return False
    cur_dxy_lo = float(np.nanmin(dxy_c[mid:i + 1]))
    prior_dxy_lo = float(np.nanmin(dxy_c[w0:mid]))
    if np.isnan(cur_dxy_lo) or np.isnan(prior_dxy_lo):
        return False
    return cur_dxy_lo >= prior_dxy_lo - 1e-9  # failed LL


def generate_mtf_smc(
    m1: pd.DataFrame,
    dxy: Optional[pd.DataFrame] = None,
    use_smt: bool = True,
    tp_mode: str = "rr2",          # rr2 | ext | ext_or_rr2
    sl_atr_buf: float = 0.25,
    require_h1_tap: bool = True,
    swing_lr: int = 2,
) -> List[Order]:
    """M5 entry after Daily bias + H1 FVG tap + optional SMT + M5 BOS."""
    m5 = resample_ohlc(m1, "5min")
    h1 = resample_ohlc(m1, "1h")
    daily = resample_ohlc(m1, "1D")

    a5 = atr_prior(m5, 14).values
    a1 = atr_prior(h1, 14).values
    o5 = m5["open"].values
    h5 = m5["high"].values
    l5 = m5["low"].values
    c5 = m5["close"].values
    t5 = m5.index
    n5 = len(m5)

    h1_h = h1["high"].values
    h1_l = h1["low"].values
    h1_t = h1.index

    bias_map = _strong_bias_after_fvg_fill(daily)
    ext_map = _ext_liq(daily)

    # DXY → M5 aligned close (ffill from 15m)
    dxy_m5 = None
    if dxy is not None and not dxy.empty:
        s = dxy["close"].reindex(m5.index, method="ffill")
        dxy_m5 = s.values

    shi, sli = swing_highs_lows(h5, l5, swing_lr, swing_lr)

    # Precompute H1 FVGs
    h1_bull = find_fvgs(h1_h, h1_l, a1, 0, len(h1) - 1, "bull", min_atr=0.05)
    h1_bear = find_fvgs(h1_h, h1_l, a1, 0, len(h1) - 1, "bear", min_atr=0.05)

    smt_tag = "smt" if use_smt else "nosmt"
    variant = f"mtf_M5_{smt_tag}_{tp_mode}_sw{swing_lr}"
    orders: List[Order] = []
    used_days = set()

    # Map M5 i → H1 index (last closed H1)
    h1_pos = h1.index.searchsorted(t5, side="right") - 1

    for i in range(40, n5 - 1):
        ts = t5[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        # London+NY roughly
        if not (7 <= ts.hour < 20):
            continue
        day = ts.date()
        if day in used_days:
            continue
        side = bias_map.get(day)
        if side is None:
            # also try previous day's bias carrying (bias from yesterday's strong close)
            # bias_map keyed by avail date = day after strong close, so day is correct
            continue

        atr_v = a5[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        # H1 FVG tap in bias direction: last closed H1 bar traded into a recent H1 FVG
        hi = int(h1_pos[i])
        if hi < 5:
            continue
        if require_h1_tap:
            tapped = False
            # look at H1 FVGs formed before hi, still "fresh" (within last 40 H1 bars)
            pool = h1_bull if side == "long" else h1_bear
            for glo, ghi, fi in pool:
                if fi >= hi or fi < hi - 40:
                    continue
                # tap: H1 bar hi range overlaps FVG
                if h1_l[hi] <= ghi and h1_h[hi] >= glo:
                    tapped = True
                    break
            if not tapped:
                continue

        # SMT (optional)
        if use_smt:
            if side == "long":
                if not _smt_bullish(l5, h5, dxy_m5, i):
                    continue
            else:
                if not _smt_bearish(l5, h5, dxy_m5, i):
                    continue

        # BOS in bias direction on this closed M5 bar
        if side == "long":
            sw = last_swing_before(shi, i)
            if sw is None or c5[i] <= h5[sw]:
                continue
            # swept swing low for SL: last swing low before BOS
            sw_l = last_swing_before(sli, i)
            if sw_l is None:
                continue
            swept = float(l5[sw_l])
            # M5 bullish FVG created by BOS window
            fvgs = find_fvgs(h5, l5, a5, max(i - 6, 0), i, "bull", min_atr=0.05)
            if not fvgs:
                continue
            glo, ghi, _ = fvgs[-1]
            px = 0.5 * (glo + ghi)
            buf = max(sl_atr_buf * atr_v, 0.15)
            sl = min(swept, glo) - buf
            if sl >= px:
                continue
        else:
            sw = last_swing_before(sli, i)
            if sw is None or c5[i] >= l5[sw]:
                continue
            sw_h = last_swing_before(shi, i)
            if sw_h is None:
                continue
            swept = float(h5[sw_h])
            fvgs = find_fvgs(h5, l5, a5, max(i - 6, 0), i, "bear", min_atr=0.05)
            if not fvgs:
                continue
            glo, ghi, _ = fvgs[-1]
            px = 0.5 * (glo + ghi)
            buf = max(sl_atr_buf * atr_v, 0.15)
            sl = max(swept, ghi) + buf
            if sl <= px:
                continue

        risk = abs(px - sl)
        if risk < 0.20:
            continue

        # TP
        ext = ext_map.get(day)
        tp_rr2 = px + 2.0 * risk if side == "long" else px - 2.0 * risk
        tp_ext = None
        if ext:
            if side == "long":
                cands = [x for x in ext["highs"] if x > px + 2.0 * risk - 1e-9]
                if cands:
                    tp_ext = min(cands)  # nearest external above with RR>=2
            else:
                cands = [x for x in ext["lows"] if x < px - 2.0 * risk + 1e-9]
                if cands:
                    tp_ext = max(cands)

        if tp_mode == "rr2":
            tp = tp_rr2
        elif tp_mode == "ext":
            if tp_ext is None:
                continue
            tp = tp_ext
        else:  # ext_or_rr2
            tp = tp_ext if tp_ext is not None else tp_rr2

        # RR floor
        rr = abs(tp - px) / risk
        if rr < 1.99:
            continue

        arm = bar_end(ts, 5)
        orders.append(Order(
            arm_time=arm, side=side, kind="limit", price=float(px),
            sl=float(sl), tp=float(tp),
            strategy="MTFSMC", variant=variant,
            meta={"day": str(day), "smt": use_smt, "tp_mode": tp_mode, "swept": swept},
            expire_minutes=90,
            max_hold_minutes=360,
        ))
        used_days.add(day)

    return dedupe_orders(orders, 40)
