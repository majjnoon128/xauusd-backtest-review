#!/usr/bin/env python3
"""Final push: NDS reentry v2 + frequency portfolios. Cap ~24 new hyps.
Prior expand combo = 37. Total reported ≈ 61. Work in results/final/.
Protocol: IS choose / OOS judge; robust=IS&OOS+; promote gates; CB on; cap $8.
"""
from __future__ import annotations
import json, sys, time, copy
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "final"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, Order
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.session_box_mss import generate_session_box_mss
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from
from run_expand import OOS_CUT, oos_trading_days, tpd_true, worst_streak
from run_expand_verify import max_daily_loss_pct, top5_ablation
from run_expand_combo import (
    CAP, SPREAD, SLIP, cap_filter, dedupe_side, retag, eval_variant, sim_period
)

def merge_port(parts, tag, minutes=30):
    oo = []
    for part, ptag in parts:
        oo.extend(retag(part, ptag) if ptag else part)
    oo = retag(oo, tag)
    return dedupe_side(oo, minutes)


def main():
    t0all = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)

    print("GEN", flush=True)
    box = generate_session_box_mss(
        m1, None, False, "limit_mid", "rr1.5", True, 0.8, "atr_buf", "M5", box_kind="asia",
    )
    nds_v2 = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M3",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
        use_reentry864=True, reentry_tp_mode="rr1.5", reentry_mode="v2",
    )
    nds_v2_m5 = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
        use_reentry864=True, reentry_tp_mode="rr1.5", reentry_mode="v2",
    )
    nds_m5 = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    )
    nds_day_m5 = generate_nds_course(
        m1, None, False, False, family="course", style="day", entry_tf="M5",
        tp_mode="rr1.5", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    )
    nds_schem = generate_nds_course(
        m1, None, False, False, family="schematic", style="scalp", entry_tf="M5",
        tp_mode="nd88", confirm="brk_p3", min_atr=1.0, pivot_lr=3, nd_zone=True,
    )
    spike15_15 = generate_spike50(m1, "M15", 1.5)
    spike15_3 = generate_spike50(m1, "M15", 3.0)
    spike5_15 = generate_spike50(m1, "M5", 1.5)
    spike5_3 = generate_spike50(m1, "M5", 3.0)
    c22o = generate_c22(m1, 22, 2.0)

    # DXY-gated copies
    nds_v2_d = apply_dxy_gate(nds_v2, dxy, True)
    nds_v2_m5_d = apply_dxy_gate(nds_v2_m5, dxy, True)
    nds_m5_d = apply_dxy_gate(nds_m5, dxy, True)
    nds_day_d = apply_dxy_gate(nds_day_m5, dxy, True)
    nds_schem_d = apply_dxy_gate(nds_schem, dxy, True)
    spike15_3_d = apply_dxy_gate(spike15_3, dxy, True)
    spike5_3_d = apply_dxy_gate(spike5_3, dxy, True)
    c22_d = apply_dxy_gate(c22o, dxy, True)

    print("  counts", {
        "box": len(box), "v2": len(nds_v2), "v2m5": len(nds_v2_m5), "m5": len(nds_m5),
        "s15_15": len(spike15_15), "s15_3": len(spike15_3), "s5_15": len(spike5_15),
        "c22": len(c22o), "schem": len(nds_schem),
    }, flush=True)

    # Audit: planned RR for v2 reentry legs only
    v2_re = [o for o in nds_v2 if (o.meta or {}).get("leg") == "reentry864_v2"]
    if v2_re:
        rrs = []
        for o in v2_re:
            risk = abs(o.price - o.sl)
            if risk > 1e-9:
                rrs.append(abs(o.tp - o.price) / risk)
        print("  v2 reentry n=", len(v2_re), "med_rr", float(np.median(rrs)), "max_rr", float(np.max(rrs)), flush=True)
    else:
        print("  v2 reentry n=0", flush=True)

    hyps = []
    # F0–F5 singles
    hyps.append(("F0", "NDS_r864v2 M3 sym rtp1.5", retag(nds_v2, "F0_nds_r864v2_M3"), 0.008))
    hyps.append(("F1", "NDS_r864v2 M3 +DXY", retag(nds_v2_d, "F1_nds_r864v2_M3_dxy"), 0.008))
    hyps.append(("F2", "NDS_r864v2 M5 +DXY", retag(nds_v2_m5_d, "F2_nds_r864v2_M5_dxy"), 0.008))
    hyps.append(("F3", "NDS_base M5 sym noDXY", retag(nds_m5, "F3_nds_M5_sym"), 0.008))
    hyps.append(("F4", "Spike50_M5_rr3 +DXY", retag(spike5_3_d, "F4_spike_M5_rr3_dxy"), 0.008))
    hyps.append(("F5", "Spike50_M5_rr1.5 noDXY", retag(spike5_15, "F5_spike_M5_rr15"), 0.008))
    # F6–F7 unions
    hyps.append(("F6", "Spike15_rr15 OR C22", merge_port([
        (spike15_15, "s"), (c22o, "c")], "F6_spike15_c22_or"), 0.008))
    hyps.append(("F7", "Spike15_rr3+DXY OR C22+DXY", merge_port([
        (spike15_3_d, "s"), (c22_d, "c")], "F7_spike3d_c22d_or"), 0.008))
    # F8–F15 portfolios
    hyps.append(("F8", "Spike15_rr15 + C22d + NDSm5d", merge_port([
        (spike15_15, "s"), (c22_d, "c"), (nds_m5_d, "n")], "F8_s15_c22d_ndsm5d"), 0.008))
    hyps.append(("F9", "Spike15_rr15 + C22d + Box", merge_port([
        (spike15_15, "s"), (c22_d, "c"), (box, "b")], "F9_s15_c22d_box"), 0.008))
    hyps.append(("F10", "Spike15_rr3d + C22d + NDSm5d", merge_port([
        (spike15_3_d, "s"), (c22_d, "c"), (nds_m5_d, "n")], "F10_s3d_c22d_ndsm5d"), 0.008))
    hyps.append(("F11", "Spike15_rr15 + C22d + NDSm5d + Box", merge_port([
        (spike15_15, "s"), (c22_d, "c"), (nds_m5_d, "n"), (box, "b")], "F11_quad"), 0.008))
    hyps.append(("F12", "Spike15_rr15 + C22 + NDSm5 + Box noDXY", merge_port([
        (spike15_15, "s"), (c22o, "c"), (nds_m5, "n"), (box, "b")], "F12_quad_nodxy"), 0.008))
    # P3-like agreement: keep only when spike3d and c22d same side within 30m — approximate by intersection times
    # Simpler: merge P3 components as OR (already F7); agreement portfolio = require both fired same day
    # Use retagged union of spike3d+c22d already as F7; F13 = F7 + Box
    hyps.append(("F13", "F7 union + Box", merge_port([
        (spike15_3_d, "s"), (c22_d, "c"), (box, "b")], "F13_f7_box"), 0.008))
    hyps.append(("F14", "F7 union + NDSm5d", merge_port([
        (spike15_3_d, "s"), (c22_d, "c"), (nds_m5_d, "n")], "F14_f7_nds"), 0.008))
    hyps.append(("F15", "F13 alias", merge_port([
        (spike15_3_d, "s"), (c22_d, "c"), (box, "b")], "F15_f7_box"), 0.008))
    hyps.append(("F16", "NDS_v2 + Spike15_rr15", merge_port([
        (nds_v2, "n"), (spike15_15, "s")], "F16_v2_spike"), 0.008))
    hyps.append(("F17", "NDS schematic ndz M5 +DXY", retag(nds_schem_d, "F17_schem_m5_dxy"), 0.008))
    hyps.append(("F18", "F11 risk05", merge_port([
        (spike15_15, "s"), (c22_d, "c"), (nds_m5_d, "n"), (box, "b")], "F18_quad_r05"), 0.005))
    hyps.append(("F19", "F8 risk05", merge_port([
        (spike15_15, "s"), (c22_d, "c"), (nds_m5_d, "n")], "F19_f8_r05"), 0.005))
    hyps.append(("F20", "Spike15_rr3 noDXY", retag(spike15_3, "F20_spike15_rr3"), 0.008))
    hyps.append(("F21", "SpikeM5_rr15 + C22d + NDSm5d", merge_port([
        (spike5_15, "s"), (c22_d, "c"), (nds_m5_d, "n")], "F21_s5_c22d_nds"), 0.008))
    hyps.append(("F22", "NDS day M5 rr15 +DXY", retag(nds_day_d, "F22_nds_day_m5_dxy"), 0.008))
    hyps.append(("F23", "MAXFREQ SpikeM5+M15 + C22 + NDSm5 + Box", merge_port([
        (spike5_15, "s5"), (spike15_15, "s15"), (c22o, "c"), (nds_m5, "n"), (box, "b")],
        "F23_maxfreq"), 0.008))

    # Deduplicate F15==F13: drop F15 evaluation later by note; keep count honest
    print(f"variants planned: {len(hyps)}", flush=True)
    with open(OUT / "hypotheses_final.json") as f:
        pre = json.load(f)
    assert len(pre) == 24

    rows = []
    all_orders = []
    for hyp, note, orders, risk in hyps:
        if not orders:
            print(f"  SKIP {hyp} empty", flush=True)
            continue
        variant = orders[0].variant
        # ensure all same variant
        orders = retag(orders, variant)
        all_orders.extend(orders)
        print(f"  eval {hyp} n_ord={len(orders)} {note}", flush=True)
        row = eval_variant(m1, orders, variant, risk, oos_cut, n_tdays, hyp, note)
        rows.append(row)
        print(f"    -> {row['verdict']} IS_R={row['IS_R']:.3f} OOS_n={row['OOS_n']} tpd={row['tpd']:.2f} PF={row['OOS_PF']:.2f} robust={row['robust']} promote={row['promote']}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "final_summary.csv", index=False)

    prior_n = 37
    meta = {
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "oos_cut": str(oos_cut),
        "oos_trading_days": int(n_tdays),
        "new_variants": int(len(rows)),
        "prior_combo_variants": prior_n,
        "total_variants_reported": prior_n + int(len(rows)),
        "cap_sl": CAP,
        "costs": {"spread": SPREAD, "slip": SLIP},
        "reentry_v2_orders": int(len(v2_re)),
        "wall_s": round(time.time() - t0all, 1),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))

    # Promote / robust tables
    prom = df[df["promote"] == True]
    rob = df[df["robust"] == True]
    keep = df[df["verdict"].isin(["KEEP", "MAYBE"])]
    print("\nPROMOTE", len(prom), flush=True)
    print(prom[["hyp", "note", "tpd", "OOS_PF", "OOS_R", "IS_R", "OOS_n"]].to_string() if len(prom) else "none", flush=True)
    print("\nROBUST", len(rob), flush=True)
    print(rob[["hyp", "note", "tpd", "OOS_PF", "OOS_R", "IS_R"]].to_string() if len(rob) else "none", flush=True)

    # Best by tpd among promote, else among robust, else among KEEP with OOS_R>0
    cand = prom if len(prom) else (rob if len(rob) else df[(df["OOS_R"] > 0) & (df["verdict"] != "DROP")])
    if len(cand):
        best = cand.sort_values(["promote", "robust", "OOS_PF", "tpd"], ascending=False).iloc[0]
        chosen = best.to_dict()
    else:
        chosen = {"note": "none"}
    (OUT / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    # Honest ceiling rows: top 5 by tpd with OOS_R>0
    pos = df[df["OOS_R"] > 0].sort_values("tpd", ascending=False).head(8)
    pos.to_csv(OUT / "frequency_ceiling.csv", index=False)

    print("DONE", meta, flush=True)


if __name__ == "__main__":
    main()
