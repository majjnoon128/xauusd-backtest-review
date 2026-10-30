"""MicroMAP M5 — single entry H1/IB/H2, no re-entries."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, body, is_bull, is_bear, inside_bar, resample_ohlc, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders


def generate_micromap(m1, dxy=None, use_dxy=False, use_vol=False, vol_mult=1.3, rule: str = "5min",
                      allow_reentry: bool = False) -> List[Order]:
    """allow_reentry: if True, emit H1 then H2-style next attempts (teacher chain); prop usually False."""
    df = resample_ohlc(m1, rule)
    a = atr_prior(df, 14).values
    bodies = body(df).values
    bull, bear = is_bull(df).values, is_bear(df).values
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    times = df.index
    ib = inside_bar(df).values
    volma = vol_ma(df["volume"], 20) if "volume" in df.columns else None
    bar_min = {"1min":1,"5min":5,"15min":15,"30min":30,"1h":60,"4h":240}.get(rule, 5)
    n = len(df)
    orders = []

    for i in range(20, n - 15):
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        for slen in (2, 3, 4):
            s0 = i - slen + 1
            if s0 < 0: continue
            # bullish spike
            if all(bull[s0:i+1]) and all(bodies[s0:i+1] > 1.0*atr_i):
                if any((high[k]-close[k]) > 0.35*bodies[k] for k in range(s0,i+1) if bodies[k]>0):
                    continue
                spike_high = float(high[s0:i+1].max()); spike_low = float(low[s0])
                for end in range(i+3, min(i+10, n-3)):
                    seg_h, seg_l, seg_b = high[i+1:end+1], low[i+1:end+1], bodies[i+1:end+1]
                    if not all(seg_h[k] <= seg_h[k-1]+0.05*atr_i for k in range(1,len(seg_h))):
                        continue
                    if float(np.mean(seg_b)) > 0.7*float(np.mean(bodies[s0:i+1])):
                        continue
                    if seg_l.min() < spike_low - 0.1*atr_i:
                        continue
                    ch_high, ch_low = float(seg_h[-1]), float(seg_l.min())
                    # H1: after channel ends, arm buy stop at ch_high
                    if in_session(times[end]):
                        arm = bar_end(times[end], bar_min)
                        entry, sl = ch_high, ch_low - 0.05*atr_i
                        risk = entry - sl
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"long","stop",entry,sl,entry+1.5*risk,"MicroMAP",f"{rule}_H1_rr1.5",{"signal_bar":times[end]},60))
                    if end+1 < n and ib[end+1] and in_session(times[end+1]):
                        arm = bar_end(times[end+1], bar_min)
                        entry, sl = float(high[end+1]), float(low[end+1])-0.05*atr_i
                        risk = entry - sl
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"long","stop",entry,sl,entry+1.5*risk,"MicroMAP",f"{rule}_IB_rr1.5",{"signal_bar":times[end+1]},60))
                    if end+2 < n and high[end+1] > ch_high and high[end+2] > high[end+1] and in_session(times[end+2]):
                        arm = bar_end(times[end+2], bar_min)
                        entry = float(close[end+2]); sl = float(min(low[end+1], ch_low))-0.05*atr_i
                        risk = entry - sl
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"long","market",entry,sl,entry+2*risk,"MicroMAP",f"{rule}_H2_rr2",{"signal_bar":times[end+2]},60))
                    break
                break
            # bearish spike
            if all(bear[s0:i+1]) and all(bodies[s0:i+1] > 1.0*atr_i):
                if any((close[k]-low[k]) > 0.35*bodies[k] for k in range(s0,i+1) if bodies[k]>0):
                    continue
                spike_low = float(low[s0:i+1].min()); spike_high = float(high[s0])
                for end in range(i+3, min(i+10, n-3)):
                    seg_h, seg_l, seg_b = high[i+1:end+1], low[i+1:end+1], bodies[i+1:end+1]
                    if not all(seg_l[k] >= seg_l[k-1]-0.05*atr_i for k in range(1,len(seg_l))):
                        continue
                    if float(np.mean(seg_b)) > 0.7*float(np.mean(bodies[s0:i+1])):
                        continue
                    if seg_h.max() > spike_high + 0.1*atr_i:
                        continue
                    ch_low, ch_high = float(seg_l[-1]), float(seg_h.max())
                    if in_session(times[end]):
                        arm = bar_end(times[end], bar_min)
                        entry, sl = ch_low, ch_high + 0.05*atr_i
                        risk = sl - entry
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"short","stop",entry,sl,entry-1.5*risk,"MicroMAP",f"{rule}_H1_rr1.5",{"signal_bar":times[end]},60))
                    if end+1 < n and ib[end+1] and in_session(times[end+1]):
                        arm = bar_end(times[end+1], bar_min)
                        entry, sl = float(low[end+1]), float(high[end+1])+0.05*atr_i
                        risk = sl - entry
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"short","stop",entry,sl,entry-1.5*risk,"MicroMAP",f"{rule}_IB_rr1.5",{"signal_bar":times[end+1]},60))
                    if end+2 < n and low[end+1] < ch_low and low[end+2] < low[end+1] and in_session(times[end+2]):
                        arm = bar_end(times[end+2], bar_min)
                        entry = float(close[end+2]); sl = float(max(high[end+1], ch_high))+0.05*atr_i
                        risk = sl - entry
                        if 0.05 < risk <= 2.5*atr_i:
                            orders.append(Order(arm,"short","market",entry,sl,entry-2*risk,"MicroMAP",f"{rule}_H2_rr2",{"signal_bar":times[end+2]},60))
                    break
                break

    orders = dedupe_orders(orders, 30)
    if use_vol and volma is not None:
        orders = apply_vol_gate(orders, df["volume"], volma, True, vol_mult, bar_min)
    return apply_dxy_gate(orders, dxy, use_dxy)
