"""fib_ote_fvg (mehraninvest): BOS impulse → Fib 1.0→0.0 → FVG/OB in 0.62–0.78 → limit entry.

Reuses zone math from nds_fib._zone_bounds. Differences vs prior losing NDS Fib 0.62–0.78:
  - requires BOS (close beyond prior swing) to define the impulse leg
  - requires FVG (or OB) *inside* the OTE zone (not just price in zone + engulf)
  - limit at FVG edge/mid/0.62 (not market engulf)
  - SL: beyond 0.78+buf OR beyond 1.0; TP at 0.0 or fixed RR2/3
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before
from strategies.nds_fib import _zone_bounds


def _ob_in_zone(o, h, l, c, i_start, i_end, side, z_lo, z_hi):
    """Last opposing candle (OB proxy) whose body overlaps zone."""
    for k in range(i_end, i_start, -1):
        if side == "long" and c[k] < o[k]:  # bearish OB in bullish retrace
            blo, bhi = c[k], o[k]
            if blo <= z_hi and bhi >= z_lo:
                return float(blo), float(bhi), k
        if side == "short" and c[k] > o[k]:
            blo, bhi = o[k], c[k]
            if blo <= z_hi and bhi >= z_lo:
                return float(blo), float(bhi), k
    return None


def generate_fib_ote_fvg(
    m1: pd.DataFrame,
    entry_tf: str = "M5",
    structure_tf: str = "M15",
    zone_obj: str = "fvg",       # fvg | ob
    entry_at: str = "mid",       # mid | edge | fib062
    sl_mode: str = "beyond78",   # beyond78 | beyond10
    tp_mode: str = "fib0",       # fib0 | rr2 | rr3
    swing_lr: int = 2,
    atr_buf: float = 0.1,
) -> List[Order]:
    bar_m = {"M1": 1, "M5": 5, "M15": 15}[entry_tf]
    st_m = {"M5": 5, "M15": 15, "H1": 60}[structure_tf]
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, f"{bar_m}min")
    st = resample_ohlc(m1, f"{st_m}min") if structure_tf != entry_tf else df

    # Structure swings on structure TF
    sh, sl_ = st["high"].values, st["low"].values
    sc, so = st["close"].values, st["open"].values
    st_times = st.index
    st_atr = atr_prior(st, 14).values
    shi, sli = swing_highs_lows(sh, sl_, swing_lr, swing_lr)

    # Entry TF arrays
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    a = atr_prior(df, 14).values
    n = len(df)

    variant = f"fibote_{structure_tf}_{entry_tf}_{zone_obj}_{entry_at}_{sl_mode}_{tp_mode}"
    orders: List[Order] = []
    used = set()

    # Map entry bars to structure index
    st_pos = st_times.searchsorted(times, side="right") - 1

    for si in range(20, len(st) - 1):
        atr_s = st_atr[si]
        if np.isnan(atr_s) or atr_s <= 0:
            continue
        # BOS long: close above last swing high
        side = None
        leg_start = leg_end = None  # price: for long, start=swing low, end=swing high (BOS)
        sw_h = last_swing_before(shi, si)
        sw_l = last_swing_before(sli, si)
        if sw_h is not None and sc[si] > sh[sw_h] and sc[si] > so[si]:
            # impulse low = last swing low before BOS
            if sw_l is not None and sw_l < sw_h:
                side = "long"
                leg_start = float(sl_[sw_l])  # Fib 1.0
                leg_end = float(sh[sw_h])     # Fib 0.0 (or BOS high)
                leg_end = max(leg_end, float(sh[si]))
        if side is None and sw_l is not None and sc[si] < sl_[sw_l] and sc[si] < so[si]:
            if sw_h is not None and sw_h < sw_l:
                side = "short"
                leg_start = float(sh[sw_h])  # Fib 1.0
                leg_end = float(sl_[sw_l])
                leg_end = min(leg_end, float(sl_[si]))
        if side is None:
            continue
        move = abs(leg_end - leg_start)
        if move < 1.2 * atr_s:
            continue

        # Fib: 1.0 at leg_start, 0.0 at leg_end
        if side == "long":
            # prices: 1.0 = low (start), 0.0 = high (end)
            swing_low, swing_high = leg_start, leg_end
            z_lo, z_hi = _zone_bounds("long", swing_high, swing_low, 0.62, 0.78)
            p78 = swing_high - 0.78 * move
            p62 = swing_high - 0.62 * move
            p10 = swing_low  # 1.0
            p00 = swing_high  # 0.0
        else:
            swing_low, swing_high = leg_end, leg_start
            z_lo, z_hi = _zone_bounds("short", swing_high, swing_low, 0.62, 0.78)
            p78 = swing_low + 0.78 * move
            p62 = swing_low + 0.62 * move
            p10 = swing_high
            p00 = swing_low

        # Search entry TF after structure bar end for FVG/OB in zone
        arm0 = bar_end(st_times[si], st_m)
        i0 = times.searchsorted(arm0, side="left")
        i1 = times.searchsorted(arm0 + pd.Timedelta(hours=6), side="left")
        if i0 >= n - 2:
            continue

        for i in range(max(i0, 10), min(i1, n - 1)):
            if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
                continue
            atr_v = a[i]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            key = (st_times[si], side)
            if key in used:
                break

            if zone_obj == "fvg":
                fvgs = find_fvgs(h, l, a, max(i - 10, 0), i, "bull" if side == "long" else "bear", 0.05)
                # FVG overlapping OTE zone
                hit = None
                for glo, ghi, fi in fvgs:
                    if glo <= z_hi and ghi >= z_lo:
                        hit = (glo, ghi)
                if hit is None:
                    continue
                glo, ghi = hit
            else:
                ob = _ob_in_zone(o, h, l, c, max(i - 15, 0), i, side, z_lo, z_hi)
                if ob is None:
                    continue
                glo, ghi, _ = ob

            # entry price
            if entry_at == "mid":
                px = 0.5 * (glo + ghi)
            elif entry_at == "edge":
                px = ghi if side == "long" else glo  # near premium/discount edge of gap
            else:  # fib062
                px = p62
            # must be in zone
            if not (z_lo - 0.05 <= px <= z_hi + 0.05):
                continue

            buf = max(atr_buf * atr_v, 0.12)
            if sl_mode == "beyond78":
                sl = (p78 - buf) if side == "long" else (p78 + buf)
            else:
                sl = (p10 - buf) if side == "long" else (p10 + buf)
            if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                continue
            risk = abs(px - sl)
            if risk < 0.25:
                continue

            if tp_mode == "fib0":
                tp = p00
                if abs(tp - px) / risk < 1.0:
                    continue
            elif tp_mode == "rr2":
                tp = px + 2 * risk if side == "long" else px - 2 * risk
            else:
                tp = px + 3 * risk if side == "long" else px - 3 * risk

            arm = bar_end(times[i], bar_m)
            orders.append(Order(
                arm_time=arm, side=side, kind="limit", price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="FibOTEFVG", variant=variant,
                meta={"z": (z_lo, z_hi), "leg": (leg_start, leg_end)},
                expire_minutes=120, max_hold_minutes=480,
            ))
            used.add(key)
            break

    return dedupe_orders(orders, 40)


def generate_fib_ote_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    """Focused grid vs prior NDS Fib loss: BOS+FVG/OB in OTE, limit entry, SL/TP variants."""
    pools = {}
    grid = [
        # structure, entry, zone_obj, entry_at, sl_mode, tp_mode
        ("M15", "M5", "fvg", "mid", "beyond78", "fib0"),
        ("M15", "M5", "fvg", "mid", "beyond78", "rr2"),
        ("M15", "M5", "fvg", "mid", "beyond78", "rr3"),
        ("M15", "M5", "fvg", "mid", "beyond10", "fib0"),
        ("M15", "M5", "fvg", "mid", "beyond10", "rr2"),
        ("M15", "M5", "fvg", "edge", "beyond78", "fib0"),
        ("M15", "M5", "fvg", "edge", "beyond10", "fib0"),
        ("M15", "M5", "fvg", "fib062", "beyond78", "fib0"),
        ("M15", "M5", "fvg", "fib062", "beyond10", "rr2"),
        ("M15", "M5", "ob", "mid", "beyond78", "fib0"),
        ("M15", "M5", "ob", "mid", "beyond10", "rr2"),
        ("M15", "M5", "ob", "edge", "beyond78", "fib0"),
        ("M15", "M15", "fvg", "mid", "beyond78", "fib0"),
        ("M15", "M15", "fvg", "mid", "beyond10", "rr2"),
        ("M15", "M15", "fvg", "edge", "beyond78", "fib0"),
        ("H1", "M5", "fvg", "mid", "beyond78", "fib0"),
        ("H1", "M5", "fvg", "mid", "beyond10", "rr2"),
        ("H1", "M5", "fvg", "edge", "beyond78", "fib0"),
        ("H1", "M5", "ob", "mid", "beyond78", "fib0"),
        ("H1", "M15", "fvg", "mid", "beyond78", "fib0"),
        ("H1", "M15", "fvg", "mid", "beyond10", "rr3"),
    ]
    for stf, etf, zobj, ent, slm, tp in grid:
        print(f" fibote {stf} {etf} {zobj} {ent} {slm} {tp}", flush=True)
        oo = generate_fib_ote_fvg(m1, etf, stf, zobj, ent, slm, tp)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  n={len(oo)}", flush=True)
    return pools
