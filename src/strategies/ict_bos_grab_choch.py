"""ict_bos_grab_choch (fx_amirabbas, claims 80% WR):
Prior BOS → wick-only liquidity grab (wick beyond swing, close back inside) → CHoCH of opposite swing
with FVG on CHoCH leg → limit at FVG; SL beyond swept extreme; TP RR2 or swing. NY/all.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before


def generate_ict_bos_grab_choch(
    m1: pd.DataFrame,
    tf: str = "M5",
    session: str = "ny",
    tp_mode: str = "rr2",
    entry_at: str = "mid",
) -> List[Order]:
    bar = 5 if tf == "M5" else 15
    df = resample_ohlc(m1, f"{bar}min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)
    variant = f"bosgrab_{tf}_{session}_{tp_mode}_{entry_at}"
    orders: List[Order] = []
    used = set()

    def in_sess(ts):
        if session == "all":
            return 7 <= ts.hour < 17
        return 12 <= ts.hour < 17

    # Precompute BOS bars
    bos_up = np.zeros(n, dtype=bool)
    bos_dn = np.zeros(n, dtype=bool)
    for i in range(10, n):
        sw = last_swing_before(shi, i)
        if sw is not None and c[i] > h[sw] and c[i] > o[i]:
            bos_up[i] = True
        sw = last_swing_before(sli, i)
        if sw is not None and c[i] < l[sw] and c[i] < o[i]:
            bos_dn[i] = True

    for i in range(40, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        if not in_sess(ts):
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue
        day = ts.normalize()

        # SHORT: recent bos_up, then wick grab above swing high, then choch below swing low
        if (day, "short") not in used:
            if bos_up[max(0, i - 50):i - 3].any():
                # find wick grab in [i-20, i]
                grab_j = None
                grab_ext = None
                for j in range(max(i - 20, 5), i + 1):
                    sw_h = last_swing_before(shi, j)
                    if sw_h is None:
                        continue
                    if h[j] > h[sw_h] and c[j] < h[sw_h]:  # wick-only
                        grab_j = j
                        grab_ext = float(h[j])
                if grab_j is not None and grab_j <= i:
                    # CHoCH at i: break last swing low that existed before/at grab
                    sw_l = last_swing_before(sli, grab_j)
                    if sw_l is not None and c[i] < l[sw_l] and i >= grab_j:
                        # require some bearish close structure
                        if c[i] < o[i] or c[i] < c[max(grab_j, i - 1)]:
                            fvgs = find_fvgs(h, l, a, grab_j, i, "bear", 0.04)
                            if fvgs:
                                glo, ghi, _ = fvgs[-1]
                                px = 0.5 * (glo + ghi) if entry_at == "mid" else float(glo)
                                sl = grab_ext + max(0.1 * atr_v, 0.12)
                                if sl > px:
                                    risk = sl - px
                                    if risk >= 0.2:
                                        tp = (px - 2 * risk) if tp_mode == "rr2" else float(l[sw_l])
                                        if tp_mode != "rr2" and tp >= px - 1.2 * risk:
                                            tp = px - 2 * risk
                                        arm = bar_end(times[i], bar)
                                        orders.append(Order(
                                            arm_time=arm, side="short", kind="limit", price=float(px),
                                            sl=float(sl), tp=float(tp), strategy="BOSGrabCHoCH",
                                            variant=variant, meta={"wick_only": True, "grab": grab_ext},
                                            expire_minutes=90, max_hold_minutes=240,
                                        ))
                                        used.add((day, "short"))

        if (day, "long") not in used:
            if bos_dn[max(0, i - 50):i - 3].any():
                grab_j = grab_ext = None
                for j in range(max(i - 20, 5), i + 1):
                    sw_l = last_swing_before(sli, j)
                    if sw_l is None:
                        continue
                    if l[j] < l[sw_l] and c[j] > l[sw_l]:
                        grab_j = j
                        grab_ext = float(l[j])
                if grab_j is not None:
                    sw_h = last_swing_before(shi, grab_j)
                    if sw_h is not None and c[i] > h[sw_h] and i >= grab_j:
                        if c[i] > o[i] or c[i] > c[max(grab_j, i - 1)]:
                            fvgs = find_fvgs(h, l, a, grab_j, i, "bull", 0.04)
                            if fvgs:
                                glo, ghi, _ = fvgs[-1]
                                px = 0.5 * (glo + ghi) if entry_at == "mid" else float(ghi)
                                sl = grab_ext - max(0.1 * atr_v, 0.12)
                                if sl < px:
                                    risk = px - sl
                                    if risk >= 0.2:
                                        tp = (px + 2 * risk) if tp_mode == "rr2" else float(h[sw_h])
                                        if tp_mode != "rr2" and tp <= px + 1.2 * risk:
                                            tp = px + 2 * risk
                                        arm = bar_end(times[i], bar)
                                        orders.append(Order(
                                            arm_time=arm, side="long", kind="limit", price=float(px),
                                            sl=float(sl), tp=float(tp), strategy="BOSGrabCHoCH",
                                            variant=variant, meta={"wick_only": True, "grab": grab_ext},
                                            expire_minutes=90, max_hold_minutes=240,
                                        ))
                                        used.add((day, "long"))

    return dedupe_orders(orders, 40)


def generate_bosgrab_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15"):
        for sess in ("ny", "all"):
            for tp in ("rr2", "swing"):
                for ent in ("mid", "edge"):
                    print(f" bosgrab {tf} {sess} {tp} {ent}", flush=True)
                    oo = generate_ict_bos_grab_choch(m1, tf, sess, tp, ent)
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
                    else:
                        print("  n=0", flush=True)
    return pools
