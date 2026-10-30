"""tema_cross (trade_ela / AdventTrading): TEMA 13/21/55 + EMA8.
Long when 55 crosses from above to below all three others; exit when 55 crosses back above all.
Mirror short as variant. SL: atr | swing | none(signal-exit via max_hold). TFs M5/M15/H1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, ema
from strategies.common import dedupe_orders
from strategies.batch2_helpers import tema
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def generate_tema_cross(
    m1: pd.DataFrame,
    tf: str = "M15",
    side_mode: str = "long",   # long | short | both
    sl_mode: str = "atr",      # atr | swing | signal
    atr_mult: float = 1.5,
) -> List[Order]:
    bar = {"M5": 5, "M15": 15, "H1": 60}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    c = df["close"]
    t55 = tema(c, 55).values
    t21 = tema(c, 21).values
    t13 = tema(c, 13).values
    e8 = ema(c, 8).values
    close = c.values
    high, low = df["high"].values, df["low"].values
    times = df.index
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(high, low, 2, 2)
    n = len(df)
    variant = f"tema_{tf}_{side_mode}_sl{sl_mode}_a{atr_mult:g}"
    orders: List[Order] = []

    def below_all(i):
        return t55[i] < t21[i] and t55[i] < t13[i] and t55[i] < e8[i]
    def above_all(i):
        return t55[i] > t21[i] and t55[i] > t13[i] and t55[i] > e8[i]

    i = 60
    while i < n - 2:
        if np.isnan(t55[i]) or np.isnan(e8[i]) or np.isnan(a[i]) or a[i] <= 0:
            i += 1; continue
        if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
            i += 1; continue
        # long entry: was NOT below_all, now below_all
        long_x = (not below_all(i - 1)) and below_all(i)
        short_x = (not above_all(i - 1)) and above_all(i)
        side = None
        if long_x and side_mode in ("long", "both"):
            side = "long"
        elif short_x and side_mode in ("short", "both"):
            side = "short"
        if side is None:
            i += 1; continue

        # find exit: reverse cross
        exit_i = None
        for j in range(i + 1, min(i + 500, n)):
            if side == "long" and (not above_all(j - 1)) and above_all(j):
                exit_i = j; break
            if side == "short" and (not below_all(j - 1)) and below_all(j):
                exit_i = j; break
        if exit_i is None:
            exit_i = min(i + 200, n - 1)

        px = float(close[i])
        atr_v = float(a[i])
        if sl_mode == "atr":
            sl = px - atr_mult * atr_v if side == "long" else px + atr_mult * atr_v
        elif sl_mode == "swing":
            if side == "long":
                sw = last_swing_before(sli, i)
                sl = (float(low[sw]) - 0.1 * atr_v) if sw is not None else px - atr_mult * atr_v
            else:
                sw = last_swing_before(shi, i)
                sl = (float(high[sw]) + 0.1 * atr_v) if sw is not None else px + atr_mult * atr_v
        else:  # signal — soft SL far; primary exit max_hold at reverse
            sl = px - 8.0 if side == "long" else px + 8.0  # cap boundary soft

        # TP: at reverse-cross close (signal exit approximation) or RR from risk
        exit_px = float(close[exit_i])
        risk = abs(px - sl)
        if risk < 0.15:
            i += 1; continue
        if sl_mode == "signal":
            tp = exit_px
            # ensure TP on correct side or use max_hold only with far TP
            if side == "long" and tp <= px:
                tp = px + 3 * risk
            if side == "short" and tp >= px:
                tp = px - 3 * risk
        else:
            # allow signal exit via max_hold; also RR3 TP as backup
            tp = px + 3 * risk if side == "long" else px - 3 * risk

        hold = max(bar, int((times[exit_i] - times[i]).total_seconds() / 60) + bar)
        arm = bar_end(times[i], bar)
        orders.append(Order(
            arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
            strategy="TEMACross", variant=variant,
            meta={"exit_i": int(exit_i), "sl_mode": sl_mode},
            expire_minutes=bar * 2, max_hold_minutes=hold,
        ))
        i = exit_i + 1  # no overlap

    return dedupe_orders(orders, bar)


def generate_tema_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15", "H1"):
        for sm in ("long", "short", "both"):
            for slm in ("atr", "swing", "signal"):
                for am in (1.0, 1.5, 2.0) if slm == "atr" else (1.5,):
                    print(f" tema {tf} {sm} {slm} {am}", flush=True)
                    oo = generate_tema_cross(m1, tf, sm, slm, am)
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
    return pools
