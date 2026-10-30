"""Research batch-1 setups (Al Brooks H2/L2, BP, Final Flag, Wedge/MW, ICT Judas).

Faithful to /workspace/trading-research/batch-1.md.
Rules enforced:
- Stop entry 1 tick beyond signal bar; expire ≈ 1 bar (cancel if next bar misses)
- SL beyond signal bar (± tick); prop filter signal_bar_range <= $8 (toggle)
- Closed-bar arm only; no future swing confirmation
- NY times via America/New_York (EDT→EST auto on first Sun Nov)
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

TICK = 0.01  # XAUUSD


def _ny(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("America/New_York")


def _in_liquidity(ts: pd.Timestamp, start_h=7, end_h=16) -> bool:
    """UTC liquidity window (default London–NY early)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert("UTC")
    return t.dayofweek < 5 and start_h <= t.hour < end_h


def _bull_close_near_high(o, h, l, c, frac=0.5) -> bool:
    rng = h - l
    if rng <= 0:
        return False
    return c > o and (c - l) / rng >= frac


def _bear_close_near_low(o, h, l, c, frac=0.5) -> bool:
    rng = h - l
    if rng <= 0:
        return False
    return c < o and (h - c) / rng >= frac


def _rr(side: str, entry: float, sl: float, rr: float) -> Optional[float]:
    risk = abs(entry - sl)
    if risk < 1e-9:
        return None
    return entry + rr * risk if side == "long" else entry - rr * risk


def _stop_order(arm, side, entry_stop, sl, tp, strategy, variant, meta, bar_m, hold=180):
    return Order(
        arm_time=arm, side=side, kind="stop", price=float(entry_stop),
        sl=float(sl), tp=float(tp), strategy=strategy, variant=variant,
        meta=meta, expire_minutes=int(bar_m), max_hold_minutes=hold,
    )


# ========== 1) H2 / L2 ==========
def generate_h2l2(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    require_quality: bool = True,
    max_sig_range: float = 8.0,
    session: str = "liq",  # liq=07-16 UTC | all=in_session broad
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    e20 = ema(close, 20)
    orders: List[Order] = []

    # State for H2 (long) and L2 (short) independently
    # pullback_leg: after AIL and a down/side move starts
    h_count = 0
    h_need_leg = False  # after H1, need a down leg before H2
    l_count = 0
    l_need_leg = False

    for i in range(25, len(df) - 1):
        ts = df.index[i]
        if ts.dayofweek >= 5:
            h_count = l_count = 0
            h_need_leg = l_need_leg = False
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        if np.isnan(e20.iloc[i]):
            continue
        o, h, l, c = float(open_.iloc[i]), float(high.iloc[i]), float(low.iloc[i]), float(close.iloc[i])
        ph, pl = float(high.iloc[i - 1]), float(low.iloc[i - 1])
        ail = c > float(e20.iloc[i])
        ais = c < float(e20.iloc[i])

        # --- H2 path (Always-In Long) ---
        if ail:
            # down/side bar starts or continues pullback context
            if c < o or l < pl:
                if h_count == 0:
                    pass  # in pullback, waiting for H1
                elif h_count >= 1:
                    h_need_leg = True
            if h > ph + 1e-12:  # high exceeds prior → H event
                if h_count == 0:
                    h_count = 1
                    h_need_leg = False
                elif h_count == 1 and h_need_leg:
                    # H2 signal bar = this bar
                    sig_range = h - l
                    if max_sig_range is None or sig_range <= max_sig_range + 1e-9:
                        ok_q = (not require_quality) or _bull_close_near_high(o, h, l, c, 0.5)
                        if ok_q:
                            entry = h + TICK
                            sl = l - TICK
                            tp = _rr("long", entry, sl, rr)
                            if tp is not None and entry > sl:
                                arm = bar_end(ts, bar)
                                v = f"h2l2_{tf}_rr{rr:g}" + ("_q" if require_quality else "_nq")
                                if max_sig_range and max_sig_range < 99:
                                    v += f"_cap{max_sig_range:g}"
                                orders.append(_stop_order(
                                    arm, "long", entry, sl, tp, "H2L2", v,
                                    {"signal_bar": ts, "kind": "H2", "sig_range": sig_range}, bar,
                                ))
                    h_count = 0
                    h_need_leg = False
                elif h_count == 1 and not h_need_leg:
                    # another H without down leg — still H1 territory; refresh
                    h_count = 1
        else:
            h_count = 0
            h_need_leg = False

        # --- L2 path (Always-In Short) ---
        if ais:
            if c > o or h > ph:
                if l_count >= 1:
                    l_need_leg = True
            if l < pl - 1e-12:
                if l_count == 0:
                    l_count = 1
                    l_need_leg = False
                elif l_count == 1 and l_need_leg:
                    sig_range = h - l
                    if max_sig_range is None or sig_range <= max_sig_range + 1e-9:
                        ok_q = (not require_quality) or _bear_close_near_low(o, h, l, c, 0.5)
                        if ok_q:
                            entry = l - TICK
                            sl = h + TICK
                            tp = _rr("short", entry, sl, rr)
                            if tp is not None and sl > entry:
                                arm = bar_end(ts, bar)
                                v = f"h2l2_{tf}_rr{rr:g}" + ("_q" if require_quality else "_nq")
                                if max_sig_range and max_sig_range < 99:
                                    v += f"_cap{max_sig_range:g}"
                                orders.append(_stop_order(
                                    arm, "short", entry, sl, tp, "H2L2", v,
                                    {"signal_bar": ts, "kind": "L2", "sig_range": sig_range}, bar,
                                ))
                    l_count = 0
                    l_need_leg = False
                elif l_count == 1 and not l_need_leg:
                    l_count = 1
        else:
            l_count = 0
            l_need_leg = False

    orders = dedupe_orders(orders, {"M1": 5, "M5": 15, "M15": 30}.get(tf, 15))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_h2l2_family(m1, dxy=None) -> Dict[str, List[Order]]:
    """~5 pre-registered variants."""
    pools = {}
    specs = [
        ("M5", 1.5, True, 8.0, False),
        ("M5", 2.0, True, 8.0, False),
        ("M5", 1.5, True, 8.0, True),
        ("M1", 1.5, True, 8.0, False),
        ("M5", 1.5, False, 8.0, False),
    ]
    for tf, rr, q, cap, dxy_on in specs:
        oo = generate_h2l2(m1, dxy, dxy_on, tf, rr, q, cap)
        if oo:
            pools[oo[0].variant + ("_dxy" if dxy_on else "")] = oo if not dxy_on else [
                Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                      o.variant + "_dxy", o.meta, o.expire_minutes, o.max_hold_minutes)
                for o in oo
            ]
    return pools


# ========== 2) Breakout Pullback ==========
def generate_bp(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    max_pb_bars: int = 3,
    max_retrace: float = 0.50,
    min_tb: int = 2,
    max_tb: int = 5,
    max_sig_range: float = 8.0,
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    orders: List[Order] = []

    def is_bull_tb(i):
        rng = h_a[i] - l_a[i]
        return rng > 0 and c_a[i] > o_a[i] and (c_a[i] - l_a[i]) / rng >= 0.5

    def is_bear_tb(i):
        rng = h_a[i] - l_a[i]
        return rng > 0 and c_a[i] < o_a[i] and (h_a[i] - c_a[i]) / rng >= 0.5

    i = 30
    n = len(df)
    while i < n - 2:
        if times[i].dayofweek >= 5 or not _in_liquidity(times[i], 6, 16):
            i += 1
            continue
        # detect bull BO: 2–5 bull trend bars ending at i
        for ntb in range(max_tb, min_tb - 1, -1):
            start = i - ntb + 1
            if start < 5:
                continue
            if not all(is_bull_tb(j) for j in range(start, i + 1)):
                continue
            # break prior swing high (max high of 10 bars before BO)
            prior_hi = float(h_a[start - 10:start].max()) if start >= 10 else float(h_a[:start].max())
            bo_high = float(h_a[start:i + 1].max())
            bo_start_low = float(l_a[start])
            if bo_high <= prior_hi:
                continue
            bo_size = bo_high - bo_start_low
            if bo_size < 0.5:
                continue
            # look for PB within next 1..max_pb_bars
            for k in range(1, max_pb_bars + 1):
                j = i + k
                if j >= n - 1:
                    break
                pb_low = float(l_a[i + 1:j + 1].min())
                retrace = (bo_high - pb_low) / bo_size
                if retrace > max_retrace + 1e-12:
                    break  # too deep → fail this BO
                # signal bar = bar j if it's a pullback bar (not continuing BO)
                if c_a[j] >= o_a[j] and k < max_pb_bars:
                    continue  # still strong — wait
                sig_h, sig_l = float(h_a[j]), float(l_a[j])
                sig_range = sig_h - sig_l
                if sig_range > max_sig_range + 1e-9:
                    break
                entry = sig_h + TICK
                sl = sig_l - TICK
                tp = _rr("long", entry, sl, rr)
                if tp is None:
                    break
                arm = bar_end(times[j], bar)
                v = f"bp_{tf}_rr{rr:g}_pb{max_pb_bars}_r{int(max_retrace*100)}"
                orders.append(_stop_order(
                    arm, "long", entry, sl, tp, "BP", v,
                    {"signal_bar": times[j], "bo_size": bo_size, "retrace": retrace}, bar,
                ))
                break
            break  # only first matching ntb
        # bear BO mirror
        for ntb in range(max_tb, min_tb - 1, -1):
            start = i - ntb + 1
            if start < 5:
                continue
            if not all(is_bear_tb(j) for j in range(start, i + 1)):
                continue
            prior_lo = float(l_a[start - 10:start].min()) if start >= 10 else float(l_a[:start].min())
            bo_low = float(l_a[start:i + 1].min())
            bo_start_high = float(h_a[start])
            if bo_low >= prior_lo:
                continue
            bo_size = bo_start_high - bo_low
            if bo_size < 0.5:
                continue
            for k in range(1, max_pb_bars + 1):
                j = i + k
                if j >= n - 1:
                    break
                pb_high = float(h_a[i + 1:j + 1].max())
                retrace = (pb_high - bo_low) / bo_size
                if retrace > max_retrace + 1e-12:
                    break
                if c_a[j] <= o_a[j] and k < max_pb_bars:
                    continue
                sig_h, sig_l = float(h_a[j]), float(l_a[j])
                if sig_h - sig_l > max_sig_range + 1e-9:
                    break
                entry = sig_l - TICK
                sl = sig_h + TICK
                tp = _rr("short", entry, sl, rr)
                if tp is None:
                    break
                arm = bar_end(times[j], bar)
                v = f"bp_{tf}_rr{rr:g}_pb{max_pb_bars}_r{int(max_retrace*100)}"
                orders.append(_stop_order(
                    arm, "short", entry, sl, tp, "BP", v,
                    {"signal_bar": times[j], "bo_size": bo_size, "retrace": retrace}, bar,
                ))
                break
            break
        i += 1

    orders = dedupe_orders(orders, 20)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_bp_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, 3, 0.50, False),
        ("M5", 2.0, 3, 0.50, False),
        ("M5", 1.5, 3, 0.50, True),
        ("M1", 1.5, 3, 0.50, False),
        ("M5", 1.5, 2, 0.40, False),
    ]
    for tf, rr, pb, ret, dxy_on in specs:
        oo = generate_bp(m1, dxy, dxy_on, tf, rr, pb, ret)
        if not oo:
            continue
        tag = oo[0].variant + ("_dxy" if dxy_on else "")
        if dxy_on:
            oo = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                        tag, o.meta, o.expire_minutes, o.max_hold_minutes) for o in oo]
        pools[tag] = oo
    return pools


# ========== 3) Final Flag fail ==========
def generate_final_flag(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    trend_bars: int = 20,
    fail_within: int = 3,
    max_sig_range: float = 8.0,
    sl_mode: str = "signal",  # signal | extreme (Brooks extreme often >$8)
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    e20 = ema(df["close"].astype(float), 20).values
    times = df.index
    orders: List[Order] = []
    n = len(df)

    for i in range(trend_bars + 5, n - fail_within - 2):
        if times[i].dayofweek >= 5 or not _in_liquidity(times[i]):
            continue
        if np.isnan(e20[i]):
            continue
        # extended bull: most closes above EMA over last trend_bars
        window = slice(i - trend_bars, i)
        ail_frac = np.mean(c_a[window] > e20[window])
        ais_frac = np.mean(c_a[window] < e20[window])
        # tight flag: last 3–6 bars range small vs prior trend range
        for flen in (3, 4, 5):
            if i - flen < trend_bars:
                continue
            flag_h = float(h_a[i - flen:i].max())
            flag_l = float(l_a[i - flen:i].min())
            flag_rng = flag_h - flag_l
            prior_rng = float(h_a[i - trend_bars:i - flen].max() - l_a[i - trend_bars:i - flen].min())
            if prior_rng <= 0 or flag_rng > 0.35 * prior_rng:
                continue
            # bull FF: AIL + BO to new high then fail back into flag
            if ail_frac >= 0.7:
                if h_a[i] <= flag_h + 1e-12:
                    continue
                bo_ext = float(h_a[i])
                for k in range(1, fail_within + 1):
                    j = i + k
                    if j >= n - 1:
                        break
                    if l_a[j] < flag_h and c_a[j] < o_a[j] and _bear_close_near_low(
                            o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                        sig_h, sig_l = float(h_a[j]), float(l_a[j])
                        if sig_h - sig_l > max_sig_range + 1e-9 and sl_mode == "signal":
                            break
                        entry = sig_l - TICK
                        if sl_mode == "extreme":
                            sl = bo_ext + TICK
                        else:
                            sl = sig_h + TICK
                        if abs(entry - sl) > max_sig_range + 0.5:
                            break
                        tp = _rr("short", entry, sl, rr)
                        if tp is None:
                            break
                        arm = bar_end(times[j], bar)
                        v = f"ff_{tf}_rr{rr:g}_{sl_mode}"
                        orders.append(_stop_order(
                            arm, "short", entry, sl, tp, "FinalFlag", v,
                            {"signal_bar": times[j], "bo_ext": bo_ext}, bar,
                        ))
                        break
            # bear FF mirror
            if ais_frac >= 0.7:
                if l_a[i] >= flag_l - 1e-12:
                    continue
                bo_ext = float(l_a[i])
                for k in range(1, fail_within + 1):
                    j = i + k
                    if j >= n - 1:
                        break
                    if h_a[j] > flag_l and c_a[j] > o_a[j] and _bull_close_near_high(
                            o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                        sig_h, sig_l = float(h_a[j]), float(l_a[j])
                        if sig_h - sig_l > max_sig_range + 1e-9 and sl_mode == "signal":
                            break
                        entry = sig_h + TICK
                        sl = (bo_ext - TICK) if sl_mode == "extreme" else (sig_l - TICK)
                        if abs(entry - sl) > max_sig_range + 0.5:
                            break
                        tp = _rr("long", entry, sl, rr)
                        if tp is None:
                            break
                        arm = bar_end(times[j], bar)
                        v = f"ff_{tf}_rr{rr:g}_{sl_mode}"
                        orders.append(_stop_order(
                            arm, "long", entry, sl, tp, "FinalFlag", v,
                            {"signal_bar": times[j], "bo_ext": bo_ext}, bar,
                        ))
                        break
            break

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_ff_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, "signal", False),
        ("M5", 2.0, "signal", False),
        ("M5", 1.5, "signal", True),
        ("M1", 1.5, "signal", False),
        ("M5", 1.5, "extreme", False),
    ]
    for tf, rr, slm, dxy_on in specs:
        oo = generate_final_flag(m1, dxy, dxy_on, tf, rr, sl_mode=slm)
        if not oo:
            continue
        tag = oo[0].variant + ("_dxy" if dxy_on else "")
        if dxy_on:
            oo = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                        tag, o.meta, o.expire_minutes, o.max_hold_minutes) for o in oo]
        pools[tag] = oo
    return pools


# ========== 4) Wedge / MicroWedge ==========
def generate_wedge(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    micro: bool = True,
    max_sig_range: float = 8.0,
    with_trend_flag: bool = False,  # if True, trade wedge flag with trend (H3/L3)
) -> List[Order]:
    """Three pushes. MicroWedge: pushes span <= 5 bars. No future pivot confirm —
    push extremes are bar highs/lows identified only after the bar closes.
    """
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    e20 = ema(df["close"].astype(float), 20).values
    times = df.index
    orders: List[Order] = []
    n = len(df)
    max_span = 5 if micro else 20

    # Local push detection without right-side confirm: a bar is a push high if
    # its high is strictly greater than the previous 1–2 bars' highs AND the next
    # CLOSED bar has made a lower high or closed down (confirm after 1 bar).
    # Arm only after that confirm bar — so push is known with 1-bar lag (no lookahead).
    push_highs: List[Tuple[int, float]] = []  # (bar_index_of_extreme, price) confirmed
    push_lows: List[Tuple[int, float]] = []

    for i in range(3, n - 1):
        # confirm push high at i-1 if h[i-1] > h[i-2] and h[i-1] > h[i] (or c[i]<o[i])
        j = i - 1
        if h_a[j] > h_a[j - 1] and (h_a[j] > h_a[i] or c_a[i] < o_a[i]):
            if h_a[j] >= h_a[max(0, j - 2):j + 1].max():
                push_highs.append((j, float(h_a[j])))
                if len(push_highs) > 8:
                    push_highs = push_highs[-8:]
        if l_a[j] < l_a[j - 1] and (l_a[j] < l_a[i] or c_a[i] > o_a[i]):
            if l_a[j] <= l_a[max(0, j - 2):j + 1].min():
                push_lows.append((j, float(l_a[j])))
                if len(push_lows) > 8:
                    push_lows = push_lows[-8:]

        if times[i].dayofweek >= 5 or not _in_liquidity(times[i]):
            continue
        if np.isnan(e20[i]):
            continue

        # Wedge top → short: last 3 push highs ascending-ish within span
        if len(push_highs) >= 3:
            p1, p2, p3 = push_highs[-3], push_highs[-2], push_highs[-1]
            span = p3[0] - p1[0]
            if 2 <= span <= max_span and p3[0] >= i - 2:
                # channel: p3 near extension of p1–p2
                if p2[0] != p1[0]:
                    slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                    proj = p2[1] + slope * (p3[0] - p2[0])
                    near = abs(p3[1] - proj) <= 0.5 * max(abs(p2[1] - p1[1]), 0.3)
                else:
                    near = True
                rising = p3[1] >= min(p1[1], p2[1])
                if near and rising and _bear_close_near_low(o_a[i], h_a[i], l_a[i], c_a[i], 0.5):
                    # with-trend flag: only short if AIS; reversal: short after bull channel
                    ail = c_a[i] > e20[i]
                    if with_trend_flag and ail:
                        pass  # skip counter-trend in strong AIL for flag mode... actually wedge bear flag is short pullback in bear — skip here
                    elif (not with_trend_flag) or (not ail):
                        sig_h, sig_l = float(h_a[i]), float(l_a[i])
                        if sig_h - sig_l <= max_sig_range + 1e-9:
                            entry = sig_l - TICK
                            sl = sig_h + TICK
                            tp = _rr("short", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(times[i], bar)
                                kind = "mw" if micro else "w"
                                v = f"{kind}_{tf}_rr{rr:g}"
                                orders.append(_stop_order(
                                    arm, "short", entry, sl, tp, "Wedge", v,
                                    {"signal_bar": times[i], "p3": p3[1], "span": span}, bar,
                                ))

        if len(push_lows) >= 3:
            p1, p2, p3 = push_lows[-3], push_lows[-2], push_lows[-1]
            span = p3[0] - p1[0]
            if 2 <= span <= max_span and p3[0] >= i - 2:
                if p2[0] != p1[0]:
                    slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                    proj = p2[1] + slope * (p3[0] - p2[0])
                    near = abs(p3[1] - proj) <= 0.5 * max(abs(p2[1] - p1[1]), 0.3)
                else:
                    near = True
                falling = p3[1] <= max(p1[1], p2[1])
                if near and falling and _bull_close_near_high(o_a[i], h_a[i], l_a[i], c_a[i], 0.5):
                    ais = c_a[i] < e20[i]
                    if with_trend_flag and ais:
                        pass
                    elif (not with_trend_flag) or (not ais):
                        sig_h, sig_l = float(h_a[i]), float(l_a[i])
                        if sig_h - sig_l <= max_sig_range + 1e-9:
                            entry = sig_h + TICK
                            sl = sig_l - TICK
                            tp = _rr("long", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(times[i], bar)
                                kind = "mw" if micro else "w"
                                v = f"{kind}_{tf}_rr{rr:g}"
                                orders.append(_stop_order(
                                    arm, "long", entry, sl, tp, "Wedge", v,
                                    {"signal_bar": times[i], "p3": p3[1], "span": span}, bar,
                                ))

    orders = dedupe_orders(orders, 15 if micro else 30)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_wedge_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        (True, "M5", 1.5, False),
        (True, "M5", 2.0, False),
        (True, "M5", 1.5, True),
        (True, "M1", 1.5, False),
        (False, "M5", 1.5, False),
    ]
    for micro, tf, rr, dxy_on in specs:
        oo = generate_wedge(m1, dxy, dxy_on, tf, rr, micro=micro)
        if not oo:
            continue
        tag = oo[0].variant + ("_dxy" if dxy_on else "")
        if dxy_on:
            oo = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                        tag, o.meta, o.expire_minutes, o.max_hold_minutes) for o in oo]
        pools[tag] = oo
    return pools


# ========== 5) Judas M15 reclaim ==========
def generate_judas(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    entry_tf: str = "M5",
    rr: float = 1.5,
    bias_mode: str = "h1_ema",  # h1_ema | daily_close | none
    max_sl: float = 8.0,
    buf_atr: float = 0.1,
) -> List[Order]:
    """DT Terminal rule: sweep midnight open + quiet 00-02 NY range, then M15
    close back beyond midnight open before 05:00 NY. Entry stop on M5/M1.
    """
    bar = {"M1": 1, "M5": 5}[entry_tf]
    m15 = resample_ohlc(m1, "15min")
    ent = m1 if entry_tf == "M1" else resample_ohlc(m1, f"{bar}min")
    h1 = resample_ohlc(m1, "60min")
    daily = resample_ohlc(m1, "1D")
    e20_h1 = ema(h1["close"].astype(float), 20)
    atr15 = atr_prior(m15, 14)

    orders: List[Order] = []
    # Group M15 by NY date
    m15_ny = m15.copy()
    m15_ny["ny"] = [_ny(t) for t in m15_ny.index]
    m15_ny["ny_date"] = [t.date() for t in m15_ny["ny"]]
    m15_ny["ny_hm"] = [(t.hour, t.minute) for t in m15_ny["ny"]]

    for day, g in m15_ny.groupby("ny_date"):
        g = g.sort_index()
        if len(g) < 8:
            continue
        # midnight open: first bar at/after 00:00 NY
        mid_rows = g[g["ny"].map(lambda t: t.hour == 0 and t.minute == 0)]
        if mid_rows.empty:
            # first bar of day
            midnight_open = float(g.iloc[0]["open"])
            mid_ts = g.index[0]
        else:
            midnight_open = float(mid_rows.iloc[0]["open"])
            mid_ts = mid_rows.index[0]
        quiet = g[g["ny"].map(lambda t: (t.hour < 2) or (t.hour == 0))]
        # 00:00–02:00
        quiet = g[(g["ny"].dt.hour >= 0) & (g["ny"].dt.hour < 2)]
        if quiet.empty:
            continue
        quiet_low = float(quiet["low"].min())
        quiet_high = float(quiet["high"].max())

        # bias
        bias = 0
        if bias_mode == "h1_ema":
            # last closed H1 before midnight
            j = e20_h1.index.searchsorted(mid_ts, side="left") - 1
            if j >= 0:
                bias = 1 if float(h1["close"].iloc[j]) > float(e20_h1.iloc[j]) else -1
        elif bias_mode == "daily_close":
            # prior daily close vs prior daily open
            dprev = pd.Timestamp(day) - pd.Timedelta(days=1)
            # daily index is UTC date of bar start
            for di in daily.index:
                if _ny(di).date() == (pd.Timestamp(day) - pd.Timedelta(days=1)).date():
                    bias = 1 if float(daily.loc[di, "close"]) > float(daily.loc[di, "open"]) else -1
                    break
        elif bias_mode == "none":
            bias = 0  # allow both

        # scan M15 before 05:00 NY for sweep + reclaim
        morning = g[g["ny"].dt.hour < 5]
        swept_bull = False
        swept_bear = False
        reclaim_bull_ts = None
        reclaim_bear_ts = None
        manip_low = quiet_low
        manip_high = quiet_high
        for ts, row in morning.iterrows():
            lo, hi, cl = float(row["low"]), float(row["high"]), float(row["close"])
            if lo < midnight_open and lo < quiet_low:
                swept_bull = True
                manip_low = min(manip_low, lo)
            if hi > midnight_open and hi > quiet_high:
                swept_bear = True
                manip_high = max(manip_high, hi)
            if swept_bull and cl > midnight_open and reclaim_bull_ts is None:
                reclaim_bull_ts = ts
            if swept_bear and cl < midnight_open and reclaim_bear_ts is None:
                reclaim_bear_ts = ts

        def _entry_after(reclaim_ts, side, extreme):
            # first quality signal bar on entry TF after reclaim, before 05:00 NY + 30m
            deadline = reclaim_ts + pd.Timedelta(minutes=30)
            # also hard stop at 05:00 NY
            ny_re = _ny(reclaim_ts)
            end_ny = ny_re.replace(hour=5, minute=0, second=0, microsecond=0)
            if end_ny <= ny_re:
                end_ny = end_ny + pd.Timedelta(days=1)
            end_utc = end_ny.tz_convert("UTC")
            deadline = min(deadline.tz_convert("UTC") if deadline.tzinfo else deadline,
                           end_utc)
            sub = ent[(ent.index > reclaim_ts) & (ent.index <= deadline)]
            atr_v = float(atr15.asof(reclaim_ts)) if reclaim_ts in atr15.index or True else 1.0
            try:
                atr_v = float(atr15.asof(reclaim_ts))
                if np.isnan(atr_v):
                    atr_v = 1.0
            except Exception:
                atr_v = 1.0
            for k in range(1, len(sub)):
                ts = sub.index[k]
                row = sub.iloc[k]
                prev = sub.iloc[k - 1]
                o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
                if side == "long":
                    if not (_bull_close_near_high(o, h, l, c, 0.5) and h > float(prev["high"])):
                        continue
                    entry = h + TICK
                    sl = min(extreme, l) - buf_atr * atr_v
                    if entry - sl > max_sl + 1e-9:
                        continue
                    tp = _rr("long", entry, sl, rr)
                    if tp is None:
                        continue
                    arm = bar_end(ts, bar)
                    v = f"judas_{entry_tf}_rr{rr:g}_{bias_mode}"
                    return _stop_order(arm, "long", entry, sl, tp, "Judas", v,
                                       {"reclaim": reclaim_ts, "midnight": midnight_open,
                                        "extreme": extreme}, bar)
                else:
                    if not (_bear_close_near_low(o, h, l, c, 0.5) and l < float(prev["low"])):
                        continue
                    entry = l - TICK
                    sl = max(extreme, h) + buf_atr * atr_v
                    if sl - entry > max_sl + 1e-9:
                        continue
                    tp = _rr("short", entry, sl, rr)
                    if tp is None:
                        continue
                    arm = bar_end(ts, bar)
                    v = f"judas_{entry_tf}_rr{rr:g}_{bias_mode}"
                    return _stop_order(arm, "short", entry, sl, tp, "Judas", v,
                                       {"reclaim": reclaim_ts, "midnight": midnight_open,
                                        "extreme": extreme}, bar)
            return None

        if reclaim_bull_ts is not None and bias >= 0:
            od = _entry_after(reclaim_bull_ts, "long", manip_low)
            if od:
                orders.append(od)
        if reclaim_bear_ts is not None and bias <= 0:
            od = _entry_after(reclaim_bear_ts, "short", manip_high)
            if od:
                orders.append(od)

    orders = dedupe_orders(orders, 60)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_judas_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, "h1_ema", False),
        ("M5", 2.0, "h1_ema", False),
        ("M5", 1.5, "h1_ema", True),
        ("M5", 1.5, "daily_close", False),
        ("M1", 1.5, "h1_ema", False),
    ]
    for tf, rr, bias, dxy_on in specs:
        oo = generate_judas(m1, dxy, dxy_on, tf, rr, bias)
        if not oo:
            # still register empty? skip
            continue
        tag = oo[0].variant + ("_dxy" if dxy_on else "")
        if dxy_on:
            oo = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                        tag, o.meta, o.expire_minutes, o.max_hold_minutes) for o in oo]
        pools[tag] = oo
    return pools
