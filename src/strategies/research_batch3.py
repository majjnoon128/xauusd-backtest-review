"""Research batch-3 setups (Brooks Failed Signal-Bar Trap, Fuller Fakey,
PDH/PDL M5 reclaim Turtle Soup, Brooks Opening Reversal, ICT Breaker +sweep).

Faithful to /workspace/trading-research/batch-3.md.
- Stop entry 1 tick; expire ≈ 1 bar; SL beyond extreme; risk <= $8
- Closed-bar arm only (bar_end); no lookahead / no future swing confirmation
- Quant appendix: keep rigor (IS/OOS/WF/MC); do not loosen for frequency
"""
from __future__ import annotations
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import resample_ohlc, atr_prior, bar_end, ema
from strategies.common import apply_dxy_gate, dedupe_orders

TICK = 0.01


def _in_liquidity(ts: pd.Timestamp, start_h=7, end_h=16) -> bool:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert("UTC")
    return t.dayofweek < 5 and start_h <= t.hour < end_h


def _ny(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("America/New_York")


def _in_kz(ts: pd.Timestamp, which: str) -> bool:
    """Kill zones in NY time. london=02-05, nyam=07-10, both, any."""
    if which == "any":
        return ts.dayofweek < 5
    ny = _ny(ts)
    h = ny.hour + ny.minute / 60.0
    if which == "london":
        return 2.0 <= h < 5.0
    if which == "nyam":
        return 7.0 <= h < 10.0
    if which == "both":
        return (2.0 <= h < 5.0) or (7.0 <= h < 10.0)
    return False


def _bull_q(o, h, l, c, frac=0.5) -> bool:
    rng = h - l
    return rng > 0 and c > o and (c - l) / rng >= frac


def _bear_q(o, h, l, c, frac=0.5) -> bool:
    rng = h - l
    return rng > 0 and c < o and (h - c) / rng >= frac


def _rr(side: str, entry: float, sl: float, rr: float) -> Optional[float]:
    risk = abs(entry - sl)
    if risk < 1e-9:
        return None
    return entry + rr * risk if side == "long" else entry - rr * risk


def _stop(arm, side, entry, sl, tp, strategy, variant, meta, bar_m, hold=180):
    return Order(
        arm_time=arm, side=side, kind="stop", price=float(entry),
        sl=float(sl), tp=float(tp), strategy=strategy, variant=variant,
        meta=meta, expire_minutes=int(bar_m), max_hold_minutes=hold,
    )


def _is_inside(h, l, ph, pl, soft=True) -> bool:
    if soft:
        return h <= ph + 1e-12 and l >= pl - 1e-12
    return h < ph - 1e-12 and l > pl + 1e-12


def _prev_day_hl(m1: pd.DataFrame) -> Dict[pd.Timestamp, Tuple[float, float]]:
    """Map each calendar date -> (PDH, PDL) of the previous trading day (UTC date)."""
    daily = m1.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    out = {}
    dates = list(daily.index)
    for i in range(1, len(dates)):
        prev = dates[i - 1]
        cur = dates[i]
        out[pd.Timestamp(cur).normalize()] = (float(daily.loc[prev, "high"]), float(daily.loc[prev, "low"]))
    return out


# ========== 1) Failed Signal-Bar Trap ==========
def generate_failed_trap(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    require_quality: bool = True,
    max_sig_range: float = 8.0,
    both_sides: bool = True,  # arm both stops; first fill wins (engine)
    session: str = "liq",
) -> List[Order]:
    """After a quality signal bar, arm stops both sides. The opposing fill = trap entry.
    Faithful Brooks: if bull signal and next bar takes out the low first → short.
    We arm both at bar_end(signal); expire 1 bar. Engine fills first touch.
    Filter: only keep the OPPOSING side as the 'trap' thesis by tagging both;
    evaluation uses both arms (BOM-style). Variant with trap_only filters to
    opposing conceptually by requiring signal quality then taking both.
    """
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    orders: List[Order] = []

    for i in range(5, len(df) - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
        sig_range = h - l
        if sig_range <= 0 or sig_range > max_sig_range + 1e-9:
            continue
        is_bull = _bull_q(o, h, l, c, 0.5) if require_quality else (c > o)
        is_bear = _bear_q(o, h, l, c, 0.5) if require_quality else (c < o)
        if not is_bull and not is_bear:
            continue
        # weak mid-close filter already in quality
        arm = bar_end(ts, bar)
        v = f"trap_{tf}_rr{rr:g}" + ("_q" if require_quality else "_nq")
        # For a bull signal: primary thesis = failed → short below; also arm long (trap cancel)
        # For a bear signal: primary thesis = failed → long above
        if is_bull:
            # short trap stop
            entry_s = l - TICK
            sl_s = h + TICK
            if sl_s - entry_s <= max_sig_range + 1e-9:
                tp = _rr("short", entry_s, sl_s, rr)
                if tp is not None:
                    orders.append(_stop(arm, "short", entry_s, sl_s, tp, "TRAP", v,
                                        {"signal_bar": ts, "sig": "bull", "role": "trap"}, bar))
            if both_sides:
                entry_l = h + TICK
                sl_l = l - TICK
                if entry_l - sl_l <= max_sig_range + 1e-9:
                    tp = _rr("long", entry_l, sl_l, rr)
                    if tp is not None:
                        orders.append(_stop(arm, "long", entry_l, sl_l, tp, "TRAP", v,
                                            {"signal_bar": ts, "sig": "bull", "role": "follow"}, bar))
        elif is_bear:
            entry_l = h + TICK
            sl_l = l - TICK
            if entry_l - sl_l <= max_sig_range + 1e-9:
                tp = _rr("long", entry_l, sl_l, rr)
                if tp is not None:
                    orders.append(_stop(arm, "long", entry_l, sl_l, tp, "TRAP", v,
                                        {"signal_bar": ts, "sig": "bear", "role": "trap"}, bar))
            if both_sides:
                entry_s = l - TICK
                sl_s = h + TICK
                if sl_s - entry_s <= max_sig_range + 1e-9:
                    tp = _rr("short", entry_s, sl_s, rr)
                    if tp is not None:
                        orders.append(_stop(arm, "short", entry_s, sl_s, tp, "TRAP", v,
                                            {"signal_bar": ts, "sig": "bear", "role": "follow"}, bar))
    orders = dedupe_orders(orders, {"M1": 3, "M5": 8, "M15": 20}.get(tf, 8))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_failed_trap_traponly(
    m1, dxy=None, use_dxy=False, tf="M5", rr=1.5, require_quality=True,
    max_sig_range=8.0, session="liq",
) -> List[Order]:
    """Only arm the OPPOSING stop (pure trap thesis, no follow-through side)."""
    return generate_failed_trap(m1, dxy, use_dxy, tf, rr, require_quality,
                                max_sig_range, both_sides=False, session=session)


def generate_failed_trap_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, True, True),   # both sides
        ("M5", 2.0, True, True),
        ("M5", 1.5, True, False),  # trap-only
        ("M5", 1.5, False, True),  # no quality
        ("M1", 1.5, True, False),
    ]
    for tf, rr, q, both in specs:
        if both:
            oo = generate_failed_trap(m1, dxy, False, tf, rr, q, 8.0, True)
        else:
            oo = generate_failed_trap_traponly(m1, dxy, False, tf, rr, q, 8.0)
            # retag variant to distinguish
            for o in oo:
                o.variant = o.variant + "_traponly"
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 2) Fakey (false break of inside bar) ==========
def generate_fakey(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 2.0,
    soft: bool = True,
    eps: float = 0.50,
    max_risk: float = 8.0,
    entry_mode: str = "mother",  # mother | signal
    max_wait: int = 6,
    session: str = "liq",
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    n = len(df)
    orders: List[Order] = []

    i = 5
    while i < n - 2:
        ts = times[i]
        if ts.dayofweek >= 5 or (session == "liq" and not _in_liquidity(ts)):
            i += 1
            continue
        # mother = i-1, inside = i (allow multiple insides by scanning)
        mh, ml = float(h_a[i - 1]), float(l_a[i - 1])
        if not _is_inside(h_a[i], l_a[i], mh, ml, soft):
            i += 1
            continue
        # extend coil of insides
        end_ib = i
        for k in range(i + 1, min(i + 4, n)):
            if _is_inside(h_a[k], l_a[k], mh, ml, soft) or _is_inside(h_a[k], l_a[k], h_a[k - 1], l_a[k - 1], soft):
                end_ib = k
            else:
                break
        # look for false break then snap-back within max_wait after end_ib
        false_side = None
        false_ext = None
        false_j = None
        for j in range(end_ib + 1, min(end_ib + 1 + max_wait, n - 1)):
            # false break low
            if l_a[j] < ml - eps:
                false_side = "low"
                false_ext = float(l_a[j])
                false_j = j
                # extend extreme while continuing below
                for j2 in range(j + 1, min(j + 3, n - 1)):
                    if l_a[j2] < false_ext:
                        false_ext = float(l_a[j2])
                        false_j = j2
                    if c_a[j2] > ml:  # snapped back inside
                        break
                break
            # false break high
            if h_a[j] > mh + eps:
                false_side = "high"
                false_ext = float(h_a[j])
                false_j = j
                for j2 in range(j + 1, min(j + 3, n - 1)):
                    if h_a[j2] > false_ext:
                        false_ext = float(h_a[j2])
                        false_j = j2
                    if c_a[j2] < mh:
                        break
                break
        if false_side is None:
            i = end_ib + 1
            continue
        # wait for snap-back + entry trigger after false_j
        triggered = False
        for j in range(false_j, min(false_j + max_wait, n - 1)):
            if false_side == "low":
                # invalidate if new low beyond extreme persists with close below
                if c_a[j] < false_ext:
                    break
                snapped = c_a[j] > ml or (l_a[j] <= mh and h_a[j] >= ml and c_a[j] > o_a[j])
                if not snapped and j == false_j:
                    continue
                if entry_mode == "mother":
                    # need evidence of snap: close back above ml
                    if c_a[j] <= ml:
                        continue
                    entry = mh + TICK
                    sl = false_ext - TICK
                    if entry - sl > max_risk + 1e-9 or entry <= sl:
                        break
                    tp = _rr("long", entry, sl, rr)
                    if tp is None:
                        break
                    arm = bar_end(times[j], bar)
                    v = f"fakey_{tf}_rr{rr:g}_e{eps:g}_{entry_mode}"
                    orders.append(_stop(arm, "long", entry, sl, tp, "FAKEY", v,
                                        {"signal_bar": times[j], "mother": times[i - 1],
                                         "false_ext": false_ext, "side": "bull"}, bar))
                    triggered = True
                    i = j + 2
                    break
                else:
                    o, h, l, c = float(o_a[j]), float(h_a[j]), float(l_a[j]), float(c_a[j])
                    if not _bull_q(o, h, l, c, 0.5):
                        continue
                    entry = h + TICK
                    sl = false_ext - TICK
                    if entry - sl > max_risk + 1e-9 or entry <= sl:
                        continue
                    tp = _rr("long", entry, sl, rr)
                    if tp is None:
                        continue
                    arm = bar_end(times[j], bar)
                    v = f"fakey_{tf}_rr{rr:g}_e{eps:g}_{entry_mode}"
                    orders.append(_stop(arm, "long", entry, sl, tp, "FAKEY", v,
                                        {"signal_bar": times[j], "false_ext": false_ext, "side": "bull"}, bar))
                    triggered = True
                    i = j + 2
                    break
            else:  # false high → bearish fakey
                if c_a[j] > false_ext:
                    break
                if entry_mode == "mother":
                    if c_a[j] >= mh:
                        continue
                    entry = ml - TICK
                    sl = false_ext + TICK
                    if sl - entry > max_risk + 1e-9 or sl <= entry:
                        break
                    tp = _rr("short", entry, sl, rr)
                    if tp is None:
                        break
                    arm = bar_end(times[j], bar)
                    v = f"fakey_{tf}_rr{rr:g}_e{eps:g}_{entry_mode}"
                    orders.append(_stop(arm, "short", entry, sl, tp, "FAKEY", v,
                                        {"signal_bar": times[j], "false_ext": false_ext, "side": "bear"}, bar))
                    triggered = True
                    i = j + 2
                    break
                else:
                    o, h, l, c = float(o_a[j]), float(h_a[j]), float(l_a[j]), float(c_a[j])
                    if not _bear_q(o, h, l, c, 0.5):
                        continue
                    entry = l - TICK
                    sl = false_ext + TICK
                    if sl - entry > max_risk + 1e-9 or sl <= entry:
                        continue
                    tp = _rr("short", entry, sl, rr)
                    if tp is None:
                        continue
                    arm = bar_end(times[j], bar)
                    v = f"fakey_{tf}_rr{rr:g}_e{eps:g}_{entry_mode}"
                    orders.append(_stop(arm, "short", entry, sl, tp, "FAKEY", v,
                                        {"signal_bar": times[j], "false_ext": false_ext, "side": "bear"}, bar))
                    triggered = True
                    i = j + 2
                    break
        if not triggered:
            i = end_ib + 1

    orders = dedupe_orders(orders, 20)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_fakey_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 2.0, 0.50, "mother"),
        ("M5", 1.5, 0.50, "mother"),
        ("M5", 2.0, 0.30, "signal"),
        ("M5", 2.0, 1.00, "mother"),
        ("M15", 2.0, 0.50, "mother"),
    ]
    for tf, rr, eps, em in specs:
        oo = generate_fakey(m1, dxy, False, tf, rr, True, eps, 8.0, em)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 3) PDH/PDL Raid + M5 reclaim (Turtle Soup aggressive) ==========
def generate_pdh_pdl_reclaim(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    rr: float = 1.5,
    kz: str = "both",  # london | nyam | both | any
    entry_mode: str = "stop",  # stop below reclaim low | close (approx as stop at reclaim low for fill discipline)
    max_risk: float = 8.0,
    require_htf_bias: bool = True,
    max_raid_beyond: float = 8.0,  # if raid extreme too far, skip
) -> List[Order]:
    """PDH raid → M5 close back below PDH → short; PDL mirror.
    No MSS/FVG required (aggressive LSG close-back version).
    HTF bias: H4 EMA20 (closed) — fade only with bias.
    """
    m5 = resample_ohlc(m1, "5min")
    h4 = resample_ohlc(m1, "240min")
    e20_h4 = ema(h4["close"].astype(float), 20)
    # shift so only prior closed H4 used
    e20_h4_s = e20_h4.shift(1)
    c_h4_s = h4["close"].astype(float).shift(1)

    pdhl = _prev_day_hl(m1)
    o_a = m5["open"].astype(float).values
    h_a = m5["high"].astype(float).values
    l_a = m5["low"].astype(float).values
    c_a = m5["close"].astype(float).values
    times = m5.index
    orders: List[Order] = []
    last_arm_day_side = set()

    # Track raid state per day
    for i in range(1, len(m5) - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if not _in_kz(ts, kz):
            continue
        tu = ts.tz_convert("UTC") if ts.tzinfo else pd.Timestamp(ts).tz_localize("UTC")
        day_key = tu.normalize()
        hl = pdhl.get(day_key)
        if hl is None:
            continue
        pdh, pdl = hl

        # HTF bias
        bias_long = bias_short = True
        if require_htf_bias:
            ec = e20_h4_s.asof(ts)
            cc = c_h4_s.asof(ts)
            if ec != ec or cc != cc:
                continue
            bias_long = bool(cc > ec)
            bias_short = bool(cc < ec)

        # Bearish PDH raid + reclaim
        if bias_short or not require_htf_bias:
            # raid: this or prior bar traded above PDH, and this bar closes back below
            traded_above = h_a[i] > pdh + 1e-12 or h_a[i - 1] > pdh + 1e-12
            reclaim = c_a[i] < pdh
            if traded_above and reclaim:
                # raid extreme = max high while above since crossing
                raid_ext = float(max(h_a[i], h_a[i - 1]))
                # look back a few bars for extreme of this raid leg
                for k in range(max(0, i - 6), i + 1):
                    if h_a[k] > pdh:
                        raid_ext = max(raid_ext, float(h_a[k]))
                if raid_ext - pdh > max_raid_beyond + 1e-9:
                    pass  # still ok if SL fits
                key = (day_key.date(), "S")
                if key not in last_arm_day_side:
                    entry = float(l_a[i]) - TICK
                    sl = raid_ext + TICK
                    if sl - entry <= max_risk + 1e-9 and sl > entry:
                        tp = _rr("short", entry, sl, rr)
                        if tp is not None:
                            # invalidate if close already > raid_ext (true BO) — skip
                            if c_a[i] <= raid_ext:
                                arm = bar_end(ts, 5)
                                v = f"pdhl_rr{rr:g}_kz{kz}" + ("_htf" if require_htf_bias else "_nohtf")
                                orders.append(_stop(arm, "short", entry, sl, tp, "PDHL", v,
                                                    {"signal_bar": ts, "pdh": pdh, "raid_ext": raid_ext,
                                                     "mode": "pdh"}, 5))
                                last_arm_day_side.add(key)

        # Bullish PDL raid + reclaim
        if bias_long or not require_htf_bias:
            traded_below = l_a[i] < pdl - 1e-12 or l_a[i - 1] < pdl - 1e-12
            reclaim = c_a[i] > pdl
            if traded_below and reclaim:
                raid_ext = float(min(l_a[i], l_a[i - 1]))
                for k in range(max(0, i - 6), i + 1):
                    if l_a[k] < pdl:
                        raid_ext = min(raid_ext, float(l_a[k]))
                key = (day_key.date(), "L")
                if key not in last_arm_day_side:
                    entry = float(h_a[i]) + TICK
                    sl = raid_ext - TICK
                    if entry - sl <= max_risk + 1e-9 and entry > sl:
                        tp = _rr("long", entry, sl, rr)
                        if tp is not None:
                            if c_a[i] >= raid_ext:
                                arm = bar_end(ts, 5)
                                v = f"pdhl_rr{rr:g}_kz{kz}" + ("_htf" if require_htf_bias else "_nohtf")
                                orders.append(_stop(arm, "long", entry, sl, tp, "PDHL", v,
                                                    {"signal_bar": ts, "pdl": pdl, "raid_ext": raid_ext,
                                                     "mode": "pdl"}, 5))
                                last_arm_day_side.add(key)

    orders = dedupe_orders(orders, 60)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_pdh_pdl_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        (1.5, "both", True),
        (2.0, "both", True),
        (1.5, "nyam", True),
        (1.5, "both", False),
        (1.5, "any", False),   # higher sample for component search
    ]
    for rr, kz, htf in specs:
        oo = generate_pdh_pdl_reclaim(m1, dxy, False, rr, kz, "stop", 8.0, htf)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 4) Opening Reversal (2nd failed BO of Y high/low) ==========

def generate_opening_reversal(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 2.0,
    session_open: str = "london",  # london UTC 07:00-08:30 | ny UTC 12:00-13:30
    max_risk: float = 8.0,
    require_second: bool = True,
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    pdhl = _prev_day_hl(m1)
    orders: List[Order] = []

    if session_open == "london":
        wh, wm, eh, em = 7, 0, 8, 30
    else:
        wh, wm, eh, em = 12, 0, 13, 30
    w0 = wh * 60 + wm
    w1 = eh * 60 + em

    cur_day = None
    y_high = y_low = None
    nfail_low = nfail_high = 0
    leg_low = None
    leg_high = None

    for i in range(1, len(df) - 1):
        ts = times[i]
        tu = ts.tz_convert("UTC") if ts.tzinfo else pd.Timestamp(ts).tz_localize("UTC")
        if tu.dayofweek >= 5:
            continue
        day_key = tu.normalize()
        mins = tu.hour * 60 + tu.minute
        if day_key != cur_day:
            cur_day = day_key
            hl = pdhl.get(day_key)
            y_high = y_low = None
            nfail_low = nfail_high = 0
            leg_low = leg_high = None
            if hl is not None:
                y_high, y_low = hl
        if y_high is None or not (w0 <= mins < w1):
            continue

        # track extremes in window
        if leg_low is None:
            leg_low = float(l_a[i]); leg_high = float(h_a[i])
        else:
            leg_low = min(leg_low, float(l_a[i]))
            leg_high = max(leg_high, float(h_a[i]))

        pierced_low = l_a[i] < y_low - 1e-12
        closed_in_from_low = pierced_low and c_a[i] > y_low
        pierced_high = h_a[i] > y_high + 1e-12
        closed_in_from_high = pierced_high and c_a[i] < y_high

        if closed_in_from_low:
            nfail_low += 1
            if (not require_second and nfail_low >= 1) or (require_second and nfail_low >= 2):
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                if _bull_q(o, h, l, c, 0.5):
                    entry = h + TICK
                    sl = leg_low - TICK
                    if entry - sl <= max_risk + 1e-9 and entry > sl:
                        tp = _rr("long", entry, sl, rr)
                        if tp is not None:
                            arm = bar_end(ts, bar)
                            v = f"orv_{session_open}_{tf}_rr{rr:g}" + ("_2nd" if require_second else "_1st")
                            orders.append(_stop(arm, "long", entry, sl, tp, "ORV", v,
                                                {"signal_bar": ts, "y_low": y_low, "nfail": nfail_low}, bar))

        if closed_in_from_high:
            nfail_high += 1
            if (not require_second and nfail_high >= 1) or (require_second and nfail_high >= 2):
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                if _bear_q(o, h, l, c, 0.5):
                    entry = l - TICK
                    sl = leg_high + TICK
                    if sl - entry <= max_risk + 1e-9 and sl > entry:
                        tp = _rr("short", entry, sl, rr)
                        if tp is not None:
                            arm = bar_end(ts, bar)
                            v = f"orv_{session_open}_{tf}_rr{rr:g}" + ("_2nd" if require_second else "_1st")
                            orders.append(_stop(arm, "short", entry, sl, tp, "ORV", v,
                                                {"signal_bar": ts, "y_high": y_high, "nfail": nfail_high}, bar))

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_orv_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("london", "M5", 2.0, True),
        ("ny", "M5", 2.0, True),
        ("london", "M5", 1.5, True),
        ("ny", "M5", 1.5, False),
        ("london", "M5", 2.0, False),
    ]
    for sess, tf, rr, sec in specs:
        oo = generate_opening_reversal(m1, dxy, False, tf, rr, sess, 8.0, sec)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 5) Breaker Block (WITH mandatory sweep) ==========
def generate_breaker(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf_block: str = "M5",
    tf_entry: str = "M5",
    rr: float = 1.5,
    disp_atr_k: float = 1.0,
    max_risk: float = 8.0,
    lookback: int = 30,
    session: str = "liq",
) -> List[Order]:
    """Breaker = sweep old extreme THEN body close beyond block distal + retest.
    Distinct from Mitigation (batch-2) which forbids sweep.
    """
    bar_b = {"M1": 1, "M5": 5, "M15": 15}[tf_block]
    bar_e = {"M1": 1, "M5": 5, "M15": 15}[tf_entry]
    blk = m1 if tf_block == "M1" else resample_ohlc(m1, f"{bar_b}min")
    ent = m1 if tf_entry == "M1" else resample_ohlc(m1, f"{bar_e}min")
    atr_b = atr_prior(blk, 14).values
    o_b = blk["open"].astype(float).values
    h_b = blk["high"].astype(float).values
    l_b = blk["low"].astype(float).values
    c_b = blk["close"].astype(float).values
    t_b = blk.index
    o_e = ent["open"].astype(float).values
    h_e = ent["high"].astype(float).values
    l_e = ent["low"].astype(float).values
    c_e = ent["close"].astype(float).values
    t_e = ent.index

    left = right = 2
    swing_lows = []
    swing_highs = []
    for i in range(left, len(blk) - right):
        if all(l_b[i] <= l_b[i - j] for j in range(1, left + 1)) and all(l_b[i] < l_b[i + j] for j in range(1, right + 1)):
            swing_lows.append((i + right, i, float(l_b[i])))
        if all(h_b[i] >= h_b[i - j] for j in range(1, left + 1)) and all(h_b[i] > h_b[i + j] for j in range(1, right + 1)):
            swing_highs.append((i + right, i, float(h_b[i])))

    events = []
    for i in range(25, len(blk) - 1):
        ts = t_b[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        if np.isnan(atr_b[i]) or atr_b[i] <= 0:
            continue
        body = abs(c_b[i] - o_b[i])
        if body < disp_atr_k * atr_b[i]:
            continue

        if c_b[i] > o_b[i]:
            # bullish breaker path: sweep old low, then close above bearish block distal
            conf = [s for s in swing_lows if s[0] <= i]
            if len(conf) < 2:
                continue
            old_sl = conf[-2]
            # MUST have swept old low
            if float(l_b[old_sl[1]:i + 1].min()) >= old_sl[2] - 1e-9:
                continue
            # last down-close before displacement = bearish block
            blk_i = None
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if c_b[j] < o_b[j]:
                    blk_i = j
                    break
            if blk_i is None:
                continue
            distal_high = float(h_b[blk_i])
            if c_b[i] <= distal_high:
                continue
            events.append({
                "side": "long", "confirm_i": i, "confirm_ts": ts,
                "blk_i": blk_i, "bh": float(h_b[blk_i]), "bl": float(l_b[blk_i]),
            })
        elif c_b[i] < o_b[i]:
            conf = [s for s in swing_highs if s[0] <= i]
            if len(conf) < 2:
                continue
            old_sh = conf[-2]
            if float(h_b[old_sh[1]:i + 1].max()) <= old_sh[2] + 1e-9:
                continue  # no sweep
            blk_i = None
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if c_b[j] > o_b[j]:
                    blk_i = j
                    break
            if blk_i is None:
                continue
            distal_low = float(l_b[blk_i])
            if c_b[i] >= distal_low:
                continue
            events.append({
                "side": "short", "confirm_i": i, "confirm_ts": ts,
                "blk_i": blk_i, "bh": float(h_b[blk_i]), "bl": float(l_b[blk_i]),
            })

    orders: List[Order] = []
    for ev in events:
        conf_ts = ev["confirm_ts"]
        after = bar_end(conf_ts, bar_b)
        j0 = int(t_e.searchsorted(after, side="left"))
        bh, bl = ev["bh"], ev["bl"]
        side = ev["side"]
        for j in range(j0, min(j0 + 40, len(ent) - 1)):
            ts = t_e[j]
            if ts.dayofweek >= 5:
                continue
            if session == "liq" and not _in_liquidity(ts):
                continue
            if side == "long" and c_e[j] < bl:
                break
            if side == "short" and c_e[j] > bh:
                break
            in_block = (l_e[j] <= bh and h_e[j] >= bl)
            if not in_block:
                continue
            o, h, l, c = float(o_e[j]), float(h_e[j]), float(l_e[j]), float(c_e[j])
            if side == "long":
                if not _bull_q(o, h, l, c, 0.5):
                    continue
                entry = h + TICK
                sl = bl - TICK
                if entry - sl > max_risk + 1e-9 or entry <= sl:
                    continue
                tp = _rr("long", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, bar_e)
                v = f"brk_{tf_block}_{tf_entry}_rr{rr:g}_k{disp_atr_k:g}"
                orders.append(_stop(arm, "long", entry, sl, tp, "BRK", v,
                                    {"signal_bar": ts, "confirm": conf_ts}, bar_e))
                break
            else:
                if not _bear_q(o, h, l, c, 0.5):
                    continue
                entry = l - TICK
                sl = bh + TICK
                if sl - entry > max_risk + 1e-9 or sl <= entry:
                    continue
                tp = _rr("short", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, bar_e)
                v = f"brk_{tf_block}_{tf_entry}_rr{rr:g}_k{disp_atr_k:g}"
                orders.append(_stop(arm, "short", entry, sl, tp, "BRK", v,
                                    {"signal_bar": ts, "confirm": conf_ts}, bar_e))
                break

    orders = dedupe_orders(orders, 20)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_breaker_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", "M5", 1.5, 1.0),
        ("M5", "M5", 2.0, 1.0),
        ("M5", "M1", 1.5, 1.0),
        ("M15", "M5", 1.5, 1.0),
        ("M5", "M5", 1.5, 0.75),
    ]
    for tb, te, rr, k in specs:
        oo = generate_breaker(m1, dxy, False, tb, te, rr, k, 8.0)
        if oo:
            pools[oo[0].variant] = oo
    return pools
