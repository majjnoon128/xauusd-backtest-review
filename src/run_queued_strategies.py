#!/usr/bin/env python3
"""Run hougaard_daily, magnet_pdmid, h4open_fvg, crt → their result dirs + combined snippets."""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_final_batch import load
from audit_runner import (
    OOS_CUT, oos_trading_days, is_rank, eval_variants, write_report, dxy_delta_df, sim, tpd_true,
)

def run_family(name, out_rel, build_fn, extra_stats_fn=None, pick_n=5):
    OUT = ROOT / "results" / out_rel
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE = OUT / "pools_cache.pkl"
    print(f"\n======== {name} → {OUT} ========", flush=True)
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "OOS tdays", n_tdays, flush=True)

    extra_lines = []
    if extra_stats_fn:
        stats = extra_stats_fn(m1)
        (OUT / "stats.json").write_text(json.dumps(stats, indent=2, default=str))
        extra_lines.append("## Stats")
        extra_lines.append("```json")
        extra_lines.append(json.dumps(stats, indent=2, default=str)[:4000])
        extra_lines.append("```")

    if CACHE.exists():
        print("LOAD cache", flush=True)
        with open(CACHE, "rb") as f:
            pools = pickle.load(f)
    else:
        pools = build_fn(m1)
        with open(CACHE, "wb") as f:
            pickle.dump(pools, f, protocol=pickle.HIGHEST_PROTOCOL)
        print("CACHED", len(pools), flush=True)

    scored = is_rank(m1, pools, oos_cut)
    for r, pf, n, v in scored[:8]:
        print(f"  IS {v}: n={n} R={r:.3f} PF={pf:.2f}", flush=True)
    best_v = scored[0][3] if scored else None
    variants = []
    for _, _, _, v in scored[:pick_n]:
        if v not in variants:
            variants.append(v)
    chosen = {"best_is": best_v, "top": [
        {"v": v, "is_r": r, "is_pf": pf, "is_n": n} for r, pf, n, v in scored[:8]
    ]}
    (OUT / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))

    rows = eval_variants(m1, dxy, pools, variants, oos_cut, n_tdays, OUT, name, best_v)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    dxy_delta_df(df).to_csv(OUT / "dxy_delta.csv", index=False)

    # leaderboard OOS for top IS
    board = []
    for r, pf, n, v in scored[:20]:
        _, st, _ = sim(m1, pools[v], v, 8.0, 0.35, 0.10, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
        board.append({"variant": v, "IS_n": n, "IS_R": r, "IS_PF": pf,
                      "OOS_n": st["n_trades"], "OOS_R": st.get("expectancy_r"),
                      "OOS_PF": st.get("profit_factor"), "tpd": tpd_true(st["n_trades"], n_tdays)})
    pd.DataFrame(board).to_csv(OUT / "is_leaderboard_oos.csv", index=False)

    write_report(OUT, name, df, best_v, n_tdays, extra_lines)
    print("DONE", name, flush=True)
    return df, chosen


def main():
    from strategies.hougaard_daily import generate_hougaard_family, pure_stats as hougaard_stats
    from strategies.magnet_pdmid import generate_magnet_family, base_rate_stats as magnet_stats
    from strategies.h4open_fvg import generate_h4open_family, overlap_with_session_box
    from strategies.crt import generate_crt_family, pure_htf_stats
    from strategies.session_box_mss import generate_session_box_mss

    run_family("Hougaard", "hougaard_daily", generate_hougaard_family, hougaard_stats)
    run_family("MagnetPDMid", "magnet_pdmid", generate_magnet_family, magnet_stats)

    # h4open with overlap note
    def h4_stats(m1):
        from strategies.h4open_fvg import generate_h4open_fvg
        oo = generate_h4open_fvg(m1, entry_tf="M15", rr=2.0, bias_mode="prev_h4")
        box = generate_session_box_mss(m1, entry_tf="M5", tp_mode="rr1.5", require_disp=True, disp_atr=0.8, entry_mode="limit_mid")
        ov = overlap_with_session_box(oo, box, 60)
        return {"overlap_vs_session_box_60m": ov, "note": "bias=prev closed H4; no lookahead on forming H4 open side as bias"}
    run_family("H4OpenFVG", "h4open_fvg", generate_h4open_family, h4_stats)

    def crt_stats(m1):
        st = pure_htf_stats(m1)
        # overlap with h4open + session box
        from strategies.crt import generate_crt_ltf
        from strategies.h4open_fvg import generate_h4open_fvg, overlap_with_session_box
        crt_oo = generate_crt_ltf(m1, "H4", "M5", False, "extreme")
        h4_oo = generate_h4open_fvg(m1, entry_tf="M5", rr=2.0, bias_mode="prev_h4")
        box = generate_session_box_mss(m1, entry_tf="M5", tp_mode="rr1.5", require_disp=True, disp_atr=0.8, entry_mode="limit_mid")
        st["overlap_crt_vs_h4open"] = overlap_with_session_box(crt_oo, h4_oo, 60)
        st["overlap_crt_vs_box"] = overlap_with_session_box(crt_oo, box, 60)
        return st
    run_family("CRT", "crt", generate_crt_family, crt_stats, pick_n=6)

    print("ALL QUEUED DONE", flush=True)


if __name__ == "__main__":
    main()
