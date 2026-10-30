#!/usr/bin/env python3
"""Batch-4 standalone tests. Priority: TTR BOM + LiqRaid (asia/eqh/pdh unified)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "final" / "research_batch4"
OUT.mkdir(parents=True, exist_ok=True)

from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.research_batch4 import (
    generate_ttr_bom_family, generate_liq_raid_family,
    generate_mtr_family, generate_climax_family,
)


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)

    families = [
        ("TTRBOM", generate_ttr_bom_family),       # priority high-freq
        ("LiqRaid", generate_liq_raid_family),     # asia/eqh/pdh unified; honest MT count
        ("MTR", generate_mtr_family),
        ("Climax2", generate_climax_family),
    ]
    rows = []
    meta = {}
    for fam, gen in families:
        print(f"\n=== {fam} ===", flush=True)
        try:
            pools = gen(m1, dxy)
        except Exception as e:
            print("GEN FAIL", e, flush=True)
            import traceback; traceback.print_exc()
            continue
        meta[fam] = {"variants": len(pools), "sizes": {k: len(v) for k, v in pools.items()}}
        print("  variants=", len(pools), "sizes=", meta[fam]["sizes"], flush=True)
        if fam == "LiqRaid":
            print("  NOTE: LiqRaid variants counted honestly across level_type∈{asia,eqh_eql,pdh_pdl}", flush=True)
        for variant, orders in pools.items():
            print(f"  eval {variant} n={len(orders)}", flush=True)
            try:
                row = eval_one(m1, orders, variant, oos_cut, n_tdays, fam)
            except Exception as e:
                print("    EVAL FAIL", e, flush=True)
                continue
            rows.append(row)
            print(f"    -> {row['verdict']} IS_R={row['IS_R']:.3f} n={row['OOS_n']} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} rob={row['robust']} prom={row['promote']}", flush=True)
            pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "oos_cut": str(oos_cut), "oos_days": int(n_tdays),
        "families": meta, "n_rows": len(rows),
        "wall_s": round(time.time() - t0, 1),
        "note": "batch-4; LiqRaid unifies asia/eqh/pdh; variants pre-registered & counted",
    }, indent=2, default=str))
    lines = ["# Research batch-4 standalone results\n",
             f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
             "Priority: TTRBOM + LiqRaid(asia). LiqRaid level_type is a counted MT axis.\n",
             "\n## Table\n", df.to_string(index=False) if len(df) else "empty",
             "\n\n## Promote / Robust\n"]
    if len(df):
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
