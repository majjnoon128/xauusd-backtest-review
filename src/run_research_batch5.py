#!/usr/bin/env python3
"""Batch-5 final setups + PWH liqraid variants. Setup catalog CLOSED after this."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "final" / "research_batch5"
OUT.mkdir(parents=True, exist_ok=True)

from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.research_batch5 import (
    generate_raw_ob_family, generate_m15_dbdt_family, generate_pwh_family,
)


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)
    families = [
        ("RawOB", generate_raw_ob_family),
        ("M15DBDT", generate_m15_dbdt_family),
        ("PWH", generate_pwh_family),  # counted in LiqRaid MT family axis
    ]
    rows, meta = [], {}
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
        "families": meta, "n_rows": len(rows), "wall_s": round(time.time() - t0, 1),
        "note": "batch-5 FINAL setups; PWH extends LiqRaid level_type axis; catalog CLOSED",
    }, indent=2, default=str))
    lines = ["# Research batch-5 (final setups)\n",
             f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
             "Catalog CLOSED after this. Next = add-on overlays only.\n",
             "\n## Table\n", df.to_string(index=False) if len(df) else "empty",
             "\n\n## Promote / Robust\n"]
    if len(df):
        pr = df[df["promote"] | df["robust"]]
        lines.append(pr.to_string(index=False) if len(pr) else "none")
        lines.append("\n\n## Non-DROP\n")
        nd = df[df["verdict"] != "DROP"]
        lines.append(nd.to_string(index=False) if len(nd) else "none")
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
