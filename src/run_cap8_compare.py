#!/usr/bin/env python3
"""Focused cap $8/$5 comparison: NDS + SessionBox + MTF SMC.
IS choose / OOS judge. Writes results/cap8_compare/.
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "cap8_compare"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "pools_cache.pkl"

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.session_box_mss import generate_session_box_mss
from strategies.mtf_smc import generate_mtf_smc
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from

CAPS = (5.0, 8.0)
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")
COST_ROWS = (("strict", 0.35, 0.10), ("cheap", 0.25, 0.05))


def risk_pct(cap): return cap / 1000.0


def oos_trading_days(m1, oos_cut):
    idx = m1.index[m1.index >= oos_cut]
    days = pd.DatetimeIndex(idx.normalize().unique())
    return [d for d in days if int(getattr(d, "day_of_week", d.dayofweek)) < 5]


def tpd_true(n, n_tdays): return float(n) / max(1, n_tdays)


def sim(m1, orders, variant, cap, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    skip = count_sl_cap_skips(oo, cap, spread)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=cb, spread=spread, slip=slip)
    return tr, st, skip, oo


def wf(m1, orders, variant, cap, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold; o1 = warm + (k + 1) * fold if k < 3 else n
        _, st, _, _ = sim(m1, orders, variant, cap, spread, slip,
                          m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1; rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0: pos += 1
    return (pos / valid if valid else 0.0), rs


def sanity(m1, orders, variant, cap, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side) <= cap + 1e-9]
    _, st0 = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes)
              for o in oo]
        _, st = simulate(m1, sh, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        out[f"shift{s}_pf"] = st["profit_factor"]
    rng = np.random.default_rng(1); rands = []
    for _ in range(3):
        ro = []
        for o in oo:
            j = m1.index.searchsorted(o.arm_time, side="left")
            if j >= len(m1) - 5: continue
            jj = int(rng.integers(max(0, j - 40), min(len(m1) - 1, j + 40)))
            px = float(m1["close"].iloc[jj]); risk = abs(o.price - o.sl)
            side = o.side if rng.random() < 0.5 else ("short" if o.side == "long" else "long")
            sl, tp = ((px - risk, px + abs(o.tp - o.price)) if side == "long"
                      else (px + risk, px - abs(o.tp - o.price)))
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, "market", px, sl, tp, "RAND", o.variant, {}, 30))
        _, st = simulate(m1, ro, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    out["pass"] = bool(out["base_n"] >= 15 and out["base_pf"] >= 1.05
                       and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
                       and out.get("shift15_pf", 0) > 0.3)
    return out


def build_pools(m1, dxy):
    if CACHE.exists():
        print("LOAD cache", CACHE, flush=True)
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    nds_pools = {}
    for tf in ("M5", "M1"):
        for tp, conf in (("rr1.5", "brk_p3"), ("sym", "brk_p3"), ("nd864", "brk_p3"),
                         ("rr1.5", "brk_pull"), ("sym", "brk_pull")):
            print(" NDS course", tf, tp, conf, flush=True)
            oo = generate_nds_course(m1, None, False, False, family="course", style="scalp",
                                     entry_tf=tf, tp_mode=tp, confirm=conf, min_atr=1.0, pivot_lr=3)
            if oo: nds_pools[oo[0].variant] = oo; print("  n=", len(oo), oo[0].variant, flush=True)
        for tp, conf, smi in (("nd88", "brk_pull", False), ("nd88", "brk_p3", False),
                              ("rr1.5", "brk_p3", False), ("nd864", "brk_pull", True)):
            print(" NDS schem", tf, tp, conf, "smi", smi, flush=True)
            oo = generate_nds_course(m1, None, False, False, family="schematic", style="scalp",
                                     entry_tf=tf, tp_mode=tp, confirm=conf, nd_zone=True,
                                     req_smi=smi, equal_top=False, min_atr=1.0, pivot_lr=3)
            if oo: nds_pools[oo[0].variant] = oo; print("  n=", len(oo), oo[0].variant, flush=True)

    box_pools = {}
    for tf in ("M5", "M1"):
        for entry, tp in (("limit_mid", "rr1.5"), ("market", "rr2"),
                          ("limit_mid", "rr2"), ("market", "rr1.5")):
            print(" BOX", tf, entry, tp, flush=True)
            oo = generate_session_box_mss(m1, None, False, entry, tp, True, 0.8, "atr_buf", tf)
            if oo: box_pools[oo[0].variant] = oo; print("  n=", len(oo), oo[0].variant, flush=True)

    mtf_pools = {}
    for smt in (True, False):
        for tp in ("rr2", "ext", "ext_or_rr2"):
            print(" MTF", smt, tp, flush=True)
            oo = generate_mtf_smc(m1, dxy, use_smt=smt, tp_mode=tp)
            if oo: mtf_pools[oo[0].variant] = oo; print("  n=", len(oo), oo[0].variant, flush=True)

    data = {"nds": nds_pools, "box": box_pools, "mtf": mtf_pools}
    with open(CACHE, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("CACHED", CACHE, flush=True)
    return data


def eval_family(m1, dxy, label, base_orders, oos_cut, n_tdays, rows, chosen):
    variants = sorted({o.variant for o in base_orders})
    if not variants:
        print("EMPTY", label, flush=True); return None
    scored = []
    for v in variants:
        _, st, _, _ = sim(m1, base_orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
        scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v))
    scored.sort(reverse=True)
    best_v = scored[0][3]
    chosen[label] = {"variant": best_v, "is_r": scored[0][0], "is_pf": scored[0][1], "is_n": scored[0][2]}
    print(f"CHOSEN {label}: {best_v} IS R={scored[0][0]:.3f} n={scored[0][2]}", flush=True)

    for use_dxy in (False, True):
        orders = apply_dxy_gate(base_orders, dxy, use_dxy) if use_dxy else list(base_orders)
        for cap in CAPS:
            for cost_name, spread, slip in COST_ROWS:
                if cost_name == "cheap" and cap != 8.0:
                    continue
                tr, st, sk, _ = sim(m1, orders, best_v, cap, spread, slip, oos_cut,
                                    m1.index[-1] + pd.Timedelta(minutes=1))
                _, st_is, _, _ = sim(m1, orders, best_v, cap, spread, slip, m1.index[0], oos_cut)
                wf_frac, wf_rs = wf(m1, orders, best_v, cap, spread, slip)
                mc_pass = None
                if st["n_trades"] >= 15 and tr is not None and len(tr):
                    mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.005,))
                    if mc is not None and len(mc):
                        mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                ver, reason = verdict_from(st, wf_frac, mc_pass)
                san = sanity(m1, orders, best_v, cap, oos_cut) if st["n_trades"] >= 15 else {}
                tpd = tpd_true(st["n_trades"], n_tdays)
                rows.append({
                    "family": label, "variant": best_v, "dxy": use_dxy, "cap": cap, "cost": cost_name,
                    "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                    "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                    "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                    "OOS_DD": st.get("max_dd_pct"),
                    "tpd": tpd, "n_tdays": n_tdays,
                    "WF+": wf_frac, "WF_rs": str(wf_rs), "MC_pass05": mc_pass,
                    "verdict": ver, "reason": reason, "sanity_pass": san.get("pass"),
                    "skip_n": sk.get("n_skipped"), "skip_pct": sk.get("skip_pct"),
                })
                if tr is not None and len(tr):
                    tag = f"{label}_{'DXY' if use_dxy else 'noDXY'}_cap{cap}_{cost_name}"
                    tr.to_csv(OUT / f"trades_{tag}.csv", index=False)
                print(f"  {label} dxy={use_dxy} @{cap}/{cost_name}: n={st['n_trades']} "
                      f"tpd={tpd:.3f} WR={st.get('win_rate')} R={st.get('expectancy_r')} → {ver}", flush=True)
    return best_v


def combine_portfolio(m1, dxy, nds_orders, nds_v, box_orders, box_v, oos_cut, n_tdays, cap=8.0, tag="port"):
    rows = []
    for use_dxy in (False, True):
        no = apply_dxy_gate(nds_orders, dxy, use_dxy) if use_dxy else list(nds_orders)
        bo = apply_dxy_gate(box_orders, dxy, use_dxy) if use_dxy else list(box_orders)
        no = [o for o in no if o.variant == nds_v]
        bo = [o for o in bo if o.variant == box_v]
        merged = sorted(no + bo, key=lambda x: x.arm_time)
        out, last = [], {}
        for o in merged:
            prev = last.get(o.side)
            if prev is not None and (o.arm_time - prev).total_seconds() < 30 * 60:
                continue
            out.append(o); last[o.side] = o.arm_time
        for cost_name, spread, slip in COST_ROWS:
            tagged = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp,
                            o.strategy, "PORT", dict(o.meta), o.expire_minutes, o.max_hold_minutes)
                      for o in out]
            tr, st, sk, _ = sim(m1, tagged, "PORT", cap, spread, slip, oos_cut,
                                m1.index[-1] + pd.Timedelta(minutes=1))
            tpd = tpd_true(st["n_trades"], n_tdays)
            rows.append({
                "tag": tag, "dxy": use_dxy, "cap": cap, "cost": cost_name,
                "nds_v": nds_v, "box_v": box_v,
                "n_nds_raw": len(no), "n_box_raw": len(bo), "n_merged": len(out),
                "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                "OOS_DD": st.get("max_dd_pct"), "tpd": tpd,
            })
            print(f"{tag} dxy={use_dxy} {cost_name}: n={st['n_trades']} tpd={tpd:.3f} "
                  f"R={st.get('expectancy_r')} PF={st.get('profit_factor')}", flush=True)
    return rows


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "bars", len(m1), "OOS trading days", n_tdays, flush=True)

    pools = build_pools(m1, dxy)
    nds_pools, box_pools, mtf_pools = pools["nds"], pools["box"], pools["mtf"]

    rows, chosen = [], {}

    def nds_group(pred, label):
        oo = [o for k, v in nds_pools.items() if pred(k) for o in v]
        if oo: eval_family(m1, dxy, label, oo, oos_cut, n_tdays, rows, chosen)

    nds_group(lambda k: k.startswith("course_scalp_M5_") and "_rr1.5_" in k, "NDS_rr15_M5")
    nds_group(lambda k: k.startswith("course_scalp_M1_") and "_rr1.5_" in k, "NDS_rr15_M1")
    nds_group(lambda k: k.startswith("course_scalp_M5_") and "_sym_" in k, "NDS_sym_M5")
    nds_group(lambda k: k.startswith("course_scalp_M1_") and "_sym_" in k, "NDS_sym_M1")
    nds_group(lambda k: k.startswith("course_scalp_M5_") and "_nd864_" in k, "NDS_nd864_M5")
    nds_group(lambda k: k.startswith("course_scalp_M1_") and "_nd864_" in k, "NDS_nd864_M1")
    nds_group(lambda k: k.startswith("schematic_scalp_M5_"), "NDS_schem_M5")
    nds_group(lambda k: k.startswith("schematic_scalp_M1_"), "NDS_schem_M1")

    for tf in ("M5", "M1"):
        oo = [o for pool in box_pools.values() for o in pool if f"box_{tf}_" in o.variant]
        eval_family(m1, dxy, f"SessionBox_{tf}", oo, oos_cut, n_tdays, rows, chosen)

    # MTF SMC: one family cell (IS pick among smt/nosmt × tp)
    oo = [o for pool in mtf_pools.values() for o in pool]
    eval_family(m1, dxy, "MTFSMC_M5", oo, oos_cut, n_tdays, rows, chosen)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)

    deltas = []
    for (fam, cap, cost), g in df.groupby(["family", "cap", "cost"]):
        a = g[g.dxy == False]; b = g[g.dxy == True]
        if len(a) and len(b):
            a, b = a.iloc[0], b.iloc[0]
            deltas.append({
                "family": fam, "cap": cap, "cost": cost, "variant": a["variant"],
                "n0": a["OOS_n"], "n1": b["OOS_n"], "dn": int(b["OOS_n"] - a["OOS_n"]),
                "R0": a["OOS_R"], "R1": b["OOS_R"], "dR": (b["OOS_R"] or 0) - (a["OOS_R"] or 0),
                "PF0": a["OOS_PF"], "PF1": b["OOS_PF"], "dPF": (b["OOS_PF"] or 0) - (a["OOS_PF"] or 0),
                "tpd0": a["tpd"], "tpd1": b["tpd"],
                "ver0": a["verdict"], "ver1": b["verdict"],
            })
    ddf = pd.DataFrame(deltas)
    ddf.to_csv(OUT / "dxy_delta.csv", index=False)

    # Portfolio NDS_rr15_M5 + SessionBox_M5 @8
    port = []
    if "NDS_rr15_M5" in chosen and "SessionBox_M5" in chosen:
        nds_v = chosen["NDS_rr15_M5"]["variant"]
        box_v = chosen["SessionBox_M5"]["variant"]
        nds_oo = [o for pool in nds_pools.values() for o in pool if o.variant == nds_v]
        box_oo = [o for pool in box_pools.values() for o in pool if o.variant == box_v]
        port += combine_portfolio(m1, dxy, nds_oo, nds_v, box_oo, box_v, oos_cut, n_tdays, 8.0,
                                  tag="port_NDS_rr15_M5+Box")
        # best NDS by IS + Box
        best_nds = max([k for k in chosen if k.startswith("NDS_")],
                       key=lambda k: (chosen[k]["is_r"], chosen[k]["is_n"]))
        if best_nds != "NDS_rr15_M5":
            nv = chosen[best_nds]["variant"]
            no2 = [o for pool in nds_pools.values() for o in pool if o.variant == nv]
            port += combine_portfolio(m1, dxy, no2, nv, box_oo, box_v, oos_cut, n_tdays, 8.0,
                                      tag=f"port_{best_nds}+Box")
    pdf = pd.DataFrame(port)
    pdf.to_csv(OUT / "portfolio_cap8.csv", index=False)
    (OUT / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    # REPORT
    focus = df[df.cost == "strict"].copy()
    lines = [
        f"# Cap $8 compare (OOS trading days={n_tdays})",
        "",
        "Variant chosen on **IS @cap8 strict** by expectancy; metrics below are **OOS**.",
        "tpd = OOS trades / OOS trading days (weekdays, not days-with-trade).",
        "",
        "## Table (strict)",
        "",
        "| Family | variant | cap | DXY | n | tpd | WR | R | PF | DD% | WF+ | MC | verdict |",
        "|---|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in focus.sort_values(["family", "cap", "dxy"]).iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        mc = f"{r['MC_pass05']:.2f}" if pd.notna(r["MC_pass05"]) else "-"
        lines.append(
            f"| {r['family']} | `{r['variant'][-42:]}` | {r['cap']} | {int(r['dxy'])} | "
            f"{int(r['OOS_n'])} | {r['tpd']:.3f} | {wr} | "
            f"{r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | {r['OOS_DD']:.1f} | {r['WF+']:.0%} | "
            f"{mc} | **{r['verdict']}** |"
        )
    lines += ["", "## DXY delta (strict @8)", ""]
    for _, r in ddf[(ddf.cap == 8.0) & (ddf.cost == "strict")].iterrows():
        lines.append(
            f"- {r['family']}: dR={r['dR']:+.3f} dPF={r['dPF']:+.2f} dn={int(r['dn'])} "
            f"tpd {r['tpd0']:.3f}→{r['tpd1']:.3f} ({r['ver0']}→{r['ver1']})"
        )
    lines += ["", "## Portfolio @8 (NDS+SessionBox, 30m dedupe)", ""]
    for _, r in pdf.iterrows():
        lines.append(
            f"- {r['tag']} dxy={r['dxy']} {r['cost']}: n={int(r['OOS_n'])} "
            f"tpd={r['tpd']:.3f} WR={r['OOS_WR']} R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f}"
        )

    # 3-line conclusion
    f8 = focus[focus.cap == 8]
    if len(f8):
        best8 = f8.sort_values("OOS_R", ascending=False).iloc[0]
        dxy_help = ddf[(ddf.cap == 8.0) & (ddf.cost == "strict") & (ddf.dR > 0.05)]
        port_line = ""
        if len(pdf):
            p0 = pdf[(pdf.dxy == False) & (pdf.cost == "strict")]
            if len(p0):
                p = p0.iloc[0]
                port_line = f"Portfolio NDS+Box @8: tpd={p['tpd']:.3f} PF={p['OOS_PF']:.2f} n={int(p['OOS_n'])}."
        lines += [
            "",
            "## Conclusion",
            f"1. At **$8** best OOS cell: `{best8['family']}` dxy={int(best8['dxy'])} "
            f"n={int(best8['OOS_n'])} tpd={best8['tpd']:.3f} WR={best8['OOS_WR']:.0%} "
            f"R={best8['OOS_R']:.3f} PF={best8['OOS_PF']:.2f} → {best8['verdict']}.",
            f"2. DXY helps (dR>+0.05 @8 strict) for: "
            + (", ".join(dxy_help["family"].tolist()) if len(dxy_help) else "none meaningfully") + ".",
            f"3. {port_line} Cap$5 often fewer trades/KEEP more often; $8 raises tpd but usually hurts R/PF.",
        ]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
