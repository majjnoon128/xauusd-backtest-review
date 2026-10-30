"""SGB Plan A risk gates for signal-only watchdog (manual execution).
No order placement — size/check/alert only. Compliant with EA/VPS ban.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import math


CONTRACT_OZ_DEFAULT = 100.0  # VERIFY in MT5 Specification before live
LOT_STEP = 0.01
TICK_SCALP_MAX_FRAC = 0.20  # of phase target
PHASE1_TARGET_FRAC = 0.08
DAILY_LOSS_FRAC = 0.05
MAX_LOSS_FRAC = 0.12
CONCURRENT_RISK_FRAC = 0.03
MIN_HOLD_SECONDS = 30


@dataclass
class AccountState:
    start_balance: float = 1000.0
    sod_balance: float = 1000.0  # balance at server midnight (~03:30 Tehran)
    live_balance: float = 1000.0
    live_equity: float = 1000.0
    tick_scalp_pnl: float = 0.0  # sum of winners closed <30s
    phase: int = 1  # 1 or 2
    consec_losses: int = 0
    day_dd_pct: float = 0.0  # (sod - equity)/sod * 100 if under


@dataclass
class OpenRisk:
    planned_risk_usd: float
    side: str
    sl_distance: float
    lots: float


@dataclass
class GateResult:
    ok: bool
    reason: str = ""
    lots: float = 0.0
    risk_usd: float = 0.0


def lots_for_risk(
    risk_usd: float,
    sl_distance: float,
    spread: float,
    commission_price_equiv: float = 0.0,
    contract_oz: float = CONTRACT_OZ_DEFAULT,
    lot_step: float = LOT_STEP,
) -> float:
    """lots = floor( risk$ / ((SL + spread + commission) * contract_oz) ) to lot_step.

    commission_price_equiv: commission expressed as equivalent price distance ($),
    e.g. RT_$per_lot / contract_oz for the sized trade is circular — prefer:
      denom = (sl + spread) * contract_oz; lots_raw = risk / denom;
      then subtract commission_rt * lots_raw from risk and re-solve once.
    Steering one-liner assumes commission already in price-equivalent dollars.
    """
    denom = (sl_distance + spread + commission_price_equiv) * contract_oz
    if denom <= 0 or risk_usd <= 0:
        return 0.0
    raw = risk_usd / denom
    # floor to step
    lots = math.floor(raw / lot_step + 1e-12) * lot_step
    return max(0.0, lots)


def check_daily_loss(state: AccountState) -> GateResult:
    floor = state.sod_balance * (1.0 - DAILY_LOSS_FRAC)
    # Official: breach on balance OR equity (even slippage)
    if state.live_balance <= floor or state.live_equity <= floor:
        return GateResult(False, f"daily_loss: bal/eq at or below SOD*0.95={floor:.2f}")
    return GateResult(True, "daily_ok")


def check_max_loss(state: AccountState) -> GateResult:
    floor = state.start_balance * (1.0 - MAX_LOSS_FRAC)
    if state.live_balance <= floor or state.live_equity <= floor:
        return GateResult(False, f"max_loss: bal/eq at or below static floor={floor:.2f}")
    return GateResult(True, "max_ok")


def check_concurrent(
    state: AccountState,
    open_risks: List[OpenRisk],
    new_risk_usd: float,
) -> GateResult:
    cap = CONCURRENT_RISK_FRAC * state.live_balance
    total = sum(r.planned_risk_usd for r in open_risks) + new_risk_usd
    if total > cap + 1e-9:
        return GateResult(False, f"concurrent_risk: {total:.2f} > 3% of live={cap:.2f}")
    return GateResult(True, "concurrent_ok", risk_usd=new_risk_usd)


def check_tick_scalp_cap(state: AccountState) -> GateResult:
    target = state.start_balance * (PHASE1_TARGET_FRAC if state.phase == 1 else 0.04)
    cap = TICK_SCALP_MAX_FRAC * target
    if state.tick_scalp_pnl >= cap:
        return GateResult(False, f"tick_scalp_cap: {state.tick_scalp_pnl:.2f} >= 20% target={cap:.2f}")
    return GateResult(True, "tick_ok")


def check_soft_cb(state: AccountState) -> GateResult:
    if state.consec_losses >= 2:
        return GateResult(False, "soft_cb: 2 consecutive losses")
    if state.day_dd_pct >= 1.0:
        return GateResult(False, "soft_cb: 1% daily DD")
    return GateResult(True, "soft_ok")


def advise_signal(
    state: AccountState,
    open_risks: List[OpenRisk],
    sl_distance: float,
    spread: float,
    risk_budget: float = 8.0,
    commission_price_equiv: float = 0.0,
    contract_oz: float = CONTRACT_OZ_DEFAULT,
    feed_ok: bool = True,
    feed_reason: str = "ok",
) -> GateResult:
    """All gates before emitting a manual-execution alert. Never places orders."""
    if not feed_ok:
        return GateResult(False, f"stale_or_bad_feed: {feed_reason}")
    for fn in (check_max_loss, check_daily_loss, check_tick_scalp_cap, check_soft_cb):
        r = fn(state)
        if not r.ok:
            return r
    lots = lots_for_risk(risk_budget, sl_distance, spread, commission_price_equiv, contract_oz)
    if lots < LOT_STEP - 1e-12:
        # Granularity: e.g. SL=8 + spread=0.30 → theoretical <0.01.
        # Surface min-lot risk for operator choice — still no auto-place.
        min_risk = LOT_STEP * (sl_distance + spread + commission_price_equiv) * contract_oz
        return GateResult(
            False,
            f"lots_below_min_step: need risk≥{min_risk:.2f} for 0.01 lot incl. costs; "
            f"or tighten SL. Operator may manually accept 0.01 if min_risk ≤ 3% concurrent.",
            lots=0.0,
            risk_usd=min_risk,
        )
    # actual risk at floored lots (price component only; spread already in sizing)
    actual_risk = lots * (sl_distance + spread + commission_price_equiv) * contract_oz
    r = check_concurrent(state, open_risks, actual_risk)
    if not r.ok:
        return r
    return GateResult(True, "emit_manual_alert", lots=lots, risk_usd=actual_risk)


def note_winner_hold_seconds(hold_s: float, pnl: float, state: AccountState) -> AccountState:
    """Call after a closed winner. If hold < 30s, add to tick-scalp PnL."""
    if pnl > 0 and hold_s < MIN_HOLD_SECONDS:
        state.tick_scalp_pnl += pnl
    return state
