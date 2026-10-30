#!/usr/bin/env python3
"""NDS course fidelity toggles: partial / reentry864 / HTF-N3.
Limited grid on best families. Writes results/expand/fidelity_*.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "expand"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, Order, compute_stats
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from
from run_expand import (
    OOS_CUT, COST_ROWS, oos_trading_days, tpd_true, worst_streak, sl_dist_stats,
)

# Families requested
FAMILY_KW = [
    ("scalp_M3_sym", dict(style="scalp", entry_tf="M3", tp_mode="sym", confirm="brk_p3")),
    ("scalp_M5_sym", dict(style="scalp", entry_tf="M5", tp_mode="sym", confirm="brk_p3")),
    ("day_M5_sym", dict(style="day", entry_tf="M5", tp_mode="sym", confirm="brk_p3")),
    ("day_M3_sym", dict(style="day", entry_tf="M3", tp_mode="sym", confirm="brk_p3")),
]

# Toggle combos (limited)
TOGGLES = [
    ("base", dict(use_partial=False, use_reentry864=False, use_htf_n3_tp=False)),
    ("pe", dict(use_partial=True, use_reentry864=False, use_htf_n3_tp=False)),
    ("r864", dict(use_partial=False, use_reentry864=True, use_htf_n3_tp=False)),
    ("htf", dict(use_partial=False, use_reentry864=False, use_htf_n3_tp=True)),
    ("full", dict(use_partial=True, use_reentry864=True, use_htf_n3_tp=True)),
]


def sim_mode(m1, orders, variant, mode, spread, slip, t0, t1):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    if mode == "cap8":
        oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= 8.0 + 1e-9]
        tr, st = simulate(m1, oo, risk_pct=0.008, max_sl_dist=8.0,
                          use_circuit_breaker=True, spread=spread, slip=slip,
                          allow_fractional=True)  # fractional needed for 1/3 legs under cap
    else:  # uncap r05
        tr, st = simulate(m1, oo, risk_pct=0.005, max_sl_dist=None,
                          use_circuit_breaker=True, spread=spread, slip=slip,
                          allow_fractional=True)
    return tr, st, oo


def wf_mode(m1, orders, variant, mode, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold
        o1 = warm + (k + 1) * fold if k < 3 else n
        _, st, _ = sim_mode(m1, orders, variant, mode, spread, slip,
                            m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1
            rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def main():
    t0all = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "OOS days", n_tdays, flush=True)

    pools = {}
    n_tried = 0
    for fam, fkw in FAMILY_KW:
        for tname, tkw in TOGGLES:
            n_tried += 1
            label = f"{fam}__{tname}"
            print(f"GEN {label}", flush=True)
            tt = time.time()
            oo = generate_nds_course(
                m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
                **fkw, **tkw,
            )
            if not oo:
                print("  empty", flush=True)
                continue
            pools[label] = oo
            print(f"  n={len(oo)} v={oo[0].variant} ({time.time()-tt:.1f}s)", flush=True)

    rows = []
    for label, oo in pools.items():
        variant = oo[0].variant
        fam, tname = label.split("__")
        for use_dxy in (False, True):
            orders = apply_dxy_gate(oo, dxy, use_dxy) if use_dxy else list(oo)
            for mode in ("cap8", "uncap"):
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and mode == "cap8":
                        # still run cheap @cap8
                        pass
                    tr_is, st_is, _ = sim_mode(m1, orders, variant, mode, spread, slip,
                                               m1.index[0], oos_cut)
                    tr, st, oos_oo = sim_mode(m1, orders, variant, mode, spread, slip,
                                             oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, wf_rs = wf_mode(m1, orders, variant, mode, spread, slip)
                    mc_pass = None
                    if st["n_trades"] >= 15 and tr is not None and len(tr):
                        risk = 0.008 if mode == "cap8" else 0.005
                        mc = run_mc(tr["r_multiple"].values, risk_pcts=(risk,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                    ver, reason = verdict_from(st, wf_frac, mc_pass)
                    # Robust = positive IS and OOS expectancy + KEEP gates on OOS
                    robust = bool(
                        st_is["n_trades"] >= 15 and st_is["expectancy_r"] > 0
                        and st["n_trades"] >= 20 and st["expectancy_r"] > 0
                        and st["profit_factor"] >= 1.05 and ver in ("KEEP", "MAYBE")
                    )
                    robust_keep = bool(robust and ver == "KEEP" and st_is["expectancy_r"] > 0)
                    tpd = tpd_true(st["n_trades"], n_tdays)
                    # signal-days approx: unique primary arms (exclude partial_2of3 double-count)
                    prim = [o for o in oos_oo if o.meta.get("leg") in ("full", "partial_1of3", "reentry864")]
                    tpd_sig = tpd_true(len({(o.arm_time, o.side, o.meta.get("leg")) for o in prim}), n_tdays)
                    sld = sl_dist_stats(oos_oo, spread)
                    rows.append({
                        "family": fam, "toggle": tname, "variant": variant,
                        "dxy": use_dxy, "mode": mode, "cost": cost_name,
                        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"],
                        "IS_PF": st_is["profit_factor"], "IS_WR": st_is.get("win_rate"),
                        "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                        "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                        "OOS_DD": st.get("max_dd_pct"), "tpd": tpd, "tpd_sig": tpd_sig,
                        "WF+": wf_frac, "MC_pass": mc_pass, "verdict": ver,
                        "robust_pos_IS_OOS": robust, "robust_KEEP": robust_keep,
                        "worst_streak": worst_streak(tr),
                        "sl_med": sld["median"], "sl_p90": sld["p90"],
                        "n_reentry_oos": sum(1 for o in oos_oo if o.meta.get("leg") == "reentry864"),
                        "n_partial_oos": sum(1 for o in oos_oo if o.meta.get("leg") == "partial_1of3"),
                    })
                    print(
                        f"{label} dxy={int(use_dxy)} {mode}/{cost_name}: "
                        f"IS_R={st_is['expectancy_r']:.3f} n={st_is['n_trades']} | "
                        f"OOS_R={st.get('expectancy_r'):.3f} n={st['n_trades']} "
                        f"tpd={tpd:.2f} → {ver} robust={robust_keep}",
                        flush=True,
                    )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "fidelity_summary.csv", index=False)
    (OUT / "fidelity_meta.json").write_text(json.dumps({
        "n_variants_tried": n_tried,
        "families": [f[0] for f in FAMILY_KW],
        "toggles": [t[0] for t in TOGGLES],
        "modes": ["cap8", "uncap"],
        "protocol": "IS/OOS 2026-07-02, WF4, MC SGB, strict/cheap, size_mult partial",
        "wall_s": round(time.time() - t0all, 1),
    }, indent=2))

    # Compact report
    focus = df[(df.cost == "strict")].copy()
    lines = [
        f"# NDS fidelity toggles (variants tried={n_tried})",
        "",
        "Toggles: base | pe (1/3 open-node) | r864 (re-entry F−0.136·D) | htf (HTF node-3 TP) | full (all three).",
        "Robust KEEP = IS_R>0 & IS_n≥15 AND OOS KEEP gates.",
        "",
        "## Strict cost — key cells",
        "",
        "| Fam | tog | mode | DXY | IS_n | IS_R | OOS_n | OOS_R | PF | tpd | V | robust |",
        "|---|---|---|:---:|---:|---:|---:|---:|---:|---:|---|:---:|",
    ]
    for _, r in focus.sort_values(["family", "toggle", "mode", "dxy"]).iterrows():
        lines.append(
            f"| {r['family']} | {r['toggle']} | {r['mode']} | {int(r['dxy'])} | "
            f"{int(r['IS_n'])} | {r['IS_R']:.3f} | {int(r['OOS_n'])} | {r['OOS_R']:.3f} | "
            f"{r['OOS_PF']:.2f} | {r['tpd']:.2f} | **{r['verdict']}** | "
            f"{'Y' if r['robust_KEEP'] else 'n'} |"
        )

    # Deltas vs base (uncap + cap8, noDXY and DXY) for IS_R and tpd
    lines += ["", "## Delta vs base (strict)", ""]
    for mode in ("cap8", "uncap"):
        for fam in df.family.unique():
            for dxy_f in (False, True):
                base = focus[(focus.family == fam) & (focus.toggle == "base") &
                             (focus.mode == mode) & (focus.dxy == dxy_f)]
                if not len(base):
                    continue
                b = base.iloc[0]
                lines.append(f"### {fam} {mode} dxy={int(dxy_f)}  (base IS_R={b['IS_R']:.3f} tpd={b['tpd']:.2f})")
                for tog in ("pe", "r864", "htf", "full"):
                    sub = focus[(focus.family == fam) & (focus.toggle == tog) &
                                (focus.mode == mode) & (focus.dxy == dxy_f)]
                    if not len(sub):
                        continue
                    s = sub.iloc[0]
                    lines.append(
                        f"- {tog}: ΔIS_R={s['IS_R']-b['IS_R']:+.3f} ΔOOS_R={s['OOS_R']-b['OOS_R']:+.3f} "
                        f"Δtpd={s['tpd']-b['tpd']:+.2f} → {s['verdict']} robust={bool(s['robust_KEEP'])}"
                    )

    rk = focus[focus.robust_KEEP == True]
    lines += ["", "## Answer", ""]
    if len(rk):
        lines.append(f"**Yes — robust KEEP cells:** {len(rk)}")
        for _, r in rk.iterrows():
            lines.append(
                f"- {r['family']}__{r['toggle']} {r['mode']} dxy={int(r['dxy'])}: "
                f"IS_R={r['IS_R']:.3f} OOS_R={r['OOS_R']:.3f} tpd={r['tpd']:.2f}"
            )
    else:
        lines.append(
            "**No robust KEEP** (positive IS_R and OOS KEEP) among fidelity toggles on this grid."
        )
    # Did anything fix IS?
    base_is = focus[(focus.toggle == "base") & (focus.mode == "uncap")]
    fixed = focus[(focus.toggle != "base") & (focus.IS_R > 0) & (focus.mode == "uncap")]
    lines.append(
        f"Uncap cells with IS_R>0 under toggles: {len(fixed)} "
        f"(base uncap IS_R>0 cells: {int((base_is.IS_R > 0).sum())})."
    )
    lines.append(f"Wall {time.time()-t0all:.0f}s. Variants tried={n_tried}.")
    (OUT / "FIDELITY_RERUN.md").write_text("\n".join(lines))
    print("DONE", OUT / "FIDELITY_RERUN.md", flush=True)


if __name__ == "__main__":
    main()
