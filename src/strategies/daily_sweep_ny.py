"""daily_sweep_ny (hosein_.bashar): daily bias → NY-open counter-trend sweep → M5 FVG pullback.

Daily bias from closed daily swing structure (HH/HL long, LH/LL short); fallbacks: prior-day
close vs open, or vs EMA. At NY open (13:30 / 14:30 UTC windows), wait for H1/M15 fakeout that
sweeps Asia or London extreme against bias; then M5 trend-direction FVG; limit mid/edge into FVG;
SL beyond fakeout+buf; TP = day high/low | prior-day extreme | RR2/3. Skip RR<1.5.
Heavy overlap expected with SessionBox→MSS→FVG and h4open_fvg — report via overlap helper.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, ema
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, asian_ranges
from strategies.h4open_fvg import overlap_with_session_box


def _london_ranges(m1: pd.DataFrame) -> dict:
    """London cash approx 07:00–12:00 UTC high/low keyed by day normalize."""
    ranges = {}
    for d in m1.index.normalize().unique():
        if int(getattr(d, "day_of_week", d.dayofweek)) >= 5:
            continue
        seg = m1[(m1.index >= d + pd.Timedelta(hours=7)) & (m1.index < d + pd.Timedelta(hours=12))]
        if len(seg) < 30:
            continue
        ranges[pd.Timestamp(d)] = (float(seg["high"].max()), float(seg["low"].min()))
    return ranges


def _daily_bias_swing(daily: pd.DataFrame, fractal: int = 2) -> Dict[pd.Timestamp, str]:
    """Bias available at the OPEN of day i from swings confirmed on closed days only.
    Key = day start (normalize); value = long|short from structure of prior closed bars.
    """
    h, l = daily["high"].values, daily["low"].values
    times = daily.index
    shi, sli = swing_highs_lows(h, l, fractal, fractal)
    out = {}
    for i in range(len(daily)):
        # only use swings fully confirmed before day i (conf = sw+fractal < i)
        ph = [s for s in shi if s + fractal < i]
        pl = [s for s in sli if s + fractal < i]
        if len(ph) < 2 or len(pl) < 2:
            continue
        bias = None
        if h[ph[-1]] > h[ph[-2]] and l[pl[-1]] > l[pl[-2]]:
            bias = "long"
        elif h[ph[-1]] < h[ph[-2]] and l[pl[-1]] < l[pl[-2]]:
            bias = "short"
        if bias:
            out[pd.Timestamp(times[i].normalize())] = bias
    return out


def _daily_bias_fallback(daily: pd.DataFrame, mode: str = "cvo") -> Dict[pd.Timestamp, str]:
    """Prior closed day: close>open (cvo) or close>EMA20 (ema). Key = next day."""
    out = {}
    c, o = daily["close"].values, daily["open"].values
    e = ema(daily["close"], 20).values if mode == "ema" else None
    times = daily.index
    for i in range(1, len(daily)):
        pi = i - 1
        if mode == "cvo":
            if c[pi] > o[pi]:
                bias = "long"
            elif c[pi] < o[pi]:
                bias = "short"
            else:
                continue
        else:
            if np.isnan(e[pi]):
                continue
            if c[pi] > e[pi]:
                bias = "long"
            elif c[pi] < e[pi]:
                bias = "short"
            else:
                continue
        out[pd.Timestamp(times[i].normalize())] = bias
    return out


def generate_daily_sweep_ny(
    m1: pd.DataFrame,
    bias_mode: str = "swing2",      # swing2|swing3|cvo|ema
    ny_start_utc: str = "13:30",    # 13:30 | 14:30
    window_h: float = 2.0,
    sweep_tf: str = "M15",          # H1 | M15
    entry_at: str = "mid",          # mid | edge
    tp_mode: str = "day_ext",       # day_ext | prior_ext | rr2 | rr3
    atr_buf: float = 0.15,
    session_ext: str = "asia",      # asia | london | either
) -> List[Order]:
    hh, mm = map(int, ny_start_utc.split(":"))
    bar_sw = 60 if sweep_tf == "H1" else 15
    sw = resample_ohlc(m1, f"{bar_sw}min")
    m5 = resample_ohlc(m1, "5min")
    daily = resample_ohlc(m1, "1D")

    if bias_mode.startswith("swing"):
        fr = int(bias_mode[-1])
        bias_map = _daily_bias_swing(daily, fr)
    elif bias_mode == "cvo":
        bias_map = _daily_bias_fallback(daily, "cvo")
    else:
        bias_map = _daily_bias_fallback(daily, "ema")

    asian = asian_ranges(m1)
    london = _london_ranges(m1)
    # prior day HL keyed by next day
    prior_hl = {}
    for d in m1.index.normalize().unique():
        seg = m1[(m1.index >= d) & (m1.index < d + pd.Timedelta(days=1))]
        if len(seg) < 60:
            continue
        prior_hl[pd.Timestamp(d) + pd.Timedelta(days=1)] = (
            float(seg["high"].max()), float(seg["low"].min())
        )

    so, sh, slo, sc = sw["open"].values, sw["high"].values, sw["low"].values, sw["close"].values
    st = sw.index
    sa = atr_prior(sw, 14).values
    sshi, ssli = swing_highs_lows(sh, slo, 2, 2)

    o5, h5, l5, c5 = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    t5 = m5.index
    a5 = atr_prior(m5, 14).values

    variant = f"dailyny_{bias_mode}_ny{ny_start_utc.replace(':','')}_w{window_h:g}_{sweep_tf}_{session_ext}_{entry_at}_{tp_mode}"
    orders: List[Order] = []
    used_days = set()

    # iterate weekdays
    days = [d for d in m1.index.normalize().unique()
            if int(getattr(d, "day_of_week", d.dayofweek)) < 5]
    for d in days:
        d = pd.Timestamp(d)
        bias = bias_map.get(d)
        if bias is None:
            continue
        win0 = d + pd.Timedelta(hours=hh, minutes=mm)
        win1 = win0 + pd.Timedelta(hours=window_h)
        # session extreme for fakeout
        ah, al = asian.get(d, (None, None, None))[:2] if d in asian else (None, None)
        lh, ll = london.get(d, (None, None))
        if session_ext == "asia":
            if ah is None:
                continue
            ext_h, ext_l = ah, al
        elif session_ext == "london":
            if lh is None:
                continue
            ext_h, ext_l = lh, ll
        else:
            cands_h = [x for x in (ah, lh) if x is not None]
            cands_l = [x for x in (al, ll) if x is not None]
            if not cands_h or not cands_l:
                continue
            ext_h, ext_l = max(cands_h), min(cands_l)

        # find counter-trend sweep on sweep_tf inside window
        i0 = st.searchsorted(win0, side="left")
        i1 = st.searchsorted(win1, side="left")
        fakeout_i = None
        fake_ext = None
        for i in range(max(i0, 5), min(i1, len(st) - 1)):
            atr_v = sa[i]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            # long bias: counter-trend fakeout = sweep below ext_l then close back above
            if bias == "long":
                if float(slo[i]) < ext_l and float(sc[i]) > ext_l and float(sc[i]) > float(so[i]):
                    # optional: also require local swing low swept
                    fakeout_i = i
                    fake_ext = float(min(slo[i], ext_l))
                    break
            else:
                if float(sh[i]) > ext_h and float(sc[i]) < ext_h and float(sc[i]) < float(so[i]):
                    fakeout_i = i
                    fake_ext = float(max(sh[i], ext_h))
                    break
        if fakeout_i is None:
            continue

        # after fakeout bar end, look for M5 trend-direction FVG within remaining window + 90m
        arm0 = bar_end(st[fakeout_i], bar_sw)
        j0 = t5.searchsorted(arm0, side="left")
        j1 = t5.searchsorted(min(win1 + pd.Timedelta(minutes=90), d + pd.Timedelta(hours=20)), side="left")
        if j0 >= len(t5) - 3:
            continue

        for j in range(max(j0, 10), min(j1, len(t5) - 1)):
            atr_v = a5[j]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            fvgs = find_fvgs(h5, l5, a5, max(j - 8, 0), j, "bull" if bias == "long" else "bear", 0.05)
            if not fvgs:
                continue
            # take most recent FVG
            glo, ghi, fi = fvgs[-1]
            if entry_at == "mid":
                px = 0.5 * (glo + ghi)
            else:
                px = ghi if bias == "long" else glo
            buf = max(atr_buf * atr_v, 0.15)
            if bias == "long":
                sl = fake_ext - buf
                if sl >= px:
                    continue
                risk = px - sl
            else:
                sl = fake_ext + buf
                if sl <= px:
                    continue
                risk = sl - px
            if risk < 0.25:
                continue

            # running day extreme so far (no lookahead: use data up to arm)
            day_seg = m1[(m1.index >= d) & (m1.index <= t5[j])]
            if len(day_seg) < 10:
                continue
            day_hi = float(day_seg["high"].max())
            day_lo = float(day_seg["low"].min())
            phl = prior_hl.get(d)

            if tp_mode == "day_ext":
                # TP = current-day high (long) / low (short) — at signal time this may be near entry;
                # use max(day_hi, px+1.5*risk) style: require day extreme still offers RR≥1.5 else skip
                tp = day_hi if bias == "long" else day_lo
            elif tp_mode == "prior_ext":
                if phl is None:
                    continue
                tp = phl[0] if bias == "long" else phl[1]
            elif tp_mode == "rr2":
                tp = px + 2 * risk if bias == "long" else px - 2 * risk
            else:
                tp = px + 3 * risk if bias == "long" else px - 3 * risk

            if bias == "long":
                if tp <= px + 1.5 * risk - 1e-9:
                    continue
            else:
                if tp >= px - 1.5 * risk + 1e-9:
                    continue
            rr = abs(tp - px) / risk
            if rr < 1.5:
                continue

            if d in used_days:
                break
            arm = bar_end(t5[j], 5)
            orders.append(Order(
                arm_time=arm, side=bias, kind="limit", price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="DailySweepNY", variant=variant,
                meta={"fake_ext": fake_ext, "bias": bias, "rr": rr, "session_ext": session_ext},
                expire_minutes=90, max_hold_minutes=360,
            ))
            used_days.add(d)
            break

    return dedupe_orders(orders, 60)


def generate_daily_sweep_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    grid = [
        # bias, ny, window, sweep_tf, session, entry, tp
        ("swing2", "13:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("swing2", "13:30", 2.0, "M15", "asia", "mid", "rr3"),
        ("swing2", "13:30", 2.0, "M15", "asia", "mid", "day_ext"),
        ("swing2", "13:30", 2.0, "M15", "asia", "mid", "prior_ext"),
        ("swing2", "13:30", 2.0, "M15", "asia", "edge", "rr2"),
        ("swing2", "13:30", 2.0, "M15", "london", "mid", "rr2"),
        ("swing2", "13:30", 2.0, "M15", "either", "mid", "rr2"),
        ("swing2", "13:30", 1.0, "M15", "asia", "mid", "rr2"),
        ("swing2", "14:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("swing2", "14:30", 2.0, "M15", "london", "mid", "rr2"),
        ("swing2", "13:30", 2.0, "H1", "asia", "mid", "rr2"),
        ("swing2", "13:30", 2.0, "H1", "either", "mid", "rr2"),
        ("swing3", "13:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("swing3", "13:30", 2.0, "M15", "either", "mid", "rr3"),
        ("cvo", "13:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("cvo", "13:30", 2.0, "M15", "either", "mid", "rr2"),
        ("ema", "13:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("ema", "14:30", 2.0, "M15", "asia", "mid", "rr2"),
        ("swing2", "13:30", 2.0, "M15", "asia", "edge", "prior_ext"),
        ("swing2", "13:30", 2.0, "M15", "london", "edge", "rr3"),
    ]
    for bias, ny, wh, stf, sess, ent, tp in grid:
        print(f" dailyny {bias} ny{ny} w{wh} {stf} {sess} {ent} {tp}", flush=True)
        oo = generate_daily_sweep_ny(m1, bias, ny, wh, stf, ent, tp, session_ext=sess)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  n={len(oo)}", flush=True)
        else:
            print("  n=0", flush=True)
    return pools


def overlap_stats(m1: pd.DataFrame, ny_orders: List[Order]) -> dict:
    from strategies.session_box_mss import generate_session_box_mss
    from strategies.h4open_fvg import generate_h4open_fvg
    box = generate_session_box_mss(
        m1, entry_tf="M5", tp_mode="rr1.5", require_disp=True, disp_atr=0.8, entry_mode="limit_mid"
    )
    h4 = generate_h4open_fvg(m1, entry_tf="M5", rr=2.0, bias_mode="prev_h4")
    ov_box = overlap_with_session_box(ny_orders, box, 60)
    ov_h4 = overlap_with_session_box(ny_orders, h4, 60)
    # incremental = NY signals with no box overlap
    return {
        "ny_n": len(ny_orders),
        "vs_session_box_60m": ov_box,
        "vs_h4open_60m": ov_h4,
        "incremental_vs_box": ov_box["h4_n"] - ov_box["overlap"],
        "incremental_vs_h4": ov_h4["h4_n"] - ov_h4["overlap"],
        "note": "overlap helper keys reuse h4_n for first-arg count",
    }
