"""Batch3 reel setups — closed-bar mechanical translations."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import (
    atr_prior, resample_ohlc, bar_end, ema, rsi, is_bull, is_bear,
)
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def _rr_tp(side, px, sl, rr):
    risk = abs(px - sl)
    if risk < 0.15:
        return None, None
    tp = px + rr * risk if side == "long" else px - rr * risk
    return risk, tp


# ---------- 1) ICT 9AM NY candle → 10–11 NY break (DeeomF3IPcr) ----------
def generate_nine_am(m1, tf_entry="M1", rr=2.0, window=("14:00", "15:00")):
    """NY 09:00 = 13:00 UTC (EDT) or 14:00 UTC (EST). Use 13:00–14:00 H1 as 9AM candle proxy (EDT).
    Mark H/L of H1 bar starting 13:00 UTC; in 14:00–15:00 wait M1 close beyond H/L; SL beyond opposite; TP rr.
    """
    h1 = resample_ohlc(m1, "60min")
    m_ent = resample_ohlc(m1, "1min" if tf_entry == "M1" else "5min")
    bar_m = 1 if tf_entry == "M1" else 5
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    wh, wm = map(int, window[0].split(":"))
    eh, em = map(int, window[1].split(":"))
    for d in dates:
        if d.dayofweek >= 5:
            continue
        # try both 13:00 and 14:00 as 9AM NY proxies
        for nine_h in (13, 14):
            nine_ts = d + pd.Timedelta(hours=nine_h)
            if nine_ts not in h1.index:
                # nearest
                j = h1.index.searchsorted(nine_ts)
                if j >= len(h1) or h1.index[j] != nine_ts:
                    continue
            row = h1.loc[nine_ts]
            hi, lo = float(row["high"]), float(row["low"])
            if hi - lo < 0.3:
                continue
            w0 = d + pd.Timedelta(hours=nine_h + 1)
            w1 = w0 + pd.Timedelta(hours=1)
            seg = m_ent[(m_ent.index >= w0) & (m_ent.index < w1)]
            taken = None
            for ts, r in seg.iterrows():
                c, h, l = float(r["close"]), float(r["high"]), float(r["low"])
                side = None
                if c > hi:
                    side = "long"; sl = lo
                elif c < lo:
                    side = "short"; sl = hi
                if side is None:
                    continue
                px = c
                risk, tp = _rr_tp(side, px, sl, rr)
                if risk is None:
                    continue
                # soft SL if too wide: atr_buf toward entry
                if risk > 12:
                    sl = px - 3.0 if side == "long" else px + 3.0
                    risk, tp = _rr_tp(side, px, sl, rr)
                    if risk is None:
                        continue
                arm = bar_end(ts, bar_m)
                v = f"nineam_h{nine_h}_{tf_entry}_rr{rr:g}"
                orders.append(Order(arm, side, "market", px, sl, tp, "NineAM", v, {"nine": nine_h}, 30, 120))
                taken = side
                break
            if taken:
                break
    return dedupe_orders(orders, 30)


def generate_nine_am_family(m1):
    pools = {}
    for tf in ("M1", "M5"):
        for rr in (1.5, 2.0, 3.0):
            oo = generate_nine_am(m1, tf, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  nineam {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 2) H4 extreme → M15 pullback (Dc_oEVIuLY5 greenside 90%/5R) ----------
def generate_h4_m15_pb(m1, rr=2.0, touch_buf=0.15):
    h4 = resample_ohlc(m1, "240min")
    m15 = resample_ohlc(m1, "15min")
    a15 = atr_prior(m15, 14).values
    orders = []
    hi = h4["high"].values; lo = h4["low"].values; ht = h4.index
    c15 = m15["close"].values; h15 = m15["high"].values; l15 = m15["low"].values
    o15 = m15["open"].values; t15 = m15.index
    # for each M15 bar, last CLOSED H4
    for i in range(20, len(m15) - 2):
        if t15[i].dayofweek >= 5:
            continue
        # last closed H4: bar that ended before this M15
        j = h4.index.searchsorted(t15[i], side="right") - 2  # prior fully closed
        if j < 0:
            continue
        hh, ll = float(hi[j]), float(lo[j])
        atrv = float(a15[i]) if not np.isnan(a15[i]) else 1.0
        # touch high → look for bearish pullback entry (close back below after wick)
        side = None; sl = None; px = float(c15[i])
        if h15[i] >= hh - touch_buf and c15[i] < hh and is_bear(m15).iloc[i]:
            # short: SL above wick
            side = "short"; sl = float(h15[i]) + 0.1 * atrv
        elif l15[i] <= ll + touch_buf and c15[i] > ll and is_bull(m15).iloc[i]:
            side = "long"; sl = float(l15[i]) - 0.1 * atrv
        if side is None:
            continue
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None or risk > 20:
            continue
        arm = bar_end(t15[i], 15)
        v = f"h4m15_rr{rr:g}"
        orders.append(Order(arm, side, "market", px, sl, tp, "H4M15", v, {}, 45, 240))
    return dedupe_orders(orders, 60)


def generate_h4_m15_family(m1):
    pools = {}
    for rr in (1.5, 2.0, 5.0):
        oo = generate_h4_m15_pb(m1, rr)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  h4m15 {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 3) Ichimoku Tenkan/Kijun flat + TK cross (Da2itqtzMWu) ----------
def generate_ichimoku(m1, tf="M15", rr=2.0, flat_bars=3):
    bar = {"M5": 5, "M15": 15, "H1": 60}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    h, l, c = df["high"], df["low"], df["close"]
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    a = atr_prior(df, 14)
    orders = []
    tv, kv, cv, av = tenkan.values, kijun.values, c.values, a.values
    hv, lv = h.values, l.values
    times = df.index
    for i in range(30, len(df) - 2):
        if times[i].dayofweek >= 5 or np.isnan(tv[i]) or np.isnan(kv[i]) or np.isnan(av[i]):
            continue
        # kijun flat: little change over flat_bars
        if abs(kv[i] - kv[i - flat_bars]) > 0.15 * av[i]:
            continue
        # tenkan crosses kijun toward price
        cross_up = tv[i - 1] <= kv[i - 1] and tv[i] > kv[i]
        cross_dn = tv[i - 1] >= kv[i - 1] and tv[i] < kv[i]
        side = None
        if cross_up and cv[i] > kv[i]:
            side = "long"
        elif cross_dn and cv[i] < kv[i]:
            side = "short"
        if side is None:
            continue
        px = float(cv[i])
        sl = float(kv[i]) - 0.2 * float(av[i]) if side == "long" else float(kv[i]) + 0.2 * float(av[i])
        # also allow atr SL
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None:
            continue
        if risk < 0.3:
            sl = px - 1.0 * float(av[i]) if side == "long" else px + 1.0 * float(av[i])
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
        arm = bar_end(times[i], bar)
        v = f"ichi_{tf}_rr{rr:g}_f{flat_bars}"
        orders.append(Order(arm, side, "market", px, sl, tp, "Ichimoku", v, {}, 60, 300))
    return dedupe_orders(orders, 30)


def generate_ichimoku_family(m1):
    pools = {}
    for tf in ("M5", "M15", "H1"):
        for rr in (1.5, 2.0):
            for fb in (2, 3):
                oo = generate_ichimoku(m1, tf, rr, fb)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  ichi {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 4) Bollinger + RSI divergence proxy (DcbdoAFKNQW) ----------
def generate_bb_div(m1, tf="M15", rr=2.0, n=20, k=2.0):
    bar = {"M5": 5, "M15": 15, "H1": 60}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    mid = df["close"].rolling(n).mean()
    sd = df["close"].rolling(n).std()
    upper, lower = mid + k * sd, mid - k * sd
    r = rsi(df["close"], 14)
    a = atr_prior(df, 14)
    orders = []
    for i in range(30, len(df) - 2):
        if df.index[i].dayofweek >= 5:
            continue
        if any(np.isnan(x) for x in (upper.iloc[i], lower.iloc[i], r.iloc[i], a.iloc[i])):
            continue
        px = float(df["close"].iloc[i])
        # long: touch lower BB + RSI rising from <35 (proxy for bullish div)
        side = None; sl = None
        if df["low"].iloc[i] <= float(lower.iloc[i]) and r.iloc[i] < 40 and r.iloc[i] > r.iloc[i - 1]:
            side = "long"; sl = float(df["low"].iloc[i]) - 0.15 * float(a.iloc[i])
        elif df["high"].iloc[i] >= float(upper.iloc[i]) and r.iloc[i] > 60 and r.iloc[i] < r.iloc[i - 1]:
            side = "short"; sl = float(df["high"].iloc[i]) + 0.15 * float(a.iloc[i])
        if side is None:
            continue
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None:
            continue
        arm = bar_end(df.index[i], bar)
        v = f"bbdiv_{tf}_rr{rr:g}"
        orders.append(Order(arm, side, "market", px, sl, tp, "BBDiv", v, {}, 45, 240))
    return dedupe_orders(orders, 45)


def generate_bb_div_family(m1):
    pools = {}
    for tf in ("M5", "M15"):
        for rr in (1.5, 2.0):
            oo = generate_bb_div(m1, tf, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  bbdiv {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 5) Spike knot + 50% opposite body (DcbfaI4MuAx) ----------
def generate_spike50(m1, tf="M5", rr=2.0, wick_body=1.5):
    bar = {"M5": 5, "M15": 15}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    a = atr_prior(df, 14)
    orders = []
    for i in range(30, len(df) - 3):
        if df.index[i].dayofweek >= 5 or np.isnan(a.iloc[i]):
            continue
        # detect bullish spike: long lower wick relative to body, then look for last red in pullback
        body = abs(float(df["close"].iloc[i]) - float(df["open"].iloc[i]))
        lower_w = min(float(df["open"].iloc[i]), float(df["close"].iloc[i])) - float(df["low"].iloc[i])
        upper_w = float(df["high"].iloc[i]) - max(float(df["open"].iloc[i]), float(df["close"].iloc[i]))
        atrv = float(a.iloc[i])
        # impulse bar
        if body < 0.3 * atrv:
            continue
        # after impulse, within next 8 bars find opposite-color candle and enter at 50% body
        if float(df["close"].iloc[i]) > float(df["open"].iloc[i]) and lower_w >= wick_body * max(body, 0.05):
            # bullish spike context → long on next bearish pullback 50%
            for j in range(i + 1, min(i + 9, len(df) - 1)):
                if float(df["close"].iloc[j]) < float(df["open"].iloc[j]):
                    o, c = float(df["open"].iloc[j]), float(df["close"].iloc[j])
                    mid = 0.5 * (o + c)
                    sl = float(df["low"].iloc[j]) - 0.05 * atrv
                    px = mid
                    side = "long"
                    risk, tp = _rr_tp(side, px, sl, rr)
                    if risk is None or risk > 15:
                        break
                    arm = bar_end(df.index[j], bar)
                    v = f"spike50_{tf}_rr{rr:g}"
                    orders.append(Order(arm, side, "limit", px, sl, tp, "Spike50", v, {}, 30, 180))
                    break
        elif float(df["close"].iloc[i]) < float(df["open"].iloc[i]) and upper_w >= wick_body * max(body, 0.05):
            for j in range(i + 1, min(i + 9, len(df) - 1)):
                if float(df["close"].iloc[j]) > float(df["open"].iloc[j]):
                    o, c = float(df["open"].iloc[j]), float(df["close"].iloc[j])
                    mid = 0.5 * (o + c)
                    sl = float(df["high"].iloc[j]) + 0.05 * atrv
                    px = mid
                    side = "short"
                    risk, tp = _rr_tp(side, px, sl, rr)
                    if risk is None or risk > 15:
                        break
                    arm = bar_end(df.index[j], bar)
                    v = f"spike50_{tf}_rr{rr:g}"
                    orders.append(Order(arm, side, "limit", px, sl, tp, "Spike50", v, {}, 30, 180))
                    break
    return dedupe_orders(orders, 40)


def generate_spike50_family(m1):
    pools = {}
    for tf in ("M5", "M15"):
        for rr in (1.5, 2.0, 3.0):
            oo = generate_spike50(m1, tf, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  spike50 {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 6) Session-open H1 direction (DbyAu4LNosZ) ----------
def generate_sess_open(m1, hour_utc=4, rr=2.0):
    """If H1 candle at hour takes prior H1 high → long bias next; prior low → short. Enter next M15 close."""
    h1 = resample_ohlc(m1, "60min")
    m15 = resample_ohlc(m1, "15min")
    a = atr_prior(m15, 14)
    orders = []
    for i in range(2, len(h1) - 1):
        ts = h1.index[i]
        if ts.dayofweek >= 5 or ts.hour != hour_utc:
            continue
        prev = h1.iloc[i - 1]; cur = h1.iloc[i]
        side = None
        if float(cur["high"]) > float(prev["high"]) and float(cur["close"]) > float(prev["close"]):
            side = "long"
        elif float(cur["low"]) < float(prev["low"]) and float(cur["close"]) < float(prev["close"]):
            side = "short"
        if side is None:
            continue
        # enter on next closed M15 after this H1 ends
        arm0 = bar_end(ts, 60)
        j = m15.index.searchsorted(arm0)
        if j >= len(m15) - 1:
            continue
        px = float(m15["close"].iloc[j])
        atrv = float(a.iloc[j]) if not np.isnan(a.iloc[j]) else 1.0
        sl = px - 1.2 * atrv if side == "long" else px + 1.2 * atrv
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None:
            continue
        arm = bar_end(m15.index[j], 15)
        v = f"sessopen_h{hour_utc}_rr{rr:g}"
        orders.append(Order(arm, side, "market", px, sl, tp, "SessOpen", v, {}, 60, 240))
    return dedupe_orders(orders, 60)


def generate_sess_open_family(m1):
    pools = {}
    for h in (2, 4, 6, 7, 13):  # NZ/Asia/London/NY proxies UTC
        for rr in (1.5, 2.0):
            oo = generate_sess_open(m1, h, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  sessopen {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 7) H1 02:30 break + M5 pinbar (DcWIKm_Mn3o) — use 02:00 H1 ----------
def generate_h1_break_pin(m1, h1_hour=2, rr=5.0):
    h1 = resample_ohlc(m1, "60min")
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        ts = d + pd.Timedelta(hours=h1_hour)
        if ts not in h1.index:
            continue
        hi, lo = float(h1.loc[ts, "high"]), float(h1.loc[ts, "low"])
        w0 = bar_end(ts, 60)
        w1 = w0 + pd.Timedelta(hours=6)
        seg = m5[(m5.index >= w0) & (m5.index < w1)]
        broken = None
        for t, r in seg.iterrows():
            c, h, l, o = float(r["close"]), float(r["high"]), float(r["low"]), float(r["open"])
            body = abs(c - o)
            # break then pinbar reverse
            if broken is None:
                if c > hi:
                    broken = "up"
                elif c < lo:
                    broken = "down"
                continue
            # pinbar against break
            lower_w = min(o, c) - l
            upper_w = h - max(o, c)
            atrv = float(a5.loc[t]) if t in a5.index and not np.isnan(a5.loc[t]) else 1.0
            side = None; sl = None; px = c
            if broken == "down" and lower_w > 1.2 * max(body, 0.05) and c > o:
                side = "long"; sl = l - 0.1 * atrv
            elif broken == "up" and upper_w > 1.2 * max(body, 0.05) and c < o:
                side = "short"; sl = h + 0.1 * atrv
            if side is None:
                continue
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            # also try rr2
            arm = bar_end(t, 5)
            v = f"h1pin_h{h1_hour}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "H1Pin", v, {}, 30, 180))
            break
    return dedupe_orders(orders, 60)


def generate_h1_pin_family(m1):
    pools = {}
    for h in (2, 7, 13):
        for rr in (2.0, 5.0):
            oo = generate_h1_break_pin(m1, h, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  h1pin {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 8) Daily H/L box + M5 pinbar outside (DcD_oZOxZBQ / DbIa6r9IIZP) ----------
def generate_daily_box_pin(m1, rr=2.0):
    d1 = resample_ohlc(m1, "1D")
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders = []
    for i in range(1, len(d1) - 1):
        day = d1.index[i]
        prev = d1.iloc[i - 1]
        hi, lo = float(prev["high"]), float(prev["low"])
        day_end = day + pd.Timedelta(days=1)
        seg = m5[(m5.index >= day) & (m5.index < day_end)]
        for t, r in seg.iterrows():
            if t.dayofweek >= 5:
                continue
            c, h, l, o = float(r["close"]), float(r["high"]), float(r["low"]), float(r["open"])
            atrv = float(a5.loc[t]) if t in a5.index and not np.isnan(a5.loc[t]) else 1.0
            body = abs(c - o)
            lower_w = min(o, c) - l
            upper_w = h - max(o, c)
            side = None; sl = None; px = c
            # above prior high → only shorts on pinbar
            if c > hi and upper_w > 1.3 * max(body, 0.05) and c < o:
                side = "short"; sl = h + 0.1 * atrv
            elif c < lo and lower_w > 1.3 * max(body, 0.05) and c > o:
                side = "long"; sl = l - 0.1 * atrv
            else:
                continue
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(t, 5)
            v = f"dbox_pin_rr{rr:g}"
            # TP toward opposite daily extreme
            if side == "short":
                tp = max(tp, lo) if False else tp  # keep rr
            orders.append(Order(arm, side, "market", px, sl, tp, "DailyBox", v, {}, 30, 360))
            break  # one per day
    return dedupe_orders(orders, 120)


def generate_daily_box_family(m1):
    pools = {}
    for rr in (1.5, 2.0, 3.0):
        oo = generate_daily_box_pin(m1, rr)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  dbox {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 9) Supertrend classic (DbsTTViMc47 AI≈ATR10 factor~3) ----------

def generate_supertrend(m1, tf="M15", period=10, mult=3.0, rr=2.0):
    bar = {"M5": 5, "M15": 15, "H1": 60}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    n = len(df)
    hl2 = ((df["high"] + df["low"]) / 2).values
    atrv = atr_prior(df, period).values
    close = df["close"].values
    times = df.index
    basic_ub = hl2 + mult * atrv
    basic_lb = hl2 - mult * atrv
    fu = basic_ub.copy(); fl = basic_lb.copy()
    for i in range(1, n):
        if np.isnan(basic_ub[i]) or np.isnan(fu[i-1]):
            continue
        fu[i] = basic_ub[i] if (basic_ub[i] < fu[i-1] or close[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = basic_lb[i] if (basic_lb[i] > fl[i-1] or close[i-1] < fl[i-1]) else fl[i-1]
    trend = np.ones(n, dtype=int)
    for i in range(1, n):
        if np.isnan(fu[i]) or np.isnan(fl[i]):
            trend[i] = trend[i-1]; continue
        if trend[i-1] == -1 and close[i] > fu[i]:
            trend[i] = 1
        elif trend[i-1] == 1 and close[i] < fl[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
    orders = []
    for i in range(period + 5, n - 2):
        if int(getattr(times[i], "day_of_week", times[i].dayofweek)) >= 5:
            continue
        if trend[i] == trend[i-1]:
            continue
        side = "long" if trend[i] == 1 else "short"
        px = float(close[i])
        sl = float(fl[i]) if side == "long" else float(fu[i])
        if np.isnan(sl):
            continue
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None:
            continue
        arm = bar_end(times[i], bar)
        v = f"st_{tf}_p{period}_m{mult:g}_rr{rr:g}"
        orders.append(Order(arm, side, "market", px, sl, tp, "Supertrend", v, {}, 60, 400))
    return dedupe_orders(orders, 30)


def generate_supertrend_family(m1):
    pools = {}
    for tf in ("M5", "M15"):
        for mult in (2.0, 3.0):
            for rr in (1.5, 2.0):
                oo = generate_supertrend(m1, tf, 10, mult, rr)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  st {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 10) NY first M15 ORB → M5 break (DbBPlWOuEpn / DdBQdZdRUpM group) ----------
def generate_ny_m15_orb(m1, range_min=15, open_utc=(13, 30), rr=2.0, entry="close_break"):
    h, m = open_utc
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        o0 = d + pd.Timedelta(hours=h, minutes=m)
        o1 = o0 + pd.Timedelta(minutes=range_min)
        seg = m1[(m1.index >= o0) & (m1.index < o1)]
        if len(seg) < max(5, range_min // 2):
            continue
        rh, rl = float(seg["high"].max()), float(seg["low"].min())
        if rh - rl < 0.2:
            continue
        win = m5[(m5.index >= o1) & (m5.index < o0 + pd.Timedelta(hours=3))]
        for t, r in win.iterrows():
            c = float(r["close"])
            atrv = float(a5.loc[t]) if t in a5.index and not np.isnan(a5.loc[t]) else 1.0
            side = None; sl = None
            if c > rh:
                side = "long"; sl = rl if (rh - rl) <= 8 else c - 1.0 * atrv
            elif c < rl:
                side = "short"; sl = rh if (rh - rl) <= 8 else c + 1.0 * atrv
            if side is None:
                continue
            px = c
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(t, 5)
            v = f"nyorb_r{range_min}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "NYORB", v, {}, 45, 180))
            break
    return dedupe_orders(orders, 60)


def generate_nyorb_family(m1):
    pools = {}
    for rm in (15, 30, 45):
        for rr in (1.5, 2.0, 3.0):
            oo = generate_ny_m15_orb(m1, rm, (13, 30), rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  nyorb {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- 11) Candle-22 H/L levels break (DcwTyNZinbN) ----------
def generate_c22(m1, hour=22, rr=2.0):
    h1 = resample_ohlc(m1, "60min")
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        # previous day's 22:00 candle
        prev = d - pd.Timedelta(days=1)
        ts = prev + pd.Timedelta(hours=hour)
        if ts not in h1.index:
            continue
        hi, lo = float(h1.loc[ts, "high"]), float(h1.loc[ts, "low"])
        day_seg = m5[(m5.index >= d + pd.Timedelta(hours=7)) & (m5.index < d + pd.Timedelta(hours=20))]
        for t, r in day_seg.iterrows():
            c = float(r["close"])
            atrv = float(a5.loc[t]) if t in a5.index and not np.isnan(a5.loc[t]) else 1.0
            side = None; sl = None
            if c > hi:
                side = "long"; sl = max(lo, c - 1.5 * atrv)
            elif c < lo:
                side = "short"; sl = min(hi, c + 1.5 * atrv)
            if side is None:
                continue
            px = c
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(t, 5)
            v = f"c22_h{hour}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "Candle22", v, {}, 60, 300))
            break
    return dedupe_orders(orders, 120)


def generate_c22_family(m1):
    pools = {}
    for h in (21, 22):
        for rr in (1.5, 2.0):
            oo = generate_c22(m1, h, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  c22 {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- Wave3b: Casper / mr.trade one-candle (DSdSZapkve3 = DSFm9FdirRv) ----------
def generate_casper(m1, rr=3.0, open_h=13, open_m=30):
    """9:30–9:35 ET (=13:30–13:35 UTC EDT) M5 H/L → M1 FVG beyond range → dig into FVG + engulf → RR.
    Also try 14:30 UTC (EST). Closed-bar only.
    """
    m5 = resample_ohlc(m1, "5min")
    m1r = resample_ohlc(m1, "1min")
    a1 = atr_prior(m1r, 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        for oh in (open_h, open_h + 1):  # EDT / EST proxies
            t0 = d + pd.Timedelta(hours=oh, minutes=open_m)
            t1 = t0 + pd.Timedelta(minutes=5)
            bar = m5[(m5.index >= t0) & (m5.index < t1)]
            if len(bar) == 0:
                # exact index
                if t0 in m5.index:
                    bar = m5.loc[[t0]]
                else:
                    continue
            hi = float(bar["high"].max()); lo = float(bar["low"].min())
            if hi - lo < 0.4:
                continue
            # scan M1 after the range candle for FVG that breaks beyond hi/lo
            scan = m1r[(m1r.index >= t1) & (m1r.index < t0 + pd.Timedelta(hours=3))]
            if len(scan) < 10:
                continue
            idx = list(scan.index)
            h = scan["high"].values; l = scan["low"].values
            o = scan["open"].values; c = scan["close"].values
            atrv = a1.reindex(scan.index).values
            taken = False
            for i in range(2, len(scan) - 2):
                # bull FVG breaking above hi: low[i] > high[i-2] and low[i] >= hi*ish
                gap_bull = l[i] > h[i - 2]
                gap_bear = h[i] < l[i - 2]
                atr_i = atrv[i] if not np.isnan(atrv[i]) else 1.0
                side = None; gap_lo = gap_hi = None
                if gap_bull and c[i] > hi and (l[i] - h[i - 2]) >= 0.05 * atr_i:
                    side = "long"; gap_lo, gap_hi = h[i - 2], l[i]
                elif gap_bear and c[i] < lo and (l[i - 2] - h[i]) >= 0.05 * atr_i:
                    side = "short"; gap_lo, gap_hi = h[i], l[i - 2]
                if side is None:
                    continue
                # wait for dig into FVG then engulf
                for j in range(i + 1, min(i + 40, len(scan) - 1)):
                    dug = (l[j] <= gap_hi and h[j] >= gap_lo)
                    if not dug:
                        continue
                    # next bar engulf of dig bar
                    k = j + 1
                    if k >= len(scan):
                        break
                    engulf = False
                    if side == "long":
                        engulf = c[k] > o[k] and c[k] > max(o[j], c[j]) and o[k] <= min(o[j], c[j]) + 0.05
                        # softer: close above dig high
                        engulf = engulf or (c[k] > h[j] and c[k] > o[k])
                    else:
                        engulf = c[k] < o[k] and c[k] < min(o[j], c[j]) and o[k] >= max(o[j], c[j]) - 0.05
                        engulf = engulf or (c[k] < l[j] and c[k] < o[k])
                    if not engulf:
                        continue
                    px = float(c[k])
                    sl = float(lo - 0.1) if side == "long" else float(hi + 0.1)
                    # tighten if wild
                    if abs(px - sl) > 10:
                        sl = px - 2.5 if side == "long" else px + 2.5
                    risk, tp = _rr_tp(side, px, sl, rr)
                    if risk is None:
                        break
                    arm = bar_end(idx[k], 1)
                    v = f"casper_h{oh}_rr{rr:g}"
                    orders.append(Order(arm, side, "market", px, sl, tp, "Casper1C", v, {}, 30, 180))
                    taken = True
                    break
                if taken:
                    break
            if taken:
                break
    return dedupe_orders(orders, 60)


def generate_casper_family(m1):
    pools = {}
    for rr in (2.0, 3.0):
        for oh in (13,):  # family already tries oh and oh+1 inside
            oo = generate_casper(m1, rr=rr, open_h=oh)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  casper {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- Wave3b: NY opposite-candle break (DIontHst4UC a_emdadian) ----------
def generate_ny_opp(m1, rr=2.0, impulse_atr=1.2):
    """After NY open (13:00 UTC), detect first impulse ≥ impulse_atr*ATR on M5;
    wait opposite-color M5 candle; trade break of that candle in impulse direction.
    """
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        for ny_h in (13, 14):
            t0 = d + pd.Timedelta(hours=ny_h)
            t1 = t0 + pd.Timedelta(hours=4)
            seg = m5[(m5.index >= t0) & (m5.index < t1)]
            if len(seg) < 15:
                continue
            idx = list(seg.index)
            o = seg["open"].values; h = seg["high"].values
            l = seg["low"].values; c = seg["close"].values
            atrv = a5.reindex(seg.index).values
            # find impulse: cumulative move over 3–8 bars
            impulse_dir = 0; impulse_end = None
            for i in range(3, min(24, len(seg) - 5)):
                atr_i = atrv[i] if not np.isnan(atrv[i]) else 1.5
                for look in (3, 4, 5, 6, 8):
                    if i - look < 0:
                        continue
                    move = c[i] - o[i - look]
                    if abs(move) >= impulse_atr * atr_i:
                        impulse_dir = 1 if move > 0 else -1
                        impulse_end = i
                        break
                if impulse_dir:
                    break
            if not impulse_dir:
                continue
            # find first opposite-color candle after impulse
            opp_i = None
            for j in range(impulse_end + 1, min(impulse_end + 18, len(seg) - 2)):
                bull = c[j] > o[j]; bear = c[j] < o[j]
                if impulse_dir > 0 and bear:
                    opp_i = j; break
                if impulse_dir < 0 and bull:
                    opp_i = j; break
            if opp_i is None:
                continue
            opp_hi, opp_lo = float(h[opp_i]), float(l[opp_i])
            if opp_hi - opp_lo < 0.25:
                continue
            # break in impulse direction
            for k in range(opp_i + 1, min(opp_i + 24, len(seg))):
                side = None; sl = None; px = float(c[k])
                if impulse_dir > 0 and c[k] > opp_hi:
                    side = "long"; sl = opp_lo - 0.1
                elif impulse_dir < 0 and c[k] < opp_lo:
                    side = "short"; sl = opp_hi + 0.1
                if side is None:
                    continue
                if abs(px - sl) > 10:
                    sl = px - 2.5 if side == "long" else px + 2.5
                risk, tp = _rr_tp(side, px, sl, rr)
                if risk is None:
                    break
                arm = bar_end(idx[k], 5)
                v = f"nyopp_h{ny_h}_rr{rr:g}"
                orders.append(Order(arm, side, "market", px, sl, tp, "NYOpp", v, {}, 60, 240))
                break
            break  # one per day
    return dedupe_orders(orders, 90)


def generate_ny_opp_family(m1):
    pools = {}
    for rr in (1.5, 2.0, 3.0):
        oo = generate_ny_opp(m1, rr=rr)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  nyopp {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---------- Wave3b: London box 10:30–15:30 IR + fractal break + RSI (DVMCmDkDS7D) ----------
def generate_lon_fractal(m1, rr=2.0, use_rsi=True):
    """Iran 10:30–15:30 = 07:00–12:00 UTC. Box H/L; fade last M15 leg via break of last swing;
    optional RSI14 M15 filter (long RSI<50, short RSI>50).
    """
    m15 = resample_ohlc(m1, "15min")
    m5 = resample_ohlc(m1, "5min")
    r15 = rsi(m15["close"], 14)
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        b0 = d + pd.Timedelta(hours=7)
        b1 = d + pd.Timedelta(hours=12)
        box = m15[(m15.index >= b0) & (m15.index < b1)]
        if len(box) < 8:
            continue
        box_hi = float(box["high"].max()); box_lo = float(box["low"].min())
        # last move: last 2 M15 bars direction
        last = box.iloc[-2:]
        last_dir = 1 if float(last["close"].iloc[-1]) > float(last["open"].iloc[0]) else -1
        # last swing: in last half of box, swing high/low (3-bar fractal)
        half = box.iloc[len(box) // 2:]
        hh = half["high"].values; ll = half["low"].values
        swing_hi = swing_lo = None
        for i in range(1, len(half) - 1):
            if hh[i] >= hh[i - 1] and hh[i] >= hh[i + 1]:
                swing_hi = float(hh[i])
            if ll[i] <= ll[i - 1] and ll[i] <= ll[i + 1]:
                swing_lo = float(ll[i])
        if swing_hi is None:
            swing_hi = float(half["high"].max())
        if swing_lo is None:
            swing_lo = float(half["low"].min())
        # fade last move: if last up → short on break of swing_lo; if last down → long on break swing_hi
        scan = m5[(m5.index >= b1) & (m5.index < b1 + pd.Timedelta(hours=5))]
        if len(scan) < 5:
            continue
        rsi_at = float(r15.iloc[r15.index.searchsorted(b1) - 1]) if len(r15) else 50.0
        if np.isnan(rsi_at):
            rsi_at = 50.0
        for t, r in scan.iterrows():
            c = float(r["close"]); px = c
            side = sl = None
            if last_dir > 0 and c < swing_lo:
                if use_rsi and rsi_at < 50:
                    continue  # want RSI>50 for shorts
                side = "short"; sl = min(swing_hi, box_hi) + 0.1
            elif last_dir < 0 and c > swing_hi:
                if use_rsi and rsi_at > 50:
                    continue
                side = "long"; sl = max(swing_lo, box_lo) - 0.1
            # also allow with-trend breakout of box as secondary (no RSI) — skip, stick to fade
            if side is None:
                continue
            if abs(px - sl) > 12:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(t, 5)
            tag = "rsi" if use_rsi else "norsi"
            v = f"lonfrac_{tag}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "LonFractal", v, {}, 90, 300))
            break
    return dedupe_orders(orders, 90)


def generate_lon_fractal_family(m1):
    pools = {}
    for use_rsi in (True, False):
        for rr in (1.5, 2.0, 3.0):
            oo = generate_lon_fractal(m1, rr=rr, use_rsi=use_rsi)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  lonfrac {oo[0].variant} n={len(oo)}", flush=True)
    return pools
