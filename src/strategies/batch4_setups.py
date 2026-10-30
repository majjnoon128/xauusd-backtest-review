"""Batch4 setups — Sess17, Iran1630Box, HourCandle, FakeBO, Trend50PB."""
from __future__ import annotations
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, rsi
from strategies.common import dedupe_orders


def _rr_tp(side, px, sl, rr):
    risk = abs(px - sl)
    if risk < 0.15:
        return None, None
    tp = px + rr * risk if side == "long" else px - rr * risk
    return risk, tp


# ---- 1) Sess17 / as_priceaction / DODs5arCJFB ----
# 17:00 on chart: Tehran=13:30UTC (EDT 9:30), broker+2=15:00, broker+3=14:00, UTC=17:00; also EST 9:30=14:30
SESS17_HOURS = {
    "tehran_edt": (13, 30),   # 17:00 IR / 9:30 NY EDT
    "tehran_est": (14, 30),   # 18:00 IR / 9:30 NY EST
    "broker_p3": (14, 0),     # 17:00 UTC+3
    "broker_p2": (15, 0),     # 17:00 UTC+2
    "utc17": (17, 0),
}


def generate_sess17(m1, label="tehran_edt", hour_min=(13, 30), entry="close",
                    sl_mode="box", rr=2.0):
    """Single M5 candle at hour_min → box H/L → breakout.
    entry: close (close beyond) | stop (arm stop at box edge, fill on touch — approximated as first M5
           that trades beyond, entry=edge±spread-ish using close of break bar clipped to edge).
    sl_mode: box (other side) | mid (box midpoint).
    """
    h, m = hour_min
    m5 = resample_ohlc(m1, "5min")
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        t0 = d + pd.Timedelta(hours=h, minutes=m)
        t1 = t0 + pd.Timedelta(minutes=5)
        bar = m5[(m5.index >= t0) & (m5.index < t1)]
        if len(bar) == 0:
            if t0 in m5.index:
                bar = m5.loc[[t0]]
            else:
                continue
        hi = float(bar["high"].max()); lo = float(bar["low"].min())
        mid = 0.5 * (hi + lo)
        if hi - lo < 0.25:
            continue
        scan = m5[(m5.index >= t1) & (m5.index < t0 + pd.Timedelta(hours=4))]
        for ts, r in scan.iterrows():
            c, hh, ll = float(r["close"]), float(r["high"]), float(r["low"])
            side = None; px = None; sl = None
            if entry == "close":
                if c > hi:
                    side = "long"; px = c
                elif c < lo:
                    side = "short"; px = c
            else:  # stop-entry approx: first bar that trades beyond
                if hh > hi:
                    side = "long"; px = hi  # fill at stop
                elif ll < lo:
                    side = "short"; px = lo
            if side is None:
                continue
            if sl_mode == "box":
                sl = lo - 0.05 if side == "long" else hi + 0.05
            else:
                sl = mid
            # soft if wild
            if abs(px - sl) > 12:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(ts, 5)
            v = f"s17_{label}_{entry}_{sl_mode}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "Sess17", v, {}, 60, 240))
            break
    return dedupe_orders(orders, 60)


def generate_sess17_family(m1):
    pools = {}
    for label, hm in SESS17_HOURS.items():
        for entry in ("close", "stop"):
            for sl_mode in ("box", "mid"):
                for rr in (1.0, 1.5, 2.0, 3.0):
                    oo = generate_sess17(m1, label, hm, entry, sl_mode, rr)
                    if oo:
                        pools[oo[0].variant] = oo
    for k, v in list(pools.items())[:8]:
        print(f"  sess17 {k} n={len(v)}", flush=True)
    print(f"  sess17 total variants={len(pools)}", flush=True)
    return pools


# ---- 2) Iran 16:30–18:00 box (DNBZPi0tK90) = 13:00–14:30 UTC ----
def generate_iran1630(m1, entry="close", rr=2.0):
    m5 = resample_ohlc(m1, "5min")
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        b0 = d + pd.Timedelta(hours=13)
        b1 = d + pd.Timedelta(hours=14, minutes=30)
        box = m5[(m5.index >= b0) & (m5.index < b1)]
        if len(box) < 10:
            continue
        hi = float(box["high"].max()); lo = float(box["low"].min())
        if hi - lo < 0.5:
            continue
        scan = m5[(m5.index >= b1) & (m5.index < b1 + pd.Timedelta(hours=4))]
        for ts, r in scan.iterrows():
            c, hh, ll = float(r["close"]), float(r["high"]), float(r["low"])
            side = px = sl = None
            # body break preferred: close beyond
            if c > hi:
                side = "long"; px = c; sl = ll - 0.1  # SL behind break candle
                # also try box other side as alt via separate variant — primary = behind break candle
            elif c < lo:
                side = "short"; px = c; sl = hh + 0.1
            if side is None:
                continue
            if abs(px - sl) < 0.2:
                sl = lo - 0.1 if side == "long" else hi + 0.1
            if abs(px - sl) > 12:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(ts, 5)
            v = f"ir1630_{entry}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "Iran1630", v, {}, 60, 240))
            break
    return dedupe_orders(orders, 60)


def generate_iran1630_family(m1):
    pools = {}
    for rr in (1.5, 2.0, 3.0):
        # body-break SL behind candle
        oo = generate_iran1630(m1, "close", rr)
        if oo:
            pools[oo[0].variant] = oo
            print(f"  ir1630 {oo[0].variant} n={len(oo)}", flush=True)
        # also SL = other side of box
        oo2 = _iran1630_boxsl(m1, rr)
        if oo2:
            pools[oo2[0].variant] = oo2
            print(f"  ir1630 {oo2[0].variant} n={len(oo2)}", flush=True)
    return pools


def _iran1630_boxsl(m1, rr):
    m5 = resample_ohlc(m1, "5min")
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        b0 = d + pd.Timedelta(hours=13); b1 = d + pd.Timedelta(hours=14, minutes=30)
        box = m5[(m5.index >= b0) & (m5.index < b1)]
        if len(box) < 10:
            continue
        hi = float(box["high"].max()); lo = float(box["low"].min())
        if hi - lo < 0.5:
            continue
        scan = m5[(m5.index >= b1) & (m5.index < b1 + pd.Timedelta(hours=4))]
        for ts, r in scan.iterrows():
            c = float(r["close"]); side = None; px = c
            if c > hi:
                side = "long"; sl = lo - 0.05
            elif c < lo:
                side = "short"; sl = hi + 0.05
            if side is None:
                continue
            if abs(px - sl) > 12:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            arm = bar_end(ts, 5)
            v = f"ir1630_boxsl_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "Iran1630", v, {}, 60, 240))
            break
    return dedupe_orders(orders, 60)


# ---- 3) Hour candle 10:00 & 13:00 UTC (DN0mtpo2Isa); also 12:00 for DLc2 15:30IR ----
def generate_hour_candle(m1, hour=10, tf="M5", rr=2.0):
    bar = 5 if tf == "M5" else 3
    # use 5min always (3min not in engine cleanly); for M3 proxy use M5
    df = resample_ohlc(m1, "5min")
    orders = []
    dates = pd.Index(m1.index.normalize().unique())
    for d in dates:
        if d.dayofweek >= 5:
            continue
        t0 = d + pd.Timedelta(hours=hour)
        t1 = t0 + pd.Timedelta(minutes=5)
        # for H1 candle interpretation: use 60min bar
        if tf == "H1":
            t1 = t0 + pd.Timedelta(hours=1)
            bar_h = resample_ohlc(m1, "60min")
            row = bar_h[(bar_h.index >= t0) & (bar_h.index < t1)]
            if len(row) == 0:
                continue
            hi = float(row["high"].max()); lo = float(row["low"].min())
            scan_start = t1
            bar_m = 5
        else:
            row = df[(df.index >= t0) & (df.index < t1)]
            if len(row) == 0:
                continue
            hi = float(row["high"].max()); lo = float(row["low"].min())
            scan_start = t1
            bar_m = 5
        if hi - lo < 0.25:
            continue
        scan = df[(df.index >= scan_start) & (df.index < t0 + pd.Timedelta(hours=3))]
        for ts, r in scan.iterrows():
            c = float(r["close"]); side = None; px = c
            if c > hi:
                side = "long"; sl = lo - 0.05
            elif c < lo:
                side = "short"; sl = hi + 0.05
            if side is None:
                continue
            if abs(px - sl) > 12:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            # if hour==10 and already taken TP conceptually skip 13 — one trade per hour slot
            arm = bar_end(ts, bar_m)
            v = f"hour{hour}_{tf}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "HourCandle", v, {}, 60, 180))
            break
    return dedupe_orders(orders, 60)


def generate_hour_candle_family(m1):
    pools = {}
    for hour in (10, 12, 13):  # 12 = DLc2 15:30 IR
        for tf in ("M5", "H1"):
            for rr in (1.5, 2.0, 3.0):
                oo = generate_hour_candle(m1, hour, tf, rr)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  hour {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---- 4) Fake breakout fade (DMkpjvqMnyF) on M15/M30 ----
def generate_fake_bo(m1, tf="M15", range_lo=3.0, range_hi=12.0, rr=2.0):
    bar = 15 if tf == "M15" else 30
    df = resample_ohlc(m1, f"{bar}min")
    orders = []
    # rolling 6-bar range; first break that returns inside within 2 bars → fade
    idx = list(df.index)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    for i in range(8, len(df) - 4):
        if int(getattr(idx[i], "day_of_week", idx[i].dayofweek)) >= 5:
            continue
        # range of prior 4 bars
        rh = float(h[i - 4:i].max()); rl = float(l[i - 4:i].min())
        rng = rh - rl
        if rng < range_lo or rng > range_hi:
            continue
        # break bar i
        broke_hi = c[i] > rh; broke_lo = c[i] < rl
        if not (broke_hi or broke_lo):
            continue
        # return within next 2 bars
        returned = False
        for j in range(i + 1, min(i + 3, len(df))):
            if broke_hi and c[j] < rh:
                returned = True; ent_i = j; side = "short"
                px = float(c[j]); sl = float(h[i:j + 1].max()) + 0.1
                break
            if broke_lo and c[j] > rl:
                returned = True; ent_i = j; side = "long"
                px = float(c[j]); sl = float(l[i:j + 1].min()) - 0.1
                break
        if not returned:
            continue
        if abs(px - sl) > 12:
            sl = px - 3.0 if side == "long" else px + 3.0
        risk, tp = _rr_tp(side, px, sl, rr)
        if risk is None:
            continue
        # TP = range width * rr already via rr; claim uses range as TP scale
        arm = bar_end(idx[ent_i], bar)
        v = f"fakebo_{tf}_rr{rr:g}"
        orders.append(Order(arm, side, "market", px, sl, tp, "FakeBO", v, {}, 90, 300))
    return dedupe_orders(orders, 120)


def generate_fake_bo_family(m1):
    pools = {}
    for tf in ("M15", "M30"):
        for rr in (1.5, 2.0, 3.0):
            oo = generate_fake_bo(m1, tf, rr=rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  fakebo {oo[0].variant} n={len(oo)}", flush=True)
    return pools


# ---- 5) Trend 50% pullback (DPej / DPCW) ----
def generate_trend50(m1, tf="M15", rr=2.0, fib=0.5):
    bar = 15 if tf == "M15" else 5
    df = resample_ohlc(m1, f"{bar}min")
    a = atr_prior(df, 14)
    orders = []
    idx = list(df.index)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atrv = a.values
    for i in range(30, len(df) - 3):
        if int(getattr(idx[i], "day_of_week", idx[i].dayofweek)) >= 5:
            continue
        atr_i = atrv[i] if not np.isnan(atrv[i]) else 2.0
        # find impulse over last 8–20 bars
        for look in (8, 12, 16, 20):
            if i - look < 0:
                continue
            move = c[i - 1] - o[i - look]
            if abs(move) < 2.5 * atr_i:
                continue
            swing_hi = float(h[i - look:i].max()); swing_lo = float(l[i - look:i].min())
            rng = swing_hi - swing_lo
            if rng < 2.0:
                continue
            direction = 1 if move > 0 else -1
            lvl = swing_hi - fib * rng if direction > 0 else swing_lo + fib * rng
            # price traded into 50% zone this bar
            if direction > 0:
                if not (l[i] <= lvl <= h[i]):
                    continue
                # long continuation
                if c[i] <= o[i]:  # still pulling back
                    continue
                side = "long"; px = float(c[i]); sl = swing_lo - 0.1
            else:
                if not (l[i] <= lvl <= h[i]):
                    continue
                if c[i] >= o[i]:
                    continue
                side = "short"; px = float(c[i]); sl = swing_hi + 0.1
            if abs(px - sl) > 15:
                sl = px - 3.0 if side == "long" else px + 3.0
            risk, tp = _rr_tp(side, px, sl, rr)
            if risk is None:
                continue
            # TP toward opposite extreme of impulse (claim: take the 50% bounce)
            if direction > 0:
                tp2 = swing_hi
            else:
                tp2 = swing_lo
            # use max of rr-tp and swing extreme
            if side == "long":
                tp = max(tp, tp2)
            else:
                tp = min(tp, tp2)
            arm = bar_end(idx[i], bar)
            v = f"t50_{tf}_f{fib:g}_rr{rr:g}"
            orders.append(Order(arm, side, "market", px, sl, tp, "Trend50", v, {}, 60, 300))
            break
    return dedupe_orders(orders, 90)


def generate_trend50_family(m1):
    pools = {}
    for tf in ("M5", "M15"):
        for fib in (0.5, 0.618):
            for rr in (1.5, 2.0, 3.0):
                oo = generate_trend50(m1, tf, rr, fib)
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  t50 {oo[0].variant} n={len(oo)}", flush=True)
    return pools
