"""Research batch-2 setups (Brooks MDB/MDT, Inside Bar, ii BOM, ICT Mitigation no-sweep, TR failed BO + 2nd).

Faithful to /workspace/trading-research/batch-2.md.
Rules:
- Stop entry 1 tick beyond signal/pattern; expire ≈ 1 bar
- SL beyond extreme (± tick); prop filter risk <= $8
- Closed-bar arm only (bar_end); no future confirmation / no lookahead
- NY times via America/New_York where needed; liquidity UTC 07–16 default
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


def _ny(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("America/New_York")


def _in_liquidity(ts: pd.Timestamp, start_h=7, end_h=16) -> bool:
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


def _is_inside(h, l, ph, pl, soft: bool = True) -> bool:
    if soft:
        return h <= ph + 1e-12 and l >= pl - 1e-12
    return h < ph - 1e-12 and l > pl + 1e-12


def _m15_ail_ais(m1: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """Always-In Long/Short from M15 EMA20 vs close, forward-filled to M1 index (closed-bar safe via shift)."""
    m15 = resample_ohlc(m1, "15min")
    e = ema(m15["close"].astype(float), 20)
    ail = (m15["close"].astype(float) > e).astype(float)
    ais = (m15["close"].astype(float) < e).astype(float)
    # shift 1 so value at m15 bar open reflects PRIOR closed m15 only when reindexed
    ail_s = ail.shift(1)
    ais_s = ais.shift(1)
    # reindex to m1 with ffill of prior closed
    ail_m1 = ail_s.reindex(m1.index, method="ffill")
    ais_m1 = ais_s.reindex(m1.index, method="ffill")
    return ail_m1, ais_m1


# ========== 1) Micro Double Bottom / Micro Double Top ==========
def generate_mdb_mdt(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 2.0,
    tol: float = 0.75,
    window: int = 4,
    entry_mode: str = "signal",  # signal | neck
    require_quality: bool = True,
    max_risk: float = 8.0,
    use_m15_bias: bool = True,
    session: str = "liq",
) -> List[Order]:
    """MDB/MDT over 2..window bars with |L1-L2|<=tol (or highs for MDT).

    No lookahead: pattern detected on closed bar i; arm at bar_end(i).
    Neck confirmation for 'neck' mode: signal bar itself closes/trades the neck
    (we require high[i] >= neck for long / low[i] <= neck for short on the signal bar).
    """
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    n = len(df)

    # M15 bias mapped via closed M15 only
    ail_m1, ais_m1 = _m15_ail_ais(m1) if use_m15_bias else (None, None)

    orders: List[Order] = []
    last_arm_i = -999

    for i in range(window + 2, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        if i - last_arm_i < 2:
            continue

        # --- scan for MDB ending at i (L2 at or near i) ---
        # find two local lows in [i-window+1, i]
        lo_idx = []
        for j in range(max(1, i - window + 1), i + 1):
            # local low: lower than neighbors inside window (simple trough)
            if l_a[j] <= l_a[j - 1] and (j == i or l_a[j] <= l_a[j + 1] if j + 1 <= i else True):
                # more strict: lowest of ±1 within available past/present
                left = l_a[j - 1]
                right = l_a[j + 1] if j + 1 <= i else l_a[j]
                if l_a[j] <= left and l_a[j] <= right:
                    lo_idx.append(j)
        # also allow the classic "two lows of bars" even if not fractal: pick two lowest distinct bars
        if len(lo_idx) < 2:
            # fallback: two bars with lows within tol, separated by ≥1 bar, neck in between
            cand = list(range(max(0, i - window + 1), i + 1))
            cand.sort(key=lambda j: l_a[j])
            if len(cand) >= 2:
                a, b = sorted([cand[0], cand[1]])
                if b > a and abs(l_a[a] - l_a[b]) <= tol + 1e-12:
                    lo_idx = [a, b]

        if len(lo_idx) >= 2:
            # take last two troughs
            a, b = lo_idx[-2], lo_idx[-1]
            if b > a and abs(l_a[a] - l_a[b]) <= tol + 1e-12 and b == i:
                neck = float(h_a[a:b + 1].max())
                pattern_low = float(min(l_a[a], l_a[b]))
                # signal bar = bar i (must be quality bull if required)
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                ok_q = (not require_quality) or _bull_close_near_high(o, h, l, c, 0.5)
                # context: optional M15 AIL
                bias_ok = True
                if use_m15_bias and ail_m1 is not None:
                    v = ail_m1.asof(ts)
                    bias_ok = bool(v == 1.0) if v == v else False
                if ok_q and bias_ok and neck > pattern_low:
                    if entry_mode == "neck":
                        # require signal bar traded/closed above neck (confirmation without future)
                        if h < neck - 1e-12:
                            pass
                        else:
                            entry = neck + TICK
                            sl = pattern_low - TICK
                            if entry - sl <= max_risk + 1e-9 and entry > sl:
                                tp = _rr("long", entry, sl, rr)
                                if tp is not None:
                                    arm = bar_end(ts, bar)
                                    vname = f"mdb_{tf}_rr{rr:g}_t{tol:g}_w{window}_{entry_mode}"
                                    if require_quality:
                                        vname += "_q"
                                    if use_m15_bias:
                                        vname += "_m15"
                                    orders.append(_stop_order(
                                        arm, "long", entry, sl, tp, "MDB", vname,
                                        {"signal_bar": ts, "neck": neck, "a": int(a), "b": int(b)}, bar,
                                    ))
                                    last_arm_i = i
                    else:
                        entry = h + TICK
                        sl = pattern_low - TICK
                        if entry - sl <= max_risk + 1e-9 and entry > sl:
                            tp = _rr("long", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(ts, bar)
                                vname = f"mdb_{tf}_rr{rr:g}_t{tol:g}_w{window}_{entry_mode}"
                                if require_quality:
                                    vname += "_q"
                                if use_m15_bias:
                                    vname += "_m15"
                                orders.append(_stop_order(
                                    arm, "long", entry, sl, tp, "MDB", vname,
                                    {"signal_bar": ts, "neck": neck, "a": int(a), "b": int(b)}, bar,
                                ))
                                last_arm_i = i

        # --- MDT mirror ---
        hi_idx = []
        for j in range(max(1, i - window + 1), i + 1):
            left = h_a[j - 1]
            right = h_a[j + 1] if j + 1 <= i else h_a[j]
            if h_a[j] >= left and h_a[j] >= right:
                hi_idx.append(j)
        if len(hi_idx) < 2:
            cand = list(range(max(0, i - window + 1), i + 1))
            cand.sort(key=lambda j: -h_a[j])
            if len(cand) >= 2:
                a, b = sorted([cand[0], cand[1]])
                if b > a and abs(h_a[a] - h_a[b]) <= tol + 1e-12:
                    hi_idx = [a, b]
        if len(hi_idx) >= 2 and i - last_arm_i >= 2:
            a, b = hi_idx[-2], hi_idx[-1]
            if b > a and abs(h_a[a] - h_a[b]) <= tol + 1e-12 and b == i:
                neck = float(l_a[a:b + 1].min())
                pattern_high = float(max(h_a[a], h_a[b]))
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                ok_q = (not require_quality) or _bear_close_near_low(o, h, l, c, 0.5)
                bias_ok = True
                if use_m15_bias and ais_m1 is not None:
                    v = ais_m1.asof(ts)
                    bias_ok = bool(v == 1.0) if v == v else False
                if ok_q and bias_ok and pattern_high > neck:
                    if entry_mode == "neck":
                        if l > neck + 1e-12:
                            pass
                        else:
                            entry = neck - TICK
                            sl = pattern_high + TICK
                            if sl - entry <= max_risk + 1e-9 and sl > entry:
                                tp = _rr("short", entry, sl, rr)
                                if tp is not None:
                                    arm = bar_end(ts, bar)
                                    vname = f"mdt_{tf}_rr{rr:g}_t{tol:g}_w{window}_{entry_mode}"
                                    if require_quality:
                                        vname += "_q"
                                    if use_m15_bias:
                                        vname += "_m15"
                                    # unify variant stem for family grouping: use mdbmdt_
                                    vname = vname.replace("mdt_", "mdbmdt_").replace("mdb_", "mdbmdt_")
                                    orders.append(_stop_order(
                                        arm, "short", entry, sl, tp, "MDBMDT", vname,
                                        {"signal_bar": ts, "neck": neck, "a": int(a), "b": int(b)}, bar,
                                    ))
                                    last_arm_i = i
                    else:
                        entry = l - TICK
                        sl = pattern_high + TICK
                        if sl - entry <= max_risk + 1e-9 and sl > entry:
                            tp = _rr("short", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(ts, bar)
                                vname = f"mdbmdt_{tf}_rr{rr:g}_t{tol:g}_w{window}_{entry_mode}"
                                if require_quality:
                                    vname += "_q"
                                if use_m15_bias:
                                    vname += "_m15"
                                orders.append(_stop_order(
                                    arm, "short", entry, sl, tp, "MDBMDT", vname,
                                    {"signal_bar": ts, "neck": neck, "a": int(a), "b": int(b)}, bar,
                                ))
                                last_arm_i = i
                                # also normalize long variant names already appended
    # normalize long variants to mdbmdt_ stem
    for o in orders:
        if o.variant.startswith("mdb_") and not o.variant.startswith("mdbmdt_"):
            o.variant = "mdbmdt_" + o.variant[len("mdb_"):]
        if o.variant.startswith("mdt_"):
            o.variant = "mdbmdt_" + o.variant[len("mdt_"):]
    orders = dedupe_orders(orders, {"M1": 5, "M5": 15, "M15": 30}.get(tf, 15))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_mdb_mdt_family(m1, dxy=None) -> Dict[str, List[Order]]:
    """~5 pre-registered high-frequency variants. Priority family."""
    pools = {}
    specs = [
        # tf, rr, tol, window, entry_mode, quality, m15, dxy
        ("M5", 2.0, 0.75, 4, "signal", True, True, False),
        ("M5", 2.0, 1.00, 4, "signal", True, True, False),
        ("M1", 2.0, 0.50, 4, "signal", True, True, False),
        ("M5", 1.5, 0.75, 3, "signal", True, False, False),
        ("M5", 2.0, 0.75, 4, "neck", True, True, False),
    ]
    for tf, rr, tol, w, em, q, m15, dxy_on in specs:
        oo = generate_mdb_mdt(m1, dxy, dxy_on, tf, rr, tol, w, em, q, 8.0, m15)
        if oo:
            # regroup by actual variant tag (all longs+shorts share stem)
            by_v: Dict[str, List[Order]] = {}
            for o in oo:
                by_v.setdefault(o.variant, []).append(o)
            for v, lst in by_v.items():
                pools[v] = lst
    # keep at most 5 distinct variants (prefer largest)
    if len(pools) > 5:
        ranked = sorted(pools.items(), key=lambda kv: -len(kv[1]))[:5]
        pools = dict(ranked)
    return pools


# ========== 2) Inside Bar (mother <= $8) trend-filtered ==========
def generate_inside_bar(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 2.0,
    soft: bool = True,
    max_mother: float = 8.0,
    sl_mode: str = "mother",  # mother | mid50
    trend: str = "ema20",  # ema20 | m15 | none
    bom: bool = False,  # if True, both sides (no trend); else with-trend only
    session: str = "liq",
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    e20 = ema(df["close"].astype(float), 20).values
    ail_m1, ais_m1 = _m15_ail_ais(m1) if trend == "m15" else (None, None)

    orders: List[Order] = []
    for i in range(25, len(df) - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        # mother = i-1, inside = i
        mh, ml = float(h_a[i - 1]), float(l_a[i - 1])
        ih, il = float(h_a[i]), float(l_a[i])
        if not _is_inside(ih, il, mh, ml, soft=soft):
            continue
        mother_range = mh - ml
        if mother_range <= 0:
            continue
        # prop filter
        if sl_mode == "mother":
            if mother_range > max_mother + 1e-9:
                continue
        else:
            # mid50: risk = half mother (+tick); must be <= max_mother
            if mother_range * 0.5 > max_mother + 1e-9:
                continue

        # trend bias
        long_ok = short_ok = True
        if not bom:
            if trend == "ema20":
                if np.isnan(e20[i]):
                    continue
                long_ok = c_a[i] > e20[i]
                short_ok = c_a[i] < e20[i]
            elif trend == "m15":
                va = ail_m1.asof(ts) if ail_m1 is not None else np.nan
                vb = ais_m1.asof(ts) if ais_m1 is not None else np.nan
                long_ok = bool(va == 1.0) if va == va else False
                short_ok = bool(vb == 1.0) if vb == vb else False

        arm = bar_end(ts, bar)
        v = f"ib_{tf}_rr{rr:g}_{'soft' if soft else 'hard'}_{sl_mode}_{trend}"
        if bom:
            v += "_bom"
        # long
        if long_ok or bom:
            entry = mh + TICK
            if sl_mode == "mother":
                sl = ml - TICK
            else:
                sl = (mh + ml) / 2.0
            if entry - sl <= max_mother + 1e-9 and entry > sl:
                tp = _rr("long", entry, sl, rr)
                if tp is not None:
                    orders.append(_stop_order(
                        arm, "long", entry, sl, tp, "IB", v,
                        {"signal_bar": ts, "mother_range": mother_range, "bom": bom}, bar,
                    ))
        # short
        if short_ok or bom:
            entry = ml - TICK
            if sl_mode == "mother":
                sl = mh + TICK
            else:
                sl = (mh + ml) / 2.0
            if sl - entry <= max_mother + 1e-9 and sl > entry:
                tp = _rr("short", entry, sl, rr)
                if tp is not None:
                    orders.append(_stop_order(
                        arm, "short", entry, sl, tp, "IB", v,
                        {"signal_bar": ts, "mother_range": mother_range, "bom": bom}, bar,
                    ))
    # For BOM pairs: engine will fill first; we keep both armed same bar (expire 1 bar).
    # Dedupe same side only.
    orders = dedupe_orders(orders, {"M1": 5, "M5": 10, "M15": 20}.get(tf, 10))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_inside_bar_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 2.0, True, "mother", "ema20", False),
        ("M5", 2.0, True, "mother", "m15", False),
        ("M5", 1.5, True, "mother", "ema20", False),
        ("M5", 2.0, False, "mother", "ema20", False),  # hard inside
        ("M5", 2.0, True, "mid50", "ema20", False),
    ]
    for tf, rr, soft, slm, tr, bom in specs:
        oo = generate_inside_bar(m1, dxy, False, tf, rr, soft, 8.0, slm, tr, bom)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 3) ii Breakout Mode ==========
def generate_ii_bom(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    soft: bool = True,
    max_height: float = 8.0,
    n_inside: int = 2,  # 2=ii, 3=iii
    with_trend_only: bool = False,
    session: str = "liq",
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    e20 = ema(df["close"].astype(float), 20).values
    orders: List[Order] = []

    for i in range(n_inside + 2, len(df) - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        # check last n_inside bars are each inside prior
        ok = True
        for k in range(i - n_inside + 1, i + 1):
            if not _is_inside(h_a[k], l_a[k], h_a[k - 1], l_a[k - 1], soft=soft):
                ok = False
                break
        if not ok:
            continue
        # pattern window = mother of first inside through last inside
        # mother of first inside is at i-n_inside
        start = i - n_inside  # mother
        end = i
        ph = float(h_a[start:end + 1].max())
        pl = float(l_a[start:end + 1].min())
        height = ph - pl
        if height <= 0 or height > max_height + 1e-9:
            continue

        long_ok = short_ok = True
        if with_trend_only:
            if np.isnan(e20[i]):
                continue
            long_ok = c_a[i] > e20[i]
            short_ok = c_a[i] < e20[i]

        arm = bar_end(ts, bar)
        tag = "ii" if n_inside == 2 else f"i{'i'*n_inside}"
        v = f"{tag}_{tf}_rr{rr:g}_{'soft' if soft else 'hard'}"
        if with_trend_only:
            v += "_trend"
        else:
            v += "_bom"

        if long_ok:
            entry = ph + TICK
            sl = pl - TICK
            if entry - sl <= max_height + 1e-9:
                tp = _rr("long", entry, sl, rr)
                if tp is not None:
                    orders.append(_stop_order(
                        arm, "long", entry, sl, tp, "II", v,
                        {"signal_bar": ts, "height": height, "n_inside": n_inside}, bar,
                    ))
        if short_ok:
            entry = pl - TICK
            sl = ph + TICK
            if sl - entry <= max_height + 1e-9:
                tp = _rr("short", entry, sl, rr)
                if tp is not None:
                    orders.append(_stop_order(
                        arm, "short", entry, sl, tp, "II", v,
                        {"signal_bar": ts, "height": height, "n_inside": n_inside}, bar,
                    ))
    orders = dedupe_orders(orders, {"M1": 5, "M5": 15, "M15": 30}.get(tf, 15))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_ii_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, True, 2, False),
        ("M5", 2.0, True, 2, False),
        ("M5", 1.5, True, 2, True),
        ("M5", 1.5, True, 3, False),  # iii
        ("M1", 1.5, True, 2, False),
    ]
    for tf, rr, soft, ni, trend in specs:
        oo = generate_ii_bom(m1, dxy, False, tf, rr, soft, 8.0, ni, trend)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 4) ICT Mitigation Block (NO sweep) ==========
def generate_mitigation(
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
    """Mitigation = failure swing (NO sweep of prior extreme) + body close beyond block distal + retest.

    Bullish path:
      - Identify bearish block = last down-close before a bullish displacement
      - Failure swing: new swing low is HIGHER than prior swing low (no sweep)
      - Body close above distal (high of bearish block) with displacement
      - Wait for retest into block range; M5 bull signal bar → buy stop above its high
      - Invalidate if body closes back below distal before entry
      - SL beyond block distal wick (low of block - tick); filter risk<=8
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

    orders: List[Order] = []

    # Precompute simple swing lows/highs on block TF (left=2,right=2) — confirmed only after right bars close
    left = right = 2
    swing_lows = []  # (idx, price) confirmed
    swing_highs = []
    for i in range(left, len(blk) - right):
        if all(l_b[i] <= l_b[i - j] for j in range(1, left + 1)) and all(l_b[i] < l_b[i + j] for j in range(1, right + 1)):
            swing_lows.append((i + right, i, float(l_b[i])))  # confirm_idx, pivot_idx, price
        if all(h_b[i] >= h_b[i - j] for j in range(1, left + 1)) and all(h_b[i] > h_b[i + j] for j in range(1, right + 1)):
            swing_highs.append((i + right, i, float(h_b[i])))

    # Scan for displacement + failure swing events on block TF
    # Event stored once confirmed; then search forward on entry TF for retest (no lookahead into event)
    events = []  # dicts
    for i in range(20, len(blk) - 1):
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

        # bullish displacement: close > open and large body
        if c_b[i] > o_b[i]:
            # find last down-close before i within lookback = bearish block
            blk_i = None
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if c_b[j] < o_b[j]:
                    blk_i = j
                    break
            if blk_i is None:
                continue
            distal_high = float(h_b[blk_i])  # must body-close above this
            distal_low = float(l_b[blk_i])   # SL beyond
            if c_b[i] <= distal_high:
                continue  # no body close beyond distal
            # failure swing: most recent confirmed swing low before i must be higher than prior swing low
            conf = [s for s in swing_lows if s[0] <= i]
            if len(conf) < 2:
                continue
            cur_sl = conf[-1]
            prev_sl = conf[-2]
            if cur_sl[2] >= prev_sl[2] - 1e-12:
                # higher low (or equal) → no sweep of old low
                # also ensure we did not trade below prev_sl between prev and now
                if float(l_b[prev_sl[1]:i + 1].min()) < prev_sl[2] - 1e-9:
                    continue  # swept → this is breaker territory, skip
                events.append({
                    "side": "long", "confirm_i": i, "confirm_ts": ts,
                    "blk_i": blk_i, "bh": distal_high, "bl": distal_low,
                    "bh_full": float(h_b[blk_i]), "bl_full": float(l_b[blk_i]),
                })
        # bearish displacement
        elif c_b[i] < o_b[i]:
            blk_i = None
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if c_b[j] > o_b[j]:
                    blk_i = j
                    break
            if blk_i is None:
                continue
            distal_low = float(l_b[blk_i])
            distal_high = float(h_b[blk_i])
            if c_b[i] >= distal_low:
                continue
            conf = [s for s in swing_highs if s[0] <= i]
            if len(conf) < 2:
                continue
            cur_sh = conf[-1]
            prev_sh = conf[-2]
            if cur_sh[2] <= prev_sh[2] + 1e-12:
                if float(h_b[prev_sh[1]:i + 1].max()) > prev_sh[2] + 1e-9:
                    continue  # swept
                events.append({
                    "side": "short", "confirm_i": i, "confirm_ts": ts,
                    "blk_i": blk_i, "bh": distal_high, "bl": distal_low,
                    "bh_full": float(h_b[blk_i]), "bl_full": float(l_b[blk_i]),
                })

    # For each event, search entry TF after confirm for retest + signal bar
    # Map confirm_ts → entry index
    for ev in events:
        conf_ts = ev["confirm_ts"]
        # first entry bar strictly after confirm bar end
        after = bar_end(conf_ts, bar_b)
        j0 = int(t_e.searchsorted(after, side="left"))
        bh, bl = ev["bh_full"], ev["bl_full"]
        side = ev["side"]
        invalidated = False
        armed = False
        for j in range(j0, min(j0 + 40, len(ent) - 1)):  # retest window ~40 entry bars
            ts = t_e[j]
            if ts.dayofweek >= 5:
                continue
            if session == "liq" and not _in_liquidity(ts):
                continue
            # invalidation: body closes back beyond distal opposite
            if side == "long" and c_e[j] < bl:
                invalidated = True
                break
            if side == "short" and c_e[j] > bh:
                invalidated = True
                break
            # retest: price trades into block range
            in_block = (l_e[j] <= bh and h_e[j] >= bl)
            if not in_block:
                continue
            o, h, l, c = float(o_e[j]), float(h_e[j]), float(l_e[j]), float(c_e[j])
            if side == "long":
                if not _bull_close_near_high(o, h, l, c, 0.5):
                    continue
                entry = h + TICK
                sl = bl - TICK
                if entry - sl > max_risk + 1e-9 or entry <= sl:
                    continue
                tp = _rr("long", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, bar_e)
                v = f"mit_{tf_block}_{tf_entry}_rr{rr:g}_k{disp_atr_k:g}"
                orders.append(_stop_order(
                    arm, "long", entry, sl, tp, "MIT", v,
                    {"signal_bar": ts, "block_ts": t_b[ev["blk_i"]], "confirm": conf_ts}, bar_e,
                ))
                armed = True
                break
            else:
                if not _bear_close_near_low(o, h, l, c, 0.5):
                    continue
                entry = l - TICK
                sl = bh + TICK
                if sl - entry > max_risk + 1e-9 or sl <= entry:
                    continue
                tp = _rr("short", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, bar_e)
                v = f"mit_{tf_block}_{tf_entry}_rr{rr:g}_k{disp_atr_k:g}"
                orders.append(_stop_order(
                    arm, "short", entry, sl, tp, "MIT", v,
                    {"signal_bar": ts, "block_ts": t_b[ev["blk_i"]], "confirm": conf_ts}, bar_e,
                ))
                armed = True
                break
        _ = invalidated, armed

    orders = dedupe_orders(orders, 20)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_mitigation_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", "M5", 1.5, 1.0),
        ("M5", "M5", 2.0, 1.0),
        ("M5", "M1", 1.5, 1.0),
        ("M15", "M5", 1.5, 1.0),
        ("M5", "M5", 1.5, 0.75),
    ]
    for tb, te, rr, k in specs:
        oo = generate_mitigation(m1, dxy, False, tb, te, rr, k, 8.0)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 5) Trading Range Extreme — failed BO + 2nd signal ==========
def generate_tr_failed_bo(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 1.5,
    tr_len: int = 24,
    min_reversals: int = 3,
    max_body_frac: float = 0.45,
    fail_within: int = 5,
    second_within: int = 8,
    max_sig_range: float = 8.0,
    prefer_mdb: bool = True,
    session: str = "liq",
) -> List[Order]:
    """TR phase on M5: limited range, many reversals, small bodies.
    Failed BO above TR_high → mark 1st sell signal → take 2nd sell signal (often MDT).
    Mirror for long at TR_low.
    """
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    n = len(df)
    orders: List[Order] = []

    def is_tr(i) -> Tuple[bool, float, float]:
        a0 = i - tr_len + 1
        if a0 < 1:
            return False, 0.0, 0.0
        hh = float(h_a[a0:i + 1].max())
        ll = float(l_a[a0:i + 1].min())
        rng = hh - ll
        if rng < 2.0 or rng > 40.0:
            return False, hh, ll
        # body fraction
        bodies = np.abs(c_a[a0:i + 1] - o_a[a0:i + 1])
        ranges = h_a[a0:i + 1] - l_a[a0:i + 1]
        ranges = np.where(ranges <= 0, np.nan, ranges)
        frac = np.nanmean(bodies / ranges)
        if not (frac == frac) or frac > max_body_frac:
            return False, hh, ll
        # reversals: count direction changes of close
        d = np.sign(np.diff(c_a[a0:i + 1]))
        d = d[d != 0]
        rev = int(np.sum(d[1:] * d[:-1] < 0)) if len(d) > 1 else 0
        if rev < min_reversals:
            return False, hh, ll
        # avoid strong trend: no 3 consecutive large trend bars
        big = 0
        for j in range(a0, i + 1):
            r = h_a[j] - l_a[j]
            if r > 0 and abs(c_a[j] - o_a[j]) / r >= 0.7 and r > 0.15 * rng:
                big += 1
                if big >= 3:
                    return False, hh, ll
            else:
                big = 0
        return True, hh, ll

    i = tr_len + 5
    while i < n - 3:
        ts = times[i]
        if ts.dayofweek >= 5 or (session == "liq" and not _in_liquidity(ts)):
            i += 1
            continue
        ok, tr_h, tr_l = is_tr(i)
        if not ok:
            i += 1
            continue

        # look for BO fail in next fail_within bars AFTER i (TR defined on closed bars through i)
        found = False
        for k in range(1, fail_within + 1):
            j = i + k
            if j >= n - 2:
                break
            # failed BO high: trade above tr_h then close back inside
            if h_a[j] > tr_h + 1e-12 and c_a[j] < tr_h and c_a[j] > tr_l:
                bo_extreme = float(h_a[j])
                # first sell signal = first bearish bar after/at j
                first_sig = None
                for s in range(j, min(j + 3, n - 1)):
                    if c_a[s] < o_a[s]:
                        first_sig = s
                        break
                if first_sig is None:
                    continue
                # second sell signal within second_within
                for s2 in range(first_sig + 1, min(first_sig + 1 + second_within, n - 1)):
                    o, h, l, c = float(o_a[s2]), float(h_a[s2]), float(l_a[s2]), float(c_a[s2])
                    if not _bear_close_near_low(o, h, l, c, 0.5):
                        continue
                    # optional micro-DT flavour: high near a recent high within 3 bars
                    if prefer_mdb:
                        recent_hi = float(h_a[max(0, s2 - 3):s2 + 1].max())
                        if h < recent_hi - 1.5:  # not near extreme — still allow but softer
                            pass
                    sig_range = h - l
                    # SL preference: behind signal if <=8 else behind BO extreme if that fits
                    entry = l - TICK
                    sl_sig = h + TICK
                    sl_bo = bo_extreme + TICK
                    if sl_sig - entry <= max_sig_range + 1e-9:
                        sl = sl_sig
                    elif sl_bo - entry <= max_sig_range + 1e-9:
                        sl = sl_bo
                    else:
                        continue
                    tp = _rr("short", entry, sl, rr)
                    if tp is None:
                        continue
                    # Always-In strong against fade? skip if 2 big bull bars after fail
                    strong_against = False
                    for t in range(j + 1, s2 + 1):
                        r = h_a[t] - l_a[t]
                        if r > 0 and c_a[t] > o_a[t] and (c_a[t] - l_a[t]) / r >= 0.7 and r > 0.3 * (tr_h - tr_l):
                            strong_against = True
                            break
                    if strong_against:
                        break
                    arm = bar_end(times[s2], bar)
                    v = f"trfbo_{tf}_rr{rr:g}_n{tr_len}"
                    orders.append(_stop_order(
                        arm, "short", entry, sl, tp, "TRFBO", v,
                        {"signal_bar": times[s2], "tr_h": tr_h, "tr_l": tr_l, "bo": bo_extreme,
                         "first_sig": times[first_sig]}, bar,
                    ))
                    found = True
                    i = s2 + 2
                    break
                if found:
                    break
            # failed BO low
            if l_a[j] < tr_l - 1e-12 and c_a[j] > tr_l and c_a[j] < tr_h:
                bo_extreme = float(l_a[j])
                first_sig = None
                for s in range(j, min(j + 3, n - 1)):
                    if c_a[s] > o_a[s]:
                        first_sig = s
                        break
                if first_sig is None:
                    continue
                for s2 in range(first_sig + 1, min(first_sig + 1 + second_within, n - 1)):
                    o, h, l, c = float(o_a[s2]), float(h_a[s2]), float(l_a[s2]), float(c_a[s2])
                    if not _bull_close_near_high(o, h, l, c, 0.5):
                        continue
                    entry = h + TICK
                    sl_sig = l - TICK
                    sl_bo = bo_extreme - TICK
                    if entry - sl_sig <= max_sig_range + 1e-9:
                        sl = sl_sig
                    elif entry - sl_bo <= max_sig_range + 1e-9:
                        sl = sl_bo
                    else:
                        continue
                    tp = _rr("long", entry, sl, rr)
                    if tp is None:
                        continue
                    strong_against = False
                    for t in range(j + 1, s2 + 1):
                        r = h_a[t] - l_a[t]
                        if r > 0 and c_a[t] < o_a[t] and (h_a[t] - c_a[t]) / r >= 0.7 and r > 0.3 * (tr_h - tr_l):
                            strong_against = True
                            break
                    if strong_against:
                        break
                    arm = bar_end(times[s2], bar)
                    v = f"trfbo_{tf}_rr{rr:g}_n{tr_len}"
                    orders.append(_stop_order(
                        arm, "long", entry, sl, tp, "TRFBO", v,
                        {"signal_bar": times[s2], "tr_h": tr_h, "tr_l": tr_l, "bo": bo_extreme,
                         "first_sig": times[first_sig]}, bar,
                    ))
                    found = True
                    i = s2 + 2
                    break
                if found:
                    break
        if not found:
            i += 1

    orders = dedupe_orders(orders, {"M1": 10, "M5": 20, "M15": 40}.get(tf, 20))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_tr_failed_bo_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    specs = [
        ("M5", 1.5, 24, True),
        ("M5", 2.0, 24, True),
        ("M5", 1.5, 30, True),
        ("M5", 1.5, 20, False),
        ("M1", 1.5, 40, True),
    ]
    for tf, rr, nlen, pref in specs:
        oo = generate_tr_failed_bo(m1, dxy, False, tf, rr, nlen, prefer_mdb=pref)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 1b) MDB/MDT after strong opposing leg (Brooks 2nd-entry) ==========
def generate_mdb_strongleg(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    tf: str = "M5",
    rr: float = 2.0,
    tol: float = 0.75,
    window: int = 4,
    strong_bars: int = 3,
    max_risk: float = 8.0,
    session: str = "liq",
) -> List[Order]:
    """Only take MDB after a strong bear leg (body-heavy down bars), MDT after strong bull leg."""
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    times = df.index
    atr = atr_prior(df, 14).values
    orders: List[Order] = []
    last_i = -999
    for i in range(window + strong_bars + 5, len(df) - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liquidity(ts):
            continue
        if i - last_i < 3:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        # strong bear leg just before window?
        bear_strong = 0
        for j in range(i - window - strong_bars, i - window + 1):
            if j < 1:
                continue
            r = h_a[j] - l_a[j]
            if r > 0 and c_a[j] < o_a[j] and (h_a[j] - c_a[j]) / r >= 0.6 and r >= 0.8 * atr[j]:
                bear_strong += 1
        bull_strong = 0
        for j in range(i - window - strong_bars, i - window + 1):
            if j < 1:
                continue
            r = h_a[j] - l_a[j]
            if r > 0 and c_a[j] > o_a[j] and (c_a[j] - l_a[j]) / r >= 0.6 and r >= 0.8 * atr[j]:
                bull_strong += 1
        # MDB: need bear_strong >= 2, two lows ending at i
        if bear_strong >= 2:
            cand = list(range(max(0, i - window + 1), i + 1))
            cand.sort(key=lambda j: l_a[j])
            if len(cand) >= 2:
                a, b = sorted([cand[0], cand[1]])
                if b == i and b > a and abs(l_a[a] - l_a[b]) <= tol + 1e-12:
                    o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                    if _bull_close_near_high(o, h, l, c, 0.6):
                        pattern_low = float(min(l_a[a], l_a[b]))
                        entry = h + TICK
                        sl = pattern_low - TICK
                        if entry - sl <= max_risk + 1e-9 and entry > sl:
                            tp = _rr("long", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(ts, bar)
                                v = f"mdb_sl_{tf}_rr{rr:g}_t{tol:g}"
                                orders.append(_stop_order(
                                    arm, "long", entry, sl, tp, "MDBSL", v,
                                    {"signal_bar": ts, "a": int(a), "b": int(b)}, bar,
                                ))
                                last_i = i
        if bull_strong >= 2 and i - last_i >= 3:
            cand = list(range(max(0, i - window + 1), i + 1))
            cand.sort(key=lambda j: -h_a[j])
            if len(cand) >= 2:
                a, b = sorted([cand[0], cand[1]])
                if b == i and b > a and abs(h_a[a] - h_a[b]) <= tol + 1e-12:
                    o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                    if _bear_close_near_low(o, h, l, c, 0.6):
                        pattern_high = float(max(h_a[a], h_a[b]))
                        entry = l - TICK
                        sl = pattern_high + TICK
                        if sl - entry <= max_risk + 1e-9 and sl > entry:
                            tp = _rr("short", entry, sl, rr)
                            if tp is not None:
                                arm = bar_end(ts, bar)
                                v = f"mdb_sl_{tf}_rr{rr:g}_t{tol:g}"
                                orders.append(_stop_order(
                                    arm, "short", entry, sl, tp, "MDBSL", v,
                                    {"signal_bar": ts, "a": int(a), "b": int(b)}, bar,
                                ))
                                last_i = i
    orders = dedupe_orders(orders, 15)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_mdb_strongleg_family(m1, dxy=None) -> Dict[str, List[Order]]:
    pools = {}
    for tf, rr, tol in [("M5", 2.0, 0.75), ("M5", 1.5, 0.75), ("M5", 2.0, 1.0), ("M1", 2.0, 0.5), ("M5", 2.0, 0.5)]:
        oo = generate_mdb_strongleg(m1, dxy, False, tf, rr, tol)
        if oo:
            pools[oo[0].variant] = oo
    return pools
