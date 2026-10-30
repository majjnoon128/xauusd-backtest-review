#!/usr/bin/env python3
"""Compare DXY_synth vs EURUSD-inverse proxy on every final pick that uses a DXY filter.
If EUR proxy kills the edge, watchdog viability with free live feeds is at risk.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "results" / "final" / "dxy_proxy"
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "data"

from engine import Order
from run_final_batch import load
from run_expand import OOS_CUT, oos_trading_days
from run_research_batch3 import eval_one
from strategies.common import apply_dxy_gate
from strategies.nds_course import generate_nds_course
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.research_batch3 import generate_breaker
from strategies.research_batch4 import generate_liq_raid
from strategies.addons_batch6 import apply_recipe, filter_atr_regime, filter_session, filter_dxy_align
from run_overlays_batch6 import retag, merge_or


def load_eur_inv() -> pd.DataFrame:
    eur = pd.read_parquet(DATA / "EURUSD.parquet")
    if eur.index.tz is None:
        eur.index = eur.index.tz_localize("UTC")
    close = eur["close"].astype(float)
    inv = (1.0 / close).to_frame("close")
    # optional OHLC inverse (high/low swap)
    if all(c in eur.columns for c in ("open", "high", "low")):
        inv["open"] = 1.0 / eur["open"].astype(float)
        inv["high"] = 1.0 / eur["low"].astype(float)   # inverse: low→high
        inv["low"] = 1.0 / eur["high"].astype(float)
    return inv


def build_f7(m1, dxy):
    spike15_3_d = apply_dxy_gate(generate_spike50(m1, "M15", 3.0), dxy, True)
    c22_d = apply_dxy_gate(generate_c22(m1, 22, 2.0), dxy, True)
    return merge_or([(spike15_3_d, "s"), (c22_d, "c")], "F7_spike3d_c22d_or")


def build_f3(m1):
    nds = generate_nds_course(
        m1, None, False, False, family="course", style="scalp", entry_tf="M5",
        tp_mode="sym", confirm="brk_p3", min_atr=1.0, pivot_lr=3,
    )
    return retag(nds, "F3_nds_M5_sym")


def build_brk(m1, dxy):
    return retag(generate_breaker(m1, dxy, False, "M5", "M1", 1.5, 1.0, 8.0), "brk_M5_M1_rr1.5_k1")


def dedup5(orders):
    orders = sorted(orders, key=lambda o: (o.arm_time, o.side))
    out, last = [], {}
    for o in orders:
        t = pd.Timestamp(o.arm_time)
        if o.side in last and abs((t - last[o.side]).total_seconds()) < 300:
            continue
        last[o.side] = t
        out.append(o)
    return out


def main():
    t0 = time.time()
    m1, dxy_synth = load()
    dxy_eur = load_eur_inv()
    # correlation note
    a = pd.concat([dxy_synth["close"].rename("synth"), dxy_eur["close"].rename("eurinv")], axis=1, join="inner").dropna()
    corr_lvl = float(a["synth"].corr(a["eurinv"]))
    corr_ret = float(a["synth"].pct_change().corr(a["eurinv"].pct_change()))
    print(f"corr level={corr_lvl:.4f} ret={corr_ret:.4f} n={len(a)}", flush=True)

    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))

    rows = []

    def ev(label, source, oo, variant):
        oo = retag(oo, variant)
        if len(oo) < 5:
            print(f"  skip tiny {label}/{source} n={len(oo)}", flush=True)
            return
        print(f"  eval {label} [{source}] n={len(oo)}", flush=True)
        row = eval_one(m1, oo, variant, oos_cut, n_tdays, label)
        row["label"] = label
        row["dxy_source"] = source
        row["n_orders"] = len(oo)
        rows.append(row)
        print(f"    -> {row['verdict']} OOS_R={row['OOS_R']:.3f} PF={row['OOS_PF']:.2f} tpd={row['tpd']:.2f} rob={row['robust']} prom={row['promote']}", flush=True)
        pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)

    for source, dxy in [("DXY_synth", dxy_synth), ("EURUSD_inv", dxy_eur)]:
        print(f"\n======== SOURCE {source} ========", flush=True)
        f3 = build_f3(m1)
        f7 = build_f7(m1, dxy)
        brk = build_brk(m1, dxy)

        # Base F7 (DXY-gated at generation)
        ev("F7_base", source, f7, f"F7|{source}")

        # F3 + dxy_align overlay
        f3_dxy = apply_recipe("dxy_align", f3, m1, dxy)
        ev("F3_dxy_align", source, f3_dxy, f"F3|dxy_align|{source}")

        # F7 + atr_regime (atr doesn't use dxy, but F7 base does)
        f7_atr = apply_recipe("atr_regime", f7, m1, dxy)
        ev("F7_atr_regime", source, f7_atr, f"F7|atr|{source}")

        # brk + sess_overlap+dxy
        brk_sod = apply_recipe("sess_overlap+dxy", brk, m1, dxy)
        ev("brk_sess_overlap+dxy", source, brk_sod, f"brk|sess+dxy|{source}")

        # brk + dxy_align
        brk_dxy = apply_recipe("dxy_align", brk, m1, dxy)
        ev("brk_dxy_align", source, brk_dxy, f"brk|dxy|{source}")

        # U3 = F3|dxy_align OR F7|atr
        u3 = dedup5(merge_or([(f3_dxy, "f3"), (f7_atr, "f7")], f"U3|{source}"))
        ev("U3_F3dxy_F7atr", source, u3, f"U3|{source}")

        # U2 = F7|atr OR brk|sess+dxy
        u2 = dedup5(merge_or([(f7_atr, "f7"), (brk_sod, "brk")], f"U2|{source}"))
        ev("U2_F7atr_brkdxy", source, u2, f"U2|{source}")

        # U4 = F3|atr OR F7|atr OR brk|sess+dxy
        f3_atr = apply_recipe("atr_regime", f3, m1, dxy)
        u4 = dedup5(merge_or([(f3_atr, "f3"), (f7_atr, "f7"), (brk_sod, "brk")], f"U4|{source}"))
        ev("U4_F3atr_F7atr_brkdxy", source, u4, f"U4|{source}")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)

    # Side-by-side comparison
    lines = [
        f"# DXY_synth vs EURUSD-inverse proxy\n",
        f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')}\n",
        f"EURUSD_inv = 1/EURUSD close (Dukascopy history on box). corr_level={corr_lvl:.4f} corr_ret={corr_ret:.4f}.\n",
        f"\n## Side-by-side (OOS)\n",
    ]
    labels = df["label"].unique()
    cmp_rows = []
    for lab in labels:
        a = df[(df.label == lab) & (df.dxy_source == "DXY_synth")]
        b = df[(df.label == lab) & (df.dxy_source == "EURUSD_inv")]
        if len(a) == 0 or len(b) == 0:
            continue
        a, b = a.iloc[0], b.iloc[0]
        killed = (a.OOS_R > 0 and b.OOS_R <= 0) or (a.robust and not b.robust and b.OOS_R < a.OOS_R * 0.5)
        weakened = b.OOS_R < a.OOS_R - 0.05
        cmp_rows.append({
            "label": lab,
            "synth_R": a.OOS_R, "synth_PF": a.OOS_PF, "synth_tpd": a.tpd, "synth_rob": a.robust, "synth_V": a.verdict,
            "eur_R": b.OOS_R, "eur_PF": b.OOS_PF, "eur_tpd": b.tpd, "eur_rob": b.robust, "eur_V": b.verdict,
            "delta_R": b.OOS_R - a.OOS_R,
            "edge_killed": bool(killed),
            "weakened": bool(weakened),
        })
        flag = "KILLED" if killed else ("WEAKENED" if weakened else "OK")
        lines.append(
            f"- **{lab}** [{flag}]: synth R={a.OOS_R:.3f} PF={a.OOS_PF:.2f} tpd={a.tpd:.2f} rob={a.robust} | "
            f"EUR_inv R={b.OOS_R:.3f} PF={b.OOS_PF:.2f} tpd={b.tpd:.2f} rob={b.robust} (ΔR={b.OOS_R-a.OOS_R:+.3f})"
        )

    cmp = pd.DataFrame(cmp_rows)
    cmp.to_csv(OUT / "compare.csv", index=False)
    n_kill = int(cmp["edge_killed"].sum()) if len(cmp) else 0
    n_weak = int(cmp["weakened"].sum()) if len(cmp) else 0
    lines.append(f"\n\n## Verdict for watchdog viability\n")
    if n_kill:
        lines.append(f"**{n_kill} label(s) KILLED** under EURUSD-inverse. Do **not** rely on those DXY filters live without real DXY.\n")
    elif n_weak:
        lines.append(f"No hard kill, but **{n_weak} weakened**. EURUSD proxy usable with caution; prefer components robust under both.\n")
    else:
        lines.append("EURUSD-inverse preserves edge on tested labels (within tolerance). Proxy viable for live when raw DXY unavailable.\n")

    # Prefer shortlist = robust under BOTH
    both = []
    for lab in labels:
        a = df[(df.label == lab) & (df.dxy_source == "DXY_synth")]
        b = df[(df.label == lab) & (df.dxy_source == "EURUSD_inv")]
        if len(a) and len(b) and a.iloc[0].robust and b.iloc[0].robust and a.iloc[0].OOS_R > 0 and b.iloc[0].OOS_R > 0:
            both.append(lab)
    lines.append(f"\nRobust+positive under **both** sources: {both if both else 'none'}\n")
    lines.append("\n## Full table\n")
    lines.append(df.to_string(index=False))
    (OUT / "REPORT.md").write_text("\n".join(lines))
    (OUT / "meta.json").write_text(json.dumps({
        "generated": str(pd.Timestamp.now(tz="Asia/Tehran")),
        "corr_level": corr_lvl, "corr_ret": corr_ret,
        "n_kill": n_kill, "n_weak": n_weak, "both_robust": both,
        "wall_s": round(time.time() - t0, 1),
    }, indent=2, default=str))
    print("DONE proxy compare", flush=True)


if __name__ == "__main__":
    main()
