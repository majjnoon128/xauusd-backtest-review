"""SP2L on M5: spike+FVG, pullback; entry A market / B stop after closed bars."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, ema, body, is_bull, is_bear, resample_ohlc, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders, apply_htf_gate


def generate_sp2l(m1, dxy=None, use_dxy=False, use_vol=False, use_htf=True,
                  rr_list=(1.0, 1.5, 2.0), vol_mult=1.3, rule: str = "5min") -> List[Order]:
    df = resample_ohlc(m1, rule)
    a = atr_prior(df, 14).values
    ranges = (df["high"] - df["low"]).values
    bull, bear = is_bull(df).values, is_bear(df).values
    high, low, close, open_ = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    times = df.index
    m15 = resample_ohlc(m1, "15min")
    m15_ema = ema(m15["close"], 50)
    volma = vol_ma(df["volume"], 20) if "volume" in df.columns else None
    bar_min = {"1min":1,"5min":5,"15min":15,"30min":30,"1h":60,"4h":240}.get(rule, 5)
    BODY_MULT, FVG_MULT = 0.8, 0.05
    orders = []
    n = len(df)
    used = np.zeros(n, dtype=bool)

    for i in range(30, n - 10):
        if used[i]:
            continue
        ts = times[i]
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        for spike_len in (2, 3, 4, 5):
            start = i - spike_len + 1
            if start < 1:
                continue
            # bullish
            if sum(bull[start:i+1]) >= max(2, spike_len - 1) and close[i] > close[start]:
                total = high[start:i+1].max() - low[start:i+1].min()
                if not all(ranges[j] > BODY_MULT * atr_i for j in range(start, i+1)):
                    if total < 2.0 * atr_i:
                        continue
                has_fvg = False
                for k in range(start, i):
                    if k + 2 <= i and low[k+2] > high[k] and (low[k+2]-high[k]) >= FVG_MULT*atr_i:
                        has_fvg = True
                        break
                if not has_fvg:
                    continue  # official SP2L: no P-Gap/FVG → invalid (no waiver)
                spike_origin_low = float(low[start:i+1].min())
                spike_high = float(high[start:i+1].max())
                spike_range = spike_high - spike_origin_low
                if spike_range < 1.2 * atr_i:
                    continue
                used[start:i+1] = True
                # look for pullback AFTER spike bar i is closed
                for j in range(i + 1, min(i + 15, n - 1)):
                    if not (low[j] < low[j-1] or close[j] < open_[j]):
                        continue
                    if (spike_high - low[j]) > 0.55 * spike_range:
                        break
                    if not in_session(times[j]):
                        continue
                    # Official: entry only when pullback candle takes prior candle's low
                    if low[j] < low[j-1]:
                        # Variant A: market after that bar closes
                        entry = float(close[j])
                        sl = spike_origin_low - 0.05 * atr_i
                        risk = entry - sl
                        if 0.08 < risk <= 2.5 * atr_i:
                            arm = bar_end(times[j], bar_min)
                            for rr in rr_list:
                                orders.append(Order(arm, "long", "market", entry, sl, entry+rr*risk,
                                                    "SP2L", f"{rule}_A_rr{rr}", {"signal_bar": times[j]}, 60))
                        # Variant B: buy stop at pullback high, only on valid 2nd-leg trigger
                        entry = float(high[j])
                        sl = spike_origin_low - 0.05 * atr_i
                        risk = entry - sl
                        if 0.08 < risk <= 2.5 * atr_i:
                            arm = bar_end(times[j], bar_min)
                            for rr in rr_list:
                                orders.append(Order(arm, "long", "stop", entry, sl, entry+rr*risk,
                                                    "SP2L", f"{rule}_B_rr{rr}", {"signal_bar": times[j]}, 60))
                    break
                break

            # bearish
            if sum(bear[start:i+1]) >= max(2, spike_len - 1) and close[i] < close[start]:
                total = high[start:i+1].max() - low[start:i+1].min()
                if not all(ranges[j] > BODY_MULT * atr_i for j in range(start, i+1)):
                    if total < 2.0 * atr_i:
                        continue
                has_fvg = False
                for k in range(start, i):
                    if k + 2 <= i and high[k+2] < low[k] and (low[k]-high[k+2]) >= FVG_MULT*atr_i:
                        has_fvg = True
                        break
                if not has_fvg:
                    continue  # official SP2L: no P-Gap/FVG → invalid (no waiver)
                spike_origin_high = float(high[start:i+1].max())
                spike_low = float(low[start:i+1].min())
                spike_range = spike_origin_high - spike_low
                if spike_range < 1.2 * atr_i:
                    continue
                used[start:i+1] = True
                for j in range(i + 1, min(i + 15, n - 1)):
                    if not (high[j] > high[j-1] or close[j] > open_[j]):
                        continue
                    if (high[j] - spike_low) > 0.55 * spike_range:
                        break
                    if not in_session(times[j]):
                        continue
                    if high[j] > high[j-1]:
                        entry = float(close[j])
                        sl = spike_origin_high + 0.05 * atr_i
                        risk = sl - entry
                        if 0.08 < risk <= 2.5 * atr_i:
                            arm = bar_end(times[j], bar_min)
                            for rr in rr_list:
                                orders.append(Order(arm, "short", "market", entry, sl, entry-rr*risk,
                                                    "SP2L", f"{rule}_A_rr{rr}", {"signal_bar": times[j]}, 60))
                        entry = float(low[j])
                        sl = spike_origin_high + 0.05 * atr_i
                        risk = sl - entry
                        if 0.08 < risk <= 2.5 * atr_i:
                            arm = bar_end(times[j], bar_min)
                            for rr in rr_list:
                                orders.append(Order(arm, "short", "stop", entry, sl, entry-rr*risk,
                                                    "SP2L", f"{rule}_B_rr{rr}", {"signal_bar": times[j]}, 60))
                    break
                break

    orders = dedupe_orders(orders, 15)
    if use_htf:
        orders = apply_htf_gate(orders, m15["close"], m15_ema, True)
    if use_vol and volma is not None:
        orders = apply_vol_gate(orders, df["volume"], volma, True, vol_mult, bar_min)
    return apply_dxy_gate(orders, dxy, use_dxy)
