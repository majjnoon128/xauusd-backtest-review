#!/usr/bin/env python3
"""Batch 3: new reel families → results/batch3/ with STRICT + LENIENT views."""
from __future__ import annotations
import json, sys, pickle
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_final_batch import load, verdict_from
from audit_runner import (
    OOS_CUT, oos_trading_days, is_rank, sim, tpd_true, wf, sanity, COST_ROWS,
)
from engine import simulate, sl_distance_price, count_sl_cap_skips, Order
from strategies.common import apply_dxy_gate
from strategies.batch3_setups import (
    generate_nine_am_family, generate_h4_m15_family, generate_ichimoku_family,
    generate_bb_div_family, generate_spike50_family, generate_sess_open_family,
    generate_h1_pin_family, generate_daily_box_family, generate_supertrend_family,
    generate_nyorb_family, generate_c22_family,
)

OUT = ROOT / "results" / "batch3"
OUT.mkdir(parents=True, exist_ok=True)

FAMILIES = [
    ("NineAM", "nine_am", generate_nine_am_family),
    ("H4M15PB", "h4_m15_pb", generate_h4_m15_family),
    ("Ichimoku", "ichimoku", generate_ichimoku_family),
    ("BBDiv", "bb_div", generate_bb_div_family),
    ("Spike50", "spike50", generate_spike50_family),
    ("SessOpen", "sess_open", generate_sess_open_family),
    ("H1Pin", "h1_pin", generate_h1_pin_family),
    ("DailyBox", "daily_box", generate_daily_box_family),
    ("Supertrend", "supertrend", generate_supertrend_family),
    ("NYORB", "ny_orb", generate_nyorb_family),
    ("Candle22", "candle22", generate_c22_family),
]


def risk_pct(cap):
    if cap is None or cap >= 1e6:
        return 0.008  # uncapped sizing still use ~$8 risk for prop realism in $ terms of R
    return cap / 1000.0


def sim_flex(m1, orders, variant, cap, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if (variant is None or o.variant == variant) and t0 <= o.arm_time < t1]
    if cap is None or cap >= 1e6:
        skip = {"n_skipped": 0, "skip_pct": 0.0, "n_total": len(oo)}
        tr, st = simulate(m1, oo, risk_pct=0.008, max_sl_dist=1e9,
                          use_circuit_breaker=cb, spread=spread, slip=slip)
        return tr, st, skip
    skip = count_sl_cap_skips(oo, cap, spread)
    oo2 = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo2, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=cb, spread=spread, slip=slip)
    return tr, st, skip


def diagnose(strict_row, lenient_rows):
    """One-line why strict failed."""
    n = strict_row.get("OOS_n", 0) or 0
    r = strict_row.get("OOS_R") or 0
    pf = strict_row.get("OOS_PF") or 0
    skip = strict_row.get("skip_pct") or 0
    # uncapped cheap
    unc = None
    for lr in lenient_rows:
        if lr.get("cap_label") == "uncapped" and lr.get("cost") == "cheap" and not lr.get("dxy"):
            unc = lr; break
    if n < 5 and skip and skip > 40:
        return "edge_killed_by_SL_cap (most signals skipped under $8)"
    if n < 10:
        return "too_few_trades under strict cap/filters"
    if r <= 0 and pf < 1.0:
        if unc and (unc.get("OOS_R") or 0) > 0.05 and (unc.get("OOS_PF") or 0) > 1.1:
            return "edge_killed_by_SL_cap_or_costs (appears only when uncapped/cheap)"
        return "no_edge_at_all (neg R even lenient)"
    if r <= 0:
        return "no_edge_at_all (OOS expectancy≤0)"
    if pf < 1.05:
        return "costs_eat_edge (gross-ish ok but PF<1.05 strict)"
    if n < 20:
        return "too_few_trades (edge hint but n<20 KEEP gate)"
    return "fails_other_KEEP_gates (WF/MC/DD)"


def eval_family(m1, dxy, name, rel, build_fn, n_tdays, oos_cut):
    fam_dir = OUT / rel
    fam_dir.mkdir(parents=True, exist_ok=True)
    cache = fam_dir / "pools_cache.pkl"
    print(f"\n======== {name} ========", flush=True)
    if cache.exists():
        with open(cache, "rb") as f:
            pools = pickle.load(f)
        print(f"LOAD cache {len(pools)}", flush=True)
    else:
        pools = build_fn(m1)
        with open(cache, "wb") as f:
            pickle.dump(pools, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"CACHED {len(pools)}", flush=True)
    if not pools:
        return {"family": name, "error": "no_orders"}, [], []

    scored = is_rank(m1, pools, oos_cut)
    best_v = scored[0][3] if scored else list(pools.keys())[0]
    variants = []
    for _, _, _, v in scored[:5]:
        if v not in variants:
            variants.append(v)
    chosen = {"best_is": best_v, "top": [
        {"v": v, "is_r": r, "is_pf": pf, "is_n": n} for r, pf, n, v in scored[:8]
    ]}
    (fam_dir / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    strict_rows = []
    lenient_rows = []
    for v in variants:
        base = pools[v]
        for use_dxy in (False, True):
            orders = apply_dxy_gate(base, dxy, use_dxy) if use_dxy else list(base)
            # STRICT official: caps 5/8, strict+cheap@8
            for cap in (5.0, 8.0):
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 8.0:
                        continue
                    tr, st, sk = sim_flex(m1, orders, v, cap, spread, slip, oos_cut,
                                         m1.index[-1] + pd.Timedelta(minutes=1))
                    _, st_is, _ = sim_flex(m1, orders, v, cap, spread, slip, m1.index[0], oos_cut)
                    wf_frac, wf_rs = wf(m1, orders, v, cap, spread, slip)
                    mc_pass = None
                    if st["n_trades"] >= 15 and tr is not None and len(tr):
                        from monte_carlo import run_mc
                        mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.005,))
                        if mc is not None and len(mc):
                            mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                    ver, reason = verdict_from(st, wf_frac, mc_pass)
                    san = sanity(m1, orders, v, cap, oos_cut) if st["n_trades"] >= 15 else {}
                    row = {
                        "family": name, "variant": v, "is_best": v == best_v,
                        "dxy": use_dxy, "cap": cap, "cost": cost_name,
                        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                        "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                        "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                        "OOS_DD": st.get("max_dd_pct"),
                        "tpd": tpd_true(st["n_trades"], n_tdays),
                        "WF+": wf_frac, "MC_pass05": mc_pass,
                        "verdict": ver, "reason": reason, "sanity_pass": san.get("pass"),
                        "skip_n": sk.get("n_skipped"), "skip_pct": sk.get("skip_pct"),
                    }
                    strict_rows.append(row)
                    print(f"  STRICT {v[-40:]} dxy={int(use_dxy)} @{cap}/{cost_name}: "
                          f"n={st['n_trades']} R={st.get('expectancy_r')} → {ver}", flush=True)

            # LENIENT: cheap costs; caps 8, 12, uncapped; no min-n in verdict (report raw)
            for cap, cap_label in ((8.0, "8"), (12.0, "12"), (None, "uncapped")):
                spread, slip = 0.25, 0.05
                tr, st, sk = sim_flex(m1, orders, v, cap, spread, slip, oos_cut,
                                     m1.index[-1] + pd.Timedelta(minutes=1))
                lenient_rows.append({
                    "family": name, "variant": v, "is_best": v == best_v,
                    "dxy": use_dxy, "cap": cap if cap else 999, "cap_label": cap_label,
                    "cost": "cheap",
                    "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                    "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                    "OOS_DD": st.get("max_dd_pct"),
                    "tpd": tpd_true(st["n_trades"], n_tdays),
                    "skip_n": sk.get("n_skipped"), "skip_pct": sk.get("skip_pct"),
                })
                print(f"  LENIENT {v[-40:]} dxy={int(use_dxy)} @{cap_label}/cheap: "
                      f"n={st['n_trades']} R={st.get('expectancy_r')} PF={st.get('profit_factor')}", flush=True)

    sdf = pd.DataFrame(strict_rows)
    ldf = pd.DataFrame(lenient_rows)
    sdf.to_csv(fam_dir / "summary_strict.csv", index=False)
    ldf.to_csv(fam_dir / "summary_lenient.csv", index=False)

    # diagnosis for IS-best @8 strict noDXY
    primary = sdf[(sdf.variant == best_v) & (sdf.cap == 8.0) & (sdf.cost == "strict") & (sdf.dxy == False)]
    if len(primary):
        pr = primary.iloc[0].to_dict()
        lens = ldf[(ldf.variant == best_v) & (ldf.dxy == False)].to_dict("records")
        diag = diagnose(pr, lens)
    else:
        pr = {}; diag = "no_primary_row"
    meta = {"family": name, "best_is": best_v, "diagnosis": diag, "primary_strict": pr}
    (fam_dir / "diagnosis.json").write_text(json.dumps(meta, indent=2, default=str))

    # short REPORT
    lines = [f"# {name}", f"IS-best: `{best_v}`", f"Diagnosis: **{diag}**", "",
             "## Strict (official)",
             "| var | cap | DXY | n | WR | R | PF | tpd | skip% | V |",
             "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---|"]
    focus = sdf[(sdf.variant == best_v) & (sdf.cost == "strict")]
    for _, r in focus.iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        lines.append(
            f"| `{str(r['variant'])[-45:]}` | {r['cap']} | {int(r['dxy'])} | {int(r['OOS_n'])} | "
            f"{wr} | {r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | {r['tpd']:.3f} | "
            f"{(r['skip_pct'] or 0)*100:.0f}% | **{r['verdict']}** |"
        )
    lines += ["", "## Lenient (cheap; no min-n)",
              "| var | cap | DXY | n | WR | R | PF | tpd | skip% |",
              "|---|---|:---:|---:|---:|---:|---:|---:|---:|"]
    focusl = ldf[(ldf.variant == best_v)]
    for _, r in focusl.iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        lines.append(
            f"| `{str(r['variant'])[-45:]}` | {r['cap_label']} | {int(r['dxy'])} | {int(r['OOS_n'])} | "
            f"{wr} | {r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | {r['tpd']:.3f} | "
            f"{(r['skip_pct'] or 0)*100:.0f}% |"
        )
    (fam_dir / "REPORT.md").write_text("\n".join(lines))
    return meta, strict_rows, lenient_rows


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "OOS tdays", n_tdays, flush=True)

    all_meta = []
    all_strict = []
    all_lenient = []
    for name, rel, fn in FAMILIES:
        try:
            meta, srows, lrows = eval_family(m1, dxy, name, rel, fn, n_tdays, oos_cut)
            all_meta.append(meta)
            all_strict.extend(srows)
            all_lenient.extend(lrows)
        except Exception as e:
            import traceback
            traceback.print_exc()
            all_meta.append({"family": name, "error": str(e)})

    pd.DataFrame(all_strict).to_csv(OUT / "all_strict.csv", index=False)
    pd.DataFrame(all_lenient).to_csv(OUT / "all_lenient.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps(all_meta, indent=2, default=str))
    print("BATCH3 DONE", flush=True)


if __name__ == "__main__":
    main()
