"""Session Box → MSS (close outside + break swing) → FVG retrace entry.

Boxes:
  asia   = UTC 00:00–07:00 (classic Asian range)
  london = UTC 07:00–08:00 (London open hour)
  both   = asia + london same day (multiple boxes / day)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import apply_dxy_gate, dedupe_orders
from strategies.ict_helpers import (
    find_fvgs, swing_highs_lows, last_swing_before, is_displacement, asian_ranges,
)


TF_RULE = {"M1": ("1min", 1), "M3": ("3min", 3), "M5": ("5min", 5), "M15": ("15min", 15)}


def _session_ranges(m1: pd.DataFrame, kind: str) -> Dict[Tuple, Tuple[float, float, pd.Timestamp]]:
    """Return {(date, box_id): (high, low, available_from_ts)}."""
    out = {}
    for d in m1.index.normalize().unique():
        if int(getattr(d, "day_of_week", d.dayofweek)) >= 5:
            continue
        day = pd.Timestamp(d)
        if kind in ("asia", "both"):
            seg = m1[(m1.index >= day) & (m1.index < day + pd.Timedelta(hours=7))]
            if len(seg) >= 30:
                out[(day.date(), "asia")] = (
                    float(seg["high"].max()), float(seg["low"].min()),
                    day + pd.Timedelta(hours=7),
                )
        if kind in ("london", "both"):
            seg = m1[(m1.index >= day + pd.Timedelta(hours=7)) &
                     (m1.index < day + pd.Timedelta(hours=8))]
            if len(seg) >= 20:
                out[(day.date(), "london")] = (
                    float(seg["high"].max()), float(seg["low"].min()),
                    day + pd.Timedelta(hours=8),
                )
    return out


def generate_session_box_mss(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    entry_mode: str = "limit_mid",  # limit_mid | market
    tp_mode: str = "rr2",           # rr1.5 | rr2 | box_opp
    require_disp: bool = True,
    disp_atr: float = 0.8,
    sl_mode: str = "atr_buf",  # atr_buf | box_opp
    entry_tf: str = "M5",           # M1 | M3 | M5 | M15
    box_kind: str = "asia",         # asia | london | both
) -> List[Order]:
    if entry_tf not in TF_RULE:
        raise ValueError(f"unsupported entry_tf={entry_tf}")
    rule, bar_m = TF_RULE[entry_tf]
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, rule)
    a = atr_prior(df, 14).values
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    shi, sli = swing_highs_lows(h, l, 2, 2)
    boxes = _session_ranges(m1, box_kind)
    variant = (
        f"box_{entry_tf}_{box_kind}_{entry_mode}_{tp_mode}_"
        f"disp{int(require_disp)}_d{disp_atr}_sl{sl_mode}"
    )
    # keep legacy variant name for asia+prior API callers that omit box_kind
    if box_kind == "asia":
        variant_legacy = f"box_{entry_tf}_{entry_mode}_{tp_mode}_disp{int(require_disp)}_d{disp_atr}_sl{sl_mode}"
        variant = variant_legacy
    orders: List[Order] = []
    used = set()

    for i in range(10, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        day = ts.normalize()
        dkey = day.date()
        # candidate boxes for this bar: available_from <= ts, and trade window after box
        cands = []
        for (dk, bid), (bh, bl, avail) in boxes.items():
            if dk != dkey:
                continue
            if ts < avail:
                continue
            # trade windows
            hr = ts.hour
            if bid == "asia":
                if not (7 <= hr < 17):
                    continue
            else:  # london
                if not (8 <= hr < 21):
                    continue
            if bh - bl < 0.5:
                continue
            cands.append((bid, bh, bl))
        if not cands:
            continue

        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        for bid, bh, bl in cands:
            if (dkey, bid, "long") in used and (dkey, bid, "short") in used:
                continue
            setups = []
            if (dkey, bid, "long") not in used and c[i] > bh:
                sw = last_swing_before(shi, i)
                if sw is not None and c[i] > h[sw]:
                    if (not require_disp) or (is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] > o[i]):
                        setups.append("long")
            if (dkey, bid, "short") not in used and c[i] < bl:
                sw = last_swing_before(sli, i)
                if sw is not None and c[i] < l[sw]:
                    if (not require_disp) or (is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] < o[i]):
                        setups.append("short")

            for side in setups:
                fvg_dir = "bull" if side == "long" else "bear"
                fvgs = find_fvgs(h, l, a, max(i - 6, 0), i, fvg_dir, min_atr=0.08)
                if not fvgs:
                    continue
                gap_lo, gap_hi, _ = fvgs[-1]
                mid = 0.5 * (gap_lo + gap_hi)
                if entry_mode == "limit_mid":
                    kind, px = "limit", mid
                else:
                    kind, px = "market", float(c[i])
                buf = max(0.25 * atr_v, 0.15)
                if sl_mode == "atr_buf":
                    sl_fvg = (gap_lo - buf) if side == "long" else (gap_hi + buf)
                    sl_edge = (bh - buf) if side == "long" else (bl + buf)
                    cands_sl = []
                    for s in (sl_fvg, sl_edge):
                        if side == "long" and s < px:
                            cands_sl.append(s)
                        if side == "short" and s > px:
                            cands_sl.append(s)
                    if not cands_sl:
                        continue
                    sl = max(cands_sl) if side == "long" else min(cands_sl)
                else:
                    sl = (min(bl, float(l[i])) - 0.05) if side == "long" else (max(bh, float(h[i])) + 0.05)
                risk = abs(px - sl)
                if risk < 0.15:
                    continue
                if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                    continue
                if tp_mode.startswith("rr"):
                    rr = float(tp_mode.replace("rr", ""))
                    tp = px + rr * risk if side == "long" else px - rr * risk
                else:
                    if side == "long":
                        tp = bh if bh > px + 0.9 * risk else px + 2 * risk
                    else:
                        tp = bl if bl < px - 0.9 * risk else px - 2 * risk

                arm = bar_end(times[i], bar_m)
                orders.append(Order(
                    arm_time=arm, side=side, kind=kind, price=px, sl=sl, tp=tp,
                    strategy="SessionBoxMSS", variant=variant,
                    meta={"signal_bar": times[i], "day": str(dkey), "box": (bh, bl), "box_id": bid},
                    expire_minutes=60 if kind == "limit" else 20,
                    max_hold_minutes=240,
                ))
                used.add((dkey, bid, side))

    dedupe_min = {1: 20, 3: 30, 5: 40, 15: 60}.get(bar_m, 40)
    orders = dedupe_orders(orders, dedupe_min)
    return apply_dxy_gate(orders, dxy, use_dxy)
