#!/usr/bin/env python3
"""Wave3b testable families: Casper1C, NYOpp, LonFractal."""
from __future__ import annotations
import json, sys, pickle
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_final_batch import load, verdict_from
from audit_runner import OOS_CUT, oos_trading_days, is_rank, sim, tpd_true, wf, COST_ROWS
from engine import simulate, sl_distance_price, count_sl_cap_skips
from strategies.common import apply_dxy_gate
from strategies.batch3_setups import (
    generate_casper_family, generate_ny_opp_family, generate_lon_fractal_family,
)
from run_batch3 import sim_flex, diagnose

OUT = ROOT / "results" / "batch3"
FAMILIES = [
    ("Casper1C", "casper1c", generate_casper_family),
    ("NYOpp", "ny_opp", generate_ny_opp_family),
    ("LonFractal", "lon_fractal", generate_lon_fractal_family),
]


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
            pickle.dump(pools, f)
    if not pools:
        print("EMPTY", flush=True)
        return [], [], {"family": name, "diagnosis": "no_signals", "best_is": None}
    scored = is_rank(m1, pools, oos_cut)
    best_v = scored[0][3] if scored else None
    variants = [v for _, _, _, v in scored[:6]]
    strict_rows, lenient_rows = [], []
    for v in variants:
        base = pools[v]
        for use_dxy in (False, True):
            orders = apply_dxy_gate(base, dxy, use_dxy) if use_dxy else list(base)
            for cap in (5.0, 8.0):
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 8.0:
                        continue
                    tr, st, sk = sim_flex(m1, orders, v, cap, spread, slip, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, _ = wf(m1, orders, v, cap, spread, slip)
                    ver, reason = verdict_from(st, wf_frac, None)
                    row = dict(family=name, variant=v, is_best=v == best_v, dxy=use_dxy, cap=cap,
                               cost=cost_name, OOS_n=st["n_trades"], OOS_WR=st.get("win_rate"),
                               OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                               tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=sk.get("skip_pct"),
                               verdict=ver, wf_frac=wf_frac)
                    strict_rows.append(row)
                    print(f"STRICT {v} dxy={int(use_dxy)} @{cap}/{cost_name} n={st['n_trades']} R={st.get('expectancy_r')} → {ver}", flush=True)
            for lab, cap in (("8", 8.0), ("12", 12.0), ("uncapped", None)):
                tr, st, sk = sim_flex(m1, orders, v, cap, 0.25, 0.05, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                lenient_rows.append(dict(family=name, variant=v, is_best=v == best_v, dxy=use_dxy,
                    cap_label=lab, cost="cheap", OOS_n=st["n_trades"], OOS_WR=st.get("win_rate"),
                    OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                    tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=sk.get("skip_pct")))
                print(f"LENIENT {v} dxy={int(use_dxy)} @{lab} n={st['n_trades']} R={st.get('expectancy_r')} PF={st.get('profit_factor')}", flush=True)
    pd.DataFrame(strict_rows).to_csv(fam_dir / "summary_strict.csv", index=False)
    pd.DataFrame(lenient_rows).to_csv(fam_dir / "summary_lenient.csv", index=False)
    (fam_dir / "chosen.json").write_text(json.dumps({"best_is": best_v, "top": scored[:8]}, indent=2, default=str))
    prim = [r for r in strict_rows if r["variant"] == best_v and r["cap"] == 8 and r["cost"] == "strict" and not r["dxy"]]
    diag = diagnose(prim[0], lenient_rows) if prim else "unknown"
    meta = {"family": name, "best_is": best_v, "diagnosis": diag}
    (fam_dir / "diagnosis.json").write_text(json.dumps(meta, indent=2))
    print(f"DONE {name} best={best_v} diag={diag}", flush=True)
    return strict_rows, lenient_rows, meta


def main():
    m1, dxy = load()
    oos_cut = m1.index[min(m1.index.searchsorted(OOS_CUT), len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    all_s, all_l, metas = [], [], []
    for name, rel, fn in FAMILIES:
        s, l, m = eval_family(m1, dxy, name, rel, fn, n_tdays, oos_cut)
        all_s.extend(s); all_l.extend(l); metas.append(m)
    # merge into batch3 CSVs
    s_path = OUT / "all_strict.csv"; l_path = OUT / "all_lenient.csv"
    if s_path.exists():
        old = pd.read_csv(s_path)
        old = old[~old.family.isin([m["family"] for m in metas])]
        pd.concat([old, pd.DataFrame(all_s)], ignore_index=True).to_csv(s_path, index=False)
    else:
        pd.DataFrame(all_s).to_csv(s_path, index=False)
    if l_path.exists():
        old = pd.read_csv(l_path)
        old = old[~old.family.isin([m["family"] for m in metas])]
        pd.concat([old, pd.DataFrame(all_l)], ignore_index=True).to_csv(l_path, index=False)
    else:
        pd.DataFrame(all_l).to_csv(l_path, index=False)
    meta_path = OUT / "meta.json"
    old_meta = json.loads(meta_path.read_text()) if meta_path.exists() else []
    old_meta = [x for x in old_meta if x.get("family") not in {m["family"] for m in metas}]
    old_meta.extend(metas)
    meta_path.write_text(json.dumps(old_meta, indent=2))
    print("WAVE3B COMPLETE", metas, flush=True)


if __name__ == "__main__":
    main()
