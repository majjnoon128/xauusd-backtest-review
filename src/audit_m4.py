#!/usr/bin/env python3
"""Rigorous audit of ProBTB m4 for lookahead / fill realism / cost / concentration."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RES = ROOT / "results"
RES.mkdir(exist_ok=True)

# ---- indicators (local, closed-bar safe) ----

def resample_ohlc(df, rule, label="left", closed="left"):
    o = df["open"].resample(rule, label=label, closed=closed).first()
    h = df["high"].resample(rule, label=label, closed=closed).max()
    l = df["low"].resample(rule, label=label, closed=closed).min()
    c = df["close"].resample(rule, label=label, closed=closed).last()
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()
    return out


def atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def pivot_confirmed(high, low, left=5, right=5):
    """Return arrays: pivot_high_price[i]=price if bar i confirmed as PH at bar i+right, else nan.
    Confirmation bar index = i+right (fully closed)."""
    n = len(high)
    ph_conf_bar = np.full(n, -1, dtype=int)  # conf_bar -> pivot_bar
    pl_conf_bar = np.full(n, -1, dtype=int)
    ph_price = np.full(n, np.nan)
    pl_price = np.full(n, np.nan)
    hv, lv = high.values, low.values
    for i in range(left, n - right):
        w = hv[i - left : i + right + 1]
        if hv[i] == w.max() and (w == hv[i]).sum() == 1:
            conf = i + right
            ph_conf_bar[conf] = i
            ph_price[conf] = hv[i]
        w = lv[i - left : i + right + 1]
        if lv[i] == w.min() and (w == lv[i]).sum() == 1:
            conf = i + right
            pl_conf_bar[conf] = i
            pl_price[conf] = lv[i]
    return ph_conf_bar, pl_conf_bar, ph_price, pl_price


def in_session(ts):
    h = ts.hour
    return ((7 <= h < 16) or (12 <= h < 21)) and ts.dayofweek < 5


@dataclass
class Setup:
    """Pending limit order after a valid breakout+return confirmation at a CLOSED bar."""
    side: str
    level: float
    sl: float
    tp: float          # set at fill time from risk
    rr: float
    brk_low: float
    brk_high: float
    atr: float
    confirm_m5_idx: int   # M5 bar index whose CLOSE confirms return (order armed after this bar)
    breakout_m5_idx: int


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    exit: float
    sl: float
    tp: float
    lots: float
    pnl_usd: float
    r_multiple: float
    reason: str
    duration_s: float
    same_m1_entry_exit: bool
    month: str
    day: str


def find_m4_setups(m5: pd.DataFrame) -> List[Setup]:
    """Detect breakouts on CLOSED M5 bars; arm limit only AFTER return bar CLOSES."""
    a = atr(m5, 14).values
    high, low, close, open_ = m5["high"].values, m5["low"].values, m5["close"].values, m5["open"].values
    n = len(m5)
    ph_conf, pl_conf, ph_px, pl_px = pivot_confirmed(m5["high"], m5["low"], 5, 5)

    levels_h: list[tuple[int, float]] = []  # (pivot_bar, price) known from conf onward
    levels_l: list[tuple[int, float]] = []
    setups: List[Setup] = []

    # Track armed breakouts waiting for return (breakout_idx, side, lvl, brk_*)
    pending_bo = []  # dicts

    for i in range(30, n):
        # Update known levels ONLY when pivot is confirmed at this closed bar
        if ph_conf[i] >= 0:
            levels_h.append((int(ph_conf[i]), float(ph_px[i])))
            levels_h = levels_h[-20:]
        if pl_conf[i] >= 0:
            levels_l.append((int(pl_conf[i]), float(pl_px[i])))
            levels_l = levels_l[-20:]

        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        # ATR for decisions: use PREVIOUS bar's ATR to avoid including current bar (conservative)
        atr_use = a[i - 1] if i > 0 and not np.isnan(a[i - 1]) else atr_i

        # --- Detect breakout at CLOSE of bar i (bar fully known) ---
        for li, lvl in levels_h:
            if i - li < 3 or i - li > 80:
                continue
            if not (close[i] > lvl and high[i] > lvl and open_[i] < lvl + 0.05 * atr_use):
                continue
            if (close[i] - open_[i]) < 0.3 * atr_use:
                continue
            pending_bo.append({
                "side": "long", "lvl": lvl, "bi": i,
                "brk_close": float(close[i]), "brk_high": float(high[i]), "brk_low": float(low[i]),
                "atr": float(atr_use), "expiry": i + 12,
            })
            break
        for li, lvl in levels_l:
            if i - li < 3 or i - li > 80:
                continue
            if not (close[i] < lvl and low[i] < lvl and open_[i] > lvl - 0.05 * atr_use):
                continue
            if (open_[i] - close[i]) < 0.3 * atr_use:
                continue
            pending_bo.append({
                "side": "short", "lvl": lvl, "bi": i,
                "brk_close": float(close[i]), "brk_high": float(high[i]), "brk_low": float(low[i]),
                "atr": float(atr_use), "expiry": i + 12,
            })
            break

        # --- Check pending breakouts for RETURN on this closed bar ---
        still = []
        for bo in pending_bo:
            if i <= bo["bi"]:
                still.append(bo)
                continue
            if i > bo["expiry"]:
                continue  # expired
            atr_b = bo["atr"]
            if bo["side"] == "long":
                touched = (low[i] <= bo["brk_close"] + 0.05 * atr_b) or (low[i] <= bo["lvl"] + 0.05 * atr_b)
                ran_away = high[i] > bo["brk_high"] + 1.5 * atr_b
            else:
                touched = (high[i] >= bo["brk_close"] - 0.05 * atr_b) or (high[i] >= bo["lvl"] - 0.05 * atr_b)
                ran_away = low[i] < bo["brk_low"] - 1.5 * atr_b
            if ran_away and not touched:
                continue  # abandon
            if not touched:
                still.append(bo)
                continue
            # Return CONFIRMED at close of bar i → arm limit order AFTER this bar
            # (order becomes active starting next M1 bar after M5 bar i ends)
            sl = (bo["brk_low"] - 0.05 * atr_b) if bo["side"] == "long" else (bo["brk_high"] + 0.05 * atr_b)
            setups.append(Setup(
                side=bo["side"], level=bo["lvl"], sl=sl, tp=0.0, rr=2.0,
                brk_low=bo["brk_low"], brk_high=bo["brk_high"], atr=atr_b,
                confirm_m5_idx=i, breakout_m5_idx=bo["bi"],
            ))
            # do not keep this breakout
        pending_bo = still

    return setups


def m5_bar_end(m5_index: pd.DatetimeIndex, idx: int) -> pd.Timestamp:
    """End time of M5 bar labeled at start (left label): start + 5 minutes."""
    return m5_index[idx] + pd.Timedelta(minutes=5)


def simulate_m4_realistic(
    m1: pd.DataFrame,
    m5: pd.DataFrame,
    setups: List[Setup],
    dxy: Optional[pd.DataFrame],
    *,
    spread: float = 0.25,
    slip: float = 0.05,
    commission: float = 7.0,
    order_delay_m1: int = 0,       # extra M1 bars after arm before order is live
    require_htf: bool = False,
    require_dxy: bool = False,
    min_sl_atr: float = 0.0,
    initial: float = 1000.0,
    risk_pct: float = 0.005,
    use_cb: bool = True,
    max_pending_bars_m1: int = 12 * 5,  # cancel if not filled within ~12 M5 bars
) -> tuple[pd.DataFrame, dict, dict]:
    """
    Fill rules for buy limit (long): need ask <= limit, ask ≈ bid + spread.
    On bid data: fill when low <= limit - spread (conservative: ask touches limit).
    Short sell limit: fill when bid >= limit, i.e. high >= limit.
    No fill on the confirmation bar. Worst-case: on fill M1 bar, if SL reachable after fill → SL.
    Path: within M1 we don't have ticks; assume for long fill at limit: if low<=SL and high>=TP
    on same bar after fill, SL wins. For fill bar specifically: if bar low <= SL (long), SL first.
    """
    times = m1.index
    high = m1["high"].values
    low = m1["low"].values
    close = m1["close"].values
    n = len(m1)

    # HTF M15 closed only: shift so bar at T is previous completed
    m15 = resample_ohlc(m1, "15min")
    m15_ema = ema(m15["close"], 50)
    # At time t, last CLOSED M15 is the bar that ended <= t.
    # With left labels, bar starting at T covers [T, T+15). It closes at T+15.
    # So last closed start = floor_15(t) - 15min.
    m15_close = m15["close"]
    m15_ema_s = m15_ema

    dxy_close = dxy["close"] if dxy is not None else None
    dxy_ema = ema(dxy["close"], 50) if dxy is not None else None

    def last_closed_m15(t):
        # bar ends at start+15m; want start+15m <= t → start <= t-15m
        deadline = t - pd.Timedelta(minutes=15)
        j = m15_close.index.searchsorted(deadline, side="right") - 1
        if j < 50:
            return None, None
        return float(m15_close.iloc[j]), float(m15_ema_s.iloc[j])

    def last_closed_dxy(t):
        if dxy_close is None:
            return None, None
        deadline = t - pd.Timedelta(minutes=15)
        j = dxy_close.index.searchsorted(deadline, side="right") - 1
        if j < 50:
            return None, None
        return float(dxy_close.iloc[j]), float(dxy_ema.iloc[j])

    # Arm each setup at first M1 index AFTER M5 confirm bar ends (+ delay)
    orders = []
    for s in setups:
        arm_time = m5_bar_end(m5.index, s.confirm_m5_idx)
        j = times.searchsorted(arm_time)
        j += order_delay_m1
        if j >= n:
            continue
        risk = abs(s.level - s.sl)
        if risk < 0.05:
            continue
        if min_sl_atr > 0 and risk < min_sl_atr * s.atr:
            continue
        if risk > 3.0 * s.atr:
            continue
        tp = s.level + s.rr * risk if s.side == "long" else s.level - s.rr * risk
        orders.append({
            "side": s.side, "limit": s.level, "sl": s.sl, "tp": tp, "atr": s.atr,
            "arm_i": j, "expire_i": min(n - 1, j + max_pending_bars_m1),
            "risk": risk,
        })
    orders.sort(key=lambda o: o["arm_i"])

    balance = initial
    trades: List[Trade] = []
    oi = 0
    consecutive_losses = 0
    day_start = initial
    halted_day = None
    current_day = None
    pos = None
    same_bar_profit = 0.0
    same_bar_count = 0
    total_profit = 0.0

    # Process chronologically: either manage position or try fills
    # Simpler: iterate orders; when flat, try to fill from arm_i onward using M1
    while oi < len(orders):
        o = orders[oi]
        oi += 1
        if pos is not None:
            continue  # shouldn't happen with sequential

        # skip orders whose arm is while we'd be busy — handled by skipping overlapping via exit time
        filled = False
        fill_i = None
        fill_px = None

        for i in range(o["arm_i"], o["expire_i"] + 1):
            t = times[i]
            day = t.strftime("%Y-%m-%d")
            if day != current_day:
                current_day = day
                day_start = balance
                consecutive_losses = 0
            if t.dayofweek >= 5 or halted_day == day:
                continue
            if not in_session(t):
                continue

            # filters at arm/fill time using last CLOSED HTF only
            if require_htf:
                c15, e15 = last_closed_m15(t)
                if c15 is None:
                    continue
                if o["side"] == "long" and not (c15 > e15):
                    continue
                if o["side"] == "short" and not (c15 < e15):
                    continue
            if require_dxy:
                cd, ed = last_closed_dxy(t)
                if cd is None:
                    continue
                if o["side"] == "long" and not (cd < ed):  # DXY bearish
                    continue
                if o["side"] == "short" and not (cd > ed):
                    continue

            # Fill check
            if o["side"] == "long":
                # ask = bid + spread; need ask <= limit → low + 0 <= ... use: low <= limit - spread
                # Conservative: require low <= limit - spread
                if low[i] <= o["limit"] - spread:
                    fill_px = o["limit"] + slip  # pay slip on top of limit (buy)
                    # Worst case on fill bar: if SL reachable (low <= sl), we get stopped
                    # Also if open gaps through limit, fill at open-ish — keep limit+slip for limit order
                    filled = True
                    fill_i = i
                    hit_sl_same = low[i] <= o["sl"]
                    hit_tp_same = high[i] >= o["tp"]
                    break
            else:
                # sell limit: fill when bid >= limit → high >= limit
                if high[i] >= o["limit"]:
                    fill_px = o["limit"] - slip
                    filled = True
                    fill_i = i
                    hit_sl_same = high[i] >= o["sl"]
                    hit_tp_same = low[i] <= o["tp"]
                    break

        if not filled:
            continue

        # Size
        lots = max(0.01, round((balance * risk_pct) / (o["risk"] * 100.0), 2))
        entry_t = times[fill_i]

        # Same-bar exit resolution (worst case = SL first if SL touched)
        if o["side"] == "long":
            if hit_sl_same:
                exit_i, reason, exit_px = fill_i, "SL", o["sl"] - slip
                same = True
            elif hit_tp_same:
                # both? already prefer SL. Only TP:
                exit_i, reason, exit_px = fill_i, "TP", o["tp"] - slip
                same = True
            else:
                same = False
                exit_i = None
        else:
            if hit_sl_same:
                exit_i, reason, exit_px = fill_i, "SL", o["sl"] + slip
                same = True
            elif hit_tp_same:
                exit_i, reason, exit_px = fill_i, "TP", o["tp"] + slip
                same = True
            else:
                same = False
                exit_i = None

        if not same:
            # scan subsequent M1 bars; worst-case if both SL and TP in same bar → SL
            for k in range(fill_i + 1, n):
                if o["side"] == "long":
                    sl_hit = low[k] <= o["sl"]
                    tp_hit = high[k] >= o["tp"]
                    if sl_hit and tp_hit:
                        exit_i, reason, exit_px = k, "SL", o["sl"] - slip
                        break
                    if sl_hit:
                        exit_i, reason, exit_px = k, "SL", o["sl"] - slip
                        break
                    if tp_hit:
                        exit_i, reason, exit_px = k, "TP", o["tp"] - slip
                        break
                else:
                    sl_hit = high[k] >= o["sl"]
                    tp_hit = low[k] <= o["tp"]
                    if sl_hit and tp_hit:
                        exit_i, reason, exit_px = k, "SL", o["sl"] + slip
                        break
                    if sl_hit:
                        exit_i, reason, exit_px = k, "SL", o["sl"] + slip
                        break
                    if tp_hit:
                        exit_i, reason, exit_px = k, "TP", o["tp"] + slip
                        break
                if k - fill_i > 2880:
                    exit_i, reason, exit_px = k, "TIME", close[k]
                    break
            if exit_i is None:
                exit_i, reason, exit_px = n - 1, "EOD", close[-1]

        exit_t = times[exit_i]
        if o["side"] == "long":
            move = exit_px - fill_px
        else:
            move = fill_px - exit_px
        # commission; spread already in fill logic via limit-spread requirement / slip
        pnl = move * 100.0 * lots - commission * lots
        r_mult = move / o["risk"] if o["risk"] else 0.0
        dur = (exit_t - entry_t).total_seconds()
        same_flag = (exit_i == fill_i)
        tr = Trade(
            side=o["side"], entry_time=entry_t, exit_time=exit_t,
            entry=fill_px, exit=exit_px, sl=o["sl"], tp=o["tp"], lots=lots,
            pnl_usd=pnl, r_multiple=r_mult, reason=reason, duration_s=dur,
            same_m1_entry_exit=same_flag,
            month=entry_t.strftime("%Y-%m"), day=entry_t.strftime("%Y-%m-%d"),
        )
        trades.append(tr)
        balance += pnl
        total_profit += pnl
        if same_flag:
            same_bar_count += 1
            same_bar_profit += pnl

        if pnl < 0:
            consecutive_losses += 1
        else:
            consecutive_losses = 0
        if use_cb:
            day = entry_t.strftime("%Y-%m-%d")
            # refresh day_start if needed
            if (day_start - balance) / day_start >= 0.01 or consecutive_losses >= 2:
                halted_day = day

        # skip later orders that arm before this exit
        while oi < len(orders) and orders[oi]["arm_i"] <= exit_i:
            oi += 1

        # day tracking at exit
        ed = exit_t.strftime("%Y-%m-%d")
        if ed != current_day:
            current_day = ed
            day_start = balance
            consecutive_losses = 0

    tdf = pd.DataFrame([asdict(t) for t in trades])
    stats = _stats(tdf, initial, balance)
    extra = {
        "same_m1_n": same_bar_count,
        "same_m1_share_of_trades": same_bar_count / len(trades) if trades else 0,
        "same_m1_pnl": same_bar_profit,
        "same_m1_share_of_pnl": (same_bar_profit / total_profit) if total_profit != 0 else 0,
        "n_setups": len(setups),
        "n_orders_armed": len(orders),
    }
    return tdf, stats, extra


def _stats(tdf, initial, final):
    if tdf is None or tdf.empty:
        return {"n_trades": 0, "win_rate": 0.0, "avg_r": 0.0, "profit_factor": 0.0,
                "max_dd_pct": 0.0, "net_pnl": 0.0, "final_balance": final, "trades_per_day": 0.0}
    wins = tdf[tdf.pnl_usd > 0]
    losses = tdf[tdf.pnl_usd <= 0]
    gp = float(wins.pnl_usd.sum()) if len(wins) else 0.0
    gl = float(-losses.pnl_usd.sum()) if len(losses) else 0.0
    pf = (gp / gl) if gl > 0 else (999.0 if gp > 0 else 0.0)
    eq = initial + tdf.pnl_usd.cumsum()
    peak = eq.cummax()
    dd = ((peak - eq) / peak.replace(0, np.nan)).max()
    days = max(1, tdf.day.nunique())
    return {
        "n_trades": int(len(tdf)),
        "win_rate": float((tdf.pnl_usd > 0).mean()),
        "avg_r": float(tdf.r_multiple.mean()),
        "profit_factor": float(pf),
        "max_dd_pct": float(dd * 100) if pd.notna(dd) else 0.0,
        "net_pnl": float(tdf.pnl_usd.sum()),
        "final_balance": float(final),
        "trades_per_day": float(len(tdf) / days),
    }


def monte_carlo(r, n_sims=4000, risks=(0.005, 0.01), seed=42):
    rng = np.random.default_rng(seed)
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 20:
        return pd.DataFrame()
    rows = []
    for risk in risks:
        passes = busts = 0
        days_list = []
        for _ in range(n_sims):
            bal = 1000.0
            day_bal = 1000.0
            cons = 0
            trades_today = 0
            day = 0
            day_cap = 2
            for t in range(400):
                if trades_today == 0:
                    day += 1
                    day_bal = bal
                    cons = 0
                    day_cap = int(rng.integers(1, 4))
                if cons >= 2 or (day_bal - bal) / day_bal >= 0.01:
                    trades_today = 0
                    continue
                rr = r[int(rng.integers(0, len(r)))]
                bal += bal * risk * rr
                cons = cons + 1 if rr < 0 else 0
                trades_today += 1
                if trades_today >= day_cap:
                    trades_today = 0
                if bal <= 1000 * 0.88:
                    busts += 1
                    break
                if (day_bal - bal) / day_bal >= 0.05:
                    busts += 1
                    break
                if bal >= 1100:
                    passes += 1
                    days_list.append(day)
                    break
        rows.append({
            "risk_pct": risk * 100,
            "pass_prob": passes / n_sims,
            "bust_prob": busts / n_sims,
            "timeout_prob": 1 - (passes + busts) / n_sims,
            "median_days_to_pass": float(np.median(days_list)) if days_list else None,
            "n_r": len(r),
        })
    return pd.DataFrame(rows)


def split_oos(m1, frac=0.30):
    cut = m1.index[int(len(m1) * (1 - frac))]
    return m1[m1.index < cut], m1[m1.index >= cut], cut


def run_period(m1_part, m5_full, setups_all, dxy, **kw):
    # filter setups whose confirm bar end is inside period
    m5 = m5_full
    kept = []
    for s in setups_all:
        end = m5_bar_end(m5.index, s.confirm_m5_idx)
        if m1_part.index.min() <= end <= m1_part.index.max():
            kept.append(s)
    return simulate_m4_realistic(m1_part, m5, kept, dxy, **kw)


def main():
    print("Loading...")
    m1 = pd.read_parquet(DATA / "XAUUSD.parquet")
    if m1.index.tz is None:
        m1.index = m1.index.tz_localize("UTC")
    dxy = pd.read_parquet(DATA / "DXY_synth.parquet")
    if dxy.index.tz is None:
        dxy.index = dxy.index.tz_localize("UTC")
    m5 = resample_ohlc(m1, "5min")
    is_m1, oos_m1, cut = split_oos(m1)
    print(f"M5 bars={len(m5)} OOS cut={cut}")

    print("Finding closed-bar m4 setups...")
    setups = find_m4_setups(m5)
    print(f"Armed setups (return confirmed on closed M5): {len(setups)}")

    scenarios = [
        ("A_baseline_old_costs", dict(spread=0.25, slip=0.05, order_delay_m1=0, require_htf=False, require_dxy=False, min_sl_atr=0.0)),
        ("B_closed_bar_minSL0.8", dict(spread=0.25, slip=0.05, order_delay_m1=0, require_htf=False, require_dxy=False, min_sl_atr=0.8)),
        ("C_htf_minSL0.8", dict(spread=0.25, slip=0.05, order_delay_m1=0, require_htf=True, require_dxy=False, min_sl_atr=0.8)),
        ("D_strict_cost_delay", dict(spread=0.35, slip=0.10, order_delay_m1=1, require_htf=False, require_dxy=False, min_sl_atr=0.8)),
        ("E_strict+htf", dict(spread=0.35, slip=0.10, order_delay_m1=1, require_htf=True, require_dxy=False, min_sl_atr=0.8)),
        ("F_strict+htf+dxy", dict(spread=0.35, slip=0.10, order_delay_m1=1, require_htf=True, require_dxy=True, min_sl_atr=0.8)),
    ]

    rows = []
    monthly_dump = {}
    mc_dump = {}
    extras = {}

    for name, kw in scenarios:
        print(f"\n=== {name} ===")
        for label, part in (("IS", is_m1), ("OOS", oos_m1), ("FULL", m1)):
            tr, st, ex = run_period(part, m5, setups, dxy, **kw)
            row = {"scenario": name, "label": label, **st, **ex}
            rows.append(row)
            print(f"  {label}: n={st['n_trades']} WR={st['win_rate']:.1%} R={st['avg_r']:.2f} "
                  f"PF={st['profit_factor']:.2f} DD={st['max_dd_pct']:.1f}% "
                  f"sameM1={ex['same_m1_n']} ({ex['same_m1_share_of_trades']:.1%}) "
                  f"samePnLshare={ex['same_m1_share_of_pnl']:.1%}")
            if label == "OOS" and tr is not None and not tr.empty:
                monthly = tr.groupby("month").agg(n=("pnl_usd", "count"), sum_r=("r_multiple", "sum"),
                                                   avg_r=("r_multiple", "mean"), pnl=("pnl_usd", "sum"))
                monthly_dump[name] = monthly
                print(monthly.to_string())
                tr.to_csv(RES / f"audit_m4_{name}_OOS_trades.csv", index=False)
                mc = monte_carlo(tr["r_multiple"].values)
                mc_dump[name] = mc
                if not mc.empty:
                    print(mc.to_string(index=False))
            extras[(name, label)] = ex

    sdf = pd.DataFrame(rows)
    sdf.to_csv(RES / "audit_m4_scenarios.csv", index=False)

    # Bias findings document data
    findings = {
        "lookahead_issues_original": [
            "M5 bars labeled at period START; signals used high/low/close of bar j at times[j] (=bar open) → acting with knowledge of the full bar (lookahead).",
            "m4 filled on the SAME touch/return bar (entry_t=times[j]) instead of arming a limit after confirmation and filling on a later bar.",
            "Engine started SL/TP scan at j+1, so same-bar SL after fill was never checked (optimistic).",
            "DXY/M15 filter used searchsorted(time)-1 on left-labeled bars → could read a still-forming HTF candle.",
            "ATR at breakout bar included the breakout bar itself.",
        ],
        "pivot_note": "Original used ph[i-5] with right=5, so pivot confirmation itself was OK (no future beyond confirm). Level list was fine; the fill timing was not.",
        "audit_fixes": [
            "Pivots added only on confirmation bar (i+right).",
            "Breakout and return require CLOSED M5; limit armed only AFTER return bar ends.",
            "Fill on subsequent M1 only; long fill requires low <= limit - spread (ask touch).",
            "On fill M1 bar (and any bar): if SL touched, SL first (worst case).",
            "HTF/DXY use last bar whose period END <= decision time.",
            "Scenarios with spread 0.35, slip 0.10, 1-M1 delay.",
        ],
    }
    (RES / "audit_m4_findings.json").write_text(json.dumps(findings, indent=2))

    # Save monthly
    for name, monthly in monthly_dump.items():
        monthly.to_csv(RES / f"audit_m4_{name}_monthly.csv")
    for name, mc in mc_dump.items():
        if mc is not None and not mc.empty:
            mc.to_csv(RES / f"audit_m4_{name}_mc.csv", index=False)

    # Update RESULTS.md
    update_results_md(sdf, monthly_dump, mc_dump, findings, len(setups), cut)
    print("\nAudit complete.")


def update_results_md(sdf, monthly_dump, mc_dump, findings, n_setups, cut):
    path = ROOT / "RESULTS.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    # remove old audit section if present
    marker = "\n## حسابرسی بایاس ProBTB m4"
    if marker in text:
        text = text.split(marker)[0].rstrip()

    lines = [marker, "",
             "### بایاس‌های نسخه‌ی اول (صریح)",
             ]
    for x in findings["lookahead_issues_original"]:
        lines.append(f"- {x}")
    lines.append(f"- نکته پیوت: {findings['pivot_note']}")
    lines.append("")
    lines.append("### اصلاحات اعمال‌شده در این حسابرسی")
    for x in findings["audit_fixes"]:
        lines.append(f"- {x}")
    lines.append(f"- تعداد ستاپ‌های m4 با تأیید کندل بسته‌شده: **{n_setups}**")
    lines.append(f"- برش OOS: `{cut}`")
    lines.append("")
    lines.append("### قبل / بعد (اعداد واقعی حسابرسی)")
    lines.append("")
    lines.append("| سناریو | بخش | n | WR | avg R | PF | MaxDD% | same-M1 n | سهم same-M1 از PnL |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in sdf.iterrows():
        lines.append(
            f"| {r['scenario']} | {r['label']} | {int(r['n_trades'])} | {r['win_rate']*100:.1f}% | "
            f"{r['avg_r']:.2f} | {r['profit_factor']:.2f} | {r['max_dd_pct']:.1f} | "
            f"{int(r['same_m1_n'])} | {r['same_m1_share_of_pnl']*100:.1f}% |"
        )
    lines.append("")
    lines.append("### مونت‌کارلو بعد از اصلاح (فقط OOS)")
    lines.append("| سناریو | ریسک% | P(پاس) | P(سوختن) | میانه روز |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, mc in mc_dump.items():
        if mc is None or mc.empty:
            continue
        for _, r in mc.iterrows():
            md = r["median_days_to_pass"] if pd.notna(r["median_days_to_pass"]) else "—"
            lines.append(
                f"| {name} | {r['risk_pct']:.1f} | {r['pass_prob']*100:.1f}% | "
                f"{r['bust_prob']*100:.1f}% | {md} |"
            )
    lines.append("")
    lines.append("### توزیع ماهانه R (OOS) — سناریوی سخت‌گیرانه اصلی")
    key = "E_strict+htf" if "E_strict+htf" in monthly_dump else (list(monthly_dump.keys())[-1] if monthly_dump else None)
    if key:
        lines.append(f"منبع: `{key}`")
        lines.append("")
        lines.append("| ماه | n | sum R | avg R | pnl $ |")
        lines.append("|---|---:|---:|---:|---:|")
        for m, r in monthly_dump[key].iterrows():
            lines.append(f"| {m} | {int(r['n'])} | {r['sum_r']:.1f} | {r['avg_r']:.2f} | {r['pnl']:.1f} |")
        # concentration
        pnl = monthly_dump[key]["pnl"]
        if pnl.sum() != 0:
            top = pnl.abs().sort_values(ascending=False).head(2)
            share = top.sum() / pnl.abs().sum()
            lines.append("")
            lines.append(f"سهم قدرمطلق PnL دو ماه برتر از کل: **{share*100:.1f}%**")
    lines.append("")
    lines.append("### حکم حسابرسی (صریح)")
    # Decide blunt verdict from OOS strict scenarios
    def oos_row(scenario):
        sub = sdf[(sdf.scenario == scenario) & (sdf.label == "OOS")]
        return sub.iloc[0] if len(sub) else None
    e = oos_row("E_strict+htf")
    d = oos_row("D_strict_cost_delay")
    a = oos_row("A_baseline_old_costs")
    b = oos_row("B_closed_bar_minSL0.8")
    if e is not None and d is not None:
        if e["avg_r"] <= 0 or e["profit_factor"] < 1.0:
            lines.append(
                f"**لبه تقریباً از بین رفت یا منفی شد** تحت هزینه‌ی سخت + تأخیر ۱ کندل + HTF "
                f"(OOS n={int(e['n_trades'])}, WR={e['win_rate']*100:.1f}%, R={e['avg_r']:.2f}, PF={e['profit_factor']:.2f}). "
                "اعداد قبلی WR ۵۴–۶۳٪ و MC≈۱۰۰٪ **قابل اعتماد نبودند**؛ عمدتاً از پر شدن لیمیت روی همان بار لمس، "
                "نادیده گرفتن SL همبار، و خواندن کندل بسته‌نشده می‌آمدند."
            )
        elif e["avg_r"] < 0.15 or e["profit_factor"] < 1.2:
            lines.append(
                f"**لبه به‌شدت ضعیف شد** (OOS سخت‌گیرانه: R={e['avg_r']:.2f}, PF={e['profit_factor']:.2f}, "
                f"n={int(e['n_trades'])}). هنوز کمی مثبت است ولی دیگر برای پاس قطعی چالش کافی به نظر نمی‌رسد؛ "
                "MC قبلی نزدیک ۱۰۰٪ را نادیده بگیر."
            )
        else:
            lines.append(
                f"لبه بعد از اصلاحات هنوز روی OOS مثبت است (R={e['avg_r']:.2f}, PF={e['profit_factor']:.2f}) "
                f"ولی ضعیف‌تر از نسخه خام. فقط نسخه حسابرسی‌شده را مبنا قرار بده؛ MC را با همین استخر R تازه حساب کن."
            )
        if a is not None and b is not None:
            lines.append(
                f"مرجع مقایسه: سناریو A (اصلاح پرشدن، هزینه قدیم) OOS R={a['avg_r']:.2f}/PF={a['profit_factor']:.2f}؛ "
                f"B (+minSL0.8) R={b['avg_r']:.2f}/PF={b['profit_factor']:.2f}؛ "
                f"D (هزینه سخت+تأخیر) R={d['avg_r']:.2f}/PF={d['profit_factor']:.2f}."
            )
    lines.append("")
    lines.append(
        "**برای واچ‌داگ:** تا وقتی نسخه حسابرسی‌شده روی OOS با هزینه سخت PF≥۱.۲ و R پایدار ماهانه ندهد، "
        "m4 را با سایز کامل پراپ ران نکن. اگر لبه مانده، فقط با فیلترهای همین حسابرسی و ریسک ۰.۵٪."
    )
    lines.append("")

    path.write_text(text + "\n".join(lines), encoding="utf-8")
    print("Updated RESULTS.md audit section")


if __name__ == "__main__":
    main()
