"""London/NY liquidity sweep of Asian or previous-day HL → displacement → MSS → FVG entry."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import apply_dxy_gate, dedupe_orders
from strategies.ict_helpers import (
    find_fvgs, swing_highs_lows, last_swing_before, is_displacement,
    asian_ranges, prev_day_hl, opposing_liquidity,
)


def generate_liq_sweep_mss(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    level: str = "asian",          # asian | prev_day | both
    session: str = "both",         # london | ny | both
    entry_mode: str = "limit_mid", # limit_mid | market
    tp_mode: str = "rr2",          # rr1.5 | rr2 | liq
    disp_atr: float = 1.0,
    sl_mode: str = "atr_buf",        # atr_buf | sweep
) -> List[Order]:
    m5 = resample_ohlc(m1, "5min")
    a = atr_prior(m5, 14).values
    o, h, l, c = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    n = len(m5)
    shi, sli = swing_highs_lows(h, l, 2, 2)
    asian = asian_ranges(m1)
    pdhl = prev_day_hl(m1)
    variant = f"ls_{level}_{session}_{entry_mode}_{tp_mode}_d{disp_atr}_sl{sl_mode}"
    orders: List[Order] = []
    used = set()  # (day, side)

    def in_sess(ts):
        hr = ts.hour  # UTC
        if session == "london":
            return 7 <= hr < 12
        if session == "ny":
            return 12 <= hr < 17
        return (7 <= hr < 12) or (12 <= hr < 17)

    for i in range(10, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        if not in_sess(ts):
            continue
        day = ts.normalize()
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        levels_hi, levels_lo = [], []
        if level in ("asian", "both"):
            for k, (ah, al, _) in asian.items():
                if k.date() == day.date():
                    levels_hi.append(ah); levels_lo.append(al)
        if level in ("prev_day", "both"):
            if day in pdhl:
                levels_hi.append(pdhl[day][0]); levels_lo.append(pdhl[day][1])
        if not levels_hi or not levels_lo:
            continue
        liq_hi, liq_lo = max(levels_hi), min(levels_lo)

        # Detect sweep on this bar or recent 3 bars in session
        swept_hi = swept_lo = False
        ext_hi = ext_lo = None
        for j in range(max(i - 3, 0), i + 1):
            if not in_sess(times[j]):
                continue
            if h[j] > liq_hi:
                swept_hi = True
                ext_hi = h[j] if ext_hi is None else max(ext_hi, h[j])
            if l[j] < liq_lo:
                swept_lo = True
                ext_lo = l[j] if ext_lo is None else min(ext_lo, l[j])

        setups = []
        # MSS + displacement on bar i after sweep
        if swept_hi and (day, "short") not in used:
            sw = last_swing_before(sli, i)
            if sw is not None and c[i] < l[sw] and is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] < o[i]:
                setups.append(("short", ext_hi, "bear"))
        if swept_lo and (day, "long") not in used:
            sw = last_swing_before(shi, i)
            if sw is not None and c[i] > h[sw] and is_displacement(o[i], c[i], atr_v, disp_atr) and c[i] > o[i]:
                setups.append(("long", ext_lo, "bull"))

        for side, sweep_ext, fvg_dir in setups:
            fvgs = find_fvgs(h, l, a, max(i - 6, 0), i, fvg_dir, min_atr=0.08)
            if not fvgs:
                continue
            gap_lo, gap_hi, form_i = fvgs[-1]
            mid = 0.5 * (gap_lo + gap_hi)
            if entry_mode == "limit_mid":
                kind, px = "limit", mid
            else:
                kind, px = "market", float(c[i])
            buf = max(0.25 * atr_v, 0.15)
            if sl_mode == "atr_buf":
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
                tp = opposing_liquidity(side, liq_hi, liq_lo, liq_hi, liq_lo, px)
                if side == "long" and tp <= px + 0.9 * risk:
                    tp = px + 2 * risk
                if side == "short" and tp >= px - 0.9 * risk:
                    tp = px - 2 * risk

            arm = bar_end(times[i], 5)
            orders.append(Order(
                arm_time=arm, side=side, kind=kind, price=px, sl=sl, tp=tp,
                strategy="LiqSweepMSS", variant=variant,
                meta={"signal_bar": times[i], "day": str(day.date()), "level": level},
                expire_minutes=60 if kind == "limit" else 20,
                max_hold_minutes=240,
            ))
            used.add((day, side))

    orders = dedupe_orders(orders, 40)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_liq_sweep_ifvg(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    level: str = "asian",
    session: str = "ny",
    tp_mode: str = "rr2",          # rr2 | swing
    disp_atr: float = 1.0,
    atr_buf: float = 0.15,
) -> List[Order]:
    """iFVG entry on LiqSweep+MSS path (trendline-break skipped — subjective).

    After sweep: look for an *opposite-direction* FVG that later gets closed through by a body
    (inversion); enter limit on retest of that inverted FVG; SL beyond sweep extreme; TP prior
    opposite swing or RR2.
    """
    from typing import Dict
    m5 = resample_ohlc(m1, "5min")
    a = atr_prior(m5, 14).values
    o, h, l, c = m5["open"].values, m5["high"].values, m5["low"].values, m5["close"].values
    times = m5.index
    n = len(m5)
    shi, sli = swing_highs_lows(h, l, 2, 2)
    asian = asian_ranges(m1)
    pdhl = prev_day_hl(m1)
    variant = f"ls_ifvg_{level}_{session}_{tp_mode}_d{disp_atr}"
    orders: List[Order] = []
    used = set()

    def in_sess(ts):
        hr = ts.hour
        if session == "london":
            return 7 <= hr < 12
        if session == "ny":
            return 12 <= hr < 17
        return (7 <= hr < 12) or (12 <= hr < 17)

    for i in range(15, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        if not in_sess(ts):
            continue
        day = ts.normalize()
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        levels_hi, levels_lo = [], []
        if level in ("asian", "both"):
            for k, (ah, al, _) in asian.items():
                if k.date() == day.date():
                    levels_hi.append(ah); levels_lo.append(al)
        if level in ("prev_day", "both"):
            if day in pdhl:
                levels_hi.append(pdhl[day][0]); levels_lo.append(pdhl[day][1])
        if not levels_hi or not levels_lo:
            continue
        liq_hi, liq_lo = max(levels_hi), min(levels_lo)

        # find recent sweep in last ~8 M5 bars
        swept_hi = swept_lo = False
        ext_hi = ext_lo = None
        sweep_j = None
        for j in range(max(i - 16, 0), i + 1):
            if not in_sess(times[j]):
                continue
            if h[j] > liq_hi:
                swept_hi = True
                ext_hi = h[j] if ext_hi is None else max(ext_hi, h[j])
                sweep_j = j if sweep_j is None else max(sweep_j, j)
            if l[j] < liq_lo:
                swept_lo = True
                ext_lo = l[j] if ext_lo is None else min(ext_lo, l[j])
                sweep_j = j if sweep_j is None else max(sweep_j, j)
        if sweep_j is None:
            continue

        setups = []
        # short: swept high → look for bullish FVG formed after sweep that then gets closed below (inversion to bear)
        if swept_hi and (day, "short") not in used:
            # opposite-dir FVG after sweep = bullish FVG (manipulation wick side)
            opp = find_fvgs(h, l, a, sweep_j, i, "bull", min_atr=0.05)
            for glo, ghi, fi in opp:
                # inversion: body close through below gap_lo after formation
                for k in range(fi + 1, i + 1):
                    if c[k] < glo:
                        setups.append(("short", ext_hi, glo, ghi, k))
                        break
        if swept_lo and (day, "long") not in used:
            opp = find_fvgs(h, l, a, sweep_j, i, "bear", min_atr=0.05)
            for glo, ghi, fi in opp:
                for k in range(fi + 1, i + 1):
                    if c[k] > ghi:
                        setups.append(("long", ext_lo, glo, ghi, k))
                        break

        for side, sweep_ext, glo, ghi, inv_i in setups:
            # arm on first retest bar at/after inversion (incl. inversion bar)
            if i < inv_i or i - inv_i > 10:
                continue
            if not (l[i] <= ghi and h[i] >= glo):
                continue
            px = 0.5 * (glo + ghi)
            buf = max(atr_buf * atr_v, 0.12)
            if side == "short":
                sl = sweep_ext + buf
                if sl <= px:
                    continue
                risk = sl - px
            else:
                sl = sweep_ext - buf
                if sl >= px:
                    continue
                risk = px - sl
            if risk < 0.2:
                continue
            if tp_mode == "rr2":
                tp = px - 2 * risk if side == "short" else px + 2 * risk
            else:
                # prior opposite swing
                if side == "short":
                    sw = last_swing_before(sli, i)
                    tp = float(l[sw]) if sw is not None else px - 2 * risk
                    if tp >= px - 1.2 * risk:
                        tp = px - 2 * risk
                else:
                    sw = last_swing_before(shi, i)
                    tp = float(h[sw]) if sw is not None else px + 2 * risk
                    if tp <= px + 1.2 * risk:
                        tp = px + 2 * risk
            arm = bar_end(times[i], 5)
            orders.append(Order(
                arm_time=arm, side=side, kind="limit", price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="LiqSweepIFVG", variant=variant,
                meta={"note": "trendline-break skipped (subjective)", "inv_i": str(times[i])},
                expire_minutes=90, max_hold_minutes=240,
            ))
            used.add((day, side))

    return apply_dxy_gate(dedupe_orders(orders, 40), dxy, use_dxy)


def generate_liq_ifvg_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    from typing import Dict as _D
    pools: _D[str, List[Order]] = {}
    for level in ("asian", "prev_day", "both"):
        for sess in ("ny", "london", "both"):
            for tp in ("rr2", "swing"):
                print(f" ls_ifvg {level} {sess} {tp}", flush=True)
                oo = generate_liq_sweep_ifvg(m1, level=level, session=sess, tp_mode=tp)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)}", flush=True)
    return pools
