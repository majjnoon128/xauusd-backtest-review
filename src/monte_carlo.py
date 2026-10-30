"""Monte Carlo simulation of SGB Class B challenge from a pool of trade R-multiples."""
from __future__ import annotations
import numpy as np
import pandas as pd


def run_mc(
    r_multiples: np.ndarray,
    *,
    n_sims: int = 5000,
    initial: float = 1000.0,
    risk_pcts=(0.005, 0.01, 0.015),
    target: float = 0.10,       # phase 1
    daily_dd: float = 0.05,
    max_dd: float = 0.12,
    circuit_2loss: bool = True,
    max_trades_per_sim: int = 400,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    r = np.asarray(r_multiples, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return pd.DataFrame()

    rows = []
    for risk in risk_pcts:
        passes = busts = 0
        days_list = []
        for _ in range(n_sims):
            bal = initial
            peak_ref = initial  # static max DD from initial
            day_bal = initial
            cons_loss = 0
            trades_today = 0
            day = 0
            outcome = "timeout"
            for t in range(max_trades_per_sim):
                # new day every ~3 trades (rough) — or random 1-4 trades/day
                if trades_today == 0:
                    day += 1
                    day_bal = bal
                    cons_loss = 0
                    day_cap = int(rng.integers(1, 4))
                # circuit breaker personal rule
                if circuit_2loss and cons_loss >= 2:
                    # skip rest of day
                    trades_today = day_cap
                    if trades_today >= day_cap:
                        trades_today = 0
                    continue
                # personal 1% daily stop
                if (day_bal - bal) / day_bal >= 0.01:
                    trades_today = 0
                    continue

                rr = r[int(rng.integers(0, len(r)))]
                pnl = bal * risk * rr
                bal += pnl
                if pnl < 0:
                    cons_loss += 1
                else:
                    cons_loss = 0
                trades_today += 1
                if trades_today >= day_cap:
                    trades_today = 0

                # SGB rules
                if bal <= initial * (1 - max_dd):
                    outcome = "bust"
                    busts += 1
                    break
                # daily DD from start-of-day (approx with equity=balance since flat between trades)
                if (day_bal - bal) / day_bal >= daily_dd:
                    outcome = "bust"
                    busts += 1
                    break
                if bal >= initial * (1 + target):
                    outcome = "pass"
                    passes += 1
                    days_list.append(day)
                    break
            else:
                outcome = "timeout"

        rows.append({
            "risk_pct": risk * 100,
            "n_sims": n_sims,
            "pass_prob": passes / n_sims,
            "bust_prob": busts / n_sims,
            "timeout_prob": 1 - (passes + busts) / n_sims,
            "median_days_to_pass": float(np.median(days_list)) if days_list else None,
            "n_r_pool": len(r),
        })
    return pd.DataFrame(rows)
