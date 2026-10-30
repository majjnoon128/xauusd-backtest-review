"""EMA trend pullback — H1 and M15."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import ema, atr_prior, resample_ohlc, bar_end, is_bull, is_bear
from strategies.common import apply_dxy_gate, dedupe_orders


def generate_ema_pullback(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    rule: str = "1h",           # 1h | 15min
    trend: str = "ema50_200",   # ema50_200 | slope50
    pullback_ema: int = 20,     # 20 | 50
    rr: float = 2.0,
    sl_mode: str = "swing",     # swing | atr
    trail: bool = False,
) -> List[Order]:
    df = resample_ohlc(m1, rule)
    bar_min = {"15min": 15, "1h": 60, "5min": 5}.get(rule, 60)
    c = df["close"]
    e20 = ema(c, 20)
    e50 = ema(c, 50)
    e200 = ema(c, 200)
    a = atr_prior(df, 14)
    bull, bear = is_bull(df).values, is_bear(df).values
    high, low, close, open_ = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    times = df.index
    n = len(df)
    pb = e20 if pullback_ema == 20 else e50
    orders: List[Order] = []
    variant = f"{rule}_{trend}_pb{pullback_ema}_sl{sl_mode}_rr{rr}"
    if trail:
        variant += "_trail"

    for i in range(220, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        # session filter London+NY roughly
        h = ts.hour
        if not (6 <= h < 20):
            continue
        atr_i = a.iloc[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        # trend
        if trend == "ema50_200":
            up = float(e50.iloc[i]) > float(e200.iloc[i]) and float(close[i]) > float(e50.iloc[i])
            dn = float(e50.iloc[i]) < float(e200.iloc[i]) and float(close[i]) < float(e50.iloc[i])
        else:
            # slope of EMA50 over 5 bars
            if i < 5:
                continue
            slope = float(e50.iloc[i] - e50.iloc[i - 5])
            up = slope > 0.15 * float(atr_i) and float(close[i]) > float(e50.iloc[i])
            dn = slope < -0.15 * float(atr_i) and float(close[i]) < float(e50.iloc[i])
        if not (up or dn):
            continue
        pb_v = float(pb.iloc[i])
        # pullback touch: low <= ema <= high on this bar, rejection close
        if up:
            if not (low[i] <= pb_v <= high[i]):
                continue
            if not bull[i]:
                continue
            if close[i] < pb_v:  # must reclaim
                continue
            # rejection: close in upper half
            if close[i] < (high[i] + low[i]) / 2:
                continue
            entry = float(close[i])
            if sl_mode == "swing":
                sl = float(min(low[i], low[i - 1])) - 0.05 * float(atr_i)
            else:
                sl = entry - 1.0 * float(atr_i)
            risk = entry - sl
            if risk < 0.08 or risk > 4 * float(atr_i):
                continue
            tp = entry + rr * risk
            side = "long"
        else:
            if not (low[i] <= pb_v <= high[i]):
                continue
            if not bear[i]:
                continue
            if close[i] > pb_v:
                continue
            if close[i] > (high[i] + low[i]) / 2:
                continue
            entry = float(close[i])
            if sl_mode == "swing":
                sl = float(max(high[i], high[i - 1])) + 0.05 * float(atr_i)
            else:
                sl = entry + 1.0 * float(atr_i)
            risk = sl - entry
            if risk < 0.08 or risk > 4 * float(atr_i):
                continue
            tp = entry - rr * risk
            side = "short"

        arm = bar_end(ts, bar_min)
        hold = int(12 * 60 / (bar_min / 60)) if trail else None  # ~12h trail proxy via time if trail
        # trailing approximated as 2R TP when not trail; when trail use 3R + max hold
        if trail:
            tp = entry + 3 * risk if side == "long" else entry - 3 * risk
            hold = int(16 * 60)  # 16h max
        orders.append(Order(
            arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
            strategy="EMA_PB", variant=variant, meta={"signal_bar": ts},
            expire_minutes=bar_min * 2, max_hold_minutes=hold,
        ))

    orders = dedupe_orders(orders, bar_min * 3)
    return apply_dxy_gate(orders, dxy, use_dxy)
