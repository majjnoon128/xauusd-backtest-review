"""Signal-only alerter stub — NEVER places orders (SGB EA ban).

Loop (live, future wiring):
1. Load promoted union/components from WATCHDOG_SPEC_FINAL shortlist
2. On new closed M5/M1 bar, generate candidate orders
3. Run advise_signal(...) gates
4. If ok: push alert (Telegram/Slack/UI) with side, entry, SL, TP, lots, risk$
5. Operator executes manually in MT5; watchdog only tracks fills the operator confirms

This module is intentionally incomplete for brokerage I/O.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .gates import AccountState, OpenRisk, GateResult, advise_signal, MIN_HOLD_SECONDS


@dataclass
class ManualAlert:
    side: str
    entry: float
    sl: float
    tp: Optional[float]
    lots: float
    risk_usd: float
    strategy: str
    note: str = "MANUAL EXECUTION REQUIRED — do not EA-send"


def build_alert(
    state: AccountState,
    open_risks: list,
    side: str,
    entry: float,
    sl: float,
    tp: Optional[float],
    strategy: str,
    spread: float,
    risk_budget: float = 8.0,
    contract_oz: float = 100.0,
) -> tuple[Optional[ManualAlert], GateResult]:
    sl_dist = abs(entry - sl)
    gate = advise_signal(state, open_risks, sl_dist, spread, risk_budget, contract_oz=contract_oz)
    if not gate.ok:
        return None, gate
    alert = ManualAlert(
        side=side, entry=entry, sl=sl, tp=tp, lots=gate.lots,
        risk_usd=gate.risk_usd, strategy=strategy,
        note=f"MANUAL EXECUTION REQUIRED; prefer hold winners ≥{MIN_HOLD_SECONDS}s",
    )
    return alert, gate
