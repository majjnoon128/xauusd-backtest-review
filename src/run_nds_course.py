#!/usr/bin/env python3
"""Backtest NDS Course 123Flag — audited protocol. Writes ONLY to results/nds_course/."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "nds_course"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order, SPREAD, SLIPPAGE
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from
from sl_analysis import classify_losses, summarize_causes

CAPS = (5.0, 7.5, 8.0)
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")
COST_ROWS = (("strict", 0.35, 0.10), ("cheap", 0.25, 0.05))


def risk_pct(cap): return cap / 1000.0


def buy_sell_split(tr):
    if tr is None or len(tr) == 0:
        return {"buy_n": 0, "sell_n": 0, "buy_pct": None, "sell_wr": None, "buy_wr": None}
    b = tr[tr["side"] == "long"]; s = tr[tr["side"] == "short"]
    def wr(x):
        return float((x["r_multiple"] > 0).mean()) if len(x) else None
    return {"buy_n": int(len(b)), "sell_n": int(len(s)),
            "buy_pct": float(len(b) / len(tr)), "buy_wr": wr(b), "sell_wr": wr(s)}


def zero_day_pct(tr, oos_idx):
    days = [d for d in pd.DatetimeIndex(oos_idx.normalize().unique())
            if int(getattr(d, "day_of_week", d.dayofweek)) < 5]
    if not days:
        return 100.0
    traded = set(tr["day"].astype(str)) if tr is not None and len(tr) else set()
    return 100.0 * sum(1 for d in days if str(d.date()) not in traded) / len(days)


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
        tr, st, _ = sim(m1, orders, variant, cap, spread, slip,
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
            if j >= len(m1) - 5:
                continue
            jj = int(rng.integers(max(0, j - 40), min(len(m1) - 1, j + 40)))
            px = float(m1["close"].iloc[jj]); risk = abs(o.price - o.sl)
            side = o.side if rng.random() < 0.5 else ("short" if o.side == "long" else "long")
            sl, tp = ((px - risk, px + abs(o.tp - o.price)) if side == "long"
                      else (px + risk, px - abs(o.tp - o.price)))
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, o.kind, px, sl, tp,
                            "RAND", o.variant, {}, 30))
        _, st = simulate(m1, ro, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    out["pass"] = bool(
        out["base_n"] >= 15 and out["base_pf"] >= 1.05
        and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
        and out.get("shift15_pf", 0) > 0.3
    )
    return out


def build(m1, dxy):
    pools = {}
    styles = ("day", "scalp")
    tfs = ("M5", "M1")
    tps = ("rr1.5", "rr2.0", "sym", "nd864", "rr0.5")
    confirms = ("brk_pull", "brk_p3")
    # keep grid manageable: M1 only with day+brk_pull and a few TPs
    combos = []
    for style, tf, tp, conf, ma in product(styles, tfs, tps, confirms, (1.0, 0.8)):
        if tf == "M1" and (style != "day" or conf != "brk_pull" or tp not in ("rr1.5", "rr2.0", "nd864") or ma != 1.0):
            continue
        if style == "scalp" and tp == "rr0.5":
            continue
        if ma == 0.8 and (tp not in ("rr1.5", "nd864") or conf != "brk_pull"):
            continue
        combos.append((style, tf, tp, conf, ma))
    print(f"combos={len(combos)}", flush=True)
    base = []
    for style, tf, tp, conf, ma in combos:
        print(f"  gen {style} {tf} {tp} {conf} a{ma}", flush=True)
        oo = generate_nds_course(m1, dxy, False, False, style, tf, tp, conf, ma, 3)
        print(f"    n={len(oo)} var={oo[0].variant if oo else '-'}", flush=True)
        base.extend(oo)
    pools["NDS_Course"] = base
    pools["NDS_Course_DXY"] = apply_dxy_gate(base, dxy, True)
    print("DXY", len(pools["NDS_Course_DXY"]), flush=True)
    return pools


def window_3m_probe(m1, dxy, oos_cut):
    """Probe ~3-month windows for inflated WR (tight TP / loose SL story)."""
    rows = []
    ends = [oos_cut, m1.index[-1], pd.Timestamp("2026-04-01", tz="UTC")]
    for end in ends:
        if end not in m1.index:
            j = m1.index.searchsorted(end)
            end = m1.index[min(j, len(m1) - 1)]
        start = end - pd.Timedelta(days=92)
        sub = m1[(m1.index >= start) & (m1.index < end)]
        if len(sub) < 10000:
            continue
        for tp in ("rr0.5", "rr1.5", "nd864"):
            oo = generate_nds_course(sub, dxy, False, False, "day", "M5", tp, "brk_pull", 1.0, 3)
            for cap in (5.0, 8.0, 20.0):  # 20 = essentially uncapped for WR probe
                tr, st, sk = sim(sub, oo, oo[0].variant if oo else "x", cap, 0.35, 0.10,
                                 sub.index[0], sub.index[-1] + pd.Timedelta(minutes=1), cb=False)
                rows.append({
                    "window_end": str(end.date()), "tp": tp, "cap": cap,
                    "n": st["n_trades"], "wr": st.get("win_rate"),
                    "R": st.get("expectancy_r"), "PF": st.get("profit_factor"),
                    "skipped": sk.get("n_skipped", sk) if isinstance(sk, dict) else sk,
                })
    pd.DataFrame(rows).to_csv(OUT / "probe_3m.csv", index=False)
    return rows


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    print("cut", oos_cut, "bars", len(m1), flush=True)
    pools = build(m1, dxy)

    print("3m probe", flush=True)
    probe = window_3m_probe(m1, dxy, oos_cut)
    print("probe rows", len(probe), flush=True)

    rows = []; best_overall = None
    for name, orders in pools.items():
        variants = sorted({o.variant for o in orders})
        print(f"SCAN {name} nvar={len(variants)} nord={len(orders)}", flush=True)
        scored = []
        for v in variants:
            tr, st, sk = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
            if st["n_trades"] >= 8:
                scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st, sk))
        scored.sort(reverse=True)
        top = scored[:6]
        if not top:
            for v in variants[:3]:
                tr, st, sk = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
                top.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st, sk))
        for exp, pf, n, v, st_is, sk in top:
            for cap in CAPS:
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 5.0:
                        continue
                    tr_oos, st_oos, sk_oos = sim(
                        m1, orders, v, cap, spread, slip, oos_cut,
                        m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, wf_rs = wf(m1, orders, v, cap, spread, slip)
                    mc_pass = None
                    if st_oos["n_trades"] >= 15:
                        mc = run_mc(tr_oos["r_multiple"].values, risk_pcts=(0.005,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", mc.iloc[0].get("pass_rate", np.nan)))
                            mc.to_csv(OUT / f"mc_{name}_{v}_cap{cap}_{cost_name}.csv", index=False)
                    ver, reason = verdict_from(st_oos, wf_frac, mc_pass)
                    san = sanity(m1, orders, v, cap, oos_cut) if st_oos["n_trades"] >= 15 else {}
                    split = buy_sell_split(tr_oos)
                    tpd = st_oos.get("trades_per_day")
                    if tpd is None and tr_oos is not None and len(tr_oos):
                        ndays = max(1, (tr_oos["exit_time"].max() - tr_oos["entry_time"].min()).days)
                        tpd = len(tr_oos) / max(1, ndays)
                    zday = zero_day_pct(tr_oos, m1[m1.index >= oos_cut].index)
                    row = {
                        "pool": name, "variant": v, "cap": cap, "cost": cost_name,
                        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                        "OOS_n": st_oos["n_trades"], "OOS_WR": st_oos.get("win_rate"),
                        "OOS_R": st_oos.get("expectancy_r"), "OOS_PF": st_oos.get("profit_factor"),
                        "OOS_DD": st_oos.get("max_dd_pct"), "tpd": tpd, "zero_day_pct": zday,
                        "WF+": wf_frac, "WF_rs": str(wf_rs), "MC_pass05": mc_pass,
                        "verdict": ver, "reason": reason, "sanity": json.dumps(san),
                        **split,
                        "skips_oos": sk_oos.get("n_skipped", sk_oos) if isinstance(sk_oos, dict) else sk_oos,
                    }
                    rows.append(row)
                    if tr_oos is not None and len(tr_oos):
                        tr_oos.to_csv(OUT / f"trades_{name}_{v}_cap{cap}_{cost_name}_OOS.csv", index=False)
                        if st_oos["n_trades"] >= 10:
                            causes = classify_losses(tr_oos, m1, dxy)
                            summarize_causes(causes).to_csv(
                                OUT / f"sl_causes_{name}_{v}_cap{cap}.csv", index=False)
                    print(f"  {name} {v} cap{cap} {cost_name}: OOS n={st_oos['n_trades']} "
                          f"WR={st_oos.get('win_rate')} R={st_oos.get('expectancy_r')} "
                          f"PF={st_oos.get('profit_factor')} → {ver}", flush=True)
                    key = (ver, st_oos.get("expectancy_r") or -99, st_oos.get("n_trades") or 0)
                    if best_overall is None or key > best_overall[0]:
                        best_overall = (key, row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    # pick best per pool
    keep = df[df["verdict"].isin(["KEEP", "MAYBE"])].sort_values(["verdict", "OOS_R"], ascending=[True, False])
    best = df.sort_values(["OOS_R", "OOS_n"], ascending=[False, False]).head(15)
    summary = {
        "best_rows": best.to_dict(orient="records"),
        "keep_maybe": keep.to_dict(orient="records"),
        "n_rows": len(df),
        "probe_3m_top": sorted(probe, key=lambda r: (-(r.get("wr") or 0), -(r.get("n") or 0)))[:10],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    # Persian short report
    lines = ["# NDS Course 123Flag — نتایج", ""]
    if best_overall:
        r = best_overall[1]
        lines += [
            f"**بهترین واریانت:** `{r['pool']}` / `{r['variant']}` cap={r['cap']} {r['cost']}",
            f"OOS n={r['OOS_n']} WR={r['OOS_WR']} R={r['OOS_R']} PF={r['OOS_PF']} DD={r['OOS_DD']} "
            f"tpd={r['tpd']} WF+={r['WF+']} MC={r['MC_pass05']} → **{r['verdict']}**",
            f"دلیل: {r['reason']}",
            f"buy/sell: {r['buy_n']}/{r['sell_n']}",
            "",
        ]
    lines.append("## Top 10 by OOS R")
    for _, r in best.head(10).iterrows():
        lines.append(
            f"- {r['pool']} `{r['variant']}` @{r['cap']}/{r['cost']}: "
            f"n={r['OOS_n']} WR={r['OOS_WR']} R={r['OOS_R']} PF={r['OOS_PF']} → {r['verdict']}"
        )
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
