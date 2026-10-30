#!/usr/bin/env python3
"""Apply pre-registered batch-6 overlays ONLY to surviving components. Fixed recipe set."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "final" / "overlays"
OUT.mkdir(parents=True, exist_ok=True)

from engine import Order
from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.common import apply_dxy_gate
from strategies.nds_course import generate_nds_course
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.research_batch3 import generate_breaker
from strategies.research_batch4 import generate_liq_raid, generate_climax_2nd
from strategies.research_batch2 import generate_mitigation
from strategies.addons_batch6 import OVERLAY_RECIPES, apply_recipe


def retag(orders, variant):
    out = []
    for o in orders:
        out.append(Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                         variant, dict(o.meta or {}), o.expire_minutes, o.max_hold_minutes,
                         getattr(o, "min_hold_minutes", None)))
    return out


def merge_or(parts, variant):
    """OR-merge tagged parts."""
    out = []
    for oo, tag in parts:
        for o in oo:
            m = dict(o.meta or {}); m["src"] = tag
            out.append(Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp, o.strategy,
                             variant, m, o.expire_minutes, o.max_hold_minutes,
                             getattr(o, "min_hold_minutes", None)))
    out.sort(key=lambda x: x.arm_time)
    return out


def build_survivors(m1, dxy):
    """Fixed survivor list — only these bases get overlays."""
    bases = {}
    # F3
    nds_m5 = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    )
    bases["F3_nds_M5_sym"] = retag(nds_m5, "F3_nds_M5_sym")
    # F7
    spike15_3_d = apply_dxy_gate(generate_spike50(m1, "M15", 3.0), dxy, True)
    c22_d = apply_dxy_gate(generate_c22(m1, 22, 2.0), dxy, True)
    bases["F7_spike3d_c22d_or"] = merge_or([(spike15_3_d, "s"), (c22_d, "c")], "F7_spike3d_c22d_or")
    # Research MAYBEs / positive-OOS candidates
    bases["liqraid_pdh_pdl_rr1.5_kzany"] = generate_liq_raid(m1, dxy, False, "pdh_pdl", 1.5, "any", 8.0, False)
    bases["liqraid_eqh_eql_rr1.5_kzlondon"] = generate_liq_raid(m1, dxy, False, "eqh_eql", 1.5, "london", 8.0, False)
    bases["brk_M5_M1_rr1.5_k1"] = generate_breaker(m1, dxy, False, "M5", "M1", 1.5, 1.0, 8.0)
    bases["clx2_M5_rr1.5_lb20"] = generate_climax_2nd(m1, dxy, False, "M5", 1.5, 8.0, 20)
    bases["mit_M15_M5_rr1.5_k1"] = generate_mitigation(m1, dxy, False, "M15", "M5", 1.5, 1.0, 8.0)
    # ensure variant tags match
    for k, oo in list(bases.items()):
        bases[k] = retag(oo, k)
    return bases


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)

    print("BUILD survivors", flush=True)
    bases = build_survivors(m1, dxy)
    for k, v in bases.items():
        print(f"  {k}: {len(v)}", flush=True)

    (OUT / "SURVIVORS.md").write_text(
        "# Survivors receiving batch-6 overlays\n\n" +
        "\n".join(f"- `{k}` n_orders={len(v)}" for k, v in bases.items()) +
        f"\n\nRecipes ({len(OVERLAY_RECIPES)} pre-registered):\n" +
        "\n".join(f"- `{n}`" for n, _ in OVERLAY_RECIPES) +
        "\n\nUS10Y skipped; news calendar skipped.\n"
    )

    rows = []
    # baseline no-overlay
    for base, oo in bases.items():
        print(f"\n=== BASE {base} ===", flush=True)
        row = eval_one(m1, oo, base, oos_cut, n_tdays, "BASE")
        row["overlay"] = "none"
        row["base"] = base
        rows.append(row)
        print(f"  -> {row['verdict']} OOS_R={row['OOS_R']:.3f} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} rob={row['robust']}", flush=True)

    for base, oo in bases.items():
        print(f"\n=== OVERLAYS on {base} ===", flush=True)
        for name, _ in OVERLAY_RECIPES:
            try:
                oo2 = apply_recipe(name, oo, m1, dxy)
            except Exception as e:
                print(f"  {name} FAIL {e}", flush=True)
                continue
            # retag so eval_one variant filter works
            variant = f"{base}|{name}"
            oo2 = retag(oo2, variant)
            print(f"  eval {name} n={len(oo2)}", flush=True)
            if len(oo2) < 5:
                print("    skip tiny", flush=True)
                continue
            row = eval_one(m1, oo2, variant, oos_cut, n_tdays, f"OV:{name}")
            row["overlay"] = name
            row["base"] = base
            rows.append(row)
            print(f"    -> {row['verdict']} OOS_R={row['OOS_R']:.3f} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} rob={row['robust']} prom={row['promote']}", flush=True)
            pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "n_bases": len(bases), "n_recipes": len(OVERLAY_RECIPES),
        "n_rows": len(rows), "wall_s": round(time.time() - t0, 1),
        "note": "overlays only on survivors; fixed recipe set; US10Y/news skipped",
    }, indent=2, default=str))

    lines = ["# Batch-6 overlay results on survivors\n",
             f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
             f"Bases={len(bases)} recipes={len(OVERLAY_RECIPES)} (pre-registered, counted).\n",
             "\n## Promote / Robust\n"]
    if len(df):
        pr = df[df["promote"] | df["robust"]]
        lines.append(pr.to_string(index=False) if len(pr) else "none")
        lines.append("\n\n## Best OOS_R per base (n≥10)\n")
        for b in df["base"].unique():
            sub = df[(df["base"] == b) & (df["OOS_n"] >= 10)].sort_values("OOS_R", ascending=False)
            if len(sub):
                r = sub.iloc[0]
                lines.append(f"- {b}: overlay={r['overlay']} R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} tpd={r['tpd']:.2f} V={r['verdict']} rob={r['robust']}")
        lines.append("\n\n## Full table\n")
        lines.append(df.to_string(index=False))
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE overlays", flush=True)


if __name__ == "__main__":
    main()
