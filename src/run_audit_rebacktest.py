"""Post-audit rebacktest: pre-registered variants at SL cap=8, calendar-day tpd, new engine.

Holdout (untouched until final): 2025-10-01 → 2025-12-31
Selection/IS: 2026-01-01 → 2026-06-30
OOS (report): 2026-07-01 → 2026-10-28

Pre-registered list (fixed BEFORE looking at holdout):
  F3 NDS scalp M5 sym brk_p3
  NDS course_scalp_M3_sym
  NDS_Fidelity day M5 nd864
  F7 spike3d|c22d OR
  breaker M5/M1 rr1.5
  liqraid pdh_pdl rr1.5 kzany
"""
from __future__ import annotations
import json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine import simulate, Order
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course, generate_nds_mechanical, generate_nds_fidelity
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.common import apply_dxy_gate, dedupe_orders
from strategies.research_batch4 import generate_liq_raid
from strategies.research_batch3 import generate_breaker

DATA = ROOT.parent / "data"
OUT = ROOT.parent / "reports"
OUT.mkdir(exist_ok=True)

HOLDOUT_END = pd.Timestamp("2025-12-31", tz="UTC")
IS_START = pd.Timestamp("2026-01-01", tz="UTC")
OOS_START = pd.Timestamp("2026-07-01", tz="UTC")
CAP = 8.0


def load():
    m1 = pd.read_parquet(DATA / "XAUUSD.parquet")
    if m1.index.tz is None:
        m1.index = m1.index.tz_localize("UTC")
    dxy = None
    p = DATA / "DXY_synth.parquet"
    if p.exists():
        dxy = pd.read_parquet(p)
        if dxy.index.tz is None:
            dxy.index = dxy.index.tz_localize("UTC")
    return m1, dxy


def weekday_count(idx):
    d = pd.DatetimeIndex(idx).normalize().unique()
    return int(sum(1 for x in d if int(getattr(x, "day_of_week", x.dayofweek)) < 5))


def retag(orders, name):
    out = []
    for o in orders:
        out.append(Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy, name,
                         dict(o.meta or {}), o.expire_minutes, o.max_hold_minutes, o.min_hold_minutes,
                         getattr(o, "legs", None)))
    return out


def merge_or(parts, name):
    oo = []
    for orders, _ in parts:
        oo.extend(orders)
    oo = dedupe_orders(oo, 45)
    return retag(oo, name)


def build_preregistered(m1, dxy):
    pools = {}
    pools["F3_nds_M5_sym"] = retag(generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    ), "F3_nds_M5_sym")
    pools["nds_scalp_M3_sym"] = retag(generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M3",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    ), "nds_scalp_M3_sym")
    pools["NDS_Mechanical_day_M5"] = retag(generate_nds_mechanical(
        m1, None, use_dxy=False, use_vol=False, style="day", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0,
    ), "NDS_Mechanical_day_M5")
    pools["NDS_Fidelity_day_M5"] = retag(generate_nds_fidelity(
        m1, dxy, use_dxy=False, style="day", entry_tf="M5", confirm="brk_p3", min_atr=1.0,
    ), "NDS_Fidelity_day_M5")
    spike = apply_dxy_gate(generate_spike50(m1, "M15", 3.0), dxy, True)
    c22 = apply_dxy_gate(generate_c22(m1, 22, 2.0), dxy, True)
    pools["F7_spike3d_c22d_or"] = merge_or([(spike, "s"), (c22, "c")], "F7_spike3d_c22d_or")
    pools["brk_M5_M1_rr1.5"] = retag(generate_breaker(m1, dxy, False, "M5", "M1", 1.5, 1.0, CAP),
                                     "brk_M5_M1_rr1.5")
    pools["liqraid_pdh_pdl"] = retag(
        generate_liq_raid(m1, dxy, False, "pdh_pdl", 1.5, "any", CAP, False), "liqraid_pdh_pdl")
    return pools


def run_slice(orders, m1, label, cap=CAP):
    days = weekday_count(m1.index)
    tdf, st = simulate(m1, orders, max_sl_dist=cap, use_circuit_breaker=True,
                       risk_pct=0.008, initial_balance=1000.0, max_open_risk_pct=0.03,
                       calendar_days=days, allow_fractional=False)
    st = dict(st)
    st["slice"] = label
    st["cap"] = cap
    st["n_orders"] = len(orders)
    return tdf, st


def main():
    t0 = time.time()
    m1, dxy = load()
    print(f"data {m1.index.min()} → {m1.index.max()} n={len(m1)}", flush=True)
    print("building preregistered pools...", flush=True)
    pools = build_preregistered(m1, dxy)
    for k, v in pools.items():
        print(f"  {k}: {len(v)} orders", flush=True)

    rows = []
    trade_dumps = {}
    slices = {
        "IS": m1[(m1.index >= IS_START) & (m1.index < OOS_START)],
        "OOS": m1[m1.index >= OOS_START],
        "HOLDOUT": m1[m1.index <= HOLDOUT_END],
    }
    for name, orders in pools.items():
        for slabel, sm1 in slices.items():
            if len(sm1) < 1000:
                continue
            # filter orders whose arm is inside slice
            oo = [o for o in orders if sm1.index[0] <= o.arm_time <= sm1.index[-1]]
            tdf, st = run_slice(oo, sm1, slabel)
            st["name"] = name
            rows.append(st)
            print(f"{name:28s} {slabel:7s} n={st['n_trades']:4d} tpd={st['trades_per_day']:.3f} "
                  f"WR={st['win_rate']:.2f} avgR={st['avg_r']:.3f} PF={st['profit_factor']:.2f} "
                  f"DD={st['max_dd_pct']:.1f}%", flush=True)
            if slabel == "OOS" and len(tdf):
                trade_dumps[name] = tdf

    # Union of IS-positive components on OOS (IS expectancy > 0, n>=20)
    is_ok = {r["name"] for r in rows if r["slice"] == "IS" and r["n_trades"] >= 20 and r["avg_r"] > 0}
    print("IS survivors:", sorted(is_ok), flush=True)
    oos_m1 = slices["OOS"]
    union_orders = []
    for name in sorted(is_ok):
        oo = [o for o in pools[name] if oos_m1.index[0] <= o.arm_time <= oos_m1.index[-1]]
        union_orders.extend(oo)
    union_orders = dedupe_orders(sorted(union_orders, key=lambda o: o.arm_time), 5)
    tdf_u, st_u = run_slice(union_orders, oos_m1, "OOS_UNION")
    st_u["name"] = "UNION_IS_positive"
    rows.append(st_u)
    print(f"UNION OOS n={st_u['n_trades']} tpd={st_u['trades_per_day']:.3f} avgR={st_u['avg_r']:.3f} "
          f"PF={st_u['profit_factor']:.2f} DD={st_u['max_dd_pct']:.1f}", flush=True)

    # MC on union
    mc = pd.DataFrame()
    if len(tdf_u):
        mc = run_mc(tdf_u["r_multiple"].values, risk_pcts=(0.008,), target=0.08,
                    trades_per_day=st_u["trades_per_day"], n_sims=3000,
                    trade_days=tdf_u["day"].values)
        print("MC:\n", mc.to_string(index=False), flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "audit_rebacktest.csv", index=False)
    # uncapped diagnostic for NDS M3
    oo = [o for o in pools["nds_scalp_M3_sym"] if oos_m1.index[0] <= o.arm_time <= oos_m1.index[-1]]
    _, st_unc = run_slice(oo, oos_m1, "OOS_UNCAPPED", cap=None)
    st_unc["name"] = "nds_scalp_M3_sym"
    print(f"M3 uncapped OOS n={st_unc['n_trades']} tpd={st_unc['trades_per_day']:.3f} avgR={st_unc['avg_r']:.3f}", flush=True)

    # Report
    lines = [
        "# Rebacktest Report (post-audit engine)",
        "",
        f"Generated: {pd.Timestamp.now(tz='UTC')}",
        "",
        "## Protocol",
        "- Engine: bid/ask explicit, gap booked, net R, SL always live, concurrent risk ≤3%, calendar-day tpd",
        "- SL cap: **$8** (plus uncapped diagnostic for NDS M3)",
        "- Risk sizing: 0.8% ($8 on $1k)",
        "- Holdout: 2025-10-01 → 2025-12-31 (reserved; reported once)",
        "- IS: 2026-01-01 → 2026-06-30 (variant selection only)",
        "- OOS: 2026-07-01 → 2026-10-28",
        "- Pre-registered list fixed in `run_audit_rebacktest.py` before holdout read for decisions",
        "",
        "## Component results",
        "",
        df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string(index=False),
        "",
        "## Union (IS-positive only)",
        f"- members: {sorted(is_ok)}",
        f"- OOS n={st_u['n_trades']} tpd={st_u['trades_per_day']:.3f} WR={st_u['win_rate']:.2f} "
        f"avgR_net={st_u['avg_r']:.3f} PF={st_u['profit_factor']:.2f} DD={st_u['max_dd_pct']:.1f}%",
        f"- sub30s profit share of 8% target: {st_u.get('sub30s_profit_pct_of_target', 0):.3f}",
        "",
        "## Monte Carlo (8% / 30d / block bootstrap)",
        mc.to_string(index=False) if len(mc) else "(insufficient trades)",
        "",
        "## Verdict on ≥3 signals/day",
    ]
    tpd = st_u["trades_per_day"]
    if tpd >= 3 and st_u["avg_r"] > 0 and st_u["max_dd_pct"] <= 12:
        lines.append(f"**MET** on OOS union: tpd={tpd:.2f}")
    else:
        lines.append(f"**NOT MET** on OOS union: tpd={tpd:.2f} (need ≥3 with positive net R and DD≤12%).")
        lines.append("Do not invent signals. Need more independent families after engine fix.")
    # R/day vs prop need ~0.45R/day at 0.8% to make 8% in ~22 days: 0.08/0.008/22 ≈ 0.45R/day
    rday = st_u["trades_per_day"] * st_u["avg_r"]
    lines += [
        "",
        f"R/day (net) ≈ {rday:.3f}; prop rough need ≈ 0.45R/day at 0.8% risk over ~22 days.",
        f"Elapsed {time.time()-t0:.1f}s",
        "",
        "## Notes",
        "- F3_nds_M5_sym is NOT derived from r864 (confirmed: use_reentry864=False).",
        "- Fidelity r864 IS R=+4.78 rows are separate experiments; excluded from union.",
        "- Multi-year Dukascopy (2023–2024) not yet downloaded; holdout uses late-2025 within current file.",
        "- Watchdog remains FROZEN until this report is accepted.",
    ]
    (OUT / "REBACKTEST_REPORT.md").write_text("\n".join(lines))
    print("wrote", OUT / "REBACKTEST_REPORT.md", flush=True)


if __name__ == "__main__":
    main()
