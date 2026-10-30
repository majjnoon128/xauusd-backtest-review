"""Research batch-4: MTR (LH/HL), Climax+2nd, unified LiqRaid+M5 reclaim (PDH/PDL|EQH/EQL|Asia),
TTR Breakout Mode.

Faithful to /workspace/trading-research/batch-4.md.
Parent rule: Asia + EQH/EQL share a family with PDH/PDL — level_type is a pre-registered
parameter; count variants honestly for multiple-testing.
Priority: TTR BOM + Asia raid.
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


def _in_liq(ts, start_h=7, end_h=16) -> bool:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert("UTC")
    return t.dayofweek < 5 and start_h <= t.hour < end_h


def _ny(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("America/New_York")


def _utc(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC")


def _bull_q(o, h, l, c, frac=0.5):
    rng = h - l
    return rng > 0 and c > o and (c - l) / rng >= frac


def _bear_q(o, h, l, c, frac=0.5):
    rng = h - l
    return rng > 0 and c < o and (h - c) / rng >= frac


def _rr(side, entry, sl, rr):
    risk = abs(entry - sl)
    if risk < 1e-9:
        return None
    return entry + rr * risk if side == "long" else entry - rr * risk


def _stop(arm, side, entry, sl, tp, strategy, variant, meta, bar_m, hold=180):
    return Order(arm_time=arm, side=side, kind="stop", price=float(entry),
                 sl=float(sl), tp=float(tp), strategy=strategy, variant=variant,
                 meta=meta, expire_minutes=int(bar_m), max_hold_minutes=hold)


def _prev_day_hl(m1):
    daily = m1.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    out = {}
    dates = list(daily.index)
    for i in range(1, len(dates)):
        out[pd.Timestamp(dates[i]).normalize()] = (
            float(daily.loc[dates[i - 1], "high"]),
            float(daily.loc[dates[i - 1], "low"]),
        )
    return out



def _prev_week_hl(m1: pd.DataFrame) -> Dict[pd.Timestamp, Tuple[float, float]]:
    """Map each UTC Monday 00:00 (week start) -> (PWH, PWL) of prior Mon-Fri week."""
    # Use Friday-close weeks: group by ISO week
    df = m1.copy()
    # week_key = Monday of the week containing the bar
    idx = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
    mondays = (idx - pd.to_timedelta(idx.dayofweek, unit="D")).normalize()
    df = df.copy()
    df["_wk"] = mondays
    g = df.groupby("_wk").agg({"high": "max", "low": "min"})
    out = {}
    weeks = list(g.index)
    for i in range(1, len(weeks)):
        # map current week Monday -> prior week HL
        out[pd.Timestamp(weeks[i]).tz_convert("UTC").normalize() if hasattr(weeks[i], "tz_convert") else pd.Timestamp(weeks[i], tz="UTC").normalize()] = (
            float(g.loc[weeks[i - 1], "high"]),
            float(g.loc[weeks[i - 1], "low"]),
        )
    return out

def _adr(m1, lookback=14):
    daily = m1.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    rng = (daily["high"] - daily["low"]).astype(float)
    return rng.rolling(lookback, min_periods=5).mean().shift(1)  # prior ADR only


# ========== 1) MTR LH sell / HL buy only ==========
def generate_mtr_lhhl(
    m1, dxy=None, use_dxy=False, tf="M5", rr=2.0, max_risk=8.0,
    swing_w=3, session="liq",
) -> List[Order]:
    """LH MTR short / HL MTR long after trendline/MA break + lower-high / higher-low test."""
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    e20 = ema(df["close"].astype(float), 20).values
    times = df.index
    n = len(df)
    # fractal swings confirmed with right=swing_w (no lookahead: emit at i+swing_w)
    swings = []  # (confirm_i, pivot_i, price, 'H'|'L')
    for i in range(swing_w, n - swing_w):
        if all(h_a[i] >= h_a[i - j] for j in range(1, swing_w + 1)) and all(h_a[i] > h_a[i + j] for j in range(1, swing_w + 1)):
            swings.append((i + swing_w, i, float(h_a[i]), "H"))
        if all(l_a[i] <= l_a[i - j] for j in range(1, swing_w + 1)) and all(l_a[i] < l_a[i + j] for j in range(1, swing_w + 1)):
            swings.append((i + swing_w, i, float(l_a[i]), "L"))
    swings.sort(key=lambda x: x[0])

    orders = []
    # state machine
    bull_broke = False  # close below e20 after bullish structure
    bear_broke = False
    last_swing_h = None
    last_swing_l = None
    prior_swing_h = None
    prior_swing_l = None
    si = 0
    for i in range(40, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liq(ts):
            continue
        while si < len(swings) and swings[si][0] <= i:
            conf_i, piv_i, px, kind = swings[si]
            if kind == "H":
                prior_swing_h = last_swing_h
                last_swing_h = (piv_i, px)
            else:
                prior_swing_l = last_swing_l
                last_swing_l = (piv_i, px)
            si += 1
        if np.isnan(e20[i]):
            continue
        # detect structure break
        if last_swing_l is not None and prior_swing_l is not None:
            # bullish structure if last L > prior L
            if last_swing_l[1] > prior_swing_l[1] and c_a[i] < e20[i] and c_a[i - 1] >= e20[i - 1]:
                bull_broke = True
                bear_broke = False
        if last_swing_h is not None and prior_swing_h is not None:
            if last_swing_h[1] < prior_swing_h[1] and c_a[i] > e20[i] and c_a[i - 1] <= e20[i - 1]:
                bear_broke = True
                bull_broke = False

        # LH MTR sell: after bull_broke, a LH (last H < prior H) + bear signal
        if bull_broke and last_swing_h is not None and prior_swing_h is not None:
            if last_swing_h[1] < prior_swing_h[1] - 1e-12 and last_swing_h[0] >= i - 8:
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                if _bear_q(o, h, l, c, 0.5):
                    entry = l - TICK
                    sl = max(h, last_swing_h[1]) + TICK
                    if sl - entry <= max_risk + 1e-9 and sl > entry:
                        tp = _rr("short", entry, sl, rr)
                        if tp is not None:
                            arm = bar_end(ts, bar)
                            v = f"mtr_lhhl_{tf}_rr{rr:g}"
                            orders.append(_stop(arm, "short", entry, sl, tp, "MTR", v,
                                                {"signal_bar": ts, "kind": "LH"}, bar))
                            bull_broke = False  # consume

        # HL MTR buy
        if bear_broke and last_swing_l is not None and prior_swing_l is not None:
            if last_swing_l[1] > prior_swing_l[1] + 1e-12 and last_swing_l[0] >= i - 8:
                o, h, l, c = float(o_a[i]), float(h_a[i]), float(l_a[i]), float(c_a[i])
                if _bull_q(o, h, l, c, 0.5):
                    entry = h + TICK
                    sl = min(l, last_swing_l[1]) - TICK
                    if entry - sl <= max_risk + 1e-9 and entry > sl:
                        tp = _rr("long", entry, sl, rr)
                        if tp is not None:
                            arm = bar_end(ts, bar)
                            v = f"mtr_lhhl_{tf}_rr{rr:g}"
                            orders.append(_stop(arm, "long", entry, sl, tp, "MTR", v,
                                                {"signal_bar": ts, "kind": "HL"}, bar))
                            bear_broke = False

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_mtr_family(m1, dxy=None):
    pools = {}
    for tf, rr in [("M5", 2.0), ("M5", 1.5), ("M15", 2.0), ("M5", 2.5), ("M1", 2.0)]:
        oo = generate_mtr_lhhl(m1, dxy, False, tf, rr)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 2) Climax + 2nd entry fade ==========
def generate_climax_2nd(
    m1, dxy=None, use_dxy=False, tf="M5", rr=1.5, max_risk=8.0,
    lookback=20, min_trend_bars=20, second_within=10, atr_k=1.5, session="liq",
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    atr = atr_prior(df, 14).values
    times = df.index
    n = len(df)
    orders = []
    i = lookback + min_trend_bars
    while i < n - 3:
        ts = times[i]
        if ts.dayofweek >= 5 or (session == "liq" and not _in_liq(ts)):
            i += 1
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        body = abs(c_a[i] - o_a[i])
        rng = h_a[i] - l_a[i]
        # largest body in lookback?
        past_bodies = np.abs(c_a[i - lookback:i] - o_a[i - lookback:i])
        is_largest = body >= past_bodies.max() - 1e-12 and body >= atr_k * atr[i]
        if not is_largest or rng <= 0:
            i += 1
            continue
        # late in trend: count directional bars before
        if c_a[i] > o_a[i] and (c_a[i] - l_a[i]) / rng >= 0.6:
            # Buy climax
            up = sum(1 for j in range(i - min_trend_bars, i) if c_a[j] > o_a[j])
            if up < min_trend_bars * 0.55:
                i += 1
                continue
            climax_high, climax_low = float(h_a[i]), float(l_a[i])
            # first sell signal
            first = None
            for j in range(i + 1, min(i + 6, n - 1)):
                if _bear_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                    first = j
                    break
            if first is None:
                i += 1
                continue
            first_high = float(h_a[first])
            # invalidate if strong continuation above climax
            invalid = False
            for j in range(i + 1, first + 1):
                if c_a[j] > climax_high + atr[i]:
                    invalid = True
                    break
            if invalid:
                i += 1
                continue
            # second sell: high >= first_high (not better price) — Brooks: better price suspicious
            taken = False
            for j in range(first + 1, min(first + 1 + second_within, n - 1)):
                if c_a[j] > climax_high + 1.5 * atr[i]:
                    break
                if not _bear_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                    continue
                if float(h_a[j]) < first_high - 0.5:  # much better = suspicious trap
                    continue
                entry = float(l_a[j]) - TICK
                sl = max(float(h_a[j]), climax_high) + TICK
                if sl - entry > max_risk + 1e-9:
                    # try SL only behind signal
                    sl = float(h_a[j]) + TICK
                    if sl - entry > max_risk + 1e-9:
                        continue
                tp = _rr("short", entry, sl, rr)
                # also allow TP at climax_low test
                if tp is None:
                    continue
                arm = bar_end(times[j], bar)
                v = f"clx2_{tf}_rr{rr:g}_lb{lookback}"
                orders.append(_stop(arm, "short", entry, sl, tp, "CLX2", v,
                                    {"signal_bar": times[j], "climax": times[i], "first": times[first]}, bar))
                taken = True
                i = j + 2
                break
            if not taken:
                i += 1
            continue

        if c_a[i] < o_a[i] and (h_a[i] - c_a[i]) / rng >= 0.6:
            # Sell climax
            dn = sum(1 for j in range(i - min_trend_bars, i) if c_a[j] < o_a[j])
            if dn < min_trend_bars * 0.55:
                i += 1
                continue
            climax_high, climax_low = float(h_a[i]), float(l_a[i])
            first = None
            for j in range(i + 1, min(i + 6, n - 1)):
                if _bull_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                    first = j
                    break
            if first is None:
                i += 1
                continue
            first_low = float(l_a[first])
            invalid = False
            for j in range(i + 1, first + 1):
                if c_a[j] < climax_low - atr[i]:
                    invalid = True
                    break
            if invalid:
                i += 1
                continue
            taken = False
            for j in range(first + 1, min(first + 1 + second_within, n - 1)):
                if c_a[j] < climax_low - 1.5 * atr[i]:
                    break
                if not _bull_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                    continue
                if float(l_a[j]) > first_low + 0.5:
                    continue
                entry = float(h_a[j]) + TICK
                sl = min(float(l_a[j]), climax_low) - TICK
                if entry - sl > max_risk + 1e-9:
                    sl = float(l_a[j]) - TICK
                    if entry - sl > max_risk + 1e-9:
                        continue
                tp = _rr("long", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(times[j], bar)
                v = f"clx2_{tf}_rr{rr:g}_lb{lookback}"
                orders.append(_stop(arm, "long", entry, sl, tp, "CLX2", v,
                                    {"signal_bar": times[j], "climax": times[i], "first": times[first]}, bar))
                taken = True
                i = j + 2
                break
            if not taken:
                i += 1
            continue
        i += 1

    orders = dedupe_orders(orders, 25)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_climax_family(m1, dxy=None):
    pools = {}
    for tf, rr, lb in [("M5", 1.5, 20), ("M5", 2.0, 20), ("M5", 1.5, 30), ("M15", 2.0, 20), ("M1", 1.5, 20)]:
        oo = generate_climax_2nd(m1, dxy, False, tf, rr, 8.0, lb)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 3) Unified Liquidity Raid + M5 reclaim ==========
def generate_liq_raid(
    m1, dxy=None, use_dxy=False,
    level_type: str = "asia",  # pdh_pdl | eqh_eql | asia | pwh_pwl
    rr: float = 1.5,
    kz: str = "london",  # london | nyam | both | any — asia forces london
    max_risk: float = 8.0,
    require_htf_bias: bool = False,
    eq_tol: float = 1.0,
    eq_min_sep: int = 10,  # bars between EQ touches (M15)
    asia_adr_lo: float = 0.15,
    asia_adr_hi: float = 0.60,
) -> List[Order]:
    """Unified Turtle-Soup-style raid+reclaim. level_type is a pre-registered axis."""
    m5 = resample_ohlc(m1, "5min")
    h4 = resample_ohlc(m1, "240min")
    e20_h4 = ema(h4["close"].astype(float), 20).shift(1)
    c_h4 = h4["close"].astype(float).shift(1)
    adr = _adr(m1)
    pdhl = _prev_day_hl(m1) if level_type == "pdh_pdl" else None
    pwhl = _prev_week_hl(m1) if level_type == "pwh_pwl" else None

    o_a = m5["open"].astype(float).values
    h_a = m5["high"].astype(float).values
    l_a = m5["low"].astype(float).values
    c_a = m5["close"].astype(float).values
    times = m5.index
    n = len(m5)

    # Precompute Asia ranges per UTC date (fixed at 06:00 UTC start of London)
    asia_ranges = {}  # date -> (ash, asl, height)
    if level_type == "asia":
        # Asian window UTC 23:00 prev → 06:00
        for i in range(n):
            tu = _utc(times[i])
            if tu.hour == 6 and tu.minute == 0:
                # look back to 23:00 previous calendar day
                start = tu - pd.Timedelta(hours=7)  # 23:00
                # collect bars in [start, tu)
                j0 = int(m5.index.searchsorted(start, side="left"))
                j1 = i  # exclusive at 06:00 bar
                if j1 - j0 < 12:
                    continue
                ash = float(h_a[j0:j1].max())
                asl = float(l_a[j0:j1].min())
                asia_ranges[tu.normalize()] = (ash, asl, ash - asl)

    # EQH/EQL on M15
    eq_levels = []  # (ready_ts, level_hi, level_lo, side) side H/L
    if level_type == "eqh_eql":
        m15 = resample_ohlc(m1, "15min")
        hh = m15["high"].astype(float).values
        ll = m15["low"].astype(float).values
        tt = m15.index
        w = 2
        sh, sl = [], []
        for i in range(w, len(m15) - w):
            if all(hh[i] >= hh[i - j] for j in range(1, w + 1)) and all(hh[i] > hh[i + j] for j in range(1, w + 1)):
                sh.append((i + w, i, float(hh[i])))  # confirm, pivot, price
            if all(ll[i] <= ll[i - j] for j in range(1, w + 1)) and all(ll[i] < ll[i + j] for j in range(1, w + 1)):
                sl.append((i + w, i, float(ll[i])))
        for a in range(len(sh)):
            for b in range(a + 1, len(sh)):
                if sh[b][1] - sh[a][1] < eq_min_sep:
                    continue
                if abs(sh[a][2] - sh[b][2]) <= eq_tol:
                    ready = tt[sh[b][0]]
                    eq_levels.append((ready, max(sh[a][2], sh[b][2]), min(sh[a][2], sh[b][2]), "H"))
                    break
        for a in range(len(sl)):
            for b in range(a + 1, len(sl)):
                if sl[b][1] - sl[a][1] < eq_min_sep:
                    continue
                if abs(sl[a][2] - sl[b][2]) <= eq_tol:
                    ready = tt[sl[b][0]]
                    eq_levels.append((ready, max(sl[a][2], sl[b][2]), min(sl[a][2], sl[b][2]), "L"))
                    break
        eq_levels.sort(key=lambda x: x[0])

    def in_kz(ts, kz_mode):
        if level_type == "asia":
            kz_mode = "london"
        if kz_mode == "any":
            return ts.dayofweek < 5
        ny = _ny(ts)
        h = ny.hour + ny.minute / 60.0
        if kz_mode == "london":
            return 2.0 <= h < 5.0
        if kz_mode == "nyam":
            return 7.0 <= h < 10.0
        if kz_mode == "both":
            return (2.0 <= h < 5.0) or (7.0 <= h < 10.0)
        return False

    orders = []
    used = set()
    eq_ptr = 0
    active_eq = []  # currently valid EQ levels

    for i in range(1, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if not in_kz(ts, kz):
            continue
        tu = _utc(ts)
        day_key = tu.normalize()

        # resolve level(s) for this bar
        levels = []  # list of (hi, lo, tag, side_for_fade) side_for_fade: 'short' if raid highs
        if level_type == "pdh_pdl":
            hl = pdhl.get(day_key) if pdhl else None
            if hl:
                pdh, pdl = hl
                levels.append((pdh, pdh, "pdh", "short"))
                levels.append((pdl, pdl, "pdl", "long"))
        elif level_type == "pwh_pwl":
            wk = (tu - pd.Timedelta(days=int(tu.dayofweek))).normalize()
            hl = pwhl.get(wk) if pwhl else None
            if hl:
                pwh, pwl = hl
                levels.append((pwh, pwh, "pwh", "short"))
                levels.append((pwl, pwl, "pwl", "long"))
        elif level_type == "asia":
            ar = asia_ranges.get(day_key)
            if not ar:
                continue
            ash, asl, height = ar
            # ADR filter using prior ADR asof
            ad = adr.asof(ts) if len(adr) else np.nan
            if ad != ad or ad <= 0:
                continue
            if not (asia_adr_lo * ad <= height <= asia_adr_hi * ad):
                continue
            levels.append((ash, ash, "ash", "short"))
            levels.append((asl, asl, "asl", "long"))
        else:  # eqh_eql
            while eq_ptr < len(eq_levels) and eq_levels[eq_ptr][0] <= ts:
                active_eq.append(eq_levels[eq_ptr])
                eq_ptr += 1
            # keep recent
            active_eq = [e for e in active_eq if (ts - e[0]).total_seconds() < 5 * 86400]
            for ready, hi, lo, side in active_eq:
                if side == "H":
                    levels.append((hi, lo, "eqh", "short"))
                else:
                    levels.append((hi, lo, "eql", "long"))

        # HTF bias
        bias_long = bias_short = True
        if require_htf_bias:
            ec = e20_h4.asof(ts); cc = c_h4.asof(ts)
            if ec != ec or cc != cc:
                continue
            bias_long = bool(cc > ec)
            bias_short = bool(cc < ec)

        for lev_hi, lev_lo, tag, fade in levels:
            key = (day_key.date(), tag)
            if key in used:
                continue
            if fade == "short":
                if require_htf_bias and not bias_short:
                    continue
                traded = h_a[i] > lev_hi + 1e-12 or h_a[i - 1] > lev_hi + 1e-12
                reclaim = c_a[i] < lev_lo  # close back below band low
                if not (traded and reclaim):
                    continue
                raid_ext = float(max(h_a[max(0, i - 6):i + 1].max(), h_a[i]))
                entry = float(l_a[i]) - TICK
                sl = raid_ext + TICK
                if sl - entry > max_risk + 1e-9 or sl <= entry:
                    continue
                if c_a[i] > raid_ext:
                    continue
                tp = _rr("short", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, 5)
                v = f"liqraid_{level_type}_rr{rr:g}_kz{kz}" + ("_htf" if require_htf_bias else "")
                orders.append(_stop(arm, "short", entry, sl, tp, "LIQRAID", v,
                                    {"signal_bar": ts, "tag": tag, "level": lev_hi, "raid_ext": raid_ext}, 5))
                used.add(key)
            else:
                if require_htf_bias and not bias_long:
                    continue
                traded = l_a[i] < lev_lo - 1e-12 or l_a[i - 1] < lev_lo - 1e-12
                reclaim = c_a[i] > lev_hi
                if not (traded and reclaim):
                    continue
                raid_ext = float(min(l_a[max(0, i - 6):i + 1].min(), l_a[i]))
                entry = float(h_a[i]) + TICK
                sl = raid_ext - TICK
                if entry - sl > max_risk + 1e-9 or entry <= sl:
                    continue
                if c_a[i] < raid_ext:
                    continue
                tp = _rr("long", entry, sl, rr)
                if tp is None:
                    continue
                arm = bar_end(ts, 5)
                v = f"liqraid_{level_type}_rr{rr:g}_kz{kz}" + ("_htf" if require_htf_bias else "")
                orders.append(_stop(arm, "long", entry, sl, tp, "LIQRAID", v,
                                    {"signal_bar": ts, "tag": tag, "level": lev_lo, "raid_ext": raid_ext}, 5))
                used.add(key)

    orders = dedupe_orders(orders, 60)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_liq_raid_family(m1, dxy=None) -> Dict[str, List[Order]]:
    """Honest multiple-testing budget: each (level_type × params) is one counted variant.
    Prioritize asia; include eqh and pdh; ~5–7 explicit pre-registered variants.
    """
    pools = {}
    # Pre-registered list (do not expand ad-hoc):
    specs = [
        ("asia", 1.5, "london", False),      # priority
        ("asia", 2.0, "london", False),
        ("asia", 1.5, "london", True),
        ("eqh_eql", 1.5, "both", False),
        ("pdh_pdl", 1.5, "both", False),
        ("eqh_eql", 1.5, "london", False),
        ("pdh_pdl", 1.5, "any", False),
        ("pwh_pwl", 1.5, "both", False),    # batch-5 addition
        ("pwh_pwl", 1.5, "any", False),
        ("pwh_pwl", 2.0, "both", False),
    ]
    for lt, rr, kz, htf in specs:
        oo = generate_liq_raid(m1, dxy, False, lt, rr, kz, 8.0, htf)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 4) TTR → Breakout Mode ==========
def generate_ttr_bom(
    m1, dxy=None, use_dxy=False, tf="M5", rr_mode="mm",  # mm | 1.5 | 2.0
    n_bars=12, max_h=8.0, min_h=1.5, max_body_frac=0.40,
    with_trend=False, session="liq",
) -> List[Order]:
    bar = {"M1": 1, "M5": 5, "M15": 15}[tf]
    df = m1 if tf == "M1" else resample_ohlc(m1, f"{bar}min")
    o_a = df["open"].astype(float).values
    h_a = df["high"].astype(float).values
    l_a = df["low"].astype(float).values
    c_a = df["close"].astype(float).values
    e20 = ema(df["close"].astype(float), 20).values
    times = df.index
    n = len(df)
    orders = []
    last_i = -999

    for i in range(n_bars + 5, n - 1):
        ts = times[i]
        if ts.dayofweek >= 5:
            continue
        if session == "liq" and not _in_liq(ts):
            continue
        if i - last_i < n_bars // 2:
            continue
        a0 = i - n_bars + 1
        tr_h = float(h_a[a0:i + 1].max())
        tr_l = float(l_a[a0:i + 1].min())
        h = tr_h - tr_l
        if h > max_h + 1e-9 or h < min_h:
            continue
        bodies = np.abs(c_a[a0:i + 1] - o_a[a0:i + 1])
        ranges = np.maximum(h_a[a0:i + 1] - l_a[a0:i + 1], 1e-9)
        if float(np.mean(bodies / ranges)) > max_body_frac:
            continue
        # no 3 consecutive strong trend bars
        streak = 0
        bad = False
        for j in range(a0, i + 1):
            r = h_a[j] - l_a[j]
            if r > 0 and abs(c_a[j] - o_a[j]) / r >= 0.7 and r > 0.25 * h:
                streak += 1
                if streak >= 3:
                    bad = True
                    break
            else:
                streak = 0
        if bad:
            continue
        # typical bar filter: h >= 2 * median bar range
        med = float(np.median(ranges))
        if h < 2.0 * med:
            continue

        long_ok = short_ok = True
        if with_trend and not np.isnan(e20[i]):
            long_ok = c_a[i] > e20[i]
            short_ok = c_a[i] < e20[i]

        arm = bar_end(ts, bar)
        if rr_mode == "mm":
            # measured move ≈ h beyond edge → R ≈ 1.0 vs full-range SL
            rr = 1.0
            tag = "mm"
        else:
            rr = float(rr_mode)
            tag = f"rr{rr:g}"
        v = f"ttrbom_{tf}_{tag}_n{n_bars}" + ("_trend" if with_trend else "_bom")

        if long_ok:
            entry = tr_h + TICK
            sl = tr_l - TICK
            tp = _rr("long", entry, sl, rr)
            if tp is not None:
                orders.append(_stop(arm, "long", entry, sl, tp, "TTRBOM", v,
                                    {"signal_bar": ts, "tr_h": tr_h, "tr_l": tr_l, "h": h}, bar))
        if short_ok:
            entry = tr_l - TICK
            sl = tr_h + TICK
            tp = _rr("short", entry, sl, rr)
            if tp is not None:
                orders.append(_stop(arm, "short", entry, sl, tp, "TTRBOM", v,
                                    {"signal_bar": ts, "tr_h": tr_h, "tr_l": tr_l, "h": h}, bar))
        last_i = i

    orders = dedupe_orders(orders, max(10, n_bars))
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_ttr_bom_family(m1, dxy=None):
    pools = {}
    specs = [
        ("M5", "mm", 12, False),
        ("M5", 1.5, 12, False),
        ("M5", 2.0, 12, False),
        ("M5", "mm", 16, False),
        ("M5", "mm", 12, True),
        ("M1", "mm", 20, False),
    ]
    for tf, rrm, nb, trend in specs:
        oo = generate_ttr_bom(m1, dxy, False, tf, rrm, nb, 8.0, 1.5, 0.40, trend)
        if oo:
            pools[oo[0].variant] = oo
    # keep at most 6; parent said ~5 — trim largest-count extras if >6 by keeping first 5-6
    if len(pools) > 6:
        # prefer M5 variants first
        items = list(pools.items())
        pools = dict(items[:6])
    return pools
