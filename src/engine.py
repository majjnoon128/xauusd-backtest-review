"""Audited backtest engine — the ONLY fill engine.

Rules:
- Signals/orders are armed AFTER the signal bar ends (closed-bar).
- No fill on the signal/arm bar.
- Bid data + ask-side fills: long limit needs low <= limit - spread;
  long stop/market pays ask ≈ mid/bid + spread/2 + slip (we use entry + spread + slip for market buys).
- Intrabar on M1: if SL and TP both reachable → SL first (worst case).
- HTF/DXY consumers must use last CLOSED bars only (helpers in indicators).
- Default costs: spread 0.35, slip 0.10, commission 7/lot.
- Market orders: 1 M1 bar delay after arm time.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal
import numpy as np
import pandas as pd

SPREAD = 0.35
SLIPPAGE = 0.10
COMMISSION_PER_LOT = 7.0
MARKET_DELAY_M1 = 1


OrderKind = Literal["limit", "stop", "market"]


@dataclass
class Order:
    """Pending order armed at arm_time (first eligible M1 is AFTER arm_time)."""
    arm_time: pd.Timestamp          # instant order becomes known (bar end)
    side: str                       # long | short
    kind: OrderKind
    price: float                    # limit/stop price; for market = reference/close
    sl: float
    tp: float
    strategy: str
    variant: str
    meta: Dict[str, Any] = field(default_factory=dict)
    expire_minutes: int = 60        # cancel if unfilled
    max_hold_minutes: int | None = None  # flat at close after N M1 bars if set
    min_hold_minutes: int | None = None  # prop: ignore SL/TP until >= N M1 bars after fill


@dataclass
class Trade:
    strategy: str
    variant: str
    side: str
    kind: str
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
    dxy_filter: bool
    vol_filter: bool
    day: str
    month: str


def sl_distance_price(entry: float, sl: float, side: str, spread: float = SPREAD) -> float:
    """Effective adverse distance in $ price, including spread to fill/stop.
    For sizing: 0.01 lot risks ~$1 per $1 of this distance.
    """
    raw = abs(entry - sl)
    # Long pays ask on entry; SL is bid-side — add half-ish via full spread buffer
    return raw + spread


def _lots_from_risk_usd(risk_usd: float, dist_price: float) -> float:
    """lot = floor(risk_usd / dist_price) * 0.01. Returns 0 if cannot fit min lot under risk."""
    if dist_price <= 0 or risk_usd <= 0:
        return 0.0
    # Each 0.01 lot risks `dist_price` USD
    n_minilots = int(risk_usd // dist_price)  # floor
    return round(n_minilots * 0.01, 2)


def _lots_fractional(risk_usd: float, dist_price: float) -> float:
    """Continuous lot for analysis: exact risk_usd / (dist per 0.01-lot unit).
    0.01 lot risks `dist_price` USD → lots = (risk_usd / dist_price) * 0.01.
    """
    if dist_price <= 0 or risk_usd <= 0:
        return 0.0
    return float(risk_usd / dist_price) * 0.01


def _lots(balance: float, risk_pct: float, entry: float, sl: float,
          spread: float = SPREAD, side: str = "long") -> float:
    dist = sl_distance_price(entry, sl, side, spread)
    risk_usd = balance * risk_pct
    return _lots_from_risk_usd(risk_usd, dist)


def _fill_price(side: str, kind: OrderKind, order_price: float, bar_open: float,
                spread: float, slip: float) -> float:
    """Fill price with gap-through: if bar opens through the order, fill at worse open."""
    if kind == "limit":
        # buy limit: fill at min(limit, open) + slip (gap-down through limit → open)
        if side == "long":
            px = min(order_price, bar_open)
            return px + slip
        # sell limit: fill at max(limit, open) - slip
        px = max(order_price, bar_open)
        return px - slip
    if kind == "stop":
        # buy stop: if open gaps above stop → fill at open; else at stop
        if side == "long":
            px = max(order_price, bar_open)
            return px + spread + slip
        # sell stop: if open gaps below stop → fill at open
        px = min(order_price, bar_open)
        return px - spread - slip
    # market
    if side == "long":
        return order_price + spread + slip  # order_price should be last close/bid ref
    return order_price - spread - slip


def _can_fill_limit(side: str, limit: float, low: float, high: float, spread: float) -> bool:
    if side == "long":
        # ask = bid + spread; need ask <= limit → low <= limit - spread
        return low <= limit - spread
    # sell limit: bid >= limit
    return high >= limit


def _can_fill_stop(side: str, stop: float, low: float, high: float) -> bool:
    if side == "long":
        return high >= stop
    return low <= stop


def count_sl_cap_skips(orders: List[Order], max_sl_dist: float, spread: float = SPREAD) -> dict:
    """How many orders fail the hard SL distance cap (before simulation)."""
    total = len(orders)
    skip = 0
    for o in orders:
        dist = sl_distance_price(o.price, o.sl, o.side, spread)
        if dist > max_sl_dist + 1e-9:
            skip += 1
    return {"n_orders": total, "n_skipped": skip, "n_kept": total - skip,
            "skip_pct": (100.0 * skip / total) if total else 0.0, "max_sl_dist": max_sl_dist}

def simulate(
    m1: pd.DataFrame,
    orders: List[Order],
    *,
    initial_balance: float = 1000.0,
    risk_pct: float = 0.005,
    max_sl_dist: float | None = 7.5,
    use_circuit_breaker: bool = True,
    spread: float = SPREAD,
    slip: float = SLIPPAGE,
    commission: float = COMMISSION_PER_LOT,
    market_delay_m1: int = MARKET_DELAY_M1,
    dxy_filter_flag: bool = False,
    vol_filter_flag: bool = False,
    allow_fractional: bool = False,
) -> tuple[pd.DataFrame, dict]:
    if not orders:
        return pd.DataFrame(), _empty_stats(initial_balance)

    times = m1.index
    high = m1["high"].values
    low = m1["low"].values
    close = m1["close"].values
    open_ = m1["open"].values
    n = len(times)

    # Prepare armed entries: first eligible M1 index strictly AFTER arm_time (+ market delay)
    pending = []
    for o in orders:
        j = times.searchsorted(o.arm_time, side="right")  # first bar with time > arm? 
        # arm_time is bar END; first M1 at or after arm_time should NOT fill as signal bar.
        # searchsorted(arm_time, side='left') finds first >= arm_time; that bar starts at arm_time
        # which is the first bar AFTER the signal bar → eligible for waiting, but market delay applies.
        j = times.searchsorted(o.arm_time, side="left")
        if j >= n:
            continue
        # skip the first eligible bar for ALL kinds? Spec: "no fill on the signal bar".
        # Signal bar ended at arm_time; M1 bar starting at arm_time is NOT the signal bar.
        # So j is OK as first wait bar. Market orders get +delay.
        if o.kind == "market":
            j += market_delay_m1
        if j >= n:
            continue
        # Also never fill on a bar whose timestamp == signal meta bar start if provided
        expire_i = times.searchsorted(o.arm_time + pd.Timedelta(minutes=o.expire_minutes), side="right") - 1
        expire_i = min(max(expire_i, j), n - 1)
        risk = abs(o.price - o.sl) if o.kind != "market" else abs(o.price - o.sl)
        # For stop/limit, risk from order price; for market from intended entry ref
        raw = abs(o.price - o.sl)
        if raw < 0.05:
            continue
        if raw / max(o.price, 1e-9) > 0.02:
            continue
        dist = sl_distance_price(o.price, o.sl, o.side, spread)
        if max_sl_dist is not None and dist > max_sl_dist + 1e-9:
            continue  # HARD CAP: cannot fit even 0.01 lot under risk budget
        # Also skip if floor lot would be 0 under risk_pct * balance
        # (unless fractional analysis mode: take every geometrically valid signal)
        if not allow_fractional:
            if _lots_from_risk_usd(initial_balance * risk_pct, dist) < 0.01:
                continue
        elif _lots_fractional(initial_balance * risk_pct, dist) <= 0:
            continue
        pending.append({
            "order": o, "start_i": j, "expire_i": expire_i,
            "risk_ref": dist,
        })
    pending.sort(key=lambda x: x["start_i"])

    balance = initial_balance
    trades: List[Trade] = []
    pi = 0
    consecutive_losses = 0
    day_start = initial_balance
    halted_day = None
    current_day = None

    while pi < len(pending):
        item = pending[pi]
        pi += 1
        o: Order = item["order"]
        filled = False
        fill_i = None
        fill_px = None

        for i in range(item["start_i"], item["expire_i"] + 1):
            t = times[i]
            dow = getattr(t, "day_of_week", t.dayofweek)
            day = t.strftime("%Y-%m-%d")
            if day != current_day:
                current_day = day
                day_start = balance
                consecutive_losses = 0
            if dow >= 5 or halted_day == day:
                continue
            # session filter left to strategy; engine allows all weekdays in session if meta says so
            # Strategies should only emit in-session arms.

            if o.kind == "limit":
                if not _can_fill_limit(o.side, o.price, low[i], high[i], spread):
                    continue
                fill_px = _fill_price(o.side, "limit", o.price, open_[i], spread, slip)
            elif o.kind == "stop":
                if not _can_fill_stop(o.side, o.price, low[i], high[i]):
                    continue
                fill_px = _fill_price(o.side, "stop", o.price, open_[i], spread, slip)
            else:  # market — fill at this bar's open reference (close of prior already delayed)
                ref = open_[i]
                fill_px = _fill_price(o.side, "market", ref, open_[i], spread, slip)

            filled = True
            fill_i = i
            break

        if not filled:
            continue

        # Skip if fill already through SL or TP (gap) — no valid trade geometry
        if o.side == "long" and (fill_px <= o.sl or fill_px >= o.tp):
            continue
        if o.side == "short" and (fill_px >= o.sl or fill_px <= o.tp):
            continue
        dist = sl_distance_price(fill_px, o.sl, o.side, spread)
        if max_sl_dist is not None and dist > max_sl_dist + 1e-9:
            continue
        if allow_fractional:
            lots = _lots_fractional(balance * risk_pct, dist)
            if lots <= 0:
                continue
        else:
            lots = _lots_from_risk_usd(balance * risk_pct, dist)
            if lots < 0.01:
                continue
        # Optional partial-exit / split-leg sizing (NDS course 1/3 + 2/3)
        sm = float((o.meta or {}).get("size_mult", 1.0) or 1.0)
        if sm <= 0:
            continue
        if sm != 1.0:
            lots = float(lots) * sm
            if (not allow_fractional) and lots < 0.01:
                # keep fractional remainder for analysis when split would floor to 0
                lots = max(lots, 0.01 * sm)
        risk = dist  # for R-multiple: use effective distance

        # Same-bar / subsequent exit with worst-case SL first
        exit_i, reason, exit_px, same = _resolve_exit(
            o.side, fill_i, o.sl, o.tp, high, low, close, n, slip,
            max_hold_minutes=o.max_hold_minutes,
            min_hold_minutes=o.min_hold_minutes,
            trail_activate_r=(o.meta or {}).get("trail_activate_r"),
            fill_px=fill_px, planned_risk=abs(o.price - o.sl),
        )
        exit_t = times[exit_i]
        entry_t = times[fill_i]
        if o.side == "long":
            move = exit_px - fill_px
        else:
            move = fill_px - exit_px
        pnl = move * 100.0 * lots - commission * lots  # 0.01 lot => $1 per $1
        # R vs planned SL distance (raw entry ref to SL); costs already in fill/exit
        planned = abs(o.price - o.sl)
        r_mult = move / planned if planned else 0.0
        day = entry_t.strftime("%Y-%m-%d")
        trades.append(Trade(
            strategy=o.strategy, variant=o.variant, side=o.side, kind=o.kind,
            entry_time=entry_t, exit_time=exit_t, entry=fill_px, exit=exit_px,
            sl=o.sl, tp=o.tp, lots=lots, pnl_usd=pnl, r_multiple=r_mult,
            reason=reason, duration_s=(exit_t - entry_t).total_seconds(),
            same_m1_entry_exit=same, dxy_filter=dxy_filter_flag,
            vol_filter=vol_filter_flag, day=day, month=entry_t.strftime("%Y-%m"),
        ))
        balance += pnl
        if pnl < 0:
            consecutive_losses += 1
        else:
            consecutive_losses = 0
        if use_circuit_breaker:
            if consecutive_losses >= 2 or (day_start - balance) / day_start >= 0.01:
                halted_day = day

        while pi < len(pending) and pending[pi]["start_i"] <= exit_i:
            pi += 1

        ed = exit_t.strftime("%Y-%m-%d")
        if ed != current_day:
            current_day = ed
            day_start = balance
            consecutive_losses = 0

    tdf = pd.DataFrame([asdict(t) for t in trades])
    return tdf, compute_stats(tdf, initial_balance, balance)


def _resolve_exit(side, fill_i, sl, tp, high, low, close, n, slip, max_hold_minutes=None,
                 min_hold_minutes=None, trail_activate_r=None, fill_px=None, planned_risk=None):
    """Optional trail: after favorable excursion >= trail_activate_r * planned_risk, SL → BE (fill_px)."""
    cur_sl = sl
    be = fill_px
    armed_trail = False
    risk = planned_risk if planned_risk and planned_risk > 0 else abs((fill_px or 0) - sl)

    def _maybe_arm(k):
        nonlocal armed_trail, cur_sl
        if trail_activate_r is None or be is None or risk <= 0 or armed_trail:
            return
        if side == "long":
            if high[k] >= be + trail_activate_r * risk:
                armed_trail = True
                cur_sl = max(cur_sl, be)
        else:
            if low[k] <= be - trail_activate_r * risk:
                armed_trail = True
                cur_sl = min(cur_sl, be)

    # Prop min-hold: ignore SL/TP exits until >= min_hold M1 bars after fill.
    # Choice documented: defer exits; if SL/TP was traversed during the forbidden
    # window, exit at that level on the first eligible bar (SL priority).
    min_h = int(min_hold_minutes or 0)
    pending_sl = False
    pending_tp = False

    def _check(k, same):
        nonlocal cur_sl, pending_sl, pending_tp
        _maybe_arm(k)
        if side == "long":
            if low[k] <= cur_sl:
                pending_sl = True
            if high[k] >= tp:
                pending_tp = True
        else:
            if high[k] >= cur_sl:
                pending_sl = True
            if low[k] <= tp:
                pending_tp = True
        elapsed = k - fill_i
        if elapsed < min_h:
            return None
        if pending_sl:
            return (k, "SL", (cur_sl - slip) if side == "long" else (cur_sl + slip), same)
        if pending_tp:
            return (k, "TP", (tp - slip) if side == "long" else (tp + slip), same)
        return None

    r = _check(fill_i, True)
    if r is not None:
        return r

    for k in range(fill_i + 1, n):
        r = _check(k, False)
        if r is not None:
            return r
        hold_lim = max_hold_minutes if max_hold_minutes is not None else 2880
        if k - fill_i >= hold_lim:
            return k, "TIME", float(close[k]), False
    return n - 1, "EOD", float(close[-1]), False


def _empty_stats(bal):
    return {
        "n_trades": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy_r": 0.0,
        "profit_factor": 0.0, "max_dd_pct": 0.0, "net_pnl": 0.0,
        "final_balance": bal, "trades_per_day": 0.0, "trading_days": 0,
        "same_m1_n": 0, "same_m1_pct": 0.0,
    }


def compute_stats(tdf: pd.DataFrame, initial: float, final: float) -> dict:
    if tdf is None or tdf.empty:
        return _empty_stats(initial)
    wins = tdf[tdf["pnl_usd"] > 0]
    losses = tdf[tdf["pnl_usd"] <= 0]
    gp = float(wins["pnl_usd"].sum()) if len(wins) else 0.0
    gl = float(-losses["pnl_usd"].sum()) if len(losses) else 0.0
    pf = (gp / gl) if gl > 0 else (999.0 if gp > 0 else 0.0)
    eq = initial + tdf["pnl_usd"].cumsum()
    peak = eq.cummax()
    dd = ((peak - eq) / peak.replace(0, np.nan)).max()
    days = int(tdf["day"].nunique()) or 1
    same_n = int(tdf["same_m1_entry_exit"].sum()) if "same_m1_entry_exit" in tdf.columns else 0
    return {
        "n_trades": int(len(tdf)),
        "win_rate": float((tdf["pnl_usd"] > 0).mean()),
        "avg_r": float(tdf["r_multiple"].mean()),
        "expectancy_r": float(tdf["r_multiple"].mean()),
        "profit_factor": float(pf),
        "max_dd_pct": float(dd * 100) if pd.notna(dd) else 0.0,
        "net_pnl": float(tdf["pnl_usd"].sum()),
        "final_balance": float(final),
        "trades_per_day": float(len(tdf) / days),
        "trading_days": days,
        "same_m1_n": same_n,
        "same_m1_pct": same_n / len(tdf),
    }
