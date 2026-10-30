"""Research batch-5 (final setups): Raw OB first retest, M15 full DB/DT, PWH via LiqRaid.
Faithful to /workspace/trading-research/batch-5.md. Setup catalog CLOSED after this.
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
from strategies.research_batch4 import generate_liq_raid

TICK = 0.01


def _in_liq(ts, start_h=7, end_h=16):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert("UTC")
    return t.dayofweek < 5 and start_h <= t.hour < end_h


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


# ========== 1) Raw OB first retest (unmitigated) ==========
def generate_raw_ob(
    m1, dxy=None, use_dxy=False,
    tf_block="M15", tf_entry="M5",
    rr=1.5, disp_atr_k=1.0, max_risk=8.0,
    entry_mode="signal",  # signal | proximal | mean
    lookback_ob=5, session="liq",
) -> List[Order]:
    """Untouched OB: last opposite candle before displacement+BOS; first retest only.
    Invalid if body closes beyond distal before entry (then it's breaker/mitigation territory).
    """
    bar_b = {"M5": 5, "M15": 15, "M1": 1}[tf_block]
    bar_e = {"M5": 5, "M15": 15, "M1": 1}[tf_entry]
    blk = m1 if tf_block == "M1" else resample_ohlc(m1, f"{bar_b}min")
    ent = m1 if tf_entry == "M1" else resample_ohlc(m1, f"{bar_e}min")
    atr = atr_prior(blk, 14).values
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
    swing_h, swing_l = [], []
    for i in range(left, len(blk) - right):
        if all(h_b[i] >= h_b[i - j] for j in range(1, left + 1)) and all(h_b[i] > h_b[i + j] for j in range(1, right + 1)):
            swing_h.append((i + right, i, float(h_b[i])))
        if all(l_b[i] <= l_b[i - j] for j in range(1, left + 1)) and all(l_b[i] < l_b[i + j] for j in range(1, right + 1)):
            swing_l.append((i + right, i, float(l_b[i])))

    # Form OBs on displacement+BOS; track untouched
    obs = []  # dicts
    for i in range(30, len(blk) - 1):
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        body = abs(c_b[i] - o_b[i])
        if body < disp_atr_k * atr[i]:
            continue
        conf_h = [s for s in swing_h if s[0] <= i]
        conf_l = [s for s in swing_l if s[0] <= i]
        # bullish BOS: close > prior swing high
        if c_b[i] > o_b[i] and conf_h:
            prior_sh = conf_h[-1][2]
            if c_b[i] > prior_sh:
                # last down-close within lookback
                ob_i = None
                for j in range(i - 1, max(0, i - lookback_ob) - 1, -1):
                    if c_b[j] < o_b[j]:
                        ob_i = j
                        break
                if ob_i is None:
                    continue
                proximal = float(o_b[ob_i])  # open
                distal = float(l_b[ob_i])
                mean = (float(o_b[ob_i]) + float(c_b[ob_i])) / 2.0
                obs.append({
                    "side": "long", "form_i": i, "form_ts": t_b[i], "ob_i": ob_i,
                    "proximal": proximal, "distal": distal, "mean": mean,
                    "touched": False, "dead": False,
                })
        # bearish BOS
        if c_b[i] < o_b[i] and conf_l:
            prior_sl = conf_l[-1][2]
            if c_b[i] < prior_sl:
                ob_i = None
                for j in range(i - 1, max(0, i - lookback_ob) - 1, -1):
                    if c_b[j] > o_b[j]:
                        ob_i = j
                        break
                if ob_i is None:
                    continue
                proximal = float(o_b[ob_i])
                distal = float(h_b[ob_i])
                mean = (float(o_b[ob_i]) + float(c_b[ob_i])) / 2.0
                obs.append({
                    "side": "short", "form_i": i, "form_ts": t_b[i], "ob_i": ob_i,
                    "proximal": proximal, "distal": distal, "mean": mean,
                    "touched": False, "dead": False,
                })

    orders = []
    for ob in obs:
        after = bar_end(ob["form_ts"], bar_b)
        j0 = int(t_e.searchsorted(after, side="left"))
        side = ob["side"]
        prox, dist, mean = ob["proximal"], ob["distal"], ob["mean"]
        for j in range(j0, min(j0 + 80, len(ent) - 1)):
            ts = t_e[j]
            if ts.dayofweek >= 5:
                continue
            if session == "liq" and not _in_liq(ts):
                continue
            # invalidation: body beyond distal
            if side == "long" and c_e[j] < dist:
                ob["dead"] = True
                break
            if side == "short" and c_e[j] > dist:
                ob["dead"] = True
                break
            # zone touch
            if side == "long":
                in_zone = l_e[j] <= prox and h_e[j] >= dist
            else:
                in_zone = h_e[j] >= prox and l_e[j] <= dist
            if not in_zone:
                continue
            if ob["touched"]:
                # hard version: reject second touch
                break
            ob["touched"] = True
            o, h, l, c = float(o_e[j]), float(h_e[j]), float(l_e[j]), float(c_e[j])
            if entry_mode == "signal":
                if side == "long":
                    if not _bull_q(o, h, l, c, 0.5):
                        continue
                    # prefer close above mean
                    if c < mean:
                        continue
                    entry = h + TICK
                    sl = dist - TICK
                else:
                    if not _bear_q(o, h, l, c, 0.5):
                        continue
                    if c > mean:
                        continue
                    entry = l - TICK
                    sl = dist + TICK
            elif entry_mode == "proximal":
                if side == "long":
                    entry = prox + TICK
                    sl = dist - TICK
                else:
                    entry = prox - TICK
                    sl = dist + TICK
            else:  # mean
                if side == "long":
                    entry = mean + TICK
                    sl = dist - TICK
                else:
                    entry = mean - TICK
                    sl = dist + TICK
            if abs(entry - sl) > max_risk + 1e-9:
                continue
            if (side == "long" and entry <= sl) or (side == "short" and sl <= entry):
                continue
            tp = _rr(side, entry, sl, rr)
            if tp is None:
                continue
            arm = bar_end(ts, bar_e)
            v = f"rawob_{tf_block}_{tf_entry}_rr{rr:g}_{entry_mode}_k{disp_atr_k:g}"
            orders.append(_stop(arm, side, entry, sl, tp, "RAWOB", v,
                                {"signal_bar": ts, "form": ob["form_ts"], "mode": entry_mode}, bar_e))
            break  # first retest only

    orders = dedupe_orders(orders, 30)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_raw_ob_family(m1, dxy=None):
    pools = {}
    specs = [
        ("M15", "M5", 1.5, "signal", 1.0),
        ("M15", "M5", 2.0, "signal", 1.0),
        ("M15", "M5", 1.5, "mean", 1.0),
        ("M15", "M1", 1.5, "signal", 1.0),
        ("M5", "M5", 1.5, "signal", 1.0),
    ]
    for tb, te, rr, em, k in specs:
        oo = generate_raw_ob(m1, dxy, False, tb, te, rr, k, 8.0, em)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 2) M15 full Double Bottom / Top ==========
def generate_m15_dbdt(
    m1, dxy=None, use_dxy=False,
    rr_mode="mm",  # mm | 1.5 | 2.0
    tol=1.0, min_sep=6, max_height=8.0,
    entry_mode="neck",  # neck | signal
    session="liq",
) -> List[Order]:
    m15 = resample_ohlc(m1, "15min")
    o_a = m15["open"].astype(float).values
    h_a = m15["high"].astype(float).values
    l_a = m15["low"].astype(float).values
    c_a = m15["close"].astype(float).values
    times = m15.index
    n = len(m15)
    w = 2
    # confirmed swings
    lows, highs = [], []
    for i in range(w, n - w):
        if all(l_a[i] <= l_a[i - j] for j in range(1, w + 1)) and all(l_a[i] < l_a[i + j] for j in range(1, w + 1)):
            lows.append((i + w, i, float(l_a[i])))
        if all(h_a[i] >= h_a[i - j] for j in range(1, w + 1)) and all(h_a[i] > h_a[i + j] for j in range(1, w + 1)):
            highs.append((i + w, i, float(h_a[i])))

    orders = []
    used = set()
    # DB: pair lows
    for a in range(len(lows)):
        for b in range(a + 1, len(lows)):
            ia, pa, la = lows[a]
            ib, pb, lb = lows[b]
            if pb - pa < min_sep:
                continue
            if abs(la - lb) > tol + 1e-12:
                continue
            neck = float(h_a[pa:pb + 1].max())
            ext = min(la, lb)
            height = neck - ext
            if height <= 0 or height > max_height + 1e-9:
                continue
            # signal at confirm of second low (=ib) or later neck break bar
            # scan from ib forward for entry trigger (closed bars only)
            for j in range(ib, min(ib + 12, n - 1)):
                ts = times[j]
                if ts.dayofweek >= 5:
                    continue
                if session == "liq" and not _in_liq(ts):
                    continue
                # invalidate if new LL
                if l_a[j] < ext - tol:
                    break
                if entry_mode == "neck":
                    # need close or trade through neck; arm buy stop at neck+tick after bar that approaches
                    if h_a[j] < neck - 1e-12 and c_a[j] < neck:
                        continue
                    entry = neck + TICK
                    sl = ext - TICK
                else:
                    if not _bull_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                        continue
                    entry = float(h_a[j]) + TICK
                    sl = ext - TICK
                    if entry - sl > max_height + 1e-9:
                        continue
                if entry - sl > max_height + 1e-9 or entry <= sl:
                    continue
                if rr_mode == "mm":
                    # measured move beyond neck ≈ height → R = height/(entry-sl) ≈ 1 if entry≈neck
                    risk = entry - sl
                    tp = entry + height
                    rr_tag = "mm"
                else:
                    rr = float(rr_mode)
                    tp = _rr("long", entry, sl, rr)
                    rr_tag = f"rr{rr:g}"
                    if tp is None:
                        continue
                key = (pb, "DB")
                if key in used:
                    break
                arm = bar_end(ts, 15)
                v = f"m15dbdt_{rr_tag}_t{tol:g}_{entry_mode}"
                orders.append(_stop(arm, "long", entry, sl, tp, "M15DBDT", v,
                                    {"signal_bar": ts, "neck": neck, "height": height}, 15, hold=360))
                used.add(key)
                break

    for a in range(len(highs)):
        for b in range(a + 1, len(highs)):
            ia, pa, ha = highs[a]
            ib, pb, hb = highs[b]
            if pb - pa < min_sep:
                continue
            if abs(ha - hb) > tol + 1e-12:
                continue
            neck = float(l_a[pa:pb + 1].min())
            ext = max(ha, hb)
            height = ext - neck
            if height <= 0 or height > max_height + 1e-9:
                continue
            for j in range(ib, min(ib + 12, n - 1)):
                ts = times[j]
                if ts.dayofweek >= 5:
                    continue
                if session == "liq" and not _in_liq(ts):
                    continue
                if h_a[j] > ext + tol:
                    break
                if entry_mode == "neck":
                    if l_a[j] > neck + 1e-12 and c_a[j] > neck:
                        continue
                    entry = neck - TICK
                    sl = ext + TICK
                else:
                    if not _bear_q(o_a[j], h_a[j], l_a[j], c_a[j], 0.5):
                        continue
                    entry = float(l_a[j]) - TICK
                    sl = ext + TICK
                if sl - entry > max_height + 1e-9 or sl <= entry:
                    continue
                if rr_mode == "mm":
                    tp = entry - height
                    rr_tag = "mm"
                else:
                    rr = float(rr_mode)
                    tp = _rr("short", entry, sl, rr)
                    rr_tag = f"rr{rr:g}"
                    if tp is None:
                        continue
                key = (pb, "DT")
                if key in used:
                    break
                arm = bar_end(ts, 15)
                v = f"m15dbdt_{rr_tag}_t{tol:g}_{entry_mode}"
                orders.append(_stop(arm, "short", entry, sl, tp, "M15DBDT", v,
                                    {"signal_bar": ts, "neck": neck, "height": height}, 15, hold=360))
                used.add(key)
                break

    orders = dedupe_orders(orders, 45)
    return apply_dxy_gate(orders, dxy, use_dxy)


def generate_m15_dbdt_family(m1, dxy=None):
    pools = {}
    specs = [
        ("mm", 1.5, "neck"),
        (2.0, 1.5, "neck"),
        (1.5, 1.5, "signal"),
        ("mm", 1.0, "neck"),
        ("mm", 1.5, "signal"),
    ]
    for rrm, tol, em in specs:
        oo = generate_m15_dbdt(m1, dxy, False, rrm, tol, 6, 8.0, em)
        if oo:
            pools[oo[0].variant] = oo
    return pools


# ========== 3) PWH/PWL via shared LiqRaid family ==========
def generate_pwh_family(m1, dxy=None):
    pools = {}
    specs = [
        (1.5, "both", False),
        (1.5, "any", False),
        (2.0, "both", False),
        (1.5, "london", False),
        (1.5, "both", True),
    ]
    for rr, kz, htf in specs:
        oo = generate_liq_raid(m1, dxy, False, "pwh_pwl", rr, kz, 8.0, htf)
        if oo:
            pools[oo[0].variant] = oo
    return pools
