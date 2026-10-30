"""Shared filters for audited strategies."""
from __future__ import annotations
from typing import List, Optional
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import ema, last_closed_value


def apply_dxy_gate(orders: List[Order], dxy: Optional[pd.DataFrame], use: bool) -> List[Order]:
    """Keep longs only if last CLOSED DXY is below its EMA50; shorts if above."""
    if not use or dxy is None or dxy.empty:
        return orders
    dxy = dxy.copy()
    dxy["ema50"] = ema(dxy["close"], 50)
    out = []
    for o in orders:
        c = last_closed_value(dxy["close"], o.arm_time, 15)
        e = last_closed_value(dxy["ema50"], o.arm_time, 15)
        if c is None or e is None:
            continue
        if o.side == "long" and c < e:
            out.append(o)
        elif o.side == "short" and c > e:
            out.append(o)
    return out


def apply_vol_gate(orders: List[Order], trigger_vol: pd.Series, vol_ma20: pd.Series,
                   use: bool, mult: float = 1.3, bar_minutes: int = 5) -> List[Order]:
    """Tick-volume PROXY: trigger bar volume > mult * 20-bar MA."""
    if not use:
        return orders
    out = []
    for o in orders:
        sig = o.meta.get("signal_bar")
        if sig is None:
            deadline = o.arm_time - pd.Timedelta(minutes=bar_minutes)
            j = trigger_vol.index.searchsorted(deadline, side="right") - 1
            if j < 0:
                continue
            sig = trigger_vol.index[j]
        if sig not in trigger_vol.index or sig not in vol_ma20.index:
            continue
        v = float(trigger_vol.loc[sig])
        m = float(vol_ma20.loc[sig])
        if np.isnan(m) or m <= 0:
            continue
        if v > mult * m:
            out.append(o)
    return out


def apply_htf_gate(orders: List[Order], m15_close: pd.Series, m15_ema50: pd.Series, use: bool) -> List[Order]:
    if not use:
        return orders
    out = []
    for o in orders:
        c = last_closed_value(m15_close, o.arm_time, 15)
        e = last_closed_value(m15_ema50, o.arm_time, 15)
        if c is None or e is None:
            continue
        if o.side == "long" and c > e:
            out.append(o)
        elif o.side == "short" and c < e:
            out.append(o)
    return out


def dedupe_orders(orders: List[Order], minutes: int = 20) -> List[Order]:
    """Dedupe by variant+side+leg so partial scale-out legs (1/3+2/3) are kept."""
    out, last = [], {}
    for o in sorted(orders, key=lambda x: (x.arm_time, x.variant)):
        leg = (o.meta or {}).get("leg", "full")
        key = (o.variant, o.side, leg)
        prev = last.get(key)
        if prev is not None and (o.arm_time - prev).total_seconds() < minutes * 60:
            continue
        out.append(o)
        last[key] = o.arm_time
    return out
