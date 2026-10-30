"""Audited backtest engine — the ONLY fill engine (post ChatGPT/Claude audit).

Rules (bid Dukascopy OHLC + constant spread):
- Signals/orders armed AFTER signal bar ends (closed-bar).
- No fill on the signal/arm bar.
- Explicit bid/ask fills for long/short × entry/exit × market/limit/stop.
- Gap-through entries: fill at worse open, then resolve (incl. immediate SL if
  geometry already invalid) — never silently drop the trade.
- Intrabar ambiguity modes: sl_first (default/worst), tp_first, random.
- SL always live; 30s rule is accounting on profitable closed trades, not deferred exits.
- Concurrent risk: open risk sum <= max_open_risk_pct (default 3%).
- Default costs: spread 0.35, slip 0.10, commission 7/lot.
- Market orders: 1 M1 bar delay after arm time.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal, Tuple
import numpy as np
import pandas as pd

SPREAD = 0.35
SLIPPAGE = 0.10
COMMISSION_PER_LOT = 7.0
MARKET_DELAY_M1 = 1
OZ_PER_LOT = 100.0  # standard contract assumption for SGB XAU

OrderKind = Literal["limit", "stop", "market"]
IntrabarMode = Literal["sl_first", "tp_first", "random"]


@dataclass
class Order:
    """Pending order armed at arm_time (first eligible M1 is AFTER arm_time)."""
    arm_time: pd.Timestamp
    side: str                       # long | short
    kind: OrderKind
    price: float
    sl: float
    tp: float
    strategy: str
    variant: str
    meta: Dict[str, Any] = field(default_factory=dict)
    expire_minutes: int = 60
    max_hold_minutes: int | None = None
    min_hold_minutes: int | None = None  # DEPRECATED: ignored for exits; kept for API compat
    # Optional split exits: list of (lot_fraction, tp_price). Sum of fractions ≈ 1.
    # If unset, uses meta size_mult + single tp (legacy). Prefer legs for partials.
    legs: List[Tuple[float, float]] | None = None


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
    r_multiple: float           # net R (pnl / actual risk incl costs)
    reason: str
    duration_s: float
    same_m1_entry_exit: bool
    dxy_filter: bool
    vol_filter: bool
    day: str
    month: str
    r_gross: float = 0.0        # move / planned SL distance (no costs)
    risk_usd: float = 0.0
    leg: str = "full"
    parent_id: str = ""


def bid_ask(bid: float, spread: float = SPREAD) -> tuple[float, float]:
    return float(bid), float(bid) + float(spread)


def sl_distance_price(entry: float, sl: float, side: str, spread: float = SPREAD) -> float:
    """Adverse $ distance used for sizing (raw |entry-sl| + spread buffer)."""
    return abs(entry - sl) + spread


def _lots_from_risk_usd(risk_usd: float, dist_price: float) -> float:
    if dist_price <= 0 or risk_usd <= 0:
        return 0.0
    n_minilots = int(risk_usd // dist_price)
    return round(n_minilots * 0.01, 2)


def _lots_fractional(risk_usd: float, dist_price: float) -> float:
    if dist_price <= 0 or risk_usd <= 0:
        return 0.0
    return float(risk_usd / dist_price) * 0.01


def _lots(balance: float, risk_pct: float, entry: float, sl: float,
          spread: float = SPREAD, side: str = "long") -> float:
    dist = sl_distance_price(entry, sl, side, spread)
    return _lots_from_risk_usd(balance * risk_pct, dist)


# ---------------------------------------------------------------------------
# Bid/ask fill model (Dukascopy bars are BID)
# ---------------------------------------------------------------------------

def _can_fill_limit(side: str, limit: float, low: float, high: float, spread: float) -> bool:
    """Limit entry trigger on the correct side of the book."""
    if side == "long":
        # Buy limit: ask must trade <= limit → bid_low + spread <= limit
        return low <= limit - spread
    # Sell limit: bid must trade >= limit
    return high >= limit


def _can_fill_stop(side: str, stop: float, low: float, high: float, spread: float) -> bool:
    """Stop entry trigger on the correct side of the book."""
    if side == "long":
        # Buy stop: ask high >= stop → bid_high + spread >= stop
        return high >= stop - spread
    # Sell stop: bid low <= stop
    return low <= stop


def _fill_price(side: str, kind: OrderKind, order_price: float, bar_open: float,
                spread: float, slip: float) -> float:
    """Entry fill with gap-through at worse open. Returns the traded price.

    Long entries pay ask; short entries receive bid.
    """
    ask_open = bar_open + spread
    if kind == "limit":
        if side == "long":
            # buy limit: fill at min(limit, ask_open) + slip (never better than limit)
            px = min(order_price, ask_open)
            return px + slip
        # sell limit: fill at max(limit, bid_open) - slip
        px = max(order_price, bar_open)
        return px - slip
    if kind == "stop":
        if side == "long":
            # buy stop: fill at max(stop, ask_open) + slip
            px = max(order_price, ask_open)
            return px + slip
        # sell stop: fill at min(stop, bid_open) - slip
        px = min(order_price, bar_open)
        return px - slip
    # market
    if side == "long":
        return ask_open + slip
    return bar_open - slip


def _exit_stop_hit(side: str, sl: float, low: float, high: float, spread: float) -> bool:
    """Stop-loss hit check (closing trade)."""
    if side == "long":
        # sell stop: bid low <= sl
        return low <= sl
    # buy stop to cover: ask high >= sl → bid_high >= sl - spread
    return high >= sl - spread


def _exit_limit_hit(side: str, tp: float, low: float, high: float, spread: float) -> bool:
    """Take-profit hit check."""
    if side == "long":
        # sell limit: bid high >= tp
        return high >= tp
    # buy limit to cover: ask low <= tp → bid_low <= tp - spread
    return low <= tp - spread


def _exit_stop_fill(side: str, sl: float, bar_open: float, spread: float, slip: float) -> float:
    """Fill price when SL is hit (incl. gap through open)."""
    if side == "long":
        # sell stop: fill at min(sl, bid_open) - slip
        return min(sl, bar_open) - slip
    # buy stop: fill at max(sl, ask_open) + slip
    ask_open = bar_open + spread
    return max(sl, ask_open) + slip


def _exit_limit_fill(side: str, tp: float, bar_open: float, spread: float, slip: float) -> float:
    """Fill price when TP is hit. Apply slip adversely (pessimistic)."""
    if side == "long":
        # sell limit: fill at max(tp, bid_open) - slip (slip worsens exit)
        return max(tp, bar_open) - slip
    ask_open = bar_open + spread
    return min(tp, ask_open) + slip


def count_sl_cap_skips(orders: List[Order], max_sl_dist: float, spread: float = SPREAD) -> dict:
    total = len(orders)
    skip = 0
    for o in orders:
        dist = sl_distance_price(o.price, o.sl, o.side, spread)
        if dist > max_sl_dist + 1e-9:
            skip += 1
    return {"n_orders": total, "n_skipped": skip, "n_kept": total - skip,
            "skip_pct": (100.0 * skip / total) if total else 0.0, "max_sl_dist": max_sl_dist}


def _normalize_legs(o: Order) -> List[Tuple[float, float]]:
    """Return list of (fraction, tp). Fractions sum to ~1."""
    if o.legs:
        legs = [(float(f), float(tp)) for f, tp in o.legs if float(f) > 0]
        s = sum(f for f, _ in legs) or 1.0
        return [(f / s, tp) for f, tp in legs]
    sm = float((o.meta or {}).get("size_mult", 1.0) or 1.0)
    return [(max(sm, 1e-9), o.tp)]


def _actual_risk_usd(side: str, fill: float, sl: float, lots: float,
                     spread: float, commission: float) -> float:
    """USD risk at entry if stopped immediately (move to SL fill + commission)."""
    # Approximate immediate SL fill from current fill reference open≈fill side-adjusted
    if side == "long":
        # long SL exit at sl - slip approx; adverse move = fill - (sl) plus slip already in model
        move = fill - sl  # positive when SL below entry
    else:
        move = sl - fill
    # include spread already embedded in fill vs bid SL for longs; add commission
    raw = abs(move) * OZ_PER_LOT * lots
    return max(raw + commission * lots, 1e-9)


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
    max_open_risk_pct: float = 0.03,
    intrabar_mode: IntrabarMode = "sl_first",
    rng_seed: int = 42,
    calendar_days: int | None = None,
    daily_loss_pct: float = 0.05,
    max_loss_pct: float = 0.12,
) -> tuple[pd.DataFrame, dict]:
    if not orders:
        return pd.DataFrame(), _empty_stats(initial_balance)

    times = m1.index
    high = m1["high"].values
    low = m1["low"].values
    close = m1["close"].values
    open_ = m1["open"].values
    n = len(times)
    rng = np.random.default_rng(rng_seed)

    pending = []
    for o in orders:
        j = times.searchsorted(o.arm_time, side="left")
        if j >= n:
            continue
        if o.kind == "market":
            j += market_delay_m1
        if j >= n:
            continue
        expire_i = times.searchsorted(o.arm_time + pd.Timedelta(minutes=o.expire_minutes), side="right") - 1
        expire_i = min(max(expire_i, j), n - 1)
        raw = abs(o.price - o.sl)
        if raw < 0.05:
            continue
        if raw / max(o.price, 1e-9) > 0.02:
            continue
        dist = sl_distance_price(o.price, o.sl, o.side, spread)
        if max_sl_dist is not None and dist > max_sl_dist + 1e-9:
            continue
        if not allow_fractional:
            if _lots_from_risk_usd(initial_balance * risk_pct, dist) < 0.01:
                continue
        elif _lots_fractional(initial_balance * risk_pct, dist) <= 0:
            continue
        pending.append({"order": o, "start_i": j, "expire_i": expire_i, "risk_ref": dist})
    pending.sort(key=lambda x: (x["start_i"], x["order"].arm_time))

    balance = initial_balance
    trades: List[Trade] = []
    pi = 0
    consecutive_losses = 0
    day_start = initial_balance
    halted_day = None
    current_day = None
    # open positions: list of dicts with exit_i, risk_usd, ...
    open_pos: List[dict] = []
    trade_seq = 0

    def _prune_open(upto_i: int):
        nonlocal open_pos
        open_pos = [p for p in open_pos if p["exit_i"] > upto_i]

    def _open_risk() -> float:
        return sum(p["risk_usd"] for p in open_pos)

    while pi < len(pending):
        item = pending[pi]
        pi += 1
        o: Order = item["order"]
        filled = False
        fill_i = None
        fill_px = None

        for i in range(item["start_i"], item["expire_i"] + 1):
            t = times[i]
            dow = int(getattr(t, "day_of_week", getattr(t, "dayofweek", t.to_pydatetime().weekday())))
            day = t.strftime("%Y-%m-%d")
            if day != current_day:
                current_day = day
                day_start = balance
                consecutive_losses = 0
            if dow >= 5 or halted_day == day:
                continue
            # Static max loss / daily loss gates (flat between trades approx)
            if balance <= initial_balance * (1.0 - max_loss_pct):
                halted_day = day
                continue
            if day_start > 0 and (day_start - balance) / day_start >= daily_loss_pct:
                halted_day = day
                continue

            if o.kind == "limit":
                if not _can_fill_limit(o.side, o.price, low[i], high[i], spread):
                    continue
                fill_px = _fill_price(o.side, "limit", o.price, open_[i], spread, slip)
            elif o.kind == "stop":
                if not _can_fill_stop(o.side, o.price, low[i], high[i], spread):
                    continue
                fill_px = _fill_price(o.side, "stop", o.price, open_[i], spread, slip)
            else:
                fill_px = _fill_price(o.side, "market", open_[i], open_[i], spread, slip)

            filled = True
            fill_i = i
            break

        if not filled:
            continue

        # Gap through SL/TP: still take the trade; mark for immediate resolution
        gap_through_sl = (
            (o.side == "long" and fill_px <= o.sl) or
            (o.side == "short" and fill_px >= o.sl)
        )
        gap_through_tp = (
            (o.side == "long" and fill_px >= o.tp) or
            (o.side == "short" and fill_px <= o.tp)
        )

        dist = sl_distance_price(fill_px, o.sl, o.side, spread)
        if (not gap_through_sl) and max_sl_dist is not None and dist > max_sl_dist + 1e-9:
            continue
        if allow_fractional:
            lots_full = _lots_fractional(balance * risk_pct, max(dist, 0.01))
        else:
            lots_full = _lots_from_risk_usd(balance * risk_pct, max(dist, 0.01))
        if lots_full < 0.01 and not allow_fractional:
            if gap_through_sl:
                lots_full = 0.01  # still book the loss at min lot
            else:
                continue

        # Partial / multi-leg sizing at 0.01 granularity
        raw_legs = _normalize_legs(o)
        # If order used size_mult as a split sibling (legacy 1/3+2/3 separate orders),
        # treat size_mult as fraction of full risk lot.
        sm = float((o.meta or {}).get("size_mult", 1.0) or 1.0)
        if o.legs is None and sm != 1.0:
            raw_legs = [(sm, o.tp)]

        # Build executable legs with 0.01 lot floor rules
        exec_legs: List[Tuple[float, float, str]] = []
        if o.legs is not None:
            # Single position with split TPs
            rem = round(lots_full, 2)
            tagged = []
            for idx, (frac, tp_i) in enumerate(raw_legs):
                if idx < len(raw_legs) - 1:
                    lot_i = round(int(lots_full * frac / 0.01) * 0.01, 2)
                    rem = round(rem - lot_i, 2)
                else:
                    lot_i = rem
                tagged.append((lot_i, tp_i, f"leg{idx+1}"))
            nonzero = [(a, b, c) for a, b, c in tagged if a >= 0.01 - 1e-12]
            if not nonzero:
                # cannot split at 0.01 — single full exit, flag it
                exec_legs = [(lots_full, o.tp, "full_nosplit")]
            else:
                # if some legs zeroed, dump remainder onto last
                if len(nonzero) < len(tagged):
                    extra = round(lots_full - sum(a for a, _, _ in nonzero), 2)
                    a, b, c = nonzero[-1]
                    nonzero[-1] = (round(a + max(extra, 0), 2), b, c + "+merged")
                exec_legs = nonzero
        else:
            lot_i = round(lots_full * sm, 2) if allow_fractional else (
                round(int(lots_full * sm / 0.01) * 0.01, 2) if sm != 1.0 else lots_full
            )
            if lot_i < 0.01:
                if allow_fractional:
                    lot_i = lots_full * sm
                else:
                    # flag: cannot honor split sibling at 0.01
                    lot_i = 0.01 if gap_through_sl else 0.0
            if lot_i <= 0:
                continue
            leg_name = str((o.meta or {}).get("leg", "full"))
            exec_legs = [(lot_i, o.tp, leg_name)]

        # Concurrent risk gate
        _prune_open(fill_i - 1)
        planned_risk = sum(
            _actual_risk_usd(o.side, fill_px, o.sl, lot_i, spread, commission)
            for lot_i, _, _ in exec_legs
        )
        if _open_risk() + planned_risk > balance * max_open_risk_pct + 1e-9:
            # cannot open — skip (prop risk cap)
            continue

        parent_id = f"{o.strategy}|{o.variant}|{times[fill_i]}|{trade_seq}"
        trade_seq += 1
        last_exit_i = fill_i

        for lot_i, tp_i, leg_name in exec_legs:
            if gap_through_sl:
                # Immediate stop at open (worse): fill already past SL
                exit_px = _exit_stop_fill(o.side, o.sl, open_[fill_i], spread, slip)
                exit_i, reason, same = fill_i, "SL_GAP", True
            elif gap_through_tp and not gap_through_sl:
                # Entry gapped through TP — fill and take TP at open side
                exit_px = _exit_limit_fill(o.side, tp_i, open_[fill_i], spread, slip)
                exit_i, reason, same = fill_i, "TP_GAP", True
            else:
                exit_i, reason, exit_px, same = _resolve_exit(
                    o.side, fill_i, o.sl, tp_i, high, low, close, open_, n, slip, spread,
                    max_hold_minutes=o.max_hold_minutes,
                    trail_activate_r=(o.meta or {}).get("trail_activate_r"),
                    fill_px=fill_px, planned_risk=abs(o.price - o.sl),
                    intrabar_mode=intrabar_mode, rng=rng,
                )

            exit_t = times[exit_i]
            entry_t = times[fill_i]
            if o.side == "long":
                move = exit_px - fill_px
            else:
                move = fill_px - exit_px
            pnl = move * OZ_PER_LOT * lot_i - commission * lot_i
            planned = abs(o.price - o.sl)
            r_gross = (move / planned) if planned else 0.0
            risk_usd = _actual_risk_usd(o.side, fill_px, o.sl, lot_i, spread, commission)
            r_net = pnl / risk_usd if risk_usd > 0 else 0.0
            day = entry_t.strftime("%Y-%m-%d")
            trades.append(Trade(
                strategy=o.strategy, variant=o.variant, side=o.side, kind=o.kind,
                entry_time=entry_t, exit_time=exit_t, entry=fill_px, exit=exit_px,
                sl=o.sl, tp=tp_i, lots=lot_i, pnl_usd=pnl, r_multiple=r_net,
                reason=reason, duration_s=(exit_t - entry_t).total_seconds(),
                same_m1_entry_exit=same, dxy_filter=dxy_filter_flag,
                vol_filter=vol_filter_flag, day=day, month=entry_t.strftime("%Y-%m"),
                r_gross=r_gross, risk_usd=risk_usd, leg=leg_name, parent_id=parent_id,
            ))
            balance += pnl
            last_exit_i = max(last_exit_i, exit_i)
            open_pos.append({"exit_i": exit_i, "risk_usd": risk_usd})

            if pnl < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
            if use_circuit_breaker:
                if consecutive_losses >= 2 or (day_start > 0 and (day_start - balance) / day_start >= 0.01):
                    halted_day = day

        ed = times[last_exit_i].strftime("%Y-%m-%d")
        if ed != current_day:
            current_day = ed
            day_start = balance
            consecutive_losses = 0

    tdf = pd.DataFrame([asdict(t) for t in trades])
    # Calendar trading-days denominator
    if calendar_days is None and len(times):
        # weekdays in m1 span
        days_idx = pd.DatetimeIndex(times).normalize().unique()
        calendar_days = int(sum(1 for d in days_idx if getattr(d, "day_of_week", d.dayofweek) < 5))
    stats = compute_stats(tdf, initial_balance, balance, trading_days_override=calendar_days)
    stats["sub30s_profit_usd"] = _sub30s_profit(tdf)
    stats["sub30s_profit_pct_of_target"] = (
        stats["sub30s_profit_usd"] / (initial_balance * 0.08)
        if initial_balance else 0.0
    )
    return tdf, stats


def _sub30s_profit(tdf: pd.DataFrame) -> float:
    if tdf is None or tdf.empty:
        return 0.0
    m = (tdf["duration_s"] < 30) & (tdf["pnl_usd"] > 0)
    return float(tdf.loc[m, "pnl_usd"].sum()) if m.any() else 0.0


def _resolve_exit(side, fill_i, sl, tp, high, low, close, open_, n, slip, spread,
                  max_hold_minutes=None, trail_activate_r=None, fill_px=None,
                  planned_risk=None, intrabar_mode: IntrabarMode = "sl_first",
                  rng=None):
    """Resolve exit. SL is ALWAYS live (no min-hold deferral).

    When both SL and TP are reachable in the same bar, intrabar_mode decides:
      sl_first (default) | tp_first | random
    """
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

    def _pick(k, same, hit_sl, hit_tp):
        if hit_sl and hit_tp:
            mode = intrabar_mode
            if mode == "random":
                mode = "sl_first" if (rng.random() < 0.5 if rng is not None else True) else "tp_first"
            if mode == "tp_first":
                hit_sl = False
            else:
                hit_tp = False
        if hit_sl:
            return (k, "SL", _exit_stop_fill(side, cur_sl, open_[k], spread, slip), same)
        if hit_tp:
            return (k, "TP", _exit_limit_fill(side, tp, open_[k], spread, slip), same)
        return None

    def _check(k, same):
        _maybe_arm(k)
        hit_sl = _exit_stop_hit(side, cur_sl, low[k], high[k], spread)
        hit_tp = _exit_limit_hit(side, tp, low[k], high[k], spread)
        return _pick(k, same, hit_sl, hit_tp)

    r = _check(fill_i, True)
    if r is not None:
        return r

    for k in range(fill_i + 1, n):
        r = _check(k, False)
        if r is not None:
            return r
        hold_lim = max_hold_minutes if max_hold_minutes is not None else 2880
        if k - fill_i >= hold_lim:
            # time exit at bid close for long (sell), ask close for short (buy)
            if side == "long":
                px = float(close[k]) - slip
            else:
                px = float(close[k]) + spread + slip
            return k, "TIME", px, False
    if side == "long":
        px = float(close[-1]) - slip
    else:
        px = float(close[-1]) + spread + slip
    return n - 1, "EOD", px, False


def _empty_stats(bal):
    return {
        "n_trades": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy_r": 0.0,
        "profit_factor": 0.0, "max_dd_pct": 0.0, "net_pnl": 0.0,
        "final_balance": bal, "trades_per_day": 0.0, "trading_days": 0,
        "same_m1_n": 0, "same_m1_pct": 0.0,
        "sub30s_profit_usd": 0.0, "sub30s_profit_pct_of_target": 0.0,
        "avg_r_gross": 0.0,
    }


def compute_stats(tdf: pd.DataFrame, initial: float, final: float,
                  trading_days_override: int | None = None,
                  period_start=None, period_end=None) -> dict:
    if tdf is None or tdf.empty:
        st = _empty_stats(initial)
        if trading_days_override:
            st["trading_days"] = int(trading_days_override)
        return st
    wins = tdf[tdf["pnl_usd"] > 0]
    losses = tdf[tdf["pnl_usd"] <= 0]
    gp = float(wins["pnl_usd"].sum()) if len(wins) else 0.0
    gl = float(-losses["pnl_usd"].sum()) if len(losses) else 0.0
    pf = (gp / gl) if gl > 0 else (999.0 if gp > 0 else 0.0)
    eq = initial + tdf["pnl_usd"].cumsum()
    peak = eq.cummax()
    dd = ((peak - eq) / peak.replace(0, np.nan)).max()
    if trading_days_override is not None and trading_days_override > 0:
        days = int(trading_days_override)
    elif period_start is not None and period_end is not None:
        idx = pd.bdate_range(period_start, period_end)
        days = max(len(idx), 1)
    else:
        # fallback: unique trade days (LEGACY — inflated tpd). Prefer override.
        days = int(tdf["day"].nunique()) or 1
    same_n = int(tdf["same_m1_entry_exit"].sum()) if "same_m1_entry_exit" in tdf.columns else 0
    avg_r = float(tdf["r_multiple"].mean())
    avg_rg = float(tdf["r_gross"].mean()) if "r_gross" in tdf.columns else avg_r
    return {
        "n_trades": int(len(tdf)),
        "win_rate": float((tdf["pnl_usd"] > 0).mean()),
        "avg_r": avg_r,
        "expectancy_r": avg_r,
        "profit_factor": float(pf),
        "max_dd_pct": float(dd * 100) if pd.notna(dd) else 0.0,
        "net_pnl": float(tdf["pnl_usd"].sum()),
        "final_balance": float(final),
        "trades_per_day": float(len(tdf) / days),
        "trading_days": days,
        "same_m1_n": same_n,
        "same_m1_pct": same_n / len(tdf),
        "sub30s_profit_usd": _sub30s_profit(tdf),
        "avg_r_gross": avg_rg,
    }
