"""ICT Silver Bullet — NY 10–11 AM America/New_York on M5.
Sweep → Displacement (+ soft MSS reclaim) → FVG retrace entry. Closed bars only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import apply_dxy_gate, dedupe_orders
from strategies.ict_helpers import (
    find_fvgs, swing_highs_lows, last_swing_before, is_displacement,
    asian_ranges, prev_day_hl, in_silver_bullet, opposing_liquidity,
)


def generate_silver_bullet(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    entry_mode: str = "limit_mid",   # limit_mid | limit_edge | market
    tp_mode: str = "rr2",            # rr1.5 | rr2 | rr3 | liq
    disp_atr: float = 0.8,
    swing_lr: int = 2,
    mss_mode: str = "reclaim",       # reclaim | swing | either
    sl_mode: str = "atr_buf",        # atr_buf | sweep
) -> List[Order]:
    m5 = resample_ohlc(m1, "5min")
    a = atr_prior(m5, 14).values
    o, h, l, c = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    n = len(m5)
    shi, sli = swing_highs_lows(h, l, swing_lr, swing_lr)
    asian = asian_ranges(m1)
    pdhl = prev_day_hl(m1)
    variant = f"sb_{entry_mode}_{tp_mode}_d{disp_atr}_sw{swing_lr}_{mss_mode}_sl{sl_mode}"
    orders: List[Order] = []
    used_days = set()

    # Precompute window bar indices per NY date
    for i in range(swing_lr + 8, n - 1):
        ts = times[i]
        dow = int(getattr(ts, "day_of_week", ts.dayofweek))
        if dow >= 5:
            continue
        if not in_silver_bullet(ts):
            continue
        day = ts.normalize()
        if day in used_days:
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        ah = al = None
        for k, (xh, xl, _) in asian.items():
            if k.date() == day.date():
                ah, al = xh, xl
                break
        ph, pl = pdhl.get(day, (None, None))
        ls = last_swing_before(shi, i)
        lsl = last_swing_before(sli, i)
        hi_cands = [x for x in (ah, ph, float(h[ls]) if ls is not None else None) if x is not None]
        lo_cands = [x for x in (al, pl, float(l[lsl]) if lsl is not None else None) if x is not None]
        if not hi_cands or not lo_cands:
            continue
        liq_hi, liq_lo = max(hi_cands), min(lo_cands)

        # SB window bars for this day (+ 30m lookback before 10 NY for sweep)
        win = []
        lookback = []
        for j in range(max(i - 24, 0), i + 1):
            if times[j].normalize() != day:
                continue
            if in_silver_bullet(times[j]):
                win.append(j)
            else:
                # 09:30–10:00 NY lookback for sweep
                tny = times[j].tz_convert("America/New_York")
                if tny.hour == 9 and tny.minute >= 30:
                    lookback.append(j)
        if not win:
            continue
        scan = lookback + win

        swept_hi = swept_lo = False
        ext_hi = ext_lo = None
        for j in scan:
            if h[j] > liq_hi:
                swept_hi = True
                ext_hi = h[j] if ext_hi is None else max(ext_hi, h[j])
            if l[j] < liq_lo:
                swept_lo = True
                ext_lo = l[j] if ext_lo is None else min(ext_lo, l[j])
        if not (swept_hi or swept_lo):
            continue

        setups = []
        # Evaluate MSS+disp on current bar i (must be in SB window)
        if swept_hi:
            mss_ok = False
            if mss_mode in ("reclaim", "either"):
                # close back below swept liquidity (failed auction)
                if c[i] < liq_hi:
                    mss_ok = True
            if mss_mode in ("swing", "either"):
                sw = last_swing_before(sli, i)
                if sw is not None and c[i] < l[sw]:
                    mss_ok = True
            if mss_ok and is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] < o[i]:
                setups.append(("short", ext_hi, "bear"))
            elif mss_ok and abs(c[i] - o[i]) >= 0.5 * atr_v and c[i] < o[i]:
                # slightly softer disp if reclaim clear
                setups.append(("short", ext_hi, "bear"))

        if swept_lo:
            mss_ok = False
            if mss_mode in ("reclaim", "either"):
                if c[i] > liq_lo:
                    mss_ok = True
            if mss_mode in ("swing", "either"):
                sw = last_swing_before(shi, i)
                if sw is not None and c[i] > h[sw]:
                    mss_ok = True
            if mss_ok and is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] > o[i]:
                setups.append(("long", ext_lo, "bull"))
            elif mss_ok and abs(c[i] - o[i]) >= 0.5 * atr_v and c[i] > o[i]:
                setups.append(("long", ext_lo, "bull"))

        for side, sweep_ext, fvg_dir in setups:
            fvgs = find_fvgs(h, l, a, max(win[0] - 3, 0), i, fvg_dir, min_atr=0.05)
            if not fvgs:
                continue
            # prefer FVG whose form is in/near window
            gap_lo, gap_hi, form_i = fvgs[-1]
            mid = 0.5 * (gap_lo + gap_hi)
            if entry_mode == "limit_mid":
                kind, px = "limit", mid
            elif entry_mode == "limit_edge":
                kind, px = "limit", (gap_hi if side == "long" else gap_lo)
            else:
                kind, px = "market", float(c[i])

            buf = max(0.25 * atr_v, 0.15)
            if sl_mode == "atr_buf":
                # SL beyond FVG invalidation (fits $1k caps); sweep mode = full extreme
                sl = (gap_hi + buf) if side == "short" else (gap_lo - buf)
            else:
                sl = sweep_ext + (0.05 if side == "short" else -0.05)
            risk = abs(px - sl)
            if risk < 0.15:
                continue
            if (side == "long" and sl >= px) or (side == "short" and sl <= px):
                continue

            if tp_mode.startswith("rr"):
                rr = float(tp_mode.replace("rr", ""))
                tp = px + rr * risk if side == "long" else px - rr * risk
            else:
                ah2 = ah if ah is not None else (ph if ph is not None else px + 2 * risk)
                al2 = al if al is not None else (pl if pl is not None else px - 2 * risk)
                ph2 = ph if ph is not None else ah2
                pl2 = pl if pl is not None else al2
                tp = opposing_liquidity(side, ah2, al2, ph2, pl2, px)
                if side == "long" and tp <= px + 0.9 * risk:
                    tp = px + 2 * risk
                if side == "short" and tp >= px - 0.9 * risk:
                    tp = px - 2 * risk

            arm = bar_end(times[i], 5)
            orders.append(Order(
                arm_time=arm, side=side, kind=kind, price=float(px), sl=float(sl), tp=float(tp),
                strategy="SilverBullet", variant=variant,
                meta={"signal_bar": times[i], "day": str(day.date()), "sweep": float(sweep_ext),
                      "fvg": (float(gap_lo), float(gap_hi))},
                expire_minutes=45 if kind == "limit" else 15,
                max_hold_minutes=180,
            ))
            used_days.add(day)
            break

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)
