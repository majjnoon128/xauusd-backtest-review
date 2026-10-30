#!/usr/bin/env python3
"""Batch 2 reel strategies → results/<family>/ + append combined REPORT + portfolio overlap."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_queued_strategies import run_family
from run_final_batch import load
from audit_runner import OOS_CUT, oos_trading_days, sim, tpd_true
from strategies.h4open_fvg import overlap_with_session_box


def portfolio_vs_keeps(m1, new_orders, label: str) -> dict:
    from strategies.session_box_mss import generate_session_box_mss
    from strategies.nds_course import generate_nds_course
    # SessionBox KEEP variant
    box = generate_session_box_mss(
        m1, entry_tf="M5", tp_mode="rr1.5", require_disp=True, disp_atr=0.8, entry_mode="limit_mid"
    )
    # NDS_sym — try generate
    try:
        from strategies.nds_course import generate_nds_course_family
        nds_pools = generate_nds_course_family(m1) if hasattr(__import__('strategies.nds_course', fromlist=['x']), 'generate_nds_course_family') else {}
    except Exception:
        nds_pools = {}
    nds = []
    # fallback: scan common
    try:
        from strategies import nds_course as nc
        if hasattr(nc, "generate_nds_course"):
            # try typical kwargs
            for kwargs in [
                dict(mode="scalp", tf="M5", target="sym", brk="p3", atr_mult=1.0),
            ]:
                try:
                    nds = nc.generate_nds_course(m1, **kwargs)
                    if nds:
                        break
                except TypeError:
                    pass
            if not nds and hasattr(nc, "generate_nds_family"):
                pools = nc.generate_nds_family(m1)
                for v, oo in pools.items():
                    if "sym" in v and "M5" in v:
                        nds = oo; break
    except Exception as e:
        nds = []
    ov_box = overlap_with_session_box(new_orders, box, 60)
    ov_nds = overlap_with_session_box(new_orders, nds, 60) if nds else {"overlap": 0, "pct": 0, "h4_n": len(new_orders), "box_n": 0}
    # per-day incremental
    def days(oo):
        return set(o.arm_time.normalize() for o in oo)
    new_d, box_d = days(new_orders), days(box)
    return {
        "label": label,
        "new_n": len(new_orders),
        "vs_SessionBox_M5_60m": ov_box,
        "vs_NDS_60m": ov_nds,
        "new_days": len(new_d),
        "incremental_days_vs_box": len(new_d - box_d),
        "shared_days_vs_box": len(new_d & box_d),
    }


def main():
    from strategies.tema_cross import generate_tema_family, generate_tema_cross
    from strategies.sma_hl_channel import generate_smahl_family, generate_sma_hl_channel
    from strategies.overlap_breakout import generate_overlap_family, generate_overlap_breakout
    from strategies.ict_bos_grab_choch import generate_bosgrab_family, generate_ict_bos_grab_choch
    from strategies.ny_close_magnet import generate_nymag_family, generate_ny_close_magnet, magnet_stats
    from strategies.gartley_textbook import generate_gartley_family, generate_gartley

    # prune gartley: wrap thinner family
    def gartley_thin(m1):
        pools = {}
        for tf in ("M5", "M15", "H1"):
            for piv in (2, 3):
                for tol in (0.08, 0.12):
                    for dm in ("xa786", "bc_ext"):
                        for slm in ("beyond_x", "buf_d"):
                            for tp in (0.382, 0.618):
                                print(f" gartley {tf} p{piv} t{tol} {dm} {slm} tp{tp}", flush=True)
                                oo = generate_gartley(m1, tf, piv, tol, dm, slm, tp)
                                if oo:
                                    pools[oo[0].variant] = oo
                                    print(f"  n={len(oo)}", flush=True)
        return pools

    def tema_thin(m1):
        pools = {}
        for tf in ("M5", "M15", "H1"):
            for sm in ("long", "short", "both"):
                for slm, ams in (("atr", (1.0, 1.5)), ("swing", (1.5,)), ("signal", (1.5,))):
                    for am in ams:
                        print(f" tema {tf} {sm} {slm} {am}", flush=True)
                        oo = generate_tema_cross(m1, tf, sm, slm, am)
                        if oo:
                            pools[oo[0].variant] = oo
                            print(f"  n={len(oo)}", flush=True)
        return pools

    m1, _ = load()
    port_notes = []

    run_family("TEMACross", "tema_cross", tema_thin, pick_n=6)
    oo = generate_tema_cross(m1, "M15", "both", "atr", 1.5)
    port_notes.append(portfolio_vs_keeps(m1, oo, "tema_M15_both_atr1.5"))

    run_family("SMAHLChannel", "sma_hl_channel", generate_smahl_family, pick_n=6)
    oo = generate_sma_hl_channel(m1, "M15", "break", 2.0, "swing")
    port_notes.append(portfolio_vs_keeps(m1, oo, "smahl_M15_break_rr2"))

    run_family("OverlapBO", "overlap_breakout", generate_overlap_family, pick_n=6)
    oo = generate_overlap_breakout(m1, "12:00", "13:30", "market", "opp", 4.0)
    port_notes.append(portfolio_vs_keeps(m1, oo, "ovbo_1200_1330_rr4"))

    def bos_extra(m1):
        return {
            "vs_liq_sweep_mss": (
                "Prior LiqSweepMSS DROP (ict3): Asian/prev-day sweep + displacement MSS + same-dir FVG. "
                "This adds prior BOS + wick-only grab (close back inside) + CHoCH + FVG on CHoCH leg."
            ),
            "claim_80pct": "OOS WR reported in family summary; claim not used for KEEP.",
        }
    run_family("BOSGrabCHoCH", "ict_bos_grab_choch", generate_bosgrab_family, bos_extra, pick_n=6)
    oo = generate_ict_bos_grab_choch(m1, "M5", "ny", "rr2", "mid")
    port_notes.append(portfolio_vs_keeps(m1, oo, "bosgrab_M5_ny_rr2"))

    def ny_extra(m1):
        return {"magnet_stats": magnet_stats(m1), "claim_75pct": "compare touch rates vs random in stats"}
    run_family("NYCloseMagnet", "ny_close_magnet", generate_nymag_family, ny_extra, pick_n=6)
    oo = generate_ny_close_magnet(m1, 21, "london_open", 1.5)
    port_notes.append(portfolio_vs_keeps(m1, oo, "nymag_h21_london_open"))

    run_family("Gartley", "gartley_textbook", gartley_thin, pick_n=6)
    oo = generate_gartley(m1, "M15", 3, 0.08, "xa786", "beyond_x", 0.618)
    port_notes.append(portfolio_vs_keeps(m1, oo, "gartley_M15_p3"))

    out = ROOT / "results" / "batch2_portfolio_overlap.json"
    out.write_text(json.dumps(port_notes, indent=2, default=str))
    print("PORTFOLIO NOTES WRITTEN", out, flush=True)
    print("ALL BATCH2 DONE", flush=True)


if __name__ == "__main__":
    main()
