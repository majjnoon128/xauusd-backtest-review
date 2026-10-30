"""AMD / PO3 + inverted FVG (iFVG) — ICT-style, closed-bar only.

Accumulation: Asian 00:00–07:00 UTC range, OR prior N M5 bars with low ATR.
Manipulation: wick/close sweep beyond one side during London (07–10) or NY (12–15) open.
Distribution: FVG formed in sweep direction, then price CLOSES through it opposite → iFVG.
Entry: market after inversion close, OR limit at inverted FVG edge (armed after close).
SL beyond manipulation extreme. TP: range opposite / 1:2 / 1:3.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, ema, resample_ohlc, bar_end, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, apply_htf_gate, dedupe_orders


def _find_fvgs(high, low, atr_arr, i_start, i_end, direction: str, min_atr=0.05):
    """Return list of (gap_lo, gap_hi, form_i) for 3-candle FVGs in [i_start, i_end].
    bullish FVG: low[k+2] > high[k]; bearish: high[k+2] < low[k].
    form_i = k+2 (last candle of the FVG pattern, known at close of that bar).
    """
    out = []
    for k in range(max(i_start, 0), max(i_end - 1, 0)):
        if k + 2 > i_end:
            break
        a = atr_arr[k + 2]
        if np.isnan(a) or a <= 0:
            continue
        if direction == "bull":
            gap = low[k + 2] - high[k]
            if gap >= min_atr * a:
                out.append((float(high[k]), float(low[k + 2]), k + 2))
        else:
            gap = low[k] - high[k + 2]
            if gap >= min_atr * a:
                out.append((float(high[k + 2]), float(low[k]), k + 2))
    return out


def _asian_ranges(m1: pd.DataFrame) -> dict:
    """Per UTC date: (range_high, range_low, end_ts) for 00:00–07:00 bars."""
    ranges = {}
    # group by date
    dates = m1.index.normalize().unique()
    for d in dates:
        mask = (m1.index >= d) & (m1.index < d + pd.Timedelta(hours=7))
        seg = m1.loc[mask]
        if len(seg) < 30:
            continue
        ranges[d] = (float(seg["high"].max()), float(seg["low"].min()),
                     d + pd.Timedelta(hours=7))
    return ranges


def generate_amd_po3_ifvg(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    use_vol: bool = False,
    use_htf: bool = False,
    range_mode: str = "asian",   # asian | m5_lowatr
    tf: str = "M5",              # M1 | M5 for FVG/inversion
    entry_mode: str = "market",  # market | limit
    tp_mode: str = "range",      # range | rr2 | rr3
    vol_mult: float = 1.3,
    m5_lookback: int = 24,
    low_atr_pct: float = 0.6,
) -> List[Order]:
    """Generate AMD+iFVG orders. One Order list for a single config combo."""
    m5 = resample_ohlc(m1, "5min")
    if tf == "M5":
        df = m5
        bar_min = 5
    else:
        df = m1
        bar_min = 1

    a = atr_prior(df, 14).values
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    volma = vol_ma(df["volume"], 20) if "volume" in df.columns else None
    m15 = resample_ohlc(m1, "15min")
    m15_ema = ema(m15["close"], 50)

    asian = _asian_ranges(m1) if range_mode == "asian" else {}
    m5_atr = atr_prior(m5, 14).values
    m5_h, m5_l = m5["high"].values, m5["low"].values
    m5_t = m5.index

    # London open 07–10 UTC, NY open 12–15 UTC
    manip_hours = set(range(7, 10)) | set(range(12, 15))

    orders: List[Order] = []
    # Track used days to avoid spam (one setup per range per side)
    used_keys = set()

    for i in range(40, n - 2):
        ts = times[i]
        h = ts.hour
        if h not in manip_hours:
            continue
        if ts.dayofweek >= 5:
            continue
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue

        # --- Accumulation range ---
        day0 = ts.normalize()
        if range_mode == "asian":
            # Use today's Asian if manipulation is same day after 07:00;
            # for NY window still use today's Asian.
            rng = asian.get(day0)
            if rng is None:
                continue
            rh, rl, rend = rng
            if ts < rend:
                continue  # range not finished
        else:
            # prior N M5 bars ending before current bar, with low ATR
            # map current df bar to m5 index
            mi = m5_t.searchsorted(ts, side="right") - 1
            if mi < m5_lookback + 5:
                continue
            window = slice(mi - m5_lookback, mi)
            atr_w = m5_atr[window]
            atr_w = atr_w[~np.isnan(atr_w)]
            if len(atr_w) < m5_lookback // 2:
                continue
            # require current prior ATR below percentile of recent
            # "low ATR" range: mean ATR of window < low_atr_pct * longer ATR
            longer = m5_atr[max(0, mi - 100):mi]
            longer = longer[~np.isnan(longer)]
            if len(longer) < 20:
                continue
            if float(np.mean(atr_w)) > low_atr_pct * float(np.mean(longer)):
                continue
            rh = float(m5_h[window].max())
            rl = float(m5_l[window].min())
            if rh - rl < 0.3 * atr_i:
                continue

        rng_size = rh - rl
        if rng_size < 0.5 * atr_i or rng_size > 8 * atr_i:
            continue

        # --- Manipulation: sweep beyond one side on THIS closed bar ---
        swept_high = (high[i] > rh) or (close[i] > rh)
        swept_low = (low[i] < rl) or (close[i] < rl)
        if swept_high and swept_low:
            continue  # both sides → skip
        if not swept_high and not swept_low:
            continue

        if swept_high:
            manip_side = "high"  # swept above → expect bearish distribution
            manip_extreme = float(high[i])
            fvg_dir = "bull"     # FVG formed in manipulation (up) direction
            trade_side = "short"
        else:
            manip_side = "low"
            manip_extreme = float(low[i])
            fvg_dir = "bear"
            trade_side = "long"

        key = (day0, manip_side, range_mode, tf)
        if key in used_keys:
            continue

        # Look for FVG formed in manip direction near/after sweep, then inversion
        # Search window: from a few bars before sweep to +12 bars after
        search_lo = max(0, i - 6)
        search_hi = min(n - 1, i + 12)
        fvgs = _find_fvgs(high, low, a, search_lo, search_hi, fvg_dir, min_atr=0.05)
        if not fvgs:
            continue

        # Prefer FVG whose form bar is at or after sweep-2
        fvgs = [f for f in fvgs if f[2] >= i - 2]
        if not fvgs:
            continue

        inverted = False
        for gap_lo, gap_hi, form_i in fvgs:
            # Inversion: price CLOSES through the FVG in opposite direction
            # For bullish FVG (gap_lo=high[k], gap_hi=low[k+2]): bearish inversion = close < gap_lo
            # For bearish FVG: bullish inversion = close > gap_hi
            for j in range(max(form_i + 1, i), min(form_i + 15, n)):
                if trade_side == "short":
                    # bearish inversion of bullish FVG
                    if close[j] < gap_lo:
                        inv_j = j
                        inv_gap_lo, inv_gap_hi = gap_lo, gap_hi
                        inverted = True
                        break
                else:
                    if close[j] > gap_hi:
                        inv_j = j
                        inv_gap_lo, inv_gap_hi = gap_lo, gap_hi
                        inverted = True
                        break
            if inverted:
                break
        if not inverted:
            continue

        # Session check on inversion bar
        inv_ts = times[inv_j]
        if inv_ts.dayofweek >= 5:
            continue
        # allow entry in London/NY broadly (07–21)
        if not (7 <= inv_ts.hour < 21):
            continue

        # SL beyond manip extreme
        buf = 0.05 * float(a[inv_j] if not np.isnan(a[inv_j]) else atr_i)
        if trade_side == "short":
            sl = manip_extreme + buf
            if entry_mode == "market":
                entry = float(close[inv_j])
                kind = "market"
            else:
                # limit at inverted FVG edge (top of bullish FVG = gap_hi side for short? 
                # sell limit at upper edge of inverted bullish FVG = gap_hi)
                entry = float(inv_gap_hi)
                kind = "limit"
            risk = sl - entry
            if risk <= 0.08:
                continue
            if tp_mode == "range":
                tp = rl  # opposite side of range
            elif tp_mode == "rr2":
                tp = entry - 2.0 * risk
            else:
                tp = entry - 3.0 * risk
            # if range TP is worse than entry (already past), skip or use rr
            if tp_mode == "range" and tp >= entry:
                tp = entry - 2.0 * risk
        else:
            sl = manip_extreme - buf
            if entry_mode == "market":
                entry = float(close[inv_j])
                kind = "market"
            else:
                entry = float(inv_gap_lo)
                kind = "limit"
            risk = entry - sl
            if risk <= 0.08:
                continue
            if tp_mode == "range":
                tp = rh
            elif tp_mode == "rr2":
                tp = entry + 2.0 * risk
            else:
                tp = entry + 3.0 * risk
            if tp_mode == "range" and tp <= entry:
                tp = entry + 2.0 * risk

        # risk sanity vs ATR
        atr_inv = float(a[inv_j]) if not np.isnan(a[inv_j]) else atr_i
        if risk > 4.0 * atr_inv or risk / max(entry, 1) > 0.015:
            continue

        arm = bar_end(inv_ts, bar_min)
        variant = f"{range_mode}_{tf}_{entry_mode}_{tp_mode}"
        if use_htf:
            variant += "_htf"
        orders.append(Order(
            arm_time=arm, side=trade_side, kind=kind, price=entry, sl=sl, tp=tp,
            strategy="AMD_PO3_iFVG", variant=variant,
            meta={"signal_bar": inv_ts, "range_hi": rh, "range_lo": rl,
                  "manip_extreme": manip_extreme},
            expire_minutes=90,
        ))
        used_keys.add(key)

    orders = dedupe_orders(orders, 60)
    if use_htf:
        orders = apply_htf_gate(orders, m15["close"], m15_ema, True)
    if use_vol and volma is not None:
        orders = apply_vol_gate(orders, df["volume"], volma, True, vol_mult, bar_min)
    return apply_dxy_gate(orders, dxy, use_dxy)
