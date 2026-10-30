"""Session VWAP mean-reversion and VWAP-trend pullback. Daily reset 00:00 UTC."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import ema, atr_prior, resample_ohlc, bar_end
from strategies.common import apply_dxy_gate, dedupe_orders


def _session_vwap_bands(m5: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """Cumulative VWAP and rolling stdev of (typical - vwap) within UTC day."""
    tp = (m5["high"] + m5["low"] + m5["close"]) / 3.0
    vol = m5["volume"].replace(0, np.nan).fillna(m5["volume"].median() if len(m5) else 1.0)
    day = m5.index.normalize()
    # cum within day
    pv = tp * vol
    cum_pv = pv.groupby(day).cumsum()
    cum_v = vol.groupby(day).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    # stdev of tp around vwap within day (expanding)
    diff = tp - vwap
    # expanding std per day
    def exp_std(s):
        return s.expanding(min_periods=12).std()
    sd = diff.groupby(day).apply(exp_std)
    if isinstance(sd.index, pd.MultiIndex):
        sd = sd.reset_index(level=0, drop=True)
    sd = sd.reindex(m5.index)
    return vwap, sd


def generate_vwap_mr(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    mode: str = "fade2sd",       # fade2sd | trend_pb
    sd_mult: float = 2.0,
    rr: float = 1.5,
    trend_filter: bool = False,
) -> List[Order]:
    m5 = resample_ohlc(m1, "5min")
    if "volume" not in m5.columns:
        m5["volume"] = 1.0
    vwap, sd = _session_vwap_bands(m5)
    e50 = ema(m5["close"], 50)
    a = atr_prior(m5, 14)
    orders: List[Order] = []
    times = m5.index
    n = len(m5)
    variant = f"{mode}_sd{sd_mult}_rr{rr}"
    if trend_filter:
        variant += "_tf"
    used_day_side = set()

    for i in range(50, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if not (7 <= ts.hour < 20):
            continue
        vw, s, atr_i = vwap.iloc[i], sd.iloc[i], a.iloc[i]
        if np.isnan(vw) or np.isnan(s) or s <= 0 or np.isnan(atr_i) or atr_i <= 0:
            continue
        c = float(m5["close"].iloc[i])
        upper, lower = float(vw) + sd_mult * float(s), float(vw) - sd_mult * float(s)
        day = ts.normalize()

        if mode == "fade2sd":
            if trend_filter:
                # only fade against mild trend stretch: allow both but skip if extreme EMA stretch
                pass
            side = None
            if c >= upper:
                if trend_filter and c > float(e50.iloc[i]):
                    # fading with trend filter: only fade if NOT strongly trending up? 
                    # with filter: fade shorts only if price still above EMA (exhaustion) — skip strong trend
                    slope = float(e50.iloc[i] - e50.iloc[i - 5]) if i >= 5 else 0
                    if slope > 0.5 * float(atr_i):
                        continue
                side, entry, sl = "short", c, c + 0.6 * float(atr_i)
                tp = float(vw)  # back to VWAP
                if entry - tp < 0.08:
                    continue
                # convert to R-based if distance to vwap defines R differently — use SL risk for R check
                risk = sl - entry
                if abs(entry - tp) < 0.8 * risk:
                    tp = entry - rr * risk
            elif c <= lower:
                if trend_filter:
                    slope = float(e50.iloc[i] - e50.iloc[i - 5]) if i >= 5 else 0
                    if slope < -0.5 * float(atr_i):
                        continue
                side, entry, sl = "long", c, c - 0.6 * float(atr_i)
                tp = float(vw)
                if tp - entry < 0.08:
                    continue
                risk = entry - sl
                if abs(tp - entry) < 0.8 * risk:
                    tp = entry + rr * risk
            if side is None:
                continue
            key = (day, side)
            if key in used_day_side:
                continue
            risk = abs(entry - sl)
            if risk < 0.08 or risk > 3.5 * float(atr_i):
                continue
            arm = bar_end(ts, 5)
            # hold until end of day roughly
            eod = day + pd.Timedelta(hours=21)
            hold = max(30, int((eod - arm).total_seconds() // 60))
            orders.append(Order(
                arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                strategy="VWAP_MR", variant=variant, meta={"signal_bar": ts},
                expire_minutes=45, max_hold_minutes=hold,
            ))
            used_day_side.add(key)

        else:  # trend_pb: trade WITH trend, pullback to VWAP
            if i < 5:
                continue
            slope = float(e50.iloc[i] - e50.iloc[i - 5])
            up = slope > 0.2 * float(atr_i) and c > float(e50.iloc[i])
            dn = slope < -0.2 * float(atr_i) and c < float(e50.iloc[i])
            side = None
            if up and float(m5["low"].iloc[i]) <= float(vw) <= float(m5["high"].iloc[i]) and c > float(vw):
                side, entry = "long", c
                sl = float(vw) - 0.8 * float(atr_i)
                risk = entry - sl
                tp = entry + rr * risk
            elif dn and float(m5["low"].iloc[i]) <= float(vw) <= float(m5["high"].iloc[i]) and c < float(vw):
                side, entry = "short", c
                sl = float(vw) + 0.8 * float(atr_i)
                risk = sl - entry
                tp = entry - rr * risk
            if side is None:
                continue
            key = (day, side, "pb")
            if key in used_day_side:
                continue
            if risk < 0.08 or risk > 3.5 * float(atr_i):
                continue
            arm = bar_end(ts, 5)
            orders.append(Order(
                arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                strategy="VWAP_MR", variant=variant, meta={"signal_bar": ts},
                expire_minutes=45,
            ))
            used_day_side.add(key)

    orders = dedupe_orders(orders, 45)
    return apply_dxy_gate(orders, dxy, use_dxy)
