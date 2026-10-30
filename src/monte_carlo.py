"""Monte Carlo of SGB Class B / Plan A phase-1 challenge.

Uses block bootstrap over the actual trade sequence (preserves clustering),
target 8%, 30-day limit, min 5 trading days, daily 5% / max 12% rules,
and empirical trades-per-day from the backtest.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def run_mc(
    r_multiples: np.ndarray,
    *,
    n_sims: int = 5000,
    initial: float = 1000.0,
    risk_pcts=(0.008,),          # $8 cap ≈ 0.8% on $1k
    target: float = 0.08,        # phase-1 8% (NOT 10%)
    daily_dd: float = 0.05,
    max_dd: float = 0.12,
    circuit_2loss: bool = True,
    max_days: int = 30,
    min_trading_days: int = 5,
    trades_per_day: float | None = None,
    trade_days: np.ndarray | None = None,  # optional day labels aligned with r
    block_size: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = np.asarray(r_multiples, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return pd.DataFrame()

    # Empirical trades/day
    if trades_per_day is None or trades_per_day <= 0:
        if trade_days is not None and len(trade_days) == len(r_multiples):
            td = pd.Series(trade_days)
            trades_per_day = float(td.groupby(td).size().mean())
        else:
            trades_per_day = 2.0
    # Block size ≈ one trading day of trades
    if block_size is None:
        block_size = max(1, int(round(trades_per_day)))

    rows = []
    for risk in risk_pcts:
        passes = busts = timeouts = min_day_fails = 0
        days_list = []
        for _ in range(n_sims):
            bal = initial
            day_bal = initial
            cons_loss = 0
            day = 0
            trading_days_used = 0
            outcome = "timeout"
            # Build a path by concatenating blocks until max_days
            path = []
            while day < max_days and len(path) < max_days * max(block_size * 3, 3):
                start = int(rng.integers(0, len(r)))
                block = [r[(start + k) % len(r)] for k in range(block_size)]
                path.extend(block)
                # consume one day per block
                day += 1
                trading_days_used += 1
                day_bal = bal
                cons_loss = 0
                for rr in block:
                    if circuit_2loss and cons_loss >= 2:
                        break
                    if day_bal > 0 and (day_bal - bal) / day_bal >= 0.01:
                        break  # personal 1% daily stop
                    pnl = bal * risk * rr
                    bal += pnl
                    if pnl < 0:
                        cons_loss += 1
                    else:
                        cons_loss = 0
                    if bal <= initial * (1 - max_dd):
                        outcome = "bust"
                        break
                    if day_bal > 0 and (day_bal - bal) / day_bal >= daily_dd:
                        outcome = "bust"
                        break
                    if bal >= initial * (1 + target):
                        outcome = "pass"
                        break
                if outcome in ("bust", "pass"):
                    break
            if outcome == "pass":
                if trading_days_used < min_trading_days:
                    # Must keep trading until min days even after hitting target early
                    # (SGB min 5 trading days) — count as fail-to-qualify unless we
                    # continue; treat as min_day_fail for reporting.
                    min_day_fails += 1
                    outcome = "min_days"
                else:
                    passes += 1
                    days_list.append(trading_days_used)
            elif outcome == "bust":
                busts += 1
            else:
                timeouts += 1

        rows.append({
            "risk_pct": risk * 100,
            "n_sims": n_sims,
            "target": target,
            "max_days": max_days,
            "block_size": block_size,
            "trades_per_day_assumed": trades_per_day,
            "pass_prob": passes / n_sims,
            "bust_prob": busts / n_sims,
            "timeout_prob": timeouts / n_sims,
            "min_days_fail_prob": min_day_fails / n_sims,
            "median_days_to_pass": float(np.median(days_list)) if days_list else None,
            "n_r_pool": len(r),
        })
    return pd.DataFrame(rows)
