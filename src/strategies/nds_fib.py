"""NDS Fib — closed M15 impulse, zone, M1 engulfing confirm; market after bar end + delay.

Primary zone: 0.62–0.78 retracement.
Comparison zone: 0.786–0.86 (legacy).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bullish_engulfing, bearish_engulfing, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders


def _zone_bounds(side: str, swing_high: float, swing_low: float, lo_fib: float, hi_fib: float):
    move = swing_high - swing_low
    if side == "long":
        # retracement from high: deeper fib = lower price
        z_hi = swing_high - lo_fib * move  # e.g. 0.62 → higher edge
        z_lo = swing_high - hi_fib * move  # e.g. 0.78 → lower edge
    else:
        z_lo = swing_low + lo_fib * move
        z_hi = swing_low + hi_fib * move
    return z_lo, z_hi


def generate_nds_fib(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    use_vol: bool = False,
    rr: float = 1.5,
    vol_mult: float = 1.3,
    zones: tuple = (("062_078", 0.62, 0.78), ("0786_086", 0.786, 0.86)),
) -> List[Order]:
    """Emit orders for each zone variant. Primary = 062_078."""
    m15 = resample_ohlc(m1, "15min")
    m15_atr = atr_prior(m15, 14)
    m1_bull = bullish_engulfing(m1)
    m1_bear = bearish_engulfing(m1)
    m1_vol_ma = vol_ma(m1["volume"], 20) if "volume" in m1.columns else None
    orders: List[Order] = []

    m15_bull = m15["close"] > m15["open"]
    m15_bear = m15["close"] < m15["open"]

    for i in range(20, len(m15) - 1):
        a = float(m15_atr.iloc[i]) if not np.isnan(m15_atr.iloc[i]) else 0
        if a <= 0:
            continue
        for length in (3, 4, 5, 6):
            if i - length + 1 < 0:
                continue
            seg = m15.iloc[i - length + 1 : i + 1]
            swing_low = float(seg["low"].min())
            swing_high = float(seg["high"].max())
            move = swing_high - swing_low
            if move < 1.5 * a:
                continue
            bull_imp = float(seg["close"].iloc[-1]) > float(seg["open"].iloc[0]) and (
                m15_bull.iloc[i - length + 1 : i + 1].mean() >= 0.6
            )
            bear_imp = float(seg["close"].iloc[-1]) < float(seg["open"].iloc[0]) and (
                m15_bear.iloc[i - length + 1 : i + 1].mean() >= 0.6
            )
            if not (bull_imp or bear_imp):
                continue
            side = "long" if bull_imp else "short"

            t0 = bar_end(m15.index[i], 15)
            t1 = t0 + pd.Timedelta(hours=4)
            j0 = m1.index.searchsorted(t0, side="left")
            j1 = m1.index.searchsorted(t1, side="left")

            found_any = False
            for zname, flo, fhi in zones:
                z_lo, z_hi = _zone_bounds(side, swing_high, swing_low, flo, fhi)
                found = False
                for j in range(j0, min(j1, len(m1))):
                    ts = m1.index[j]
                    if not in_session(ts):
                        continue
                    if side == "long":
                        if not bool(m1_bull.iloc[j]):
                            continue
                        px = float(m1["close"].iloc[j])
                        if not (z_lo <= px <= z_hi or z_lo <= float(m1["low"].iloc[j]) <= z_hi):
                            continue
                        entry = px
                        sl = float(min(m1["low"].iloc[j], z_lo) - 0.1 * a)
                        risk = entry - sl
                        if risk <= 0.05:
                            continue
                        tp = entry + rr * risk
                    else:
                        if not bool(m1_bear.iloc[j]):
                            continue
                        px = float(m1["close"].iloc[j])
                        if not (z_lo <= px <= z_hi or z_lo <= float(m1["high"].iloc[j]) <= z_hi):
                            continue
                        entry = px
                        sl = float(max(m1["high"].iloc[j], z_hi) + 0.1 * a)
                        risk = sl - entry
                        if risk <= 0.05:
                            continue
                        tp = entry - rr * risk
                    arm = bar_end(ts, 1)
                    orders.append(Order(
                        arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                        strategy="NDS_Fib", variant=f"{zname}_rr{rr}",
                        meta={"signal_bar": ts, "zone": zname}, expire_minutes=30,
                    ))
                    found = True
                    found_any = True
                    break
                # continue other zones independently (comparison)
            if found_any:
                break  # one impulse length per M15 bar

    orders = dedupe_orders(orders, 30)
    if use_vol and m1_vol_ma is not None:
        orders = apply_vol_gate(orders, m1["volume"], m1_vol_ma, True, vol_mult, 1)
    return apply_dxy_gate(orders, dxy, use_dxy)
