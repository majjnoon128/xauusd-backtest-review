#!/usr/bin/env python3
"""fib_ote_fvg + fib78_limit audited → results/fib_ote_fvg/ and results/fib78_limit/.
Compare deltas vs prior losing NDS Fib 0.62–0.78 (engulf market).
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_queued_strategies import run_family


def main():
    from strategies.fib_ote_fvg import generate_fib_ote_family
    from strategies.fib78_limit import generate_fib78_family

    def ote_note(m1):
        return {
            "vs_nds_fib_062_078": (
                "Prior NDS Fib: M15 impulse (no BOS req), zone 0.62–0.78, M1 engulf market entry. "
                "This: BOS-defined leg, FVG/OB must lie in OTE, limit at FVG mid/edge/0.62, "
                "SL beyond 0.78 or 1.0, TP at Fib 0.0 or RR2/3."
            ),
            "note_log_scale": "N/A for this family (linear Fib).",
        }

    def fib78_note(m1):
        return {
            "vs_nds_fib_062_078": (
                "Prior NDS Fib used full 0.62–0.78 zone + engulf. "
                "This: exact 0.78 limit only, trend HH/HL|LH/LL filter, SL just beyond 1.0+buf, "
                "TP at 0.0 (~theoretical RR≈3.5 before buf; buf+cap compresses RR), "
                "first-touch vs any, fractal 2/3 on M5/M15/H1/H2."
            ),
            "log_scale_fib": (
                "Irrelevant intraday on XAUUSD — price span << log curvature; linear Fib only."
            ),
            "invalidation": (
                "If price exceeds Fib 1.0 during swing confirmation → skip. "
                "Post-arm pierce of 1.0 before fill approximated via expire window "
                "(engine has no mid-wait price-invalidate); first_touch_only=True preferred."
            ),
        }

    run_family("FibOTEFVG", "fib_ote_fvg", generate_fib_ote_family, ote_note, pick_n=6)
    run_family("Fib78Limit", "fib78_limit", generate_fib78_family, fib78_note, pick_n=6)
    print("ALL FIB DONE", flush=True)


if __name__ == "__main__":
    main()
