#!/usr/bin/env python3
"""daily_sweep_ny audited → results/daily_sweep_ny/; overlap vs SessionBox + h4open."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_queued_strategies import run_family


def main():
    from strategies.daily_sweep_ny import generate_daily_sweep_family, overlap_stats, generate_daily_sweep_ny

    def extra(m1):
        # representative variant for overlap
        oo = generate_daily_sweep_ny(
            m1, "swing2", "13:30", 2.0, "M15", "mid", "rr2", session_ext="asia"
        )
        st = overlap_stats(m1, oo)
        st["spec"] = (
            "Daily bias (HH/HL|LH/LL or cvo/ema) → NY 13:30/14:30 UTC window → "
            "H1/M15 counter-trend sweep of Asia/London extreme → M5 FVG limit → "
            "SL beyond fakeout; TP day/prior/RR2/3; skip RR<1.5."
        )
        return st

    run_family("DailySweepNY", "daily_sweep_ny", generate_daily_sweep_family, extra, pick_n=6)
    print("DONE daily_sweep_ny", flush=True)


if __name__ == "__main__":
    main()
