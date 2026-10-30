#!/usr/bin/env python3
"""NDS schematic + M1/M5 side-by-side. Writes results/nds_course/schematic/ only."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "nds_course" / "schematic"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order, SPREAD, SLIPPAGE
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from

CAPS = (5.0, 7.5, 8.0)
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")
COST_ROWS = (("strict", 0.35, 0.10), ("cheap", 0.25, 0.05))
TOTAL_SPREAD_REF = 0.45  # for cost-share report


def risk_pct(cap): return cap / 1000.0


def sim(m1, orders, variant, cap, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    skip = count_sl_cap_skips(oo, cap, spread)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=cb, spread=spread, slip=slip)
    return tr, st, skip


def wf(m1, orders, variant, cap, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold; o1 = warm + (k + 1) * fold if k < 3 else n
        _, st, _ = sim(m1, orders, variant, cap, spread, slip,
                       m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1; rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def sanity(m1, orders, variant, cap, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side) <= cap + 1e-9]
    _, st0 = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
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
                       and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1)
    return out


def cost_share(orders, spread_tot=TOTAL_SPREAD_REF):
    if not orders:
        return {}
    dists = np.array([abs(o.price - o.sl) for o in orders], dtype=float)
    dists = dists[dists > 0]
    if len(dists) == 0:
        return {}
    return {
        "n": len(dists),
        "med_sl": float(np.median(dists)),
        "p25_sl": float(np.percentile(dists, 25)),
        "p75_sl": float(np.percentile(dists, 75)),
        "cost_share_med": float(spread_tot / np.median(dists)),
        "frac_sl_le_5": float((dists <= 5).mean()),
        "frac_sl_le_8": float((dists <= 8).mean()),
        "spread_ref": spread_tot,
    }


def build(m1, dxy):
    specs = []
    # Baseline course (compare to prior KEEP)
    for tf, conf in (("M5", "brk_p3"), ("M1", "brk_p3"), ("M1", "brk_pull")):
        specs.append(dict(family="course", style="scalp", entry_tf=tf, tp_mode="rr1.5", confirm=conf))
    for ctx, tf in (("ctx_M5", "M1"), ("ctx_M15", "M1"), ("ctx_M5", "M5")):
        specs.append(dict(family="course", style=ctx, entry_tf=tf, tp_mode="rr1.5", confirm="brk_p3"))
    # Schematic
    for tf, tp, conf, smi, eq in product(
            ("M5", "M1"),
            ("nd88", "nd864", "rr1.5"),
            ("brk_pull", "brk_p3"),
            (False, True),
            (False, True)):
        # prune grid
        if eq and smi:
            continue
        if tf == "M1" and tp == "nd864" and conf == "brk_p3":
            continue
        if smi and conf != "brk_pull":
            continue
        if eq and tp != "rr1.5":
            continue
        specs.append(dict(family="schematic", style="scalp", entry_tf=tf, tp_mode=tp,
                          confirm=conf, nd_zone=True, req_smi=smi, equal_top=eq))
    for ctx in ("ctx_M5", "ctx_M15"):
        specs.append(dict(family="schematic", style=ctx, entry_tf="M1", tp_mode="nd88",
                          confirm="brk_pull", nd_zone=True, req_smi=False, equal_top=False))
        specs.append(dict(family="schematic", style=ctx, entry_tf="M1", tp_mode="rr1.5",
                          confirm="brk_p3", nd_zone=True))

    print(f"specs={len(specs)}", flush=True)
    pools = {"ALL": []}
    cost_rows = []
    for sp in specs:
        print(" gen", sp, flush=True)
        kw = dict(dxy=None, use_dxy=False, use_vol=False, min_atr=1.0, pivot_lr=3, hold_min=240)
        kw.update(sp)
        # defaults for missing schematic flags
        kw.setdefault("nd_zone", False)
        kw.setdefault("req_smi", False)
        kw.setdefault("equal_top", False)
        oo = generate_nds_course(m1, **kw)
        print("  n=", len(oo), oo[0].variant if oo else "-", flush=True)
        pools["ALL"].extend(oo)
        cs = cost_share(oo)
        cs.update({"variant": oo[0].variant if oo else sp["family"], **{k: sp.get(k) for k in
                   ("family", "style", "entry_tf", "tp_mode", "confirm")}})
        cost_rows.append(cs)
    pools["ALL_DXY"] = apply_dxy_gate(pools["ALL"], dxy, True)
    pd.DataFrame(cost_rows).to_csv(OUT / "cost_share_m1_m5.csv", index=False)
    print("DXY", len(pools["ALL_DXY"]), flush=True)
    return pools


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    print("cut", oos_cut, "bars", len(m1), flush=True)
    pools = build(m1, dxy)
    rows = []
    for name, orders in pools.items():
        variants = sorted({o.variant for o in orders})
        print(f"SCAN {name} nvar={len(variants)}", flush=True)
        # score on IS @cap8
        scored = []
        for v in variants:
            tr, st, sk = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
            if st["n_trades"] >= 6:
                scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st))
        scored.sort(reverse=True)
        top = scored[:8]
        # always include baseline course scalp M5/M1 rr1.5 brk_p3 if present
        must = [v for v in variants if "course_scalp_M5_rr1.5_brk_p3" in v or "course_scalp_M1_rr1.5_brk_p3" in v]
        have = {t[3] for t in top}
        for v in must:
            if v not in have:
                tr, st, sk = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
                top.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st))
        for exp, pf, n, v, st_is in top:
            for cap in CAPS:
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 5.0:
                        continue
                    tr, st, sk = sim(m1, orders, v, cap, spread, slip, oos_cut,
                                     m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, wf_rs = wf(m1, orders, v, cap, spread, slip)
                    mc_pass = None
                    if st["n_trades"] >= 15:
                        mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.005,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                    ver, reason = verdict_from(st, wf_frac, mc_pass)
                    san = sanity(m1, orders, v, cap, oos_cut) if st["n_trades"] >= 15 else {}
                    tpd = st.get("trades_per_day")
                    if tpd is None and tr is not None and len(tr):
                        ndays = max(1, (pd.to_datetime(tr["exit_time"]).max() - pd.to_datetime(tr["entry_time"]).min()).days)
                        tpd = len(tr) / max(1, ndays)
                    buy = int((tr["side"] == "long").sum()) if tr is not None and len(tr) else 0
                    sell = int((tr["side"] == "short").sum()) if tr is not None and len(tr) else 0
                    # cost share on kept OOS orders
                    oo_oos = [o for o in orders if o.variant == v and o.arm_time >= oos_cut
                              and sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
                    cs = cost_share(oo_oos)
                    row = {
                        "pool": name, "variant": v, "cap": cap, "cost": cost_name,
                        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                        "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                        "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                        "OOS_DD": st.get("max_dd_pct"), "tpd": tpd, "WF+": wf_frac, "WF_rs": str(wf_rs),
                        "MC_pass05": mc_pass, "verdict": ver, "reason": reason,
                        "buy_n": buy, "sell_n": sell, "sanity_pass": san.get("pass"),
                        "med_sl": cs.get("med_sl"), "cost_share_med": cs.get("cost_share_med"),
                        "skips": sk.get("n_skipped"),
                    }
                    rows.append(row)
                    if tr is not None and len(tr):
                        tr.to_csv(OUT / f"trades_{name}_{v}_cap{cap}_{cost_name}_OOS.csv", index=False)
                    print(f"  {v} @{cap}/{cost_name}: n={st['n_trades']} WR={st.get('win_rate')} "
                          f"R={st.get('expectancy_r')} PF={st.get('profit_factor')} → {ver}", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    # M1 vs M5 side-by-side for comparable variants
    side = []
    for _, r in df.iterrows():
        side.append(r)
    # comparison table: pivot by entry_tf tag in variant name
    df["tf"] = df["variant"].str.extract(r"_(M1|M5)_")[0]
    cmp = df[(df["cost"] == "strict")].sort_values(["verdict", "OOS_R"], ascending=[True, False])
    keep = df[df.verdict.isin(["KEEP", "MAYBE"])].sort_values(["verdict", "OOS_R"], ascending=[True, False])
    base = df[df.variant.str.contains("course_scalp_M5_rr1.5_brk_p3", regex=False) & (df.cost == "strict") & (df.cap == 5.0)]
    lines = ["# NDS Schematic + M1/M5", "",
             "## New schematic rules",
             "- ND zone 78–96% of recent range (vs course 86.4%)",
             "- Level 88% TP (`nd88`); SMI break; equal-top; brk_rally12=brk_pull",
             "- Hook-under-hook / hook-beside-hook noted as discretionary→filters smi/eq",
             "",
             "## KEEP/MAYBE"]
    for _, r in keep.iterrows():
        lines.append(
            f"- **{r['verdict']}** `{r['variant']}` @{r['cap']}/{r['cost']}: "
            f"n={int(r['OOS_n'])} WR={r['OOS_WR']} R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} "
            f"DD={r['OOS_DD']} tpd={r['tpd']} WF={r['WF+']} MC={r['MC_pass05']} "
            f"cost_share={r['cost_share_med']}"
        )
    lines += ["", "## M1 vs M5 (strict, best per TF)", ""]
    for tf in ("M5", "M1"):
        sub = df[(df.tf == tf) & (df.cost == "strict")].sort_values("OOS_R", ascending=False).head(5)
        lines.append(f"### {tf}")
        for _, r in sub.iterrows():
            lines.append(
                f"- `{r['variant']}` @{r['cap']}: n={int(r['OOS_n'])} WR={r['OOS_WR']} "
                f"R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} tpd={r['tpd']} "
                f"medSL={r['med_sl']} cost/R={r['cost_share_med']} → {r['verdict']}"
            )
    lines += ["", "## vs prior scalp_M5_rr1.5_brk_p3 @5"]
    if len(base):
        b = base.iloc[0]
        lines.append(f"baseline OOS n={b['OOS_n']} R={b['OOS_R']} PF={b['OOS_PF']} → {b['verdict']}")
    (OUT / "REPORT.md").write_text("\n".join(lines))
    (OUT / "summary.json").write_text(json.dumps({
        "keep_maybe": keep.to_dict(orient="records"),
        "n_rows": len(df),
    }, indent=2, default=str))
    print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
