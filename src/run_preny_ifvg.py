#!/usr/bin/env python3
"""preny_h1_candle + liq_sweep iFVG variant → results/; overlap notes."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_queued_strategies import run_family


def main():
    from strategies.preny_h1_candle import generate_preny_family, overlap_stats, generate_preny_h1_candle
    from strategies.liq_sweep_mss import generate_liq_ifvg_family, generate_liq_sweep_ifvg, generate_liq_sweep_mss

    def preny_extra(m1):
        oo = generate_preny_h1_candle(m1, "12-13", "mid", "h1_opp")
        st = overlap_stats(m1, oo)
        st["spec"] = (
            "Last closed H1 before NY (12–13 / 13–14 UTC) → M5 sweep of H1 H/L → "
            "MSS (body break of last M5 fractal) → first FVG limit; SL beyond sweep; "
            "TP H1 opposite edge or RR1.5/2; expire NY morning. Trendline N/A."
        )
        return st

    def ifvg_extra(m1):
        base = generate_liq_sweep_mss(m1, level="asian", session="ny", entry_mode="limit_mid", tp_mode="rr2")
        ifvg = generate_liq_sweep_ifvg(m1, level="asian", session="ny", tp_mode="rr2")
        return {
            "baseline_ls_asian_ny_n": len(base),
            "ifvg_asian_ny_n": len(ifvg),
            "prior_ict3": "LiqSweepMSS all DROP (OOS n≈4–18, often neg R or tiny n)",
            "note_trendline": "Trendline-break filter skipped (subjective); not coded.",
            "delta_logic": (
                "Baseline: displacement MSS + same-direction FVG after sweep. "
                "iFVG: opposite-direction FVG closed through by body → retest of inverted gap."
            ),
        }

    run_family("PreNYH1", "preny_h1_candle", generate_preny_family, preny_extra, pick_n=6)
    run_family("LiqSweepIFVG", "liq_sweep_ifvg", generate_liq_ifvg_family, ifvg_extra, pick_n=6)
    print("ALL PRENY+IFVG DONE", flush=True)


if __name__ == "__main__":
    main()
