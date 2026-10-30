"""Candle Range Theory (CRT).

HTF (H4/D1/H1): candle2 wicks beyond candle1 high/low and closes back inside candle1 range
(stronger: inside candle1 body). Short after high sweep / long after low sweep.
Entry at candle2 close, SL beyond candle2 wick, TP = candle1 opposite extreme.
LTF refine: after HTF CRT closes, M5/M15 MSS/FVG entry with tighter SL, TP still CRT target.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.ict_helpers import find_fvgs, swing_highs_lows, last_swing_before


def _crt_events(htf: pd.DataFrame, body_close: bool = False) -> List[dict]:
    """Detect CRT at closed bar i (candle2), candle1 = i-1. Available at bar end of i."""
    o, h, l, c = htf["open"].values, htf["high"].values, htf["low"].values, htf["close"].values
    times = htf.index
    out = []
    for i in range(1, len(htf)):
        # candle2 wicks beyond candle1 and closes inside candle1 range
        # high sweep short
        if h[i] > h[i - 1] and c[i] < h[i - 1] and c[i] > l[i - 1]:
            if body_close:
                body_hi = max(o[i - 1], c[i - 1])
                body_lo = min(o[i - 1], c[i - 1])
                if not (body_lo < c[i] < body_hi):
                    pass
                else:
                    out.append({"i": i, "side": "short", "tp": float(l[i - 1]), "sl_ext": float(h[i]),
                                "c1_hi": float(h[i - 1]), "c1_lo": float(l[i - 1]),
                                "entry_ref": float(c[i]), "time": times[i],
                                "mid": 0.5 * (h[i - 1] + l[i - 1])})
                    continue
            else:
                out.append({"i": i, "side": "short", "tp": float(l[i - 1]), "sl_ext": float(h[i]),
                            "c1_hi": float(h[i - 1]), "c1_lo": float(l[i - 1]),
                            "entry_ref": float(c[i]), "time": times[i],
                            "mid": 0.5 * (h[i - 1] + l[i - 1])})
        # low sweep long
        if l[i] < l[i - 1] and c[i] > l[i - 1] and c[i] < h[i - 1]:
            if body_close:
                body_hi = max(o[i - 1], c[i - 1])
                body_lo = min(o[i - 1], c[i - 1])
                if body_lo < c[i] < body_hi:
                    out.append({"i": i, "side": "long", "tp": float(h[i - 1]), "sl_ext": float(l[i]),
                                "c1_hi": float(h[i - 1]), "c1_lo": float(l[i - 1]),
                                "entry_ref": float(c[i]), "time": times[i],
                                "mid": 0.5 * (h[i - 1] + l[i - 1])})
            else:
                out.append({"i": i, "side": "long", "tp": float(h[i - 1]), "sl_ext": float(l[i]),
                            "c1_hi": float(h[i - 1]), "c1_lo": float(l[i - 1]),
                            "entry_ref": float(c[i]), "time": times[i],
                            "mid": 0.5 * (h[i - 1] + l[i - 1])})
    return out


def pure_htf_stats(m1: pd.DataFrame) -> dict:
    """Raw HTF CRT: WR if TP vs SL first on M1 after entry at close; median SL $."""
    out = {}
    for tf, rule in (("4h", "H4"), ("1D", "D1"), ("1h", "H1")):
        htf = resample_ohlc(m1, tf)
        for body in (False, True):
            ev = _crt_events(htf, body)
            wins = losses = 0
            sl_dists = []
            for e in ev:
                risk = abs(e["entry_ref"] - e["sl_ext"])
                sl_dists.append(risk)
                # walk m1 after event time
                j = m1.index.searchsorted(e["time"] + pd.Timedelta(minutes={"4h": 240, "1D": 1440, "1h": 60}[tf]), side="left")
                # actually bar_end of HTF candle
                from indicators import bar_end as be
                mins = {"4h": 240, "1D": 1440, "1h": 60}[tf]
                arm = e["time"] + pd.Timedelta(minutes=mins)  # left-labeled end
                j = m1.index.searchsorted(arm, side="left")
                if j >= len(m1) - 2:
                    continue
                side = e["side"]
                sl, tp, px = e["sl_ext"], e["tp"], e["entry_ref"]
                hit = None
                for k in range(j, min(j + mins * 3, len(m1))):  # up to 3 HTF bars
                    if side == "long":
                        if m1["low"].iloc[k] <= sl:
                            hit = "SL"; break
                        if m1["high"].iloc[k] >= tp:
                            hit = "TP"; break
                    else:
                        if m1["high"].iloc[k] >= sl:
                            hit = "SL"; break
                        if m1["low"].iloc[k] <= tp:
                            hit = "TP"; break
                if hit == "TP":
                    wins += 1
                elif hit == "SL":
                    losses += 1
            n = wins + losses
            key = f"{rule}_{'body' if body else 'range'}"
            out[key] = {
                "n_events": len(ev), "resolved": n, "wins": wins, "losses": losses,
                "WR": wins / n if n else None,
                "median_sl_usd": float(np.median(sl_dists)) if sl_dists else None,
                "pct_sl_over_8": float(np.mean([d > 8 for d in sl_dists])) if sl_dists else None,
                "pct_sl_over_5": float(np.mean([d > 5 for d in sl_dists])) if sl_dists else None,
            }
    return out


def generate_crt_htf(
    m1: pd.DataFrame,
    htf: str = "H4",          # H4 | D1 | H1
    body_close: bool = False,
    atr_buf: float = 0.05,
) -> List[Order]:
    rule = {"H4": "4h", "D1": "1D", "H1": "1h"}[htf]
    mins = {"H4": 240, "D1": 1440, "H1": 60}[htf]
    df = resample_ohlc(m1, rule)
    ev = _crt_events(df, body_close)
    tag = "body" if body_close else "range"
    variant = f"crt_htf_{htf}_{tag}"
    orders = []
    for e in ev:
        px = e["entry_ref"]
        buf = atr_buf
        if e["side"] == "long":
            sl = e["sl_ext"] - buf
            tp = e["tp"]
            if sl >= px or tp <= px:
                continue
        else:
            sl = e["sl_ext"] + buf
            tp = e["tp"]
            if sl <= px or tp >= px:
                continue
        if abs(px - sl) < 0.3:
            continue
        arm = e["time"] + pd.Timedelta(minutes=mins)
        orders.append(Order(
            arm_time=arm, side=e["side"], kind="market", price=px, sl=float(sl), tp=float(tp),
            strategy="CRT", variant=variant,
            meta={"htf": htf, "c1": (e["c1_lo"], e["c1_hi"])},
            expire_minutes=30, max_hold_minutes=mins * 3,
        ))
    return dedupe_orders(orders, 120)


def generate_crt_ltf(
    m1: pd.DataFrame,
    htf: str = "H4",
    entry_tf: str = "M5",     # M5 | M15
    body_close: bool = False,
    tp_mode: str = "extreme", # extreme | mid_partial (TP at mid as primary — use mid as TP)
    atr_buf: float = 0.1,
) -> List[Order]:
    rule = {"H4": "4h", "D1": "1D", "H1": "1h"}[htf]
    mins = {"H4": 240, "D1": 1440, "H1": 60}[htf]
    hdf = resample_ohlc(m1, rule)
    ev = _crt_events(hdf, body_close)
    bar_m = 5 if entry_tf == "M5" else 15
    df = resample_ohlc(m1, f"{bar_m}min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)

    tag = "body" if body_close else "range"
    variant = f"crt_ltf_{htf}_{entry_tf}_{tag}_{tp_mode}"
    orders = []
    for e in ev:
        arm0 = e["time"] + pd.Timedelta(minutes=mins)
        # search LTF bars in next HTF period
        i0 = times.searchsorted(arm0, side="left")
        i1 = times.searchsorted(arm0 + pd.Timedelta(minutes=mins), side="left")
        if i0 >= len(times) - 2:
            continue
        side = e["side"]
        for i in range(max(i0, 10), min(i1, len(times) - 1)):
            atr_v = a[i]
            if np.isnan(atr_v) or atr_v <= 0:
                continue
            # MSS/FVG back inside range
            if side == "long":
                if not (e["c1_lo"] <= c[i] <= e["c1_hi"]):
                    continue
                sw = last_swing_before(shi, i)
                if sw is None or c[i] <= h[sw]:
                    continue
                fvgs = find_fvgs(h, l, a, max(i - 6, 0), i, "bull", 0.05)
                if not fvgs:
                    continue
                glo, ghi, _ = fvgs[-1]
                px = 0.5 * (glo + ghi)
                buf = max(atr_buf * atr_v, 0.12)
                sl = min(float(l[i]), glo) - buf
                if sl >= px:
                    continue
            else:
                if not (e["c1_lo"] <= c[i] <= e["c1_hi"]):
                    continue
                sw = last_swing_before(sli, i)
                if sw is None or c[i] >= l[sw]:
                    continue
                fvgs = find_fvgs(h, l, a, max(i - 6, 0), i, "bear", 0.05)
                if not fvgs:
                    continue
                glo, ghi, _ = fvgs[-1]
                px = 0.5 * (glo + ghi)
                buf = max(atr_buf * atr_v, 0.12)
                sl = max(float(h[i]), ghi) + buf
                if sl <= px:
                    continue
            risk = abs(px - sl)
            if risk < 0.20:
                continue
            if tp_mode == "extreme":
                tp = e["tp"]
            else:
                tp = e["mid"]
            if side == "long" and tp <= px + 0.5 * risk:
                continue
            if side == "short" and tp >= px - 0.5 * risk:
                continue
            rr = abs(tp - px) / risk
            if rr < 1.0:
                continue
            arm = bar_end(times[i], bar_m)
            orders.append(Order(
                arm_time=arm, side=side, kind="limit", price=float(px),
                sl=float(sl), tp=float(tp),
                strategy="CRT", variant=variant,
                meta={"htf": htf, "event": str(e["time"])},
                expire_minutes=60, max_hold_minutes=mins,
            ))
            break
    return dedupe_orders(orders, 60)


def generate_crt_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for htf in ("H4", "D1", "H1"):
        for body in (False, True):
            print(f" crt htf {htf} body={body}", flush=True)
            oo = generate_crt_htf(m1, htf, body)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  n={len(oo)} med_sl≈", flush=True)
        for etf in ("M5", "M15"):
            for body in (False, True):
                for tp in ("extreme", "mid_partial"):
                    print(f" crt ltf {htf} {etf} body={body} {tp}", flush=True)
                    oo = generate_crt_ltf(m1, htf, etf, body, tp)
                    if oo:
                        pools[oo[0].variant] = oo
                        print(f"  n={len(oo)}", flush=True)
    return pools
