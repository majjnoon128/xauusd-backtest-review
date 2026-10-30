"""Pro BTB M5 — 6 entry modes, closed-bar, orders armed after return/breakout bar end."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, pivot_confirmed, resample_ohlc, bullish_engulfing, bearish_engulfing, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders


def generate_pro_btb(m1, dxy=None, use_dxy=False, use_vol=False, rr=2.0, vol_mult=1.3, rule: str = "5min") -> List[Order]:
    m5 = resample_ohlc(m1, rule)
    bar_min = {"1min":1,"5min":5,"15min":15,"30min":30,"1h":60,"4h":240}.get(rule, 5)
    a = atr_prior(m5, 14).values
    high, low, close, open_ = m5["high"].values, m5["low"].values, m5["close"].values, m5["open"].values
    times = m5.index
    left = 3 if bar_min >= 15 else 5
    ph_conf, pl_conf, ph_px, pl_px = pivot_confirmed(m5["high"], m5["low"], left, left)
    bull_eng, bear_eng = bullish_engulfing(m5).values, bearish_engulfing(m5).values
    volma = vol_ma(m5["volume"], 20) if "volume" in m5.columns else None
    levels_h, levels_l = [], []
    pending_bo = []
    orders = []
    n = len(m5)

    for i in range(30, n):
        if ph_conf[i] >= 0:
            levels_h.append((int(ph_conf[i]), float(ph_px[i]))); levels_h = levels_h[-20:]
        if pl_conf[i] >= 0:
            levels_l.append((int(pl_conf[i]), float(pl_px[i]))); levels_l = levels_l[-20:]
        atr_use = a[i]
        if np.isnan(atr_use) or atr_use <= 0:
            continue

        # Detect breakout at CLOSE of i
        for li, lvl in levels_h:
            if not (3 <= i - li <= 80):
                continue
            if not (close[i] > lvl and high[i] > lvl and open_[i] < lvl + 0.05 * atr_use):
                continue
            if (close[i] - open_[i]) < 0.3 * atr_use:
                continue
            pending_bo.append({"side": "long", "lvl": lvl, "bi": i,
                "brk_close": float(close[i]), "brk_high": float(high[i]), "brk_low": float(low[i]),
                "atr": float(atr_use), "expiry": i + 12})
            break
        for li, lvl in levels_l:
            if not (3 <= i - li <= 80):
                continue
            if not (close[i] < lvl and low[i] < lvl and open_[i] > lvl - 0.05 * atr_use):
                continue
            if (open_[i] - close[i]) < 0.3 * atr_use:
                continue
            pending_bo.append({"side": "short", "lvl": lvl, "bi": i,
                "brk_close": float(close[i]), "brk_high": float(high[i]), "brk_low": float(low[i]),
                "atr": float(atr_use), "expiry": i + 12})
            break

        still = []
        for bo in pending_bo:
            if i <= bo["bi"]:
                still.append(bo); continue
            if i > bo["expiry"]:
                continue
            atr_b = bo["atr"]
            if bo["side"] == "long":
                touched = (low[i] <= bo["brk_close"] + 0.05*atr_b) or (low[i] <= bo["lvl"] + 0.05*atr_b)
                ran = high[i] > bo["brk_high"] + 1.5*atr_b
            else:
                touched = (high[i] >= bo["brk_close"] - 0.05*atr_b) or (high[i] >= bo["lvl"] - 0.05*atr_b)
                ran = low[i] < bo["brk_low"] - 1.5*atr_b
            if ran and not touched:
                continue
            if not touched:
                still.append(bo); continue
            # Return confirmed at close of i → arm orders AFTER this bar
            if not in_session(times[i]):
                continue
            arm = bar_end(times[i], bar_min)
            side = bo["side"]
            sl = (bo["brk_low"] - 0.05*atr_b) if side == "long" else (bo["brk_high"] + 0.05*atr_b)
            brk_c, brk_h, brk_l, lvl = bo["brk_close"], bo["brk_high"], bo["brk_low"], bo["lvl"]
            ret_c, ret_h, ret_l = float(close[i]), float(high[i]), float(low[i])
            meta = {"signal_bar": times[i]}

            def add(kind, price, variant):
                if side == "long":
                    risk = price - sl
                    if risk <= 0.05 or risk > 3*atr_b: return
                    tp = price + rr * risk
                else:
                    risk = sl - price
                    if risk <= 0.05 or risk > 3*atr_b: return
                    tp = price - rr * risk
                orders.append(Order(arm, side, kind, price, sl, tp, "ProBTB", f"{rule}_{variant}_rr{rr}", meta, 60))

            # m1 Buy/Sell Limit at breakeven (brk close)
            add("limit", brk_c, "m1_limit_breakeven")
            # m2 Stop after return: stop at ret high/low
            add("stop", ret_h if side=="long" else ret_l, "m2_stop_after_return")
            # m3 Market after return close
            add("market", ret_c, "m3_market_after_return")
            # m4 Limit at broken level
            add("limit", lvl, "m4_limit_broken_level")
            # m5 Stop at breakout extreme
            add("stop", brk_h if side=="long" else brk_l, "m5_stop_breakout_extreme")
            # m6 Market with engulfing on return bar
            if (side=="long" and bull_eng[i]) or (side=="short" and bear_eng[i]):
                add("market", ret_c, "m6_market_candle_confirm")
        pending_bo = still

    orders = dedupe_orders(orders, 20)
    if use_vol and volma is not None:
        orders = apply_vol_gate(orders, m5["volume"], volma, True, vol_mult, bar_min)
    return apply_dxy_gate(orders, dxy, use_dxy)
