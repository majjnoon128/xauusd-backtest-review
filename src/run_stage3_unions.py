#!/usr/bin/env python3
"""Stage-3: small fixed pre-registered unions of robust overlayed survivors.
Counted for MT. Signal-frequency honesty: report overlap, not sum of tpds.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "final" / "stage3"
OUT.mkdir(parents=True, exist_ok=True)

from engine import Order
from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.addons_batch6 import apply_recipe
from run_overlays_batch6 import build_survivors, retag, merge_or

# Pre-registered unions only (fixed set)
UNIONS = [
    ("U1_F3atr_F7atr", [("F3_nds_M5_sym", "atr_regime"), ("F7_spike3d_c22d_or", "atr_regime")]),
    ("U2_F7atr_brkdxy", [("F7_spike3d_c22d_or", "atr_regime"), ("brk_M5_M1_rr1.5_k1", "sess_overlap+dxy")]),
    ("U3_F3dxy_F7atr", [("F3_nds_M5_sym", "dxy_align"), ("F7_spike3d_c22d_or", "atr_regime")]),
    ("U4_F3atr_F7atr_brkdxy", [("F3_nds_M5_sym", "atr_regime"), ("F7_spike3d_c22d_or", "atr_regime"),
                               ("brk_M5_M1_rr1.5_k1", "sess_overlap+dxy")]),
    ("U5_F7atr_liqpartial", [("F7_spike3d_c22d_or", "atr_regime"),
                             ("liqraid_pdh_pdl_rr1.5_kzany", "ex_partial_be")]),
    ("U6_F3atr_F7atr_mh30", [("F3_nds_M5_sym", "atr_regime"), ("F7_spike3d_c22d_or", "atr_regime")]),
    # U6 same components then mh30s on union
]


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    bases = build_survivors(m1, dxy)
    print("bases", {k: len(v) for k, v in bases.items()}, flush=True)

    cache = {}
    def get(base, overlay):
        key = (base, overlay)
        if key not in cache:
            oo = bases[base]
            if overlay and overlay != "none":
                oo = apply_recipe(overlay, oo, m1, dxy)
            cache[key] = retag(oo, f"{base}|{overlay}")
            print(f"  cached {base}|{overlay} n={len(cache[key])}", flush=True)
        return cache[key]

    rows = []
    for name, parts in UNIONS:
        print(f"\n=== {name} ===", flush=True)
        tagged = []
        for bi, (b, ov) in enumerate(parts):
            oo = get(b, ov)
            tagged.append((oo, f"p{bi}"))
        if name == "U6_F3atr_F7atr_mh30":
            merged = merge_or(tagged, name)
            merged = apply_recipe("mh30s", merged, m1, dxy)
            merged = retag(merged, name)
        else:
            merged = merge_or(tagged, name)
        # de-dupe same arm_time+side within 5 min (OR portfolio collision)
        merged.sort(key=lambda o: (o.arm_time, o.side))
        dedup = []
        last = {}
        for o in merged:
            k = o.side
            t = pd.Timestamp(o.arm_time)
            if k in last and abs((t - last[k]).total_seconds()) < 300:
                continue
            last[k] = t
            dedup.append(o)
        print(f"  n_merged={len(merged)} n_dedup5m={len(dedup)}", flush=True)
        row = eval_one(m1, retag(dedup, name), name, oos_cut, n_tdays, "U")
        row["union"] = name
        row["n_orders"] = len(dedup)
        rows.append(row)
        print(f"  -> {row['verdict']} OOS_R={row['OOS_R']:.3f} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} rob={row['robust']} prom={row['promote']}", flush=True)
        pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    lines = ["# Stage-3 unions (pre-registered)\n",
             f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
             "Unions of robust overlayed survivors only. Dedup same-side within 5m.\n\n",
             df.to_string(index=False)]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "n_unions": len(UNIONS), "wall_s": round(time.time() - t0, 1),
    }, indent=2, default=str))
    print("DONE stage3", flush=True)


if __name__ == "__main__":
    main()
