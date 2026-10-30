#!/usr/bin/env python3
"""Attribution: where Poursamadi (+other) setups fail. Short CSV/JSON to results/attribution/."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import simulate, sl_distance_price, count_sl_cap_skips, SPREAD, SLIPPAGE
from monte_carlo import run_mc
from strategies import (
    generate_nds_fib, generate_idris, generate_sp2l, generate_pro_btb,
    generate_micromap, generate_amd_po3_ifvg,
)
from strategies.common import apply_htf_gate
from indicators import ema, resample_ohlc
from run_final_batch import load, apply_confirmations, filter_cap, period_orders

OUT = ROOT / "results" / "attribution"
OUT.mkdir(parents=True, exist_ok=True)

CAPS = [5.0, 7.5, 8.0, 9.0, None]  # None = uncapped
COST_MODES = {
    "strict": (0.35, 0.10),   # current
    "cheap": (0.20, 0.05),    # ~0.25 total
    "gross": (0.0, 0.0),      # raw edge
}


def risk_pct_for(cap):
    if cap is None:
        return 0.005  # still size at 0.5% of balance using actual dist
    return min(cap / 1000.0, 0.03)  # $8 → 0.8%, capped by SGB 3%


def eval_oos(m1, orders, cap, spread, slip, flags=None, dxy=None, variant=None, do_mc=False):
    cut = m1.index[int(len(m1) * 0.70)]
    oo = list(orders)
    if variant:
        oo = [o for o in oo if o.variant == variant]
    if flags:
        oo = apply_confirmations(oo, m1, dxy, flags)
    oo = period_orders(oo, cut, m1.index[-1] + pd.Timedelta(minutes=1))
    skip = count_sl_cap_skips(oo, cap if cap is not None else 1e9, spread)
    if cap is not None:
        oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(
        m1, oo, risk_pct=risk_pct_for(cap if cap is not None else 5.0),
        max_sl_dist=cap, use_circuit_breaker=True,
        spread=spread, slip=slip,
    )
    row = {
        "n": st["n_trades"], "wr": st["win_rate"], "r": st["expectancy_r"],
        "pf": st["profit_factor"], "dd": st["max_dd_pct"], "tpd": st["trades_per_day"],
        "net": st["net_pnl"], "skip_pct": skip["skip_pct"], "n_orders_oos": skip["n_orders"],
        "n_kept_orders": skip["n_kept"],
    }
    if do_mc and tr is not None and len(tr) >= 12 and st["profit_factor"] >= 1.05:
        risk = risk_pct_for(cap if cap is not None else 5.0)
        mc = run_mc(tr["r_multiple"].values, n_sims=2000, risk_pcts=(risk,))
        row["mc_pass"] = float(mc.iloc[0]["pass_prob"]) if len(mc) else None
    else:
        row["mc_pass"] = None
    return row, tr


def wf_pos(m1, orders, cap, spread, slip, flags, dxy, variant):
    n = len(m1); warm = int(n * 0.40); rest = n - warm; fold = rest // 4
    pos = 0; valid = 0
    for k in range(4):
        o0 = warm + k * fold
        o1 = warm + (k + 1) * fold if k < 3 else n
        oos = m1.iloc[o0:o1]
        oo = [o for o in orders if o.variant == variant] if variant else list(orders)
        if flags:
            oo = apply_confirmations(oo, m1, dxy, flags)
        oo = period_orders(oo, oos.index[0], oos.index[-1] + pd.Timedelta(minutes=1))
        if cap is not None:
            oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
        tr, st = simulate(m1, oo, risk_pct=risk_pct_for(cap if cap else 5), max_sl_dist=cap,
                          use_circuit_breaker=True, spread=spread, slip=slip)
        if st["n_trades"] >= 3:
            valid += 1
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid) if valid else 0.0


def main():
    print("LOAD", flush=True)
    m1, dxy = load()
    rows = []
    diffs = {
        "SP2L": [
            "Official best TF: M1/M5 (we test M5/M15/H1). OK on M5.",
            "MISSING: spike must break key S/R or S/D — we have no key-level filter.",
            "MISSING: spike from channel edge — not coded.",
            "OPTIONAL: HTF trend agree — we can gate, not required in base.",
            "EXCLUDED by prop: 50% add-on (teacher uses it to improve avg entry).",
            "Session: teacher prefers NY; we allow London+NY hours.",
            "Discretionary: what counts as 'large candle' / valid P-Gap size — we use ATR thresholds.",
        ],
        "ProBTB": [
            "Official best TF: M5 and M15 — we previously only M5; now both.",
            "Level = confirmed pivot H/L — teacher means 'key S/R'; discretionary which pivots count.",
            "Breakout validity extras we added (open near level, body>=0.3ATR) — not in page text.",
            "Modes 2–6 from Amir/images; page text only shows mode 1 (limit at BE).",
            "Teacher: entry near key level → naturally small SL; $5 hard cap still kills wide gold swings.",
            "Discretionary: which breakout is 'valid', return candle quality.",
        ],
        "MicroMAP": [
            "Official TF: up to M30 — we used M5; now M5/M15/H1.",
            "CORE TEACHER FEATURE: re-entries 2 and 3 after stop (higher WR). PROP bans re-entry + 2-loss circuit → we only take ONE entry. Structural mismatch.",
            "H2/H3 confirmation are teacher's higher-WR path; we emit H2 loosely, not sequential.",
            "Microchannel detection is approximate (monotonic highs + smaller bodies).",
            "No indicator OK; discretionary spike/channel quality not fully coded.",
        ],
        "NDS_Fib": [
            "Impulse = 60% same-color bars heuristic, not clean swing.",
            "Zone 0.62-0.78 per Amir; legacy 0.786-0.86.",
            "M1 engulfing confirm — mechanical.",
        ],
        "Idris": [
            "H4 zone + M1 hidden RSI div + IB — coded; IB trigger = market at close not stop at IB extreme.",
            "Very few signals under filters.",
        ],
        "AMD_PO3_iFVG": [
            "Asian range UTC OK; manip accepts close beyond range (looser than wick sweep).",
            "iFVG mechanical approximation of ICT-style.",
        ],
    }
    (OUT / "definition_gaps.json").write_text(json.dumps(diffs, indent=2, ensure_ascii=False))

    print("GENERATE pools...", flush=True)
    pools = {}
    # Poursamadi multi-TF
    for rule, tag in [("5min", "M5"), ("15min", "M15"), ("1h", "H1")]:
        print(f"  SP2L {tag}", flush=True)
        pools[f"SP2L_{tag}"] = generate_sp2l(m1, use_htf=False, rule=rule)
        print(f"  ProBTB {tag}", flush=True)
        pools[f"ProBTB_{tag}"] = generate_pro_btb(m1, rr=2.0, rule=rule)
        print(f"  MicroMAP {tag}", flush=True)
        pools[f"MicroMAP_{tag}"] = generate_micromap(m1, rule=rule)

    print("  NDS/Idris/AMD", flush=True)
    pools["NDS_Fib"] = generate_nds_fib(m1, rr=1.5, zones=(("062_078", 0.62, 0.78),))
    pools["Idris"] = generate_idris(m1)
    pools["AMD"] = generate_amd_po3_ifvg(m1, range_mode="asian", tf="M5", entry_mode="market", tp_mode="range")

    # Prefer teacher-aligned variants
    prefer = {
        "SP2L_M5": lambda v: "_A_rr1.0" in v or "_A_rr1.5" in v,
        "SP2L_M15": lambda v: "_A_rr1.0" in v or "_A_rr1.5" in v,
        "SP2L_H1": lambda v: "_A_rr1.0" in v or "_A_rr1.5" in v,
        "ProBTB_M5": lambda v: "m5_stop_breakout" in v or "m1_limit_breakeven" in v or "m4_limit_broken" in v,
        "ProBTB_M15": lambda v: "m5_stop_breakout" in v or "m1_limit_breakeven" in v or "m4_limit_broken" in v,
        "ProBTB_H1": lambda v: "m5_stop_breakout" in v or "m1_limit_breakeven" in v or "m4_limit_broken" in v,
        "MicroMAP_M5": lambda v: "H1_rr" in v or "IB_rr" in v or "H2_rr" in v,
        "MicroMAP_M15": lambda v: "H1_rr" in v or "IB_rr" in v or "H2_rr" in v,
        "MicroMAP_H1": lambda v: "H1_rr" in v or "IB_rr" in v or "H2_rr" in v,
        "NDS_Fib": lambda v: True,
        "Idris": lambda v: True,
        "AMD": lambda v: True,
    }

    # Filters to try (few)
    filter_sets = [
        ("baseline", {}),
        ("htf", {"htf": True}),
        ("htf+not_ext", {"htf": True, "not_extended": True}),
    ]

    print("MATRIX...", flush=True)
    for name, orders in pools.items():
        variants = sorted({o.variant for o in orders})
        # pick up to 3 preferred variants by IS gross expectancy quickly
        cut = m1.index[int(len(m1) * 0.70)]
        cand = []
        pref_fn = prefer.get(name, lambda v: True)
        for v in variants:
            if not pref_fn(v):
                continue
            vo = [o for o in orders if o.variant == v and o.arm_time < cut]
            if len(vo) < 8:
                continue
            tr, st = simulate(m1, filter_cap(vo, 9.0) if True else vo,
                              risk_pct=0.009, max_sl_dist=9.0, use_circuit_breaker=False,
                              spread=0.0, slip=0.0)
            cand.append((st["expectancy_r"], st["n_trades"], v))
        cand.sort(reverse=True)
        chosen = [c[2] for c in cand[:2]] if cand else (variants[:2] if variants else [])
        if not chosen and variants:
            chosen = variants[:1]
        print(f"  {name} chosen={chosen}", flush=True)

        for v, (fname, flags), (cname, (sp, sl)), cap in product(
            chosen, filter_sets, COST_MODES.items(), CAPS
        ):
            # skip some wasteful combos
            if cname == "gross" and cap not in (5.0, 9.0, None):
                continue
            if cname == "cheap" and cap not in (5.0, 8.0, 9.0, None):
                continue
            do_mc = (cname == "strict" and cap in (8.0, 9.0, None) and "M5" in name) or (
                cname == "strict" and cap == 9.0
            )
            row, _ = eval_oos(m1, orders, cap, sp, sl, flags, dxy, v, do_mc=do_mc)
            row.update({
                "setup": name, "variant": v, "filter": fname, "cost": cname,
                "cap": cap if cap is not None else "uncapped",
                "spread": sp, "slip": sl,
            })
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "matrix.csv", index=False)
    print(f"wrote matrix {len(df)} rows", flush=True)

    # Compact summary: best OOS PF per setup×TF under strict@$8/@9/uncapped
    summary = []
    for setup in sorted(df["setup"].unique()):
        for cap in [5.0, 8.0, 9.0, "uncapped"]:
            for cost in ["gross", "cheap", "strict"]:
                sub = df[(df["setup"] == setup) & (df["cap"] == cap) & (df["cost"] == cost)]
                if sub.empty:
                    continue
                # best by oos pf with n>=8 else best n
                sub2 = sub[sub["n"] >= 8]
                best = sub2.sort_values(["pf", "r", "n"], ascending=False).iloc[0] if len(sub2) else sub.sort_values("n", ascending=False).iloc[0]
                summary.append({
                    "setup": setup, "cap": cap, "cost": cost,
                    "variant": best["variant"], "filter": best["filter"],
                    "n": int(best["n"]), "wr": round(float(best["wr"]), 3),
                    "r": round(float(best["r"]), 3), "pf": round(float(best["pf"]), 3),
                    "dd": round(float(best["dd"]), 2), "tpd": round(float(best["tpd"]), 2),
                    "skip_pct": round(float(best["skip_pct"]), 1),
                    "mc_pass": best.get("mc_pass"),
                })
    sdf = pd.DataFrame(summary)
    sdf.to_csv(OUT / "best_per_cell.csv", index=False)

    # Attribution deltas for Poursamadi M5 mode5 / A rr1 / H1
    attr = {}
    for setup, variant_substr, flags in [
        ("ProBTB_M5", "m5_stop_breakout", {"htf": True, "not_extended": True}),
        ("ProBTB_M15", "m5_stop_breakout", {"htf": True}),
        ("SP2L_M5", "_A_rr1.0", {"htf": True}),
        ("SP2L_M15", "_A_rr1.0", {"htf": True}),
        ("MicroMAP_M5", "H1_rr", {}),
        ("MicroMAP_M15", "H1_rr", {}),
        ("NDS_Fib", "062_078", {"htf": True}),
        ("AMD", "asian_M5_market_range", {}),
        ("Idris", "h4_rsi", {}),
    ]:
        if setup not in pools:
            continue
        orders = pools[setup]
        variants = [v for v in {o.variant for o in orders} if variant_substr in v]
        if not variants:
            continue
        v = variants[0]
        cells = {}
        for label, cap, sp, sl in [
            ("strict_cap5", 5.0, 0.35, 0.10),
            ("strict_cap8", 8.0, 0.35, 0.10),
            ("strict_cap9", 9.0, 0.35, 0.10),
            ("strict_uncap", None, 0.35, 0.10),
            ("cheap_cap9", 9.0, 0.20, 0.05),
            ("gross_cap9", 9.0, 0.0, 0.0),
            ("gross_uncap", None, 0.0, 0.0),
        ]:
            r, _ = eval_oos(m1, orders, cap, sp, sl, flags, dxy, v, do_mc=(label.startswith("strict_cap") and cap in (8.0, 9.0)))
            cells[label] = {k: r[k] for k in ("n", "wr", "r", "pf", "dd", "skip_pct", "mc_pass", "tpd")}
        # reasons
        g = cells["gross_uncap"]["pf"]
        s5 = cells["strict_cap5"]["pf"]
        s9 = cells["strict_cap9"]["pf"]
        reason = []
        if g < 1.0:
            reason.append("no_raw_edge_even_gross_uncapped")
        else:
            reason.append("raw_edge_exists_gross")
        if cells["strict_uncap"]["pf"] < 1.0 <= g:
            reason.append("costs_kill_edge")
        if cells["strict_cap5"]["skip_pct"] > 50:
            reason.append("sl_cap5_removes_>50pct_signals")
        if cells["strict_cap9"]["pf"] > cells["strict_cap5"]["pf"] + 0.15:
            reason.append("higher_cap_helps")
        if cells["strict_cap9"]["pf"] < 1.05 and cells["gross_cap9"]["pf"] >= 1.1:
            reason.append("definition_or_costs_not_just_cap")
        attr[setup] = {"variant": v, "flags": flags, "cells": cells, "drivers": reason}

    (OUT / "attribution.json").write_text(json.dumps(attr, indent=2, default=str))

    # Honest verdicts
    verdicts = []
    for setup, info in attr.items():
        c = info["cells"]
        drivers = info["drivers"]
        # pick best strict among cap8/9/uncap
        best_label = max(
            ["strict_cap8", "strict_cap9", "strict_uncap"],
            key=lambda L: (c[L]["pf"] if c[L]["n"] >= 10 else -1, c[L]["n"])
        )
        b = c[best_label]
        if b["n"] < 15 or b["pf"] < 1.05 or b["r"] <= 0:
            verd = "DROP"
        elif b["pf"] >= 1.2 and b["r"] >= 0.15:
            verd = "KEEP_CANDIDATE"
        else:
            verd = "MAYBE"
        # primary failure reason
        if "no_raw_edge_even_gross_uncapped" in drivers:
            primary = "تعریف مکانیکی/زمینه بازار: حتی بدون هزینه و بدون کپ، لبهٔ خام نیست"
        elif "costs_kill_edge" in drivers and "sl_cap5_removes_>50pct_signals" in drivers:
            primary = "ترکیب هزینهٔ سخت + کپ SL حساب ۱k؛ ستاپ برای SL تنگ‌تر/اسپرد کمتر طراحی شده"
        elif "sl_cap5_removes_>50pct_signals" in drivers:
            primary = "کپ فاصله SL روی حساب ۱k بیشتر سیگنال‌ها را حذف یا ناقص می‌کند"
        elif "costs_kill_edge" in drivers:
            primary = "لبهٔ خام با اسپرد+اسلیپ سخت از بین می‌رود"
        else:
            primary = "لبه OOS پایدار زیر قوانین SGB دیده نشد؛ احتمالاً عناصر اختیاری معلم کد نشده"
        if "MicroMAP" in setup:
            primary = "بازورود ۲ و ۳ (هستهٔ وین‌ریت معلم) با قانون پراپ ممنوع است — بزرگ‌ترین شکاف تعریف"
        verdicts.append({
            "setup": setup, "verdict": verd, "best_cell": best_label,
            "best_n": b["n"], "best_pf": b["pf"], "best_r": b["r"], "best_wr": b["wr"],
            "mc": b.get("mc_pass"), "gross_uncap_pf": c["gross_uncap"]["pf"],
            "strict_cap5_pf": c["strict_cap5"]["pf"], "strict_cap9_pf": c["strict_cap9"]["pf"],
            "cap5_skip_pct": c["strict_cap5"]["skip_pct"], "primary_reason": primary,
            "drivers": drivers,
        })

    vdf = pd.DataFrame(verdicts)
    vdf.to_csv(OUT / "verdicts.csv", index=False)
    (OUT / "verdicts.json").write_text(json.dumps(verdicts, indent=2, ensure_ascii=False, default=str))

    # Print short
    print("\n=== BEST CELLS (strict) ===", flush=True)
    for _, r in sdf[(sdf["cost"] == "strict") & (sdf["cap"].isin([5.0, 8.0, 9.0, "uncapped"]))].iterrows():
        if r["n"] >= 5:
            print(f"{r['setup']:14} cap={r['cap']!s:>8} n={r['n']:4} WR={r['wr']:.0%} PF={r['pf']:.2f} R={r['r']:+.2f} skip={r['skip_pct']:.0f}% mc={r['mc_pass']}", flush=True)
    print("\n=== VERDICTS ===", flush=True)
    for v in verdicts:
        print(f"{v['setup']:14} {v['verdict']:16} grossU={v['gross_uncap_pf']:.2f} s5={v['strict_cap5_pf']:.2f} s9={v['strict_cap9_pf']:.2f} | {v['primary_reason'][:80]}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
