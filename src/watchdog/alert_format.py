"""Format signal-only alert text for Bale/Telegram (≤4096 chars). No network send."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class AlertPayload:
    side: str
    entry: float
    sl: float
    tp: Optional[float]
    lots: float
    risk_usd: float
    strategy: str
    dollar_proxy: str = "EURUSD_inv"
    hold_note: str = "Hold winners ≥30s (tick-scalp cap)"


def format_alert(p: AlertPayload) -> str:
    tp = f"{p.tp:.2f}" if p.tp is not None else "—"
    text = (
        f"🔔 XAUUSD.X SIGNAL (MANUAL ONLY)\n"
        f"{p.side.upper()} @ {p.entry:.2f}\n"
        f"SL {p.sl:.2f} | TP {tp}\n"
        f"Lots {p.lots:.2f} | Risk ${p.risk_usd:.2f}\n"
        f"Setup: {p.strategy}\n"
        f"Dollar gate: {p.dollar_proxy}\n"
        f"{p.hold_note}\n"
        f"⛔ Do not EA-send — execute in MT5 manually"
    )
    if len(text) > 4096:
        text = text[:4090] + "…"
    return text
