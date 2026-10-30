#!/usr/bin/env python3
"""Standalone family tests for research batch-3. Prioritize PDHL + Failed Trap."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "final" / "research_batch3"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price
from monte_carlo import run_mc
from run_final_batch import load, verdict_from
from run_expand import OOS_CUT, oos_trading_days, tpd_true, worst_streak
from run_expand_verify import max_daily_loss_pct, top5_ablation
from strategies.research_batch3 import (
    generate_failed_trap_family, generate_pdh_pdl_family,
    generate_fakey_family, generate_orv_family, generate_breaker_family,
)

CAP, SPREAD, SLIP, RISK = 8.0, 0.35, 0.10, 0.008


def eval_one(m1, orders, variant, oos_cut, n_tdays, family):
    oo = [o for o in orders if o.variant == variant]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, SPREAD) <= CAP + 1e-9]
    tr_is, st_is = simulate(m1, [o for o in oo if o.arm_time < oos_cut],
                            risk_pct=RISK, max_sl_dist=CAP, use_circuit_breaker=True,
                            spread=SPREAD, slip=SLIP, allow_fractional=True)
    tr, st = simulate(m1, [o for o in oo if o.arm_time >= oos_cut],
                      risk_pct=RISK, max_sl_dist=CAP, use_circuit_breaker=True,
                      spread=SPREAD, slip=SLIP, allow_fractional=True)
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0
    for k in range(4):
        a0 = warm + k * fold
        a1 = warm + (k + 1) * fold if k < 3 else n
        t0, t1 = m1.index[a0], m1.index[a1 - 1] + pd.Timedelta(minutes=1)
        _, stf = simulate(m1, [o for o in oo if t0 <= o.arm_time < t1],
                          risk_pct=RISK, max_sl_dist=CAP, use_circuit_breaker=True,
                          spread=SPREAD, slip=SLIP, allow_fractional=True)
        if stf["n_trades"] >= 5:
            valid += 1
            if stf["expectancy_r"] > 0:
                pos += 1
    wf = pos / valid if valid else 0.0
    mc = None
    if st["n_trades"] >= 15 and tr is not None and len(tr):
        mcdf = run_mc(tr["r_multiple"].values, risk_pcts=(RISK,))
        if mcdf is not None and len(mcdf):
            mc = float(mcdf.iloc[0]["pass_prob"])
    tpd = tpd_true(st["n_trades"], n_tdays)
    verd, _ = verdict_from({**st, "trades_per_day": tpd}, wf, mc)
    robust = bool(st_is["expectancy_r"] > 0 and st["expectancy_r"] > 0
                  and st_is["n_trades"] >= 10 and st["n_trades"] >= 15)
    promote = bool(robust and st["profit_factor"] >= 1.05 and wf >= 0.5
                   and (mc is None or mc >= 0.25) and st["n_trades"] >= 20
                   and st["max_dd_pct"] <= 25)
    return {
        "family": family, "variant": variant, "n_orders": len(oo),
        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
        "OOS_n": st["n_trades"], "OOS_WR": st["win_rate"], "OOS_R": st["expectancy_r"],
        "OOS_PF": st["profit_factor"], "OOS_DD": st["max_dd_pct"], "tpd": tpd,
        "WF+": wf, "MC_pass": mc, "worst_streak": worst_streak(tr),
        "mdl_pct": max_daily_loss_pct(tr), "verdict": verd,
        "robust": robust, "promote": promote,
        "OOS_R_no5": top5_ablation(tr)["exp_R_no_top5"],
    }


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)

    families = [
        ("PDHL", generate_pdh_pdl_family),          # priority
        ("FailedTrap", generate_failed_trap_family), # priority
        ("Fakey", generate_fakey_family),
        ("ORV", generate_orv_family),
        ("Breaker", generate_breaker_family),
    ]
    rows = []
    meta_counts = {}
    for fam, gen in families:
        print(f"\n=== {fam} ===", flush=True)
        try:
            pools = gen(m1, dxy)
        except Exception as e:
            print(f"  GEN FAIL {e}", flush=True)
            import traceback; traceback.print_exc()
            continue
        meta_counts[fam] = {"variants": len(pools), "sizes": {k: len(v) for k, v in pools.items()}}
        print(f"  variants={len(pools)} sizes={meta_counts[fam]['sizes']}", flush=True)
        for variant, orders in pools.items():
            print(f"  eval {variant} n={len(orders)}", flush=True)
            try:
                row = eval_one(m1, orders, variant, oos_cut, n_tdays, fam)
            except Exception as e:
                print(f"    EVAL FAIL {e}", flush=True)
                continue
            rows.append(row)
            print(f"    -> {row['verdict']} IS_R={row['IS_R']:.3f} n={row['OOS_n']} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} rob={row['robust']} prom={row['promote']}", flush=True)
            pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "oos_cut": str(oos_cut), "oos_days": int(n_tdays),
        "families": meta_counts, "n_rows": len(rows),
        "budget_per_family": 5, "wall_s": round(time.time() - t0, 1),
        "note": "batch-3; prioritize PDHL+Trap; quant appendix = keep rigor",
    }, indent=2, default=str))

    lines = ["# Research batch-3 standalone results\n",
             f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
             "Protocol: strict 0.35/0.10, cap $8, CB on, IS→OOS. Priority: PDHL, FailedTrap.\n",
             "Quant appendix: intraday gold MA/technical predictability mostly illusory after snooping+costs — rigor NOT lowered.\n"]
    if len(df):
        lines.append("\n## Table\n")
        lines.append(df.to_string(index=False))
        lines.append("\n\n## Promote / Robust\n")
        pr = df[df["promote"] | df["robust"]]
        lines.append(pr.to_string(index=False) if len(pr) else "none")
        lines.append("\n\n## Per-family best OOS_R (n≥10)\n")
        for fam in df["family"].unique():
            sub = df[(df["family"] == fam) & (df["OOS_n"] >= 10)].sort_values("OOS_R", ascending=False)
            if len(sub):
                r = sub.iloc[0]
                lines.append(f"- {fam}: {r['variant']} tpd={r['tpd']:.2f} PF={r['OOS_PF']:.2f} R={r['OOS_R']:.3f} V={r['verdict']} rob={r['robust']}")
            else:
                lines.append(f"- {fam}: no sized OOS")
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
