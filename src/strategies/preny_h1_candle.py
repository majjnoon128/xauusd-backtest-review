"""preny_h1_candle (hosein_.bashar): last closed H1 before NY open → M5 sweep → MSS → FVG limit.

Reference = last closed H1 in window before NY (test 12:00–13:00 and 13:00–14:00 UTC =
DST-aware NY 8–9 / 9–10 ET). After that H1 closes: wait for M5 sweep of its high or low,
then MSS back inside (closed-body break of last M5 fractal), first FVG of MSS leg, limit at
FVG touch; SL beyond sweep extreme/last swing +buffer; TP = opposite edge of H1 candle;
also RR 1.5/2; skip RR<1; expire end of NY morning. Overlap vs SessionBox + daily_sweep_ny.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before
from strategies.h4open_fvg import overlap_with_session_box


def generate_preny_h1_candle(
    m1: pd.DataFrame,
    ref_window: str = "12-13",   # 12-13 | 13-14  (UTC hour of the H1 candle that must close)
    entry_at: str = "mid",       # mid | edge
    tp_mode: str = "h1_opp",     # h1_opp | rr1.5 | rr2
    atr_buf: float = 0.15,
) -> List[Order]:
    h1 = resample_ohlc(m1, "1h")
    m5 = resample_ohlc(m1, "5min")
    wh0, wh1 = map(int, ref_window.split("-"))

    o1, h1h, l1, c1 = h1["open"].values, h1["high"].values, h1["low"].values, h1["close"].values
    t1 = h1.index

    o, h, l, c = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    n = len(m5)
    a = atr_prior(m5, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)

    variant = f"preny_h1_{ref_window}_{entry_at}_{tp_mode}"
    orders: List[Order] = []
    used = set()

    # For each weekday, pick the H1 candle whose open hour is wh0 (closes at wh1)
    for di, ts_h in enumerate(t1):
        if int(getattr(ts_h, "day_of_week", ts_h.dayofweek)) >= 5:
            continue
        if ts_h.hour != wh0:
            continue
        day = ts_h.normalize()
        if day in used:
            continue
        ref_hi, ref_lo = float(h1h[di]), float(l1[di])
        ref_o, ref_c = float(o1[di]), float(c1[di])
        # H1 known at close = bar_end of this H1
        known = bar_end(ts_h, 60)
        # trade window: from H1 close until end of NY morning (~16:00 UTC)
        win1 = day + pd.Timedelta(hours=16)
        j0 = times.searchsorted(known, side="left")
        j1 = times.searchsorted(win1, side="left")
        if j0 >= n - 5:
            continue

        sweep_side = None  # long if swept low then MSS up; short if swept high then MSS down
        sweep_ext = None
        sweep_j = None
        for j in range(j0, min(j1, n - 1)):
            atr_v = a[j]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            # detect sweep
            if l[j] < ref_lo:
                sweep_side = "long_pending"
                sweep_ext = float(l[j]) if sweep_ext is None else min(sweep_ext, float(l[j]))
                sweep_j = j
            if h[j] > ref_hi:
                # if both, prefer most recent
                if sweep_side != "long_pending" or (sweep_j is not None and j > sweep_j):
                    sweep_side = "short_pending"
                    sweep_ext = float(h[j]) if sweep_side == "short_pending" else sweep_ext
                    sweep_ext = float(h[j])
                    sweep_j = j

            if sweep_j is None or j < sweep_j + 1:
                continue

            # MSS: closed-body break of last M5 fractal back inside H1 range
            side = None
            if sweep_side == "long_pending":
                sw = last_swing_before(shi, j)  # break above last swing high
                if sw is not None and c[j] > h[sw] and c[j] > o[j] and c[j] > ref_lo:
                    side = "long"
            elif sweep_side == "short_pending":
                sw = last_swing_before(sli, j)
                if sw is not None and c[j] < l[sw] and c[j] < o[j] and c[j] < ref_hi:
                    side = "short"
            if side is None:
                continue

            # first FVG of MSS leg (from sweep_j to j)
            fvgs = find_fvgs(h, l, a, sweep_j, j, "bull" if side == "long" else "bear", 0.05)
            if not fvgs:
                continue
            glo, ghi, fi = fvgs[0]  # first
            if entry_at == "mid":
                px = 0.5 * (glo + ghi)
            else:
                px = ghi if side == "long" else glo
            buf = max(atr_buf * atr_v, 0.12)
            # SL beyond sweep extreme or last swing
            if side == "long":
                swl = last_swing_before(sli, j)
                swing_sl = float(l[swl]) if swl is not None else sweep_ext
                sl = min(sweep_ext, swing_sl) - buf
                if sl >= px:
                    continue
                risk = px - sl
                h1_opp = ref_hi  # opposite edge
            else:
                swh = last_swing_before(shi, j)
                swing_sl = float(h[swh]) if swh is not None else sweep_ext
                sl = max(sweep_ext, swing_sl) + buf
                if sl <= px:
                    continue
                risk = sl - px
                h1_opp = ref_lo
            if risk < 0.2:
                continue

            if tp_mode == "h1_opp":
                tp = h1_opp
            elif tp_mode == "rr1.5":
                tp = px + 1.5 * risk if side == "long" else px - 1.5 * risk
            else:
                tp = px + 2.0 * risk if side == "long" else px - 2.0 * risk

            if side == "long" and tp <= px + 1.0 * risk - 1e-9:
                continue
            if side == "short" and tp >= px - 1.0 * risk + 1e-9:
                continue
            if abs(tp - px) / risk < 1.0:
                continue

            # expire end of NY morning from arm
            arm = bar_end(times[j], 5)
            remain = max(15, int((win1 - arm).total_seconds() / 60))
            orders.append(Order(
                arm_time=arm, side=side, kind="limit", price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="PreNYH1", variant=variant,
                meta={"ref_h1": str(ts_h), "ref_hi": ref_hi, "ref_lo": ref_lo},
                expire_minutes=min(remain, 180), max_hold_minutes=240,
            ))
            used.add(day)
            break

    return dedupe_orders(orders, 50)


def generate_preny_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for rw in ("12-13", "13-14"):
        for ent in ("mid", "edge"):
            for tp in ("h1_opp", "rr1.5", "rr2"):
                print(f" preny {rw} {ent} {tp}", flush=True)
                oo = generate_preny_h1_candle(m1, rw, ent, tp)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
                else:
                    print("  n=0", flush=True)
    return pools


def overlap_stats(m1: pd.DataFrame, oo: List[Order]) -> dict:
    from strategies.session_box_mss import generate_session_box_mss
    from strategies.daily_sweep_ny import generate_daily_sweep_ny
    box = generate_session_box_mss(
        m1, entry_tf="M5", tp_mode="rr1.5", require_disp=True, disp_atr=0.8, entry_mode="limit_mid"
    )
    ny = generate_daily_sweep_ny(
        m1, "swing2", "13:30", 2.0, "M15", "mid", "rr2", session_ext="asia"
    )
    return {
        "preny_n": len(oo),
        "vs_session_box_60m": overlap_with_session_box(oo, box, 60),
        "vs_daily_sweep_ny_60m": overlap_with_session_box(oo, ny, 60),
        "note_dst": "12:00–13:00 UTC ≈ NY 8–9 ET (EDT) / 7–8 (EST); 13:00–14:00 ≈ 9–10 ET (EDT).",
    }
