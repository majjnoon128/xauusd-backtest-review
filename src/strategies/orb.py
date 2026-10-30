"""Opening Range Breakout — London 07:00 UTC, NY 13:30 UTC."""
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


def generate_orb(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    session: str = "london",          # london | ny
    range_min: int = 30,              # 15 | 30 | 60
    entry: str = "stop",              # stop | close_break
    sl_mode: str = "opposite",        # opposite | mid | atr_buf
    rr: float = 2.0,                  # 1.5 | 2.0 | 0 (eod = session end)
    atr_filter: bool = True,
    atr_lo: float = 0.4,
    atr_hi: float = 3.0,
) -> List[Order]:
    if session == "london":
        open_h, open_m = 7, 0
        sess_end_h = 12  # flat by 12:00 UTC if eod
    else:
        open_h, open_m = 13, 30
        sess_end_h = 20

    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders: List[Order] = []
    # group by UTC date
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        open_ts = d + pd.Timedelta(hours=open_h, minutes=open_m)
        range_end = open_ts + pd.Timedelta(minutes=range_min)
        # range bars: [open_ts, range_end)
        seg = m1[(m1.index >= open_ts) & (m1.index < range_end)]
        if len(seg) < max(5, range_min // 2):
            continue
        rh, rl = float(seg["high"].max()), float(seg["low"].min())
        mid = 0.5 * (rh + rl)
        rng = rh - rl
        if rng < 0.15:
            continue
        # ATR filter on last closed M5 before range_end
        if atr_filter:
            j = a5.index.searchsorted(range_end, side="left") - 1
            if j < 0 or np.isnan(a5.iloc[j]) or a5.iloc[j] <= 0:
                continue
            atr_v = float(a5.iloc[j])
            if not (atr_lo * atr_v <= rng <= atr_hi * atr_v):
                continue
        # trade window after range
        win_end = d + pd.Timedelta(hours=sess_end_h)
        after = m1[(m1.index >= range_end) & (m1.index < win_end)]
        if after.empty:
            continue
        # one direction per day: first break only (or both armed as stops)
        variant = f"{session}_r{range_min}_{entry}_sl{sl_mode}_rr{rr}"
        if atr_filter:
            variant += "_atr"
        max_hold = int((win_end - range_end).total_seconds() // 60)

        # ATR at range end for atr_buf
        jatr = a5.index.searchsorted(range_end, side="left") - 1
        atr_v = float(a5.iloc[jatr]) if jatr >= 0 and not np.isnan(a5.iloc[jatr]) else rng / 2

        def _sl(side, px):
            if sl_mode == "opposite":
                return rl if side == "long" else rh
            if sl_mode == "mid":
                return mid
            buf = max(0.35 * atr_v, 0.15)
            return (px - buf) if side == "long" else (px + buf)

        if entry == "stop":
            # arm both stops at range end; engine one-position will take first
            for side, px in (("long", rh), ("short", rl)):
                sl = _sl(side, px)
                risk = abs(px - sl)
                if risk < 0.08:
                    continue
                if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                    continue
                if rr and rr > 0:
                    tp = px + rr * risk if side == "long" else px - rr * risk
                    hold = None
                else:
                    # eod: wide TP, max_hold
                    tp = px + 5 * risk if side == "long" else px - 5 * risk
                    hold = max_hold
                orders.append(Order(
                    arm_time=range_end, side=side, kind="stop", price=px, sl=sl, tp=tp,
                    strategy="ORB", variant=variant, meta={"signal_bar": range_end, "day": str(d.date())},
                    expire_minutes=max_hold, max_hold_minutes=hold,
                ))
        else:
            # close_break on M5: first closed M5 beyond range
            m5_win = m5[(m5.index >= range_end) & (m5.index < win_end)]
            fired = False
            for ts, row in m5_win.iterrows():
                side = None
                if float(row["close"]) > rh:
                    side, entry_px = "long", float(row["close"])
                    sl = _sl("long", rh if sl_mode != "atr_buf" else entry_px)
                elif float(row["close"]) < rl:
                    side, entry_px = "short", float(row["close"])
                    sl = _sl("short", rl if sl_mode != "atr_buf" else entry_px)
                if side is None:
                    continue
                risk = abs(entry_px - sl)
                if risk < 0.08:
                    continue
                arm = bar_end(ts, 5)
                if rr and rr > 0:
                    tp = entry_px + rr * risk if side == "long" else entry_px - rr * risk
                    hold = None
                else:
                    tp = entry_px + 5 * risk if side == "long" else entry_px - 5 * risk
                    hold = max(1, int((win_end - arm).total_seconds() // 60))
                orders.append(Order(
                    arm_time=arm, side=side, kind="market", price=entry_px, sl=sl, tp=tp,
                    strategy="ORB", variant=variant, meta={"signal_bar": ts, "day": str(d.date())},
                    expire_minutes=60, max_hold_minutes=hold,
                ))
                fired = True
                break

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)
