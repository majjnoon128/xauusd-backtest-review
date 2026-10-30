#!/usr/bin/env python3
"""Rerun affected strategies after code-audit fixes. Short outputs to results/audit_code/."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import simulate, sl_distance_price, SPREAD, SLIPPAGE
from monte_carlo import run_mc
from strategies import (
    generate_nds_fib, generate_idris, generate_sp2l, generate_pro_btb,
    generate_micromap, generate_amd_po3_ifvg,
)
from run_final_batch import (
    load, apply_confirmations, filter_cap, period_orders, eval_set,
    pick_best_filter_is, walk_forward_folds, verdict_from, CANDIDATE_FILTERS, CAPS, RISK_PCT,
)

OUT = ROOT / "results" / "audit_code"
OUT.mkdir(parents=True, exist_ok=True)


def wf_stats(orders, m1, dxy, flags, variant, cap):
    folds = walk_forward_folds(m1, 4)
    rs = []
    for is_df, oos_df, name in folds:
        # filter on full m1 context but evaluate OOS window only
        vo = [o for o in orders if o.variant == variant]
        fo = apply_confirmations(vo, m1, dxy, flags)
        fo = period_orders(fo, oos_df.index[0], oos_df.index[-1] + pd.Timedelta(minutes=1))
        fo = filter_cap(fo, cap)
        tr, st = simulate(m1, fo, risk_pct=RISK_PCT[cap], max_sl_dist=cap, use_circuit_breaker=True)
        rs.append(st.get("expectancy_r", 0) if st["n_trades"] else None)
    valid = [x for x in rs if x is not None]
    pos = sum(1 for x in valid if x > 0) / len(valid) if valid else 0
    return pos, rs


def run_one(name, orders, m1, dxy, variants, cap):
    cut = m1.index[int(len(m1) * 0.70)]
    m1_is = m1[m1.index < cut]
    best = pick_best_filter_is(orders, m1_is, dxy, cap, variants)
    if best is None:
        return {"strategy": name, "cap": cap, "verdict": "DROP", "reason": "no IS candidate"}
    score, variant, fname, flags, is_st = best
    vo = [o for o in orders if o.variant == variant]
    fo = apply_confirmations(vo, m1, dxy, flags)
    # OOS
    oos_o = period_orders(fo, cut, m1.index[-1] + pd.Timedelta(minutes=1))
    oos_o = filter_cap(oos_o, cap)
    tr, oos_st = simulate(m1, oos_o, risk_pct=RISK_PCT[cap], max_sl_dist=cap, use_circuit_breaker=True)
    wf_pos, wf_rs = wf_stats(orders, m1, dxy, flags, variant, cap)
    mc_pass = None
    if tr is not None and len(tr) >= 15 and oos_st["profit_factor"] >= 1.1:
        mc = run_mc(tr["r_multiple"].values, n_sims=3000, risk_pcts=(0.005,))
        if mc is not None and len(mc):
            mc_pass = float(mc.iloc[0]["pass_prob"])
            mc.to_csv(OUT / f"mc_{name}_cap{cap}.csv", index=False)
    verd, reason = verdict_from(oos_st, wf_pos, mc_pass)
    row = {
        "strategy": name, "cap": cap, "variant": variant, "filter": fname, "flags": flags,
        "is_n": is_st["n_trades"], "is_r": is_st["expectancy_r"], "is_pf": is_st["profit_factor"],
        "oos_n": oos_st["n_trades"], "oos_wr": oos_st["win_rate"], "oos_r": oos_st["expectancy_r"],
        "oos_pf": oos_st["profit_factor"], "oos_dd": oos_st["max_dd_pct"], "oos_tpd": oos_st["trades_per_day"],
        "wf_pos_frac": wf_pos, "wf_rs": wf_rs, "mc_pass_0.5pct": mc_pass,
        "verdict": verd, "reason": reason,
        "same_m1_pct": oos_st.get("same_m1_pct"),
    }
    if tr is not None and len(tr):
        tr.to_csv(OUT / f"trades_{name}_cap{cap}_OOS.csv", index=False)
    return row


def gap_through_recheck(m1, orders):
    from engine import _can_fill_stop, _fill_price
    times = m1.index
    high, low, open_ = m1["high"].values, m1["low"].values, m1["open"].values
    n = len(times)
    gap = fill = 0
    adv = []
    for o in orders[:6000]:
        if o.kind != "stop":
            continue
        j = times.searchsorted(o.arm_time, side="left")
        expire = times.searchsorted(o.arm_time + pd.Timedelta(minutes=o.expire_minutes), side="right") - 1
        expire = min(max(expire, j), n - 1)
        for i in range(j, expire + 1):
            if not _can_fill_stop(o.side, o.price, low[i], high[i]):
                continue
            fill += 1
            coded = _fill_price(o.side, "stop", o.price, open_[i], SPREAD, SLIPPAGE)
            if o.side == "long":
                old = o.price + SPREAD + SLIPPAGE
                if open_[i] > o.price:
                    gap += 1
                    adv.append(coded - old)  # should be >=0 (worse = higher for long)
            else:
                old = o.price - SPREAD - SLIPPAGE
                if open_[i] < o.price:
                    gap += 1
                    adv.append(old - coded)  # worse = lower fill for short → old-coded >=0
            break
    return {"fills": fill, "gaps": gap, "gap_pct": round(100*gap/max(fill,1),2),
            "mean_extra_adverse": float(np.mean(adv)) if adv else 0}


def main():
    print("LOAD", flush=True)
    m1, dxy = load()
    rows = []

    print("GEN NDS...", flush=True)
    nds = generate_nds_fib(m1, rr=1.5) + generate_nds_fib(m1, rr=2.0)
    nds_v = sorted({o.variant for o in nds})
    for cap in CAPS:
        rows.append(run_one("NDS_Fib", nds, m1, dxy, nds_v, cap))
        print(" ", rows[-1]["verdict"], rows[-1]["oos_n"], rows[-1]["oos_pf"], flush=True)

    print("GEN Idris...", flush=True)
    idr = generate_idris(m1)
    for cap in CAPS:
        rows.append(run_one("Idris", idr, m1, dxy, sorted({o.variant for o in idr}), cap))
        print(" ", rows[-1]["verdict"], rows[-1]["oos_n"], rows[-1]["oos_pf"], flush=True)

    print("GEN SP2L (fixed FVG)...", flush=True)
    sp = generate_sp2l(m1, use_htf=True)
    for cap in CAPS:
        rows.append(run_one("SP2L", sp, m1, dxy, sorted({o.variant for o in sp}), cap))
        print(" ", rows[-1]["verdict"], rows[-1]["oos_n"], rows[-1]["oos_pf"], flush=True)

    print("GEN ProBTB...", flush=True)
    pb = generate_pro_btb(m1, rr=2.0)
    # also focus m5 stop with previous KEEP filter for direct compare
    pb_v = sorted({o.variant for o in pb})
    for cap in CAPS:
        rows.append(run_one("ProBTB", pb, m1, dxy, pb_v, cap))
        print(" ", rows[-1]["verdict"], rows[-1]["variant"], rows[-1]["filter"],
              rows[-1]["oos_n"], rows[-1]["oos_pf"], rows[-1].get("mc_pass_0.5pct"), flush=True)

    # Forced previous KEEP config under fixed engine
    print("ProBTB forced prior KEEP config...", flush=True)
    m5 = [o for o in pb if o.variant == "M5_m5_stop_breakout_extreme_rr2.0"]
    fo = apply_confirmations(m5, m1, dxy, {"htf": True, "not_extended": True})
    cut = m1.index[int(len(m1) * 0.70)]
    oos = filter_cap(period_orders(fo, cut, m1.index[-1] + pd.Timedelta(minutes=1)), 5.0)
    tr, st = simulate(m1, oos, risk_pct=0.005, max_sl_dist=5.0, use_circuit_breaker=True)
    mc_pass = None
    if tr is not None and len(tr) >= 15:
        mc = run_mc(tr["r_multiple"].values, n_sims=3000, risk_pcts=(0.005,))
        if len(mc):
            mc_pass = float(mc.iloc[0]["pass_prob"])
    forced = {"label": "ProBTB_prior_KEEP_fixed_engine", "oos": st, "mc_pass": mc_pass,
              "n_oos_orders": len(oos)}
    if tr is not None and len(tr):
        tr.to_csv(OUT / "trades_ProBTB_priorKEEP_fixed_OOS.csv", index=False)
    print(" forced", st["n_trades"], st["profit_factor"], st["win_rate"], mc_pass, flush=True)

    print("gap recheck...", flush=True)
    gap = gap_through_recheck(m1, m5)
    print(" ", gap, flush=True)

    print("GEN MicroMAP...", flush=True)
    mm = generate_micromap(m1)
    for cap in CAPS:
        rows.append(run_one("MicroMAP", mm, m1, dxy, sorted({o.variant for o in mm}) or ["H1_rr1.5"], cap))
        print(" ", rows[-1]["verdict"], rows[-1]["oos_n"], rows[-1]["oos_pf"], flush=True)

    print("GEN AMD...", flush=True)
    amd = generate_amd_po3_ifvg(m1, range_mode="asian", tf="M5", entry_mode="market", tp_mode="range")
    # also a couple variants
    amd += generate_amd_po3_ifvg(m1, range_mode="asian", tf="M5", entry_mode="market", tp_mode="rr2")
    amd += generate_amd_po3_ifvg(m1, range_mode="asian", tf="M5", entry_mode="limit", tp_mode="range")
    for cap in CAPS:
        rows.append(run_one("AMD_PO3_iFVG", amd, m1, dxy, sorted({o.variant for o in amd}), cap))
        print(" ", rows[-1]["verdict"], rows[-1]["variant"], rows[-1]["oos_n"], rows[-1]["oos_pf"], flush=True)

    # Forced prior AMD KEEP
    amd0 = [o for o in amd if o.variant == "asian_M5_market_range"]
    oos_a = filter_cap(period_orders(amd0, cut, m1.index[-1] + pd.Timedelta(minutes=1)), 5.0)
    tr_a, st_a = simulate(m1, oos_a, risk_pct=0.005, max_sl_dist=5.0, use_circuit_breaker=True)
    forced_amd = {"label": "AMD_prior_KEEP_fixed_engine", "oos": st_a, "n": len(oos_a)}
    print(" forced AMD", st_a["n_trades"], st_a["profit_factor"], st_a["win_rate"], flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "rerun_verdicts.csv", index=False)
    summary = {
        "forced_probtb": {
            "n": forced["oos"]["n_trades"], "wr": forced["oos"]["win_rate"],
            "pf": forced["oos"]["profit_factor"], "r": forced["oos"]["expectancy_r"],
            "dd": forced["oos"]["max_dd_pct"], "mc": forced["mc_pass"],
            "same_m1_pct": forced["oos"].get("same_m1_pct"),
        },
        "forced_amd": {
            "n": forced_amd["oos"]["n_trades"], "wr": forced_amd["oos"]["win_rate"],
            "pf": forced_amd["oos"]["profit_factor"], "r": forced_amd["oos"]["expectancy_r"],
            "dd": forced_amd["oos"]["max_dd_pct"],
        },
        "gap_through_after_fix": gap,
        "verdicts": rows,
    }
    (OUT / "rerun_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("DONE", flush=True)
    print(df[["strategy","cap","variant","filter","oos_n","oos_wr","oos_pf","oos_r","verdict","mc_pass_0.5pct"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
