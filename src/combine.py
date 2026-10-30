"""Multi-strategy portfolio under prop rules + overlap / correlation analysis."""
from __future__ import annotations
from typing import List, Dict
import numpy as np
import pandas as pd
from engine import Order


def signal_overlap(orders_by_strat: Dict[str, List[Order]], window_min: int = 30) -> pd.DataFrame:
    names = list(orders_by_strat.keys())
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa = sorted(orders_by_strat[a], key=lambda s: s.arm_time)
            sb = sorted(orders_by_strat[b], key=lambda s: s.arm_time)
            overlaps = conflicts = 0
            for x in sa:
                for y in sb:
                    dt = abs((x.arm_time - y.arm_time).total_seconds()) / 60.0
                    if dt <= window_min:
                        if x.side == y.side:
                            overlaps += 1
                        else:
                            conflicts += 1
            rows.append({
                "a": a, "b": b, "same_side_overlaps": overlaps,
                "opposite_conflicts": conflicts,
                "n_a": len(sa), "n_b": len(sb),
            })
    return pd.DataFrame(rows)


def outcome_correlation(trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()
    daily = trades.groupby(["strategy", "day"])["pnl_usd"].sum().unstack(0).fillna(0)
    if daily.shape[1] < 2:
        return pd.DataFrame()
    return daily.corr()


def signals_per_day_stats(orders: List[Order]) -> dict:
    if not orders:
        return {"avg": 0, "median": 0, "pct_zero_days": 100, "n_days": 0,
                "london_avg": 0, "ny_avg": 0, "distribution": {}}
    df = pd.DataFrame([{
        "day": o.arm_time.strftime("%Y-%m-%d"),
        "hour": o.arm_time.hour,
        "session": ("london" if 7 <= o.arm_time.hour < 12 else
                    "ny" if 12 <= o.arm_time.hour < 21 else "other"),
    } for o in orders])
    days = pd.date_range(df["day"].min(), df["day"].max(), freq="B")
    counts = df.groupby("day").size()
    counts = counts.reindex([d.strftime("%Y-%m-%d") for d in days], fill_value=0)
    dist = counts.value_counts().sort_index().to_dict()
    by_sess = df.groupby(["day", "session"]).size().unstack(fill_value=0)
    return {
        "avg": float(counts.mean()),
        "median": float(counts.median()),
        "pct_zero_days": float((counts == 0).mean() * 100),
        "n_days": int(len(counts)),
        "london_avg": float(by_sess["london"].mean()) if "london" in by_sess else 0,
        "ny_avg": float(by_sess["ny"].mean()) if "ny" in by_sess else 0,
        "distribution": {int(k): int(v) for k, v in dist.items()},
    }


def build_combined_orders(
    orders_by_strat: Dict[str, List[Order]],
    priority: List[str] | None = None,
) -> List[Order]:
    priority = priority or list(orders_by_strat.keys())
    rank = {n: i for i, n in enumerate(priority)}
    all_o = []
    for name, ords in orders_by_strat.items():
        for o in ords:
            all_o.append(o)
    all_o.sort(key=lambda s: (s.arm_time, rank.get(s.strategy, 99)))
    out = []
    last_t = None
    for o in all_o:
        if last_t is not None and abs((o.arm_time - last_t).total_seconds()) < 300:
            continue
        out.append(o)
        last_t = o.arm_time
    return out
