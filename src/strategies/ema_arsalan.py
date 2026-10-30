"""Arsalan EMA setups on XAUUSD.

Mode 1 — sharp trend continuation:
  M1+EMA60 or M5+EMA20. Sharp = last N bars mostly one side of EMA, low body-overlap,
  EMA slope/ATR high, price displaced >k*ATR from EMA before pullback.
  Entry: limit at EMA on 1st touch (also 2nd/3rd). SL behind minor swing preceding pullback.
  TP 1R / 1.5R / 2R.

Mode 2 — weak trend reversal:
  EMA20 on M1 or M5. Weak = high avg body-overlap while still one-sided vs EMA.
  Entry: close of strong full-body candle (body>=body_frac*range, body>=x*ATR) that closes
  across EMA20 against the weak trend. SL beyond that candle. TP 1R / 2R.
  Filters: leaves FVG (3-candle gap); optional at 24h range extreme → use TP2 only variant.

Prop: all orders get min_hold_minutes=2 (engine defers SL/TP until ≥2 M1 bars).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, ema, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before, find_fvgs


def _body_overlap_frac(o, h, l, c, i) -> float:
    """Fraction of current body contained in prior bar's range. 0 if no body."""
    if i < 1:
        return 0.0
    body_lo, body_hi = min(float(o[i]), float(c[i])), max(float(o[i]), float(c[i]))
    if body_hi - body_lo < 1e-9:
        return 1.0  # doji → full overlap-ish
    prev_lo, prev_hi = float(l[i - 1]), float(h[i - 1])
    inter = max(0.0, min(body_hi, prev_hi) - max(body_lo, prev_lo))
    return inter / (body_hi - body_lo)


def _avg_overlap(o, h, l, c, i, n_bars) -> float:
    vals = [_body_overlap_frac(o, h, l, c, j) for j in range(i - n_bars + 1, i + 1) if j >= 1]
    return float(np.mean(vals)) if vals else 1.0


def _side_ratio(c, ema_v, i, n_bars, side: str) -> float:
    """Fraction of last n closes on trend side of EMA."""
    s = 0
    for j in range(i - n_bars + 1, i + 1):
        if side == "long" and c[j] > ema_v[j]:
            s += 1
        elif side == "short" and c[j] < ema_v[j]:
            s += 1
    return s / n_bars


def _ema_slope_atr(ema_v, atr_v, i, look=5) -> float:
    if i < look or np.isnan(atr_v[i]) or atr_v[i] <= 0:
        return 0.0
    return abs(ema_v[i] - ema_v[i - look]) / atr_v[i]


def _day_range(h, l, times, i, hours=24):
    t0 = times[i] - pd.Timedelta(hours=hours)
    j0 = times.searchsorted(t0, side="left")
    if j0 >= i:
        return None, None
    return float(np.max(h[j0:i + 1])), float(np.min(l[j0:i + 1]))


def generate_ema_arsalan_mode1(
    m1: pd.DataFrame,
    entry_tf: str = "M1",       # M1 | M5
    ema_len: int | None = None, # default 60 for M1, 20 for M5
    n_bars: int = 15,
    max_overlap: float = 0.45,
    min_side: float = 0.75,
    min_slope_atr: float = 0.15,
    min_disp_atr: float = 0.8,
    touch_max: int = 1,         # 1 | 2 | 3
    rr: float = 1.5,
    atr_buf: float = 0.1,
) -> List[Order]:
    bar_m = 1 if entry_tf == "M1" else 5
    ema_len = ema_len if ema_len is not None else (60 if entry_tf == "M1" else 20)
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, "5min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    e = ema(df["close"], ema_len).values
    shi, sli = swing_highs_lows(h, l, 2, 2)

    variant = f"arsalan_m1sharp_{entry_tf}_ema{ema_len}_n{n_bars}_ov{max_overlap}_t{touch_max}_rr{rr}"
    orders: List[Order] = []
    # track touches per sharp regime
    touch_count = 0
    regime_side = None
    regime_start = -1

    for i in range(max(ema_len + n_bars + 5, 40), n - 1):
        if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0 or np.isnan(e[i]):
            continue
        # Determine trend side from EMA slope
        slope = e[i] - e[i - 5]
        side = "long" if slope > 0 else "short"
        # Sharp checks on bar i-1 (closed context before pullback touch)
        j = i  # evaluate at current closed bar
        if _side_ratio(c, e, j, n_bars, side) < min_side:
            touch_count = 0; regime_side = None; continue
        if _avg_overlap(o, h, l, c, j, n_bars) > max_overlap:
            touch_count = 0; regime_side = None; continue
        if _ema_slope_atr(e, a, j) < min_slope_atr:
            touch_count = 0; regime_side = None; continue
        # Displacement: max distance from EMA in last n_bars > k*ATR
        disp = 0.0
        for k in range(j - n_bars + 1, j + 1):
            disp = max(disp, abs(c[k] - e[k]) / atr_v)
        if disp < min_disp_atr:
            touch_count = 0; regime_side = None; continue

        if regime_side != side:
            regime_side = side
            touch_count = 0
            regime_start = j

        # Pullback touch: price trades through EMA this bar (wick/body)
        touched = (l[j] <= e[j] <= h[j])
        if not touched:
            continue
        # First touch after displacement: require that a few bars ago price was away
        away = False
        for k in range(max(regime_start, j - n_bars), j):
            if side == "long" and c[k] > e[k] + min_disp_atr * 0.5 * atr_v:
                away = True; break
            if side == "short" and c[k] < e[k] - min_disp_atr * 0.5 * atr_v:
                away = True; break
        if not away:
            continue

        touch_count += 1
        if touch_count > touch_max:
            continue

        px = float(e[j])  # limit at EMA
        buf = max(atr_buf * atr_v, 0.10)
        if side == "long":
            sw = last_swing_before(sli, j)
            if sw is None:
                continue
            sl = float(l[sw]) - buf
            if sl >= px:
                sl = px - max(0.3 * atr_v, 0.25)
        else:
            sw = last_swing_before(shi, j)
            if sw is None:
                continue
            sl = float(h[sw]) + buf
            if sl <= px:
                sl = px + max(0.3 * atr_v, 0.25)
        risk = abs(px - sl)
        if risk < 0.20:
            continue
        tp = px + rr * risk if side == "long" else px - rr * risk
        arm = bar_end(times[j], bar_m)
        orders.append(Order(
            arm_time=arm, side=side, kind="limit", price=px, sl=float(sl), tp=float(tp),
            strategy="ArsalanEMA", variant=variant,
            meta={"mode": 1, "touch": touch_count, "ema": px},
            expire_minutes=30, max_hold_minutes=240, min_hold_minutes=2,
        ))

    return dedupe_orders(orders, 20)


def generate_ema_arsalan_mode2(
    m1: pd.DataFrame,
    entry_tf: str = "M1",       # M1 | M5
    ema_len: int = 20,
    n_bars: int = 15,
    min_overlap: float = 0.55,  # weak = high overlap
    min_side: float = 0.65,
    body_frac: float = 0.65,
    body_atr: float = 0.5,
    rr: float = 2.0,
    require_fvg: bool = True,
    range_extreme: bool = False,  # only take if signal near 24h high/low
    atr_buf: float = 0.05,
) -> List[Order]:
    bar_m = 1 if entry_tf == "M1" else 5
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, "5min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    e = ema(df["close"], ema_len).values

    tag_fvg = "fvg" if require_fvg else "nofvg"
    tag_rx = "rx" if range_extreme else "any"
    variant = f"arsalan_m2rev_{entry_tf}_ema{ema_len}_ov{min_overlap}_bf{body_frac}_rr{rr}_{tag_fvg}_{tag_rx}"
    orders: List[Order] = []

    for i in range(max(ema_len + n_bars + 5, 40), n - 1):
        if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0 or np.isnan(e[i]):
            continue
        # Weak trend direction (still one-sided but choppy)
        slope = e[i] - e[i - 5]
        weak_side = "long" if slope > 0 else "short"  # prevailing weak trend
        if _side_ratio(c, e, i, n_bars, weak_side) < min_side:
            continue
        if _avg_overlap(o, h, l, c, i, n_bars) < min_overlap:
            continue

        # Strong reversal candle closing across EMA against weak trend
        rng = h[i] - l[i]
        if rng < 1e-9:
            continue
        body = abs(c[i] - o[i])
        if body / rng < body_frac or body < body_atr * atr_v:
            continue

        if weak_side == "long":
            # against = short: bearish close across/below EMA
            if not (c[i] < o[i] and c[i] < e[i] and o[i] > e[i]):
                # also allow close below EMA from above
                if not (c[i] < o[i] and c[i] < e[i]):
                    continue
            side = "short"
        else:
            if not (c[i] > o[i] and c[i] > e[i]):
                continue
            side = "long"

        if require_fvg:
            # candle leaves FVG: 3-candle gap in signal direction ending at i
            fvgs = find_fvgs(h, l, a, max(i - 3, 0), i, "bear" if side == "short" else "bull", min_atr=0.05)
            if not fvgs or fvgs[-1][2] != i:
                # also accept FVG formed at i-1 or i
                if not fvgs:
                    continue
                if fvgs[-1][2] < i - 1:
                    continue

        if range_extreme:
            dh, dl = _day_range(h, l, times, i, 24)
            if dh is None:
                continue
            # signal near extreme of weak trend
            if weak_side == "long" and side == "short":
                if h[i] < dh - 0.15 * atr_v:
                    continue
            elif weak_side == "short" and side == "long":
                if l[i] > dl + 0.15 * atr_v:
                    continue
            else:
                continue

        px = float(c[i])
        buf = max(atr_buf * atr_v, 0.08)
        if side == "long":
            sl = float(l[i]) - buf
        else:
            sl = float(h[i]) + buf
        risk = abs(px - sl)
        if risk < 0.15:
            continue
        tp = px + rr * risk if side == "long" else px - rr * risk
        arm = bar_end(times[i], bar_m)
        orders.append(Order(
            arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
            strategy="ArsalanEMA", variant=variant,
            meta={"mode": 2, "weak_side": weak_side},
            expire_minutes=15, max_hold_minutes=180, min_hold_minutes=2,
        ))

    return dedupe_orders(orders, 25)


def generate_ema_arsalan_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    """Focused family grid for IS selection."""
    pools: Dict[str, List[Order]] = {}
    # Mode 1
    for tf, ema_len in (("M1", 60), ("M5", 20)):
        for n_bars, max_ov in ((12, 0.65), (18, 0.55)):
            for touch in (1, 3):
                for rr in (1.0, 1.5, 2.0):
                    print(f" M1sharp {tf} ema{ema_len} n{n_bars} ov{max_ov} t{touch} rr{rr}", flush=True)
                    oo = generate_ema_arsalan_mode1(
                        m1, entry_tf=tf, ema_len=ema_len, n_bars=n_bars,
                        max_overlap=max_ov, touch_max=touch, rr=rr,
                    )
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
    # Mode 2 (tighter body_atr on M1 to curb spam)
    for tf in ("M1", "M5"):
        for ov in (0.60, 0.70):
            for bf in (0.65, 0.75):
                for rr in (1.0, 2.0):
                    for fvg in (True, False):
                        for rx in (False, True):
                            if rx and rr != 2.0:
                                continue
                            bat = 0.8 if tf == "M1" else 0.5
                            print(f" M2rev {tf} ov{ov} bf{bf} rr{rr} fvg{fvg} rx{rx}", flush=True)
                            oo = generate_ema_arsalan_mode2(
                                m1, entry_tf=tf, min_overlap=ov, body_frac=bf,
                                body_atr=bat, rr=rr, require_fvg=fvg, range_extreme=rx,
                            )
                            if oo:
                                pools[oo[0].variant] = oo
                                print(f"  n={len(oo)}", flush=True)
    return pools
