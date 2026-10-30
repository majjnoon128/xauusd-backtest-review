"""Asian range breakout 00:00–07:00 UTC → London/NY. SL: opposite/mid/atr_buf."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, bar_end, resample_ohlc
from strategies.common import apply_dxy_gate, dedupe_orders


def _sl_tp(side, px, rh, rl, mid, atr_v, sl_mode, rr):
    if sl_mode == "opposite":
        sl = rl if side == "long" else rh
    elif sl_mode == "mid":
        sl = mid
    else:  # atr_buf — SL just beyond broken level
        buf = max(0.35 * atr_v, 0.15)
        sl = (px - buf) if side == "long" else (px + buf)
    risk = abs(px - sl)
    if risk < 0.08:
        return None
    # if mid/opposite still puts SL on wrong side of entry for fade cases
    if side == "long" and sl >= px:
        return None
    if side == "short" and sl <= px:
        return None
    tp = px + rr * risk if side == "long" else px - rr * risk
    return sl, tp, risk


def generate_asian_bo(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    mode: str = "breakout",
    sl_mode: str = "atr_buf",
    rr: float = 2.0,
    entry: str = "stop",
    window: str = "london_ny",
) -> List[Order]:
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders: List[Order] = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if int(getattr(d, "day_of_week", d.dayofweek)) >= 5:
            continue
        asian = m1[(m1.index >= d) & (m1.index < d + pd.Timedelta(hours=7))]
        if len(asian) < 30:
            continue
        rh, rl = float(asian["high"].max()), float(asian["low"].min())
        mid = 0.5 * (rh + rl)
        rng = rh - rl
        if rng < 0.4:
            continue
        j = a5.index.searchsorted(d + pd.Timedelta(hours=7), side="left") - 1
        atr_v = float(a5.iloc[j]) if j >= 0 and not np.isnan(a5.iloc[j]) else rng / 3
        if atr_v <= 0:
            continue
        # soft size filter only
        if rng < 0.25 * atr_v or rng > 25 * atr_v:
            continue
        wins = []
        if window in ("london_ny", "london"):
            wins.append((d + pd.Timedelta(hours=7), d + pd.Timedelta(hours=12)))
        if window in ("london_ny", "ny"):
            wins.append((d + pd.Timedelta(hours=12), d + pd.Timedelta(hours=20)))
        variant = f"asian_{mode}_{entry}_sl{sl_mode}_rr{rr}_{window}"
        day_used = False
        for w0, w1 in wins:
            if day_used and mode == "breakout":
                break
            max_hold = int((w1 - w0).total_seconds() // 60)
            if mode == "breakout":
                if entry == "stop":
                    for side, px in (("long", rh), ("short", rl)):
                        out = _sl_tp(side, px, rh, rl, mid, atr_v, sl_mode, rr)
                        if out is None:
                            continue
                        sl, tp, _ = out
                        orders.append(Order(
                            arm_time=w0, side=side, kind="stop", price=px, sl=sl, tp=tp,
                            strategy="AsianBO", variant=variant,
                            meta={"signal_bar": w0, "day": str(d.date())},
                            expire_minutes=max_hold,
                        ))
                    day_used = True
                else:
                    m5_win = m5[(m5.index >= w0) & (m5.index < w1)]
                    for ts, row in m5_win.iterrows():
                        side = None
                        if float(row["close"]) > rh:
                            side, ep = "long", float(row["close"])
                        elif float(row["close"]) < rl:
                            side, ep = "short", float(row["close"])
                        if side is None:
                            continue
                        out = _sl_tp(side, ep, rh, rl, mid, atr_v, sl_mode, rr)
                        if out is None:
                            continue
                        sl, tp, _ = out
                        orders.append(Order(
                            arm_time=bar_end(ts, 5), side=side, kind="market", price=ep, sl=sl, tp=tp,
                            strategy="AsianBO", variant=variant,
                            meta={"signal_bar": ts, "day": str(d.date())},
                            expire_minutes=90,
                        ))
                        day_used = True
                        break
            else:
                # fade false-break reclaim
                m5_win = m5[(m5.index >= w0) & (m5.index < w1)]
                swept_hi = swept_lo = False
                for ts, row in m5_win.iterrows():
                    h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
                    if h > rh:
                        swept_hi = True
                    if l < rl:
                        swept_lo = True
                    side = None
                    if swept_hi and c < rh:
                        side, ep = "short", c
                        # SL above sweep extreme
                        sl = h + 0.05
                        risk = sl - ep
                        if risk < 0.08:
                            continue
                        tp = mid if sl_mode in ("mid", "opposite") else ep - rr * risk
                        if sl_mode == "atr_buf":
                            tp = ep - rr * risk
                    elif swept_lo and c > rl:
                        side, ep = "long", c
                        sl = l - 0.05
                        risk = ep - sl
                        if risk < 0.08:
                            continue
                        tp = mid if sl_mode in ("mid", "opposite") else ep + rr * risk
                        if sl_mode == "atr_buf":
                            tp = ep + rr * risk
                    if side is None:
                        continue
                    if side == "long" and tp <= ep:
                        tp = ep + rr * abs(ep - sl)
                    if side == "short" and tp >= ep:
                        tp = ep - rr * abs(ep - sl)
                    orders.append(Order(
                        arm_time=bar_end(ts, 5), side=side, kind="market", price=ep, sl=sl, tp=tp,
                        strategy="AsianBO", variant=variant,
                        meta={"signal_bar": ts, "day": str(d.date())},
                        expire_minutes=60,
                    ))
                    day_used = True
                    break
            if day_used:
                break

    orders = dedupe_orders(orders, 45)
    return apply_dxy_gate(orders, dxy, use_dxy)
