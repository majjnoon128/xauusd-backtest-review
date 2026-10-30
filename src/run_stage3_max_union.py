#!/usr/bin/env python3
"""Max union of ALL robust+positive components — 3/day is a MINIMUM not a cap.
Dedupe only simultaneous/overlapping (same side within 5m) for concurrent-risk honesty.
Do NOT prune profitable robust components for frequency.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "final" / "stage3_max"
OUT.mkdir(parents=True, exist_ok=True)

from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.common import apply_dxy_gate
from strategies.nds_course import generate_nds_course
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.research_batch3 import generate_breaker
from strategies.research_batch4 import generate_liq_raid
from strategies.addons_batch6 import apply_recipe
from run_overlays_batch6 import retag, merge_or
from watchdog.dollar_proxy import load_research_proxy

# All components that were robust+OOS_R>0 under BOTH synth and EUR (from dxy_proxy)
# Plus other robust overlay rows from overlays/summary — keep all that pass rigor.
COMPONENTS = [
    ("F3_nds_M5_sym", "atr_regime"),
    ("F3_nds_M5_sym", "dxy_align"),
    ("F3_nds_M5_sym", "mh30s"),
    ("F3_nds_M5_sym", "none"),
    ("F7_spike3d_c22d_or", "atr_regime"),
    ("F7_spike3d_c22d_or", "mh30s"),
    ("F7_spike3d_c22d_or", "ex_partial_be"),
    ("F7_spike3d_c22d_or", "none"),
    ("brk_M5_M1_rr1.5_k1", "sess_overlap+dxy"),
    ("liqraid_pdh_pdl_rr1.5_kzany", "ex_partial_be"),
]


def build_bases(m1, dxy):
    from strategies.research_batch4 import generate_liq_raid
    nds = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    )
    f3 = retag(nds, "F3_nds_M5_sym")
    spike = apply_dxy_gate(generate_spike50(m1, "M15", 3.0), dxy, True)
    c22 = apply_dxy_gate(generate_c22(m1, 22, 2.0), dxy, True)
    f7 = merge_or([(spike, "s"), (c22, "c")], "F7_spike3d_c22d_or")
    brk = retag(generate_breaker(m1, dxy, False, "M5", "M1", 1.5, 1.0, 8.0), "brk_M5_M1_rr1.5_k1")
    liq = retag(generate_liq_raid(m1, dxy, False, "pdh_pdl", 1.5, "any", 8.0, False),
                "liqraid_pdh_pdl_rr1.5_kzany")
    return {
        "F3_nds_M5_sym": f3,
        "F7_spike3d_c22d_or": f7,
        "brk_M5_M1_rr1.5_k1": brk,
        "liqraid_pdh_pdl_rr1.5_kzany": liq,
    }


def dedupe_overlap(orders, window_s=300):
    """Same-side within window_s — concurrent/overlap only, not frequency prune."""
    orders = sorted(orders, key=lambda o: (o.arm_time, o.side))
    out, last = [], {}
    for o in orders:
        t = pd.Timestamp(o.arm_time)
        if o.side in last and abs((t - last[o.side]).total_seconds()) < window_s:
            continue
        last[o.side] = t
        out.append(o)
    return out


def main():
    t0 = time.time()
    m1, _ = load()
    dxy, src = load_research_proxy("EURUSD_inv")
    print("dollar_proxy", src, flush=True)
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    bases = build_bases(m1, dxy)

    parts = []
    per_comp = []
    for bi, (base, ov) in enumerate(COMPONENTS):
        oo = bases[base]
        if ov != "none":
            oo = apply_recipe(ov, oo, m1, dxy)
        oo = retag(oo, f"{base}|{ov}")
        print(f"  comp {base}|{ov} n={len(oo)}", flush=True)
        # eval alone
        if len(oo) >= 5:
            row = eval_one(m1, oo, f"{base}|{ov}", oos_cut, n_tdays, "C")
            row["base"] = base
            row["overlay"] = ov
            per_comp.append(row)
            print(f"    solo -> {row['verdict']} R={row['OOS_R']:.3f} tpd={row['tpd']:.2f} rob={row['robust']}", flush=True)
            # keep only rigor-pass for union: robust and OOS_R>0 (or promote/KEEP with OOS_R>0 and MC)
            if row["robust"] and row["OOS_R"] > 0:
                parts.append((oo, f"p{bi}"))
            elif row["verdict"] in ("KEEP", "PROMOTE") and row["OOS_R"] > 0 and row.get("MC_pass", 0) >= 0.95:
                # Amir: don't prune profitable that pass rigor — KEEP with strong MC counts
                if row.get("WF+", 0) >= 0.5:
                    parts.append((oo, f"p{bi}"))
                    print("    INCLUDED via KEEP+MC rigor", flush=True)

    print(f"\nUNION parts={len(parts)}", flush=True)
    merged = merge_or(parts, "MAX_ALL_ROBUST")
    raw_n = len(merged)
    dedup = dedupe_overlap(merged, 300)
    print(f"merged={raw_n} dedup5m={len(dedup)}", flush=True)

    row = eval_one(m1, retag(dedup, "MAX_ALL_ROBUST"), "MAX_ALL_ROBUST", oos_cut, n_tdays, "MAX")
    row["n_raw"] = raw_n
    row["n_dedup"] = len(dedup)
    row["n_parts"] = len(parts)

    # also tighter overlap windows for concurrent realism: 15m, 60m
    rows_u = [row]
    for w, name in [(60, "MAX_dedup60s"), (900, "MAX_dedup15m"), (3600, "MAX_dedup60m")]:
        d = dedupe_overlap(merged, w)
        r = eval_one(m1, retag(d, name), name, oos_cut, n_tdays, "MAX")
        r["n_raw"] = raw_n
        r["n_dedup"] = len(d)
        r["n_parts"] = len(parts)
        r["dedup_window_s"] = w
        rows_u.append(r)
        print(f"  {name} n={len(d)} tpd={r['tpd']:.2f} R={r['OOS_R']:.3f} rob={r['robust']} V={r['verdict']}", flush=True)

    pd.DataFrame(per_comp).to_csv(OUT / "components.csv", index=False)
    pd.DataFrame(rows_u).to_csv(OUT / "unions.csv", index=False)

    lines = [
        f"# Max union — 3/day is MINIMUM not cap\n",
        f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
        f"Dollar proxy: {src}. Components kept if robust+OOS_R>0 (or KEEP+MC rigor).\n",
        f"Dedupe = same-side overlap window only (concurrent-risk), NOT frequency pruning.\n\n",
        f"## Per-component\n",
        pd.DataFrame(per_comp).to_string(index=False),
        f"\n\n## Unions\n",
        pd.DataFrame(rows_u).to_string(index=False),
        f"\n\n## Honest signals/day\n",
        f"- Raw OR merge (no dedupe): orders={raw_n}\n",
        f"- After 5m same-side dedupe: tpd={row['tpd']:.2f} OOS_R={row['OOS_R']:.3f} rob={row['robust']}\n",
        f"If tpd ≥ 3 under rigor, that meets Amir's MINIMUM; do not cut further.\n",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "proxy": src, "n_parts": len(parts), "raw_n": raw_n,
        "tpd_dedup5m": row["tpd"], "wall_s": round(time.time() - t0, 1),
        "policy": "3/day MINIMUM; keep all rigor-pass; dedupe overlap only",
    }, indent=2, default=str))
    print("DONE max union tpd", row["tpd"], flush=True)


if __name__ == "__main__":
    main()
