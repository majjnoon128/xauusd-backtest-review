#!/usr/bin/env python3
import sys, json, shutil
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_final_batch as rfb
from strategies import generate_pro_btb, generate_amd_po3_ifvg
from combine import build_combined_orders, signal_overlap

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"

def parse_flags(x):
    if isinstance(x, dict):
        return x
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return {}
    if isinstance(x, str):
        if not x or x == "{}":
            return {}
        return json.loads(x)
    return {}

def main():
    m1, dxy = rfb.load()
    meta = json.loads((RES / "meta.json").read_text())
    cut = pd.Timestamp(meta["oos_cut"])
    m1_oos = m1[m1.index >= cut]
    final = pd.read_csv(RES / "final_verdicts.csv")
    keeps = final[final["verdict"] == "KEEP"]
    pool = {}
    for _, r in keeps.iterrows():
        flags = parse_flags(r["flags"])
        print("building", r["strategy"], r["variant"], flags)
        if r["strategy"] == "ProBTB":
            base = generate_pro_btb(m1, dxy, use_dxy=False, use_vol=False, rr=2.0)
        else:
            base = generate_amd_po3_ifvg(
                m1, dxy, range_mode="asian", tf="M5", entry_mode="market",
                tp_mode="range", use_htf=False, use_dxy=False, use_vol=False,
            )
        vo = [o for o in base if o.variant == r["variant"]]
        fo = rfb.apply_confirmations(vo, m1, dxy, flags)
        fo = rfb.filter_cap(fo, float(r["cap"]))
        pool[r["strategy"]] = fo
        tr, st = rfb.eval_set(fo, m1_oos, "OOS", float(r["cap"]), strategy=r["strategy"], variant=r["variant"])
        print("  solo", st["n_trades"], st["avg_r"], st["profit_factor"])

    combo = build_combined_orders(pool)
    print("combo orders", len(combo))
    tr, st = rfb.eval_set(combo, m1_oos, "OOS", 5.0, strategy="COMBO", variant="merged")
    print("combo5", st["n_trades"], st["avg_r"], st["profit_factor"], st["max_dd_pct"])
    if tr is not None and not tr.empty:
        tr.to_csv(RES / "combined_oos_cap5.0.csv", index=False)

    p7 = {k: rfb.filter_cap(v, 7.5) for k, v in pool.items()}
    c7 = build_combined_orders(p7)
    tr7, st7 = rfb.eval_set(c7, m1_oos, "OOS", 7.5, strategy="COMBO", variant="merged")
    print("combo7.5", st7["n_trades"], st7["avg_r"], st7["profit_factor"])
    if tr7 is not None and not tr7.empty:
        tr7.to_csv(RES / "combined_oos_cap7.5.csv", index=False)

    overlap_df = signal_overlap(pool, 30)
    overlap_df.to_csv(RES / "signal_overlap.csv", index=False)
    skip_rows = pd.read_csv(RES / "sl_cap_skips.csv").to_dict("records")
    stats_df = pd.read_csv(RES / "stats_all.csv")
    spd_rows = json.loads((RES / "signals_per_day.json").read_text())
    combined_stats = [{**st, "name": "KEEP_merged_cap5.0"}, {**st7, "name": "KEEP_merged_cap7.5"}]
    rfb.write_results_md(meta, skip_rows, final, stats_df, spd_rows, overlap_df, combined_stats)
    shutil.copy(ROOT / "RESULTS.md", Path("/workspace/trading/RESULTS.md"))
    print("DONE results", (Path("/workspace/trading/RESULTS.md")).stat().st_size)

if __name__ == "__main__":
    main()
