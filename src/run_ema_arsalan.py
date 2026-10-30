#!/usr/bin/env python3
"""Arsalan EMA audited backtest → results/ema_arsalan/.
Caps $5/$8, ±DXY, IS choose / OOS judge. min_hold=2 M1 bars (prop).
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "ema_arsalan"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "pools_cache.pkl"

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order
from monte_carlo import run_mc
from strategies.ema_arsalan import generate_ema_arsalan_family
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
            if st["expectancy_r"] > 0: pos += 1
    return (pos / valid if valid else 0.0), rs


def sanity(m1, orders, variant, cap, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side) <= cap + 1e-9]
    _, st0 = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes,
                    min_hold_minutes=o.min_hold_minutes)
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
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, "market", px, sl, tp,
                            "RAND", o.variant, {}, 30, min_hold_minutes=2))
        _, st = simulate(m1, ro, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    out["pass"] = bool(out["base_n"] >= 15 and out["base_pf"] >= 1.05
                       and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
                       and out.get("shift15_pf", 0) > 0.3)
    return out


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "OOS trading days", n_tdays, flush=True)
    print("NOTE: min_hold_minutes=2 — SL/TP deferred until ≥2 M1 bars after fill.", flush=True)

    if CACHE.exists():
        print("LOAD cache", flush=True)
        with open(CACHE, "rb") as f:
            pools = pickle.load(f)
    else:
        pools = generate_ema_arsalan_family(m1)
        with open(CACHE, "wb") as f:
            pickle.dump(pools, f, protocol=pickle.HIGHEST_PROTOCOL)
        print("CACHED", len(pools), flush=True)

    scored = []
    for v, oo in pools.items():
        _, st, _ = sim(m1, oo, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
        if st["n_trades"] >= 8:
            scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v))
    scored.sort(reverse=True)
    print(f"IS ranked {len(scored)}", flush=True)
    for r, pf, n, v in scored[:8]:
        print(f"  {v}: n={n} R={r:.3f} PF={pf:.2f}", flush=True)
    if not scored:
        for v, oo in pools.items():
            _, st, _ = sim(m1, oo, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
            scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v))
        scored.sort(reverse=True)

    best_v = scored[0][3]
    # report: best overall + best mode1 + best mode2
    best_m1 = next((v for _,_,_,v in scored if "m1sharp" in v), best_v)
    best_m2 = next((v for _,_,_,v in scored if "m2rev" in v), best_v)
    report_variants = []
    for v in (best_v, best_m1, best_m2):
        if v not in report_variants:
            report_variants.append(v)
    for _,_,_,v in scored[:5]:
        if v not in report_variants:
            report_variants.append(v)

    chosen = {"best_is": best_v, "best_mode1": best_m1, "best_mode2": best_m2,
              "top5": [{"v": v, "is_r": r, "is_pf": pf, "is_n": n} for r, pf, n, v in scored[:5]],
              "min_hold_policy": "defer SL/TP until >=2 M1 bars after fill; if SL/TP traversed during hold, exit at that level on first eligible bar (SL priority)"}

    rows = []
    for v in report_variants:
        base = pools[v]
        for use_dxy in (False, True):
            orders = apply_dxy_gate(base, dxy, use_dxy) if use_dxy else list(base)
            for cap in CAPS:
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 8.0:
                        continue
                    tr, st, sk = sim(m1, orders, v, cap, spread, slip, oos_cut,
                                     m1.index[-1] + pd.Timedelta(minutes=1))
                    _, st_is, _ = sim(m1, orders, v, cap, spread, slip, m1.index[0], oos_cut)
                    wf_frac, wf_rs = wf(m1, orders, v, cap, spread, slip)
                    mc_pass = None
                    if st["n_trades"] >= 15 and tr is not None and len(tr):
                        mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.005,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                    ver, reason = verdict_from(st, wf_frac, mc_pass)
                    san = sanity(m1, orders, v, cap, oos_cut) if st["n_trades"] >= 15 else {}
                    tpd = tpd_true(st["n_trades"], n_tdays)
                    rows.append({
                        "family": "ArsalanEMA", "variant": v, "is_best": v == best_v,
                        "dxy": use_dxy, "cap": cap, "cost": cost_name,
                        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                        "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                        "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                        "OOS_DD": st.get("max_dd_pct"),
                        "tpd": tpd, "n_tdays": n_tdays,
                        "WF+": wf_frac, "WF_rs": str(wf_rs), "MC_pass05": mc_pass,
                        "verdict": ver, "reason": reason, "sanity_pass": san.get("pass"),
                        "skip_n": sk.get("n_skipped"), "skip_pct": sk.get("skip_pct"),
                    })
                    tag = f"{v}_{'DXY' if use_dxy else 'noDXY'}_cap{cap}_{cost_name}"
                    if tr is not None and len(tr):
                        tr.to_csv(OUT / f"trades_{tag}.csv", index=False)
                    print(f"  {v[-55:]} dxy={use_dxy} @{cap}/{cost_name}: n={st['n_trades']} "
                          f"tpd={tpd:.3f} R={st.get('expectancy_r')} → {ver}", flush=True)

    board = []
    for r, pf, n, v in scored[:25]:
        oo = pools[v]
        _, st, _ = sim(m1, oo, v, 8.0, 0.35, 0.10, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
        board.append({"variant": v, "IS_n": n, "IS_R": r, "IS_PF": pf,
                      "OOS_n": st["n_trades"], "OOS_R": st.get("expectancy_r"),
                      "OOS_PF": st.get("profit_factor"), "tpd": tpd_true(st["n_trades"], n_tdays)})
    pd.DataFrame(board).to_csv(OUT / "is_leaderboard_oos.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    (OUT / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    deltas = []
    for (v, cap, cost), g in df.groupby(["variant", "cap", "cost"]):
        a = g[g.dxy == False]; b = g[g.dxy == True]
        if len(a) and len(b):
            a, b = a.iloc[0], b.iloc[0]
            deltas.append({
                "variant": v, "cap": cap, "cost": cost,
                "n0": a["OOS_n"], "n1": b["OOS_n"], "dn": int(b["OOS_n"] - a["OOS_n"]),
                "R0": a["OOS_R"], "R1": b["OOS_R"], "dR": (b["OOS_R"] or 0) - (a["OOS_R"] or 0),
                "PF0": a["OOS_PF"], "PF1": b["OOS_PF"], "dPF": (b["OOS_PF"] or 0) - (a["OOS_PF"] or 0),
                "ver0": a["verdict"], "ver1": b["verdict"],
            })
    pd.DataFrame(deltas).to_csv(OUT / "dxy_delta.csv", index=False)

    lines = [
        f"# Arsalan EMA (OOS trading days={n_tdays})",
        f"IS-best: `{best_v}` | mode1: `{best_m1}` | mode2: `{best_m2}`",
        "Prop min-hold: defer SL/TP until ≥2 M1 bars after fill.",
        "",
        "| variant | cap | DXY | n | tpd | WR | R | PF | DD% | WF+ | MC | verdict | best |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|:---:|",
    ]
    focus = df[df.cost == "strict"].sort_values(["is_best", "variant", "cap", "dxy"], ascending=[False, True, True, True])
    for _, r in focus.iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        mc = f"{r['MC_pass05']:.2f}" if pd.notna(r["MC_pass05"]) else "-"
        lines.append(
            f"| `{r['variant'][-50:]}` | {r['cap']} | {int(r['dxy'])} | {int(r['OOS_n'])} | "
            f"{r['tpd']:.3f} | {wr} | {r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | {r['OOS_DD']:.1f} | "
            f"{r['WF+']:.0%} | {mc} | **{r['verdict']}** | {int(r['is_best'])} |"
        )
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
