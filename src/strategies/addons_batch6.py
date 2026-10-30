"""Batch-6 add-ons: pre-registered filters/exits as overlays on surviving components.
Faithful to /workspace/trading-research/batch-6.md. US10Y skipped (no free intraday source).
News: FF thisweek JSON when cached at data/calendar/ff_thisweek.json (live). Historical IS/OOS needs a multi-week archive — otherwise pass-through.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Tuple, Callable
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import resample_ohlc, atr_prior, ema
from strategies.common import apply_dxy_gate
from strategies.news_calendar import filter_news_window, load_ff_events

TICK = 0.01
SPREAD_PROXY = 0.35  # audited engine default


def _utc(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC")


# ---- Filter: session ----
def filter_session(orders: List[Order], mode: str = "overlap") -> List[Order]:
    """mode: overlap=UTC12-15 | london_ny=UTC12-16 | broad=UTC07-15
    Always block: Mon before 08 UTC, Fri after 14 UTC, rollover ~UTC20-22.
    """
    out = []
    for o in orders:
        tu = _utc(o.arm_time)
        if tu.dayofweek >= 5:
            continue
        # day filters
        if tu.dayofweek == 0 and tu.hour < 8:
            continue
        if tu.dayofweek == 4 and (tu.hour > 14 or (tu.hour == 14 and tu.minute > 0)):
            continue
        # rollover dead zone
        if 20 <= tu.hour < 22:
            continue
        h = tu.hour
        if mode == "overlap" and not (12 <= h < 15):
            continue
        if mode == "london_ny" and not (12 <= h < 16):
            continue
        if mode == "broad" and not (7 <= h < 16):
            continue
        out.append(o)
    return out


# ---- Filter: ATR regime ----
def filter_atr_regime(orders: List[Order], m1: pd.DataFrame, tf: str = "M5",
                      lo: float = 0.5, hi: float = 2.0, avg_n: int = 50) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    atr = atr_prior(df, 14)
    avg = atr.rolling(avg_n, min_periods=10).mean()
    out = []
    for o in orders:
        a = atr.asof(o.arm_time)
        m = avg.asof(o.arm_time)
        if a != a or m != m or m <= 0:
            continue
        # also ForexR: ATR >= 4 * spread
        if a < 4.0 * SPREAD_PROXY:
            continue
        ratio = a / m
        if ratio < lo or ratio > hi:
            continue
        out.append(o)
    return out


# ---- Filter: ADR fill ----
def filter_adr_fill(orders: List[Order], m1: pd.DataFrame,
                    lo_pct: float = 25.0, hi_pct: float = 110.0) -> List[Order]:
    daily = m1.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    adr14 = (daily["high"] - daily["low"]).rolling(14, min_periods=5).mean().shift(1)
    out = []
    for o in orders:
        tu = _utc(o.arm_time)
        day = tu.normalize()
        ad = adr14.asof(day)
        if ad != ad or ad <= 0:
            continue
        # today's range so far (closed M1 up to arm)
        day_mask = (m1.index >= day) & (m1.index <= o.arm_time)
        if not day_mask.any():
            continue
        sub = m1.loc[day_mask]
        today_range = float(sub["high"].max() - sub["low"].min())
        fill = 100.0 * today_range / float(ad)
        if fill < lo_pct or fill > hi_pct:
            continue
        out.append(o)
    return out


# ---- Filter: DXY alignment (no US10Y) ----
def filter_dxy_align(orders: List[Order], dxy: Optional[pd.DataFrame],
                     min_score: int = 2, strong_pct: float = 0.20) -> List[Order]:
    """Score 0-2 without 10Y: +1 inverse DXY supports side, +1 if not fighting strong DXY impulse.
    Require score >= min_score (default 2 = both).
    """
    if dxy is None or dxy.empty:
        return orders  # cannot filter — pass through (honest: no data ≠ free pass for score)
    d = dxy.copy()
    # daily open for % from open (synth DXY may lack open — use first close of day)
    close = d["close"].astype(float)
    if "open" in d.columns:
        d_open = d["open"].astype(float).resample("1D").first().reindex(d.index, method="ffill")
    else:
        d_open = close.resample("1D").first().reindex(d.index, method="ffill")
    d["pct_from_open"] = (close - d_open) / d_open.replace(0, pd.NA) * 100.0
    e20 = ema(close, 20)
    out = []
    for o in orders:
        # last closed dxy bar before arm
        j = d.index.searchsorted(o.arm_time, side="right") - 1
        if j < 1:
            continue
        c = float(d["close"].iloc[j])
        e = float(e20.iloc[j]) if not np.isnan(e20.iloc[j]) else None
        pct = float(d["pct_from_open"].iloc[j])
        score = 0
        # inverse support
        if e is not None:
            if o.side == "long" and c < e:
                score += 1
            elif o.side == "short" and c > e:
                score += 1
        # not fighting strong impulse
        if o.side == "long" and pct >= strong_pct:
            pass  # fighting strong DXY up — no +1
        elif o.side == "short" and pct <= -strong_pct:
            pass
        else:
            score += 1
        if score >= min_score:
            out.append(o)
    return out


# ---- Exit overlays (mutate Order copies) ----
def apply_exit_partial_be(orders: List[Order], time_stop_m5_bars: int = 24) -> List[Order]:
    """50% at 1R conceptually via trail_activate_r=1.0 (BE after 1R) + time-stop.
    Engine supports trail_activate_r → BE; true 50% partial needs split legs.
    We emit two legs: 0.5 size @ TP=1R, 0.5 size with BE trail + longer TP.
    """
    out = []
    hold = time_stop_m5_bars * 5  # M5 bars → minutes
    for o in orders:
        risk = abs(o.price - o.sl)
        if risk < 1e-9:
            continue
        tp1 = o.price + risk if o.side == "long" else o.price - risk
        # leg1: 50% scalp 1R
        m1 = dict(o.meta or {})
        m1["leg"] = "1/2"
        m1["overlay"] = "partial_be"
        out.append(Order(
            o.arm_time, o.side, o.kind, o.price, o.sl, float(tp1), o.strategy,
            o.variant + "|ex_partial_be", m1, o.expire_minutes, hold,
            getattr(o, "min_hold_minutes", None),
        ))
        # leg2: remainder BE after 1R, TP at original or 2R
        tp2 = o.tp
        if tp2 is None:
            tp2 = o.price + 2 * risk if o.side == "long" else o.price - 2 * risk
        m2 = dict(o.meta or {})
        m2["leg"] = "2/2"
        m2["overlay"] = "partial_be"
        m2["trail_activate_r"] = 1.0
        out.append(Order(
            o.arm_time, o.side, o.kind, o.price, o.sl, float(tp2), o.strategy,
            o.variant + "|ex_partial_be", m2, o.expire_minutes, hold,
            getattr(o, "min_hold_minutes", None),
        ))
    return out


def apply_exit_trail(orders: List[Order], activate_r: float = 1.5,
                     time_stop_m5_bars: int = 24) -> List[Order]:
    hold = time_stop_m5_bars * 5
    out = []
    for o in orders:
        m = dict(o.meta or {})
        m["overlay"] = "trail15"
        m["trail_activate_r"] = activate_r
        out.append(Order(
            o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
            o.variant + "|ex_trail15", m, o.expire_minutes, hold,
            getattr(o, "min_hold_minutes", None),
        ))
    return out


def apply_min_hold_30s(orders: List[Order]) -> List[Order]:
    """SGB tick-scalp: prefer winners hold >= 30s. Model as min_hold_minutes=1 (1 M1 bar)."""
    out = []
    for o in orders:
        out.append(Order(
            o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
            o.variant + "|mh30s", dict(o.meta or {}), o.expire_minutes, o.max_hold_minutes,
            1,  # min 1 M1 minute
        ))
    return out


# ---- Pre-registered overlay recipes (FIXED set — counted for MT) ----
OVERLAY_RECIPES = [
    ("sess_overlap", lambda oo, m1, dxy: filter_session(oo, "overlap")),
    ("sess_london_ny", lambda oo, m1, dxy: filter_session(oo, "london_ny")),
    ("atr_regime", lambda oo, m1, dxy: filter_atr_regime(oo, m1)),
    ("adr_fill", lambda oo, m1, dxy: filter_adr_fill(oo, m1)),
    ("dxy_align", lambda oo, m1, dxy: filter_dxy_align(oo, dxy, 2)),
    ("sess_overlap+atr", lambda oo, m1, dxy: filter_atr_regime(filter_session(oo, "overlap"), m1)),
    ("sess_overlap+dxy", lambda oo, m1, dxy: filter_dxy_align(filter_session(oo, "overlap"), dxy, 2)),
    ("ex_partial_be", lambda oo, m1, dxy: apply_exit_partial_be(oo)),
    ("ex_trail15", lambda oo, m1, dxy: apply_exit_trail(oo)),
    ("mh30s", lambda oo, m1, dxy: apply_min_hold_30s(oo)),
    ("sess_overlap+ex_partial_be", lambda oo, m1, dxy: apply_exit_partial_be(filter_session(oo, "overlap"))),
    ("stack_overlap_atr_dxy_partial", lambda oo, m1, dxy: apply_exit_partial_be(
        filter_dxy_align(filter_atr_regime(filter_session(oo, "overlap"), m1), dxy, 2))),
    ("news_tier1_pm30", lambda oo, m1, dxy: filter_news_window(oo, load_ff_events(), 30)),
    ("sess_overlap+news", lambda oo, m1, dxy: filter_news_window(filter_session(oo, "overlap"), load_ff_events(), 30)),
]


def apply_recipe(name: str, orders: List[Order], m1, dxy) -> List[Order]:
    for n, fn in OVERLAY_RECIPES:
        if n == name:
            return fn(orders, m1, dxy)
    raise KeyError(name)
