#!/usr/bin/env python3
"""SessionBox second-priority expand → append to results/expand/."""
from __future__ import annotations
import json, pickle, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "expand"
CACHE = OUT / "box_pools_cache.pkl"

from engine import simulate, sl_distance_price, Order
from monte_carlo import run_mc
from strategies.session_box_mss import generate_session_box_mss
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from
from run_expand import (
    OOS_CUT, COST_ROWS, oos_trading_days, tpd_true, worst_streak, sl_dist_stats,
)

CAPS = (8.0, 12.0, 15.0)  # 12/15 = INFO only (need Amir approval + smaller lot)


def sim_cap(m1, orders, variant, cap, spread, slip, t0, t1, fractional=False, risk_pct=None):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    if not fractional:
        oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
        rp = (cap / 1000.0) if risk_pct is None else risk_pct
        tr, st = simulate(m1, oo, risk_pct=rp, max_sl_dist=cap,
                          use_circuit_breaker=True, spread=spread, slip=slip)
    else:
        rp = 0.005 if risk_pct is None else risk_pct
        tr, st = simulate(m1, oo, risk_pct=rp, max_sl_dist=None,
                          use_circuit_breaker=True, spread=spread, slip=slip,
                          allow_fractional=True)
    return tr, st, oo


def wf_cap(m1, orders, variant, cap, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold; o1 = warm + (k + 1) * fold if k < 3 else n
        _, st, _ = sim_cap(m1, orders, variant, cap, spread, slip,
                           m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1; rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0: pos += 1
    return (pos / valid if valid else 0.0), rs


def build_box_pools(m1):
    if CACHE.exists():
        print("LOAD box cache", flush=True)
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    pools = {}
    # Limited: 3 TF × 3 box × 1 entry/tp (KEEP params) + M1 rr2 asia = 10
    configs = []
    for tf in ("M1", "M3", "M5"):
        for bk in ("asia", "london", "both"):
            configs.append((tf, bk, "limit_mid", "rr1.5"))
    configs.append(("M1", "asia", "limit_mid", "rr2"))  # prior M1 KEEP shape
    configs.append(("M15", "asia", "limit_mid", "rr1.5"))
    configs.append(("M15", "both", "limit_mid", "rr1.5"))
    for tf, bk, em, tp in configs:
        print(f" BOX {tf} {bk} {em} {tp}", flush=True)
        t0 = time.time()
        oo = generate_session_box_mss(
            m1, None, False, em, tp, True, 0.8, "atr_buf", tf, box_kind=bk,
        )
        if oo:
            pools[oo[0].variant] = oo
            print(f"  n={len(oo)} {oo[0].variant} ({time.time()-t0:.1f}s)", flush=True)
        else:
            print(f"  empty ({time.time()-t0:.1f}s)", flush=True)
    data = {"pools": pools, "n_variants_tried": len(pools)}
    with open(CACHE, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    return data


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    data = build_box_pools(m1)
    pools = data["pools"]
    rows, chosen = [], {}

    # Families: Box_{tf}_{box_kind}
    fam_keys = {}
    for k, v in pools.items():
        # variant: box_M5_limit_mid_... (asia legacy) OR box_M5_london_...
        parts = k.split("_")
        # box_{tf}_{...}
        tf = parts[1]
        if parts[2] in ("asia", "london", "both"):
            bk = parts[2]
        else:
            bk = "asia"
        fam = f"Box_{tf}_{bk}"
        fam_keys.setdefault(fam, []).extend(v)

    for fam, oo in sorted(fam_keys.items()):
        variants = sorted({o.variant for o in oo})
        scored = []
        for v in variants:
            _, st, _ = sim_cap(m1, oo, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
            scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v))
        scored.sort(reverse=True)
        best_v = scored[0][3]
        chosen[fam] = {"variant": best_v, "is_r": scored[0][0], "is_n": scored[0][2]}
        print(f"CHOSEN {fam}: {best_v} IS R={scored[0][0]:.3f} n={scored[0][2]}", flush=True)
        for use_dxy in (False, True):
            orders = apply_dxy_gate(oo, dxy, use_dxy) if use_dxy else list(oo)
            for cap in CAPS:
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 8.0:
                        continue
                    tr, st, oos_oo = sim_cap(m1, orders, best_v, cap, spread, slip, oos_cut,
                                             m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, wf_rs = wf_cap(m1, orders, best_v, cap, spread, slip)
                    mc_pass = None
                    if st["n_trades"] >= 15 and tr is not None and len(tr):
                        mc = run_mc(tr["r_multiple"].values, risk_pcts=(cap / 1000.0,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                    ver, reason = verdict_from(st, wf_frac, mc_pass)
                    # Flag non-$8 as INFO
                    if cap > 8:
                        ver_out = f"INFO_{ver}"
                    else:
                        ver_out = ver
                    sld = sl_dist_stats(oos_oo, spread)
                    tpd = tpd_true(st["n_trades"], n_tdays)
                    rows.append({
                        "family": fam, "variant": best_v, "dxy": use_dxy, "cap": cap,
                        "cost": cost_name, "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                        "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                        "OOS_DD": st.get("max_dd_pct"), "tpd": tpd, "WF+": wf_frac,
                        "MC_pass": mc_pass, "verdict": ver_out, "base_verdict": ver,
                        "worst_streak": worst_streak(tr),
                        "sl_med": sld["median"], "sl_p90": sld["p90"],
                        "needs_approval": cap > 8.0,
                    })
                    print(
                        f"  {fam} dxy={int(use_dxy)} @{cap}/{cost_name}: "
                        f"n={st['n_trades']} tpd={tpd:.3f} R={st.get('expectancy_r')} → {ver_out}",
                        flush=True,
                    )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "box_summary.csv", index=False)
    (OUT / "box_chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    # Merge portfolio: prior Box_M5 asia KEEP shape + NDS_scalp_M3 if available
    nds_cache = OUT / "nds_pools_cache.pkl"
    port_rows = []
    if nds_cache.exists():
        with open(nds_cache, "rb") as f:
            nds = pickle.load(f)["pools"]
        nds_v = "course_scalp_M3_sym_brk_p3_a1.0"
        box_v = chosen.get("Box_M5_asia", {}).get("variant")
        if box_v and nds_v in nds:
            no = apply_dxy_gate(nds[nds_v], dxy, True)  # M3 KEEP used DXY
            bo = list(pools[box_v])  # asia box prefers no DXY historically
            merged = sorted(no + bo, key=lambda x: x.arm_time)
            out, last = [], {}
            for o in merged:
                prev = last.get(o.side)
                if prev is not None and (o.arm_time - prev).total_seconds() < 30 * 60:
                    continue
                out.append(o); last[o.side] = o.arm_time
            tagged = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp,
                            o.strategy, "PORT", dict(o.meta), o.expire_minutes, o.max_hold_minutes)
                      for o in out]
            # Portfolio under $8 hard cap (Amir rule) + fractional uncapped info
            for mode, kw in (
                ("cap8", dict(max_sl_dist=8.0, allow_fractional=False, risk_pct=0.008)),
                ("uncap_r05", dict(max_sl_dist=None, allow_fractional=True, risk_pct=0.005)),
            ):
                tr, st = simulate(m1, tagged, use_circuit_breaker=True, spread=0.35, slip=0.10, **kw)
                if tr is not None and len(tr):
                    tr = tr[pd.to_datetime(tr["entry_time"], utc=True) >= oos_cut].reset_index(drop=True)
                    if len(tr):
                        from engine import compute_stats
                        st = compute_stats(tr, 1000.0, 1000.0 + float(tr["pnl_usd"].sum()))
                    else:
                        st = {"n_trades": 0, "win_rate": 0, "expectancy_r": 0, "profit_factor": 0, "max_dd_pct": 0}
                tpd = tpd_true(st["n_trades"], n_tdays)
                mc_pass = None
                if st["n_trades"] >= 15 and tr is not None and len(tr):
                    mc = run_mc(tr["r_multiple"].values, risk_pcts=(kw["risk_pct"],))
                    if mc is not None and len(mc):
                        mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                port_rows.append({
                    "mode": mode, "box_v": box_v, "nds_v": nds_v,
                    "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                    "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                    "OOS_DD": st.get("max_dd_pct"), "tpd": tpd, "MC_pass": mc_pass,
                    "worst_streak": worst_streak(tr) if tr is not None else 0,
                })
                print(f"PORT {mode}: n={st['n_trades']} tpd={tpd:.3f} R={st.get('expectancy_r')} PF={st.get('profit_factor')}", flush=True)
    if port_rows:
        pd.DataFrame(port_rows).to_csv(OUT / "portfolio_nds_m3_plus_box.csv", index=False)

    # Append box section to REPORT
    lines = ["", "## SessionBox expand (2nd priority, IS @cap8 strict)", "",
             f"Box variants tried: **{data['n_variants_tried']}**. Caps $12/$15 marked INFO (need Amir OK + smaller lot).",
             "",
             "| Family | cap | DXY | n | tpd | WR | R | PF | DD% | V |",
             "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---|"]
    focus = df[(df.cost == "strict")].copy()
    for _, r in focus.sort_values(["family", "cap", "dxy"]).iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        lines.append(
            f"| {r['family']} | {r['cap']} | {int(r['dxy'])} | {int(r['OOS_n'])} | "
            f"{r['tpd']:.3f} | {wr} | {r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | "
            f"{r['OOS_DD']:.1f} | **{r['verdict']}** |"
        )
    if port_rows:
        lines += ["", "### Portfolio NDS_M3(sym+DXY) + Box_M5_asia (30m dedupe)", ""]
        for p in port_rows:
            lines.append(
                f"- {p['mode']}: n={p['OOS_n']} tpd={p['tpd']:.3f} R={p['OOS_R']:.3f} "
                f"PF={p['OOS_PF']:.2f} DD={p['OOS_DD']:.1f} MC={p['MC_pass']} streak={p['worst_streak']}"
            )
    keeps8 = df[(df.cap == 8) & (df.cost == "strict") & (df.base_verdict == "KEEP")]
    lines += ["", "### Box conclusion", ""]
    if len(keeps8):
        lines.append("KEEP @8 strict: " + ", ".join(sorted(keeps8.family.unique())))
    else:
        lines.append("No new Box KEEP @8 strict beyond prior asia M5 shape (see table).")
    (OUT / "REPORT.md").write_text((OUT / "REPORT.md").read_text() + "\n".join(lines))
    print("DONE box expand", flush=True)


if __name__ == "__main__":
    main()
