#!/usr/bin/env python3
"""Batch 4 runner — strict + lenient."""
from __future__ import annotations
import json, sys, pickle
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_final_batch import load, verdict_from
from audit_runner import OOS_CUT, oos_trading_days, is_rank, sim, tpd_true, wf, COST_ROWS
from strategies.common import apply_dxy_gate
from run_batch3 import sim_flex, diagnose
from strategies.batch4_setups import (
    generate_sess17_family, generate_iran1630_family, generate_hour_candle_family,
    generate_fake_bo_family, generate_trend50_family,
)

OUT = ROOT / "results" / "batch4"
OUT.mkdir(parents=True, exist_ok=True)

FAMILIES = [
    ("Sess17", "sess17", generate_sess17_family),
    ("Iran1630", "iran1630", generate_iran1630_family),
    ("HourCandle", "hour_candle", generate_hour_candle_family),
    ("FakeBO", "fake_bo", generate_fake_bo_family),
    ("Trend50", "trend50", generate_trend50_family),
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
        return [], [], {"family": name, "diagnosis": "no_signals", "best_is": None}
    # Cap variants for IS rank if huge (Sess17)
    if len(pools) > 40:
        # pre-score lightly on IS trade count / keep diversity of labels
        scored_all = is_rank(m1, pools, oos_cut)
        pools = {v: pools[v] for _,_,_,v in scored_all[:24]}
        print(f"TRIM to top24 IS", flush=True)
    scored = is_rank(m1, pools, oos_cut)
    best_v = scored[0][3] if scored else None
    variants = [v for _,_,_,v in scored[:8]]
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
                    strict_rows.append(dict(family=name, variant=v, is_best=v==best_v, dxy=use_dxy, cap=cap,
                        cost=cost_name, OOS_n=st["n_trades"], OOS_WR=st.get("win_rate"),
                        OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                        tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=sk.get("skip_pct"),
                        verdict=ver, wf_frac=wf_frac))
                    print(f"STRICT {v} dxy={int(use_dxy)} @{cap}/{cost_name} n={st['n_trades']} R={st.get('expectancy_r')} → {ver}", flush=True)
            for lab, cap in (("8", 8.0), ("12", 12.0), ("uncapped", None)):
                tr, st, sk = sim_flex(m1, orders, v, cap, 0.25, 0.05, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                lenient_rows.append(dict(family=name, variant=v, is_best=v==best_v, dxy=use_dxy,
                    cap_label=lab, cost="cheap", OOS_n=st["n_trades"], OOS_WR=st.get("win_rate"),
                    OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                    tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=sk.get("skip_pct")))
    pd.DataFrame(strict_rows).to_csv(fam_dir/"summary_strict.csv", index=False)
    pd.DataFrame(lenient_rows).to_csv(fam_dir/"summary_lenient.csv", index=False)
    (fam_dir/"chosen.json").write_text(json.dumps({"best_is": best_v, "top": scored[:10]}, indent=2, default=str))
    prim = [r for r in strict_rows if r["variant"]==best_v and r["cap"]==8 and r["cost"]=="strict" and not r["dxy"]]
    diag = diagnose(prim[0], lenient_rows) if prim else "unknown"
    meta = {"family": name, "best_is": best_v, "diagnosis": diag}
    (fam_dir/"diagnosis.json").write_text(json.dumps(meta, indent=2))
    print(f"DONE {name} best={best_v} diag={diag}", flush=True)
    return strict_rows, lenient_rows, meta


def main():
    m1, dxy = load()
    oos_cut = m1.index[min(m1.index.searchsorted(OOS_CUT), len(m1)-1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    all_s, all_l, metas = [], [], []
    for name, rel, fn in FAMILIES:
        s, l, m = eval_family(m1, dxy, name, rel, fn, n_tdays, oos_cut)
        all_s.extend(s); all_l.extend(l); metas.append(m)
    pd.DataFrame(all_s).to_csv(OUT/"all_strict.csv", index=False)
    pd.DataFrame(all_l).to_csv(OUT/"all_lenient.csv", index=False)
    (OUT/"meta.json").write_text(json.dumps(metas, indent=2))
    print("BATCH4 COMPLETE", metas, flush=True)


if __name__ == "__main__":
    main()
