#!/usr/bin/env python3
"""Verification pass for r864/full before watchdog.
(1) Audit documented in VERIFY.md — lookahead fix already applied in nds_course.
(2) Cap reentry TP rr1.5/2/3 + top-5 ablation.
(3) Sanity + WF4 + SGB MC for scalp_M3_sym r864 & full @cap8 ±DXY.
(4) Portfolio with SessionBox_M5 asia @cap8, 30m dedupe.
"""
from __future__ import annotations
import json, sys, time, copy
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "expand"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, Order, compute_stats
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course, _scan_reentry864
from strategies.session_box_mss import generate_session_box_mss
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from
from run_expand import (
    OOS_CUT, COST_ROWS, oos_trading_days, tpd_true, worst_streak,
)
from run_expand_fidelity import sim_mode, wf_mode

FAM_KW = dict(style="scalp", entry_tf="M3", tp_mode="sym", confirm="brk_p3")


def max_daily_loss_pct(tr: pd.DataFrame, initial=1000.0) -> float:
    if tr is None or len(tr) == 0:
        return 0.0
    t = tr.copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t["day"] = t["entry_time"].dt.strftime("%Y-%m-%d")
    # approximate equity path: start each day from running bal
    bal = initial
    worst = 0.0
    for day, g in t.groupby("day", sort=True):
        day_start = bal
        for pnl in g["pnl_usd"].values:
            bal += float(pnl)
            dd = (day_start - bal) / day_start * 100.0 if day_start > 0 else 0.0
            worst = max(worst, dd)
    return float(worst)


def top5_ablation(tr: pd.DataFrame, initial=1000.0) -> dict:
    if tr is None or len(tr) == 0:
        return {"n": 0, "sum_R": 0, "top5_R": 0, "share_top5": None,
                "exp_R_all": 0, "exp_R_no_top5": 0, "pf_all": 0, "pf_no_top5": 0,
                "n_no_top5": 0}
    r = tr["r_multiple"].astype(float).values
    idx = np.argsort(-r)  # descending
    top5_idx = set(idx[:min(5, len(idx))].tolist())
    mask = np.array([i not in top5_idx for i in range(len(r))])
    top5_R = float(r[list(top5_idx)].sum()) if top5_idx else 0.0
    sum_R = float(r.sum())
    share = (top5_R / sum_R) if sum_R != 0 else None
    tr2 = tr.iloc[mask].reset_index(drop=True) if mask.any() else tr.iloc[0:0]
    st_all = compute_stats(tr, initial, initial + float(tr["pnl_usd"].sum()))
    if len(tr2):
        st2 = compute_stats(tr2, initial, initial + float(tr2["pnl_usd"].sum()))
    else:
        st2 = {"expectancy_r": 0.0, "profit_factor": 0.0, "n_trades": 0}
    return {
        "n": int(len(tr)),
        "sum_R": sum_R,
        "top5_R": top5_R,
        "share_top5": share,
        "top5_max_R": float(r[idx[0]]) if len(r) else 0.0,
        "exp_R_all": float(st_all["expectancy_r"]),
        "exp_R_no_top5": float(st2["expectancy_r"]),
        "pf_all": float(st_all["profit_factor"]),
        "pf_no_top5": float(st2["profit_factor"]),
        "n_no_top5": int(st2["n_trades"]),
        "WR_all": float(st_all["win_rate"]),
        "WR_no_top5": float(st2.get("win_rate", 0)),
    }


def sanity_cap8(m1, orders, variant, oos_cut, spread=0.35, slip=0.10):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= 8.0 + 1e-9]
    _, st0 = simulate(m1, oo, risk_pct=0.008, max_sl_dist=8.0,
                      use_circuit_breaker=False, spread=spread, slip=slip,
                      allow_fractional=True)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes)
              for o in oo]
        _, st = simulate(m1, sh, risk_pct=0.008, max_sl_dist=8.0,
                         use_circuit_breaker=False, spread=spread, slip=slip,
                         allow_fractional=True)
        out[f"shift{s}_pf"] = st["profit_factor"]
    rng = np.random.default_rng(1)
    rands = []
    for _ in range(3):
        ro = []
        for o in oo:
            j = m1.index.searchsorted(o.arm_time, side="left")
            if j >= len(m1) - 5:
                continue
            jj = int(rng.integers(max(0, j - 40), min(len(m1) - 1, j + 40)))
            px = float(m1["close"].iloc[jj]); risk = abs(o.price - o.sl)
            side = o.side if rng.random() < 0.5 else ("short" if o.side == "long" else "long")
            sl, tp = ((px - risk, px + abs(o.tp - o.price)) if side == "long"
                      else (px + risk, px - abs(o.tp - o.price)))
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, "market", px, sl, tp,
                            "RAND", o.variant, {}, 30))
        _, st = simulate(m1, ro, risk_pct=0.008, max_sl_dist=8.0,
                         use_circuit_breaker=False, spread=spread, slip=slip,
                         allow_fractional=True)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    out["pass"] = bool(
        out["base_n"] >= 15 and out["base_pf"] >= 1.05
        and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
        and out.get("shift15_pf", 0) > 0.3
    )
    return out


def audit_spot_checks(m1):
    """Static code + sample-order checks for lookahead / fill bias."""
    findings = []
    # 1) reentry arm after new-flag conf (post-fix)
    oo = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        use_reentry864=True, reentry_tp_mode="rr1.5", **FAM_KW,
    )
    re = [o for o in oo if (o.meta or {}).get("leg") == "reentry864"]
    findings.append({
        "check": "reentry_arm_after_new_flag",
        "n_reentry": len(re),
        "all_have_audit_flag": all((o.meta or {}).get("audit") == "arm_after_new_flag" for o in re),
        "max_planned_rr": max(abs(o.price - o.tp) / abs(o.price - o.sl) for o in re) if re else None,
    })
    # 2) size_mult on partials
    oo_pe = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        use_partial=True, **FAM_KW,
    )
    # sm spot check unused
    legs = {}
    for o in oo_pe:
        legs.setdefault((o.meta or {}).get("leg"), []).append((o.meta or {}).get("size_mult"))
    findings.append({
        "check": "partial_size_mult",
        "legs": {k: {"n": len(v), "sm": sorted(set(v))[:5]} for k, v in legs.items()},
    })
    # 3) engine: commission per trade (lots), worst-case SL, gap skip — static confirm
    findings.append({
        "check": "engine_rules",
        "gap_through_fill": True,  # _fill_price uses open if through
        "worst_case_SL_first": True,  # _resolve_exit pending_sl before pending_tp
        "no_fill_on_arm_bar": True,  # searchsorted arm_time side=left; market +delay
        "costs_per_leg": "pnl = move*100*lots - commission*lots (each Order = one Trade)",
        "size_mult_applied": "lots *= meta.size_mult before pnl",
    })
    # 4) rr caps vs sym fat tail
    fat = {}
    for rtp in ("rr1.5", "rr2", "rr3", "sym"):
        oo = generate_nds_course(
            m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
            use_reentry864=True, reentry_tp_mode=rtp, **FAM_KW,
        )
        re = [o for o in oo if (o.meta or {}).get("leg") == "reentry864"]
        rrs = [abs(o.price - o.tp) / max(abs(o.price - o.sl), 1e-9) for o in re]
        fat[rtp] = {
            "n": len(re),
            "med_rr": float(np.median(rrs)) if rrs else None,
            "p95_rr": float(np.percentile(rrs, 95)) if rrs else None,
            "max_rr": float(max(rrs)) if rrs else None,
        }
    findings.append({"check": "reentry_planned_rr_by_cap", "by_mode": fat})
    return findings


def eval_cell(m1, dxy, orders, variant, use_dxy, oos_cut, n_tdays, label):
    oo = apply_dxy_gate(orders, dxy, True) if use_dxy else list(orders)
    spread, slip = 0.35, 0.10
    tr_is, st_is, _ = sim_mode(m1, oo, variant, "cap8", spread, slip, m1.index[0], oos_cut)
    tr, st, _ = sim_mode(m1, oo, variant, "cap8", spread, slip,
                         oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
    wf_frac, wf_rs = wf_mode(m1, oo, variant, "cap8", spread, slip)
    mc_pass = None
    if st["n_trades"] >= 15 and tr is not None and len(tr):
        mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.008,))
        if mc is not None and len(mc):
            mc_pass = float(mc.iloc[0]["pass_prob"])
    san = sanity_cap8(m1, oo, variant, oos_cut, spread, slip) if st["n_trades"] >= 15 else {}
    ab_is = top5_ablation(tr_is)
    ab_oos = top5_ablation(tr)
    verd, reason = verdict_from(
        {**st, "trades_per_day": tpd_true(st["n_trades"], n_tdays)},
        wf_frac, mc_pass,
    )
    # override trades_per_day with true OOS days
    tpd = tpd_true(st["n_trades"], n_tdays)
    mdl = max_daily_loss_pct(tr)
    row = {
        "label": label,
        "variant": variant,
        "dxy": use_dxy,
        "mode": "cap8",
        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
        "OOS_n": st["n_trades"], "OOS_WR": st["win_rate"], "OOS_R": st["expectancy_r"],
        "OOS_PF": st["profit_factor"], "OOS_DD": st["max_dd_pct"],
        "tpd": tpd, "avg_R": st["avg_r"],
        "WF+": wf_frac, "WF_rs": json.dumps(wf_rs),
        "MC_pass": mc_pass,
        "sanity_pass": san.get("pass"),
        "sanity_base_pf": san.get("base_pf"),
        "sanity_shift15": san.get("shift15_pf"),
        "sanity_rand": san.get("rand_mean_pf"),
        "worst_streak": worst_streak(tr),
        "max_daily_loss_pct": mdl,
        "sgb_daily5_ok": mdl < 5.0,
        "verdict": verd, "reason": reason,
        # ablation
        "IS_top5_share": ab_is["share_top5"], "IS_R_no_top5": ab_is["exp_R_no_top5"],
        "IS_PF_no_top5": ab_is["pf_no_top5"], "IS_top5_maxR": ab_is["top5_max_R"],
        "OOS_top5_share": ab_oos["share_top5"], "OOS_R_no_top5": ab_oos["exp_R_no_top5"],
        "OOS_PF_no_top5": ab_oos["pf_no_top5"], "OOS_top5_maxR": ab_oos["top5_max_R"],
        "n_reentry_oos": int(sum(1 for _, r in (tr.iterrows() if tr is not None and len(tr) else [])
                                 if False)),  # filled below
    }
    if tr is not None and len(tr) and "meta" not in tr.columns:
        # engine doesn't dump meta; count from orders that filled roughly by variant tag
        pass
    # count reentry among OOS orders that would fill under cap — use arm times in OOS trades via strategy side
    # Approximate: re-sim isn't needed; count from order pool OOS under cap
    oos_oo = [o for o in oo if o.variant == variant and o.arm_time >= oos_cut
              and sl_distance_price(o.price, o.sl, o.side, spread) <= 8.0 + 1e-9]
    row["n_reentry_oos_orders"] = sum(1 for o in oos_oo if (o.meta or {}).get("leg") == "reentry864")
    row["n_partial_oos_orders"] = sum(1 for o in oos_oo if str((o.meta or {}).get("leg", "")).startswith("partial"))
    return row, tr, oo


def portfolio_cap8(m1, dxy, comps, oos_cut, n_tdays, dedupe_min=30):
    """comps: list of (label, orders, prefer_dxy bool|None). Filter each to cap8 then merge."""
    rows = []
    for port_dxy in (False, True):
        merged = []
        for label, oo, prefer_dxy in comps:
            use = prefer_dxy if prefer_dxy is not None else port_dxy
            chunk = apply_dxy_gate(oo, dxy, True) if use else list(oo)
            for o in chunk:
                if sl_distance_price(o.price, o.sl, o.side, 0.35) <= 8.0 + 1e-9:
                    merged.append(o)
        merged.sort(key=lambda x: x.arm_time)
        out, last = [], {}
        for o in merged:
            # dedupe by side (portfolio-level); keep different legs of same setup
            leg = (o.meta or {}).get("leg", "full")
            key = (o.side, leg if str(leg).startswith("partial") else "any")
            # User asked deduped portfolio — same 30m by side as build_portfolio
            prev = last.get(o.side)
            if prev is not None and (o.arm_time - prev).total_seconds() < dedupe_min * 60:
                continue
            out.append(o)
            last[o.side] = o.arm_time
        tagged = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp,
                        o.strategy, "PORT", dict(o.meta), o.expire_minutes, o.max_hold_minutes)
                  for o in out]
        # full-period sim with CB then slice OOS
        tr_all, _ = simulate(
            m1, tagged, risk_pct=0.008, max_sl_dist=8.0,
            use_circuit_breaker=True, spread=0.35, slip=0.10,
            allow_fractional=True,
        )
        if tr_all is not None and len(tr_all):
            tr = tr_all[pd.to_datetime(tr_all["entry_time"], utc=True) >= oos_cut].reset_index(drop=True)
            if len(tr):
                bal = 1000.0 + float(tr["pnl_usd"].sum())
                st = compute_stats(tr, 1000.0, bal)
            else:
                st = {"n_trades": 0, "win_rate": 0, "expectancy_r": 0, "profit_factor": 0,
                      "max_dd_pct": 0, "avg_r": 0, "net_pnl": 0}
        else:
            tr = pd.DataFrame()
            st = {"n_trades": 0, "win_rate": 0, "expectancy_r": 0, "profit_factor": 0,
                  "max_dd_pct": 0, "avg_r": 0, "net_pnl": 0}
        tpd = tpd_true(st["n_trades"], n_tdays)
        mc_pass = None
        if st["n_trades"] >= 15 and len(tr):
            mc = run_mc(tr["r_multiple"].values, risk_pcts=(0.008,))
            if mc is not None and len(mc):
                mc_pass = float(mc.iloc[0]["pass_prob"])
        mdl = max_daily_loss_pct(tr)
        verd, reason = verdict_from({**st, "trades_per_day": tpd}, 1.0, mc_pass)  # WF N/A → pass 1.0 placeholder
        # For portfolio, require own WF-like: use OOS only criteria + MC
        if st["n_trades"] < 20 or st["expectancy_r"] <= 0 or st["profit_factor"] < 1.05:
            verd, reason = "DROP", "OOS ضعیف"
        elif st["max_dd_pct"] > 25:
            verd, reason = "DROP", "DD"
        elif st["expectancy_r"] >= 0.15 and st["profit_factor"] >= 1.2 and (mc_pass is None or mc_pass >= 0.25):
            verd, reason = "KEEP", "portfolio OOS"
        elif st["expectancy_r"] > 0 and st["profit_factor"] >= 1.05:
            verd, reason = "MAYBE", "portfolio weak"
        else:
            verd, reason = "DROP", "fail"
        rows.append({
            "port_dxy": port_dxy,
            "n_orders_merged": len(out),
            "OOS_n": st["n_trades"], "OOS_WR": st["win_rate"], "OOS_PF": st["profit_factor"],
            "OOS_R": st["expectancy_r"], "avg_R": st.get("avg_r", st["expectancy_r"]),
            "OOS_DD": st["max_dd_pct"], "tpd": tpd,
            "worst_streak": worst_streak(tr),
            "max_daily_loss_pct": mdl,
            "sgb_daily5_ok": mdl < 5.0,
            "MC_pass": mc_pass,
            "verdict": verd, "reason": reason,
            "components": "+".join(c[0] for c in comps),
            "OOS_top5": json.dumps(top5_ablation(tr)),
        })
    return rows


def main():
    t0 = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "OOS days", n_tdays, flush=True)

    print("=== AUDIT ===", flush=True)
    findings = audit_spot_checks(m1)
    (OUT / "verify_audit.json").write_text(json.dumps(findings, indent=2, default=str))
    for f in findings:
        print(json.dumps(f, default=str)[:300], flush=True)

    # Generate pools: r864 & full × rtp caps
    pools = {}
    configs = []
    for toggle, tkw in (
        ("r864", dict(use_partial=False, use_reentry864=True, use_htf_n3_tp=False)),
        ("full", dict(use_partial=True, use_reentry864=True, use_htf_n3_tp=True)),
    ):
        for rtp in ("rr1.5", "rr2", "rr3", "sym"):
            label = f"scalp_M3_sym__{toggle}__rtp{rtp}"
            print(f"GEN {label}", flush=True)
            tt = time.time()
            oo = generate_nds_course(
                m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
                reentry_tp_mode=rtp, **FAM_KW, **tkw,
            )
            if not oo:
                print("  empty", flush=True)
                continue
            pools[label] = oo
            configs.append((label, toggle, rtp, oo[0].variant))
            print(f"  n={len(oo)} v={oo[0].variant} ({time.time()-tt:.1f}s)", flush=True)

    rows = []
    for label, toggle, rtp, variant in configs:
        oo = pools[label]
        for use_dxy in (False, True):
            lab = f"{label}__{'DXY' if use_dxy else 'noDXY'}"
            print(f"EVAL {lab}", flush=True)
            row, tr, _ = eval_cell(m1, dxy, oo, variant, use_dxy, oos_cut, n_tdays, lab)
            row["toggle"] = toggle
            row["rtp"] = rtp
            rows.append(row)
            print(
                f"  OOS n={row['OOS_n']} R={row['OOS_R']:.3f} PF={row['OOS_PF']:.2f} "
                f"tpd={row['tpd']:.2f} WF={row['WF+']} MC={row['MC_pass']} "
                f"san={row['sanity_pass']} top5share={row['OOS_top5_share']} "
                f"R_no5={row['OOS_R_no_top5']:.3f} → {row['verdict']}",
                flush=True,
            )

    rdf = pd.DataFrame(rows)
    rdf.to_csv(OUT / "verify_summary.csv", index=False)

    # Portfolio: best capped r864/full noDXY + Box_M5 asia @cap8
    print("=== PORTFOLIO ===", flush=True)
    print("GEN Box_M5 asia", flush=True)
    box_oo = generate_session_box_mss(
        m1, None, False, "limit_mid", "rr1.5", True, 0.8, "atr_buf", "M5", box_kind="asia",
    )
    print(f"  box n={len(box_oo)} v={box_oo[0].variant if box_oo else None}", flush=True)

    # Prefer rtp rr1.5 (sane) for portfolio; also try rr2
    port_rows = []
    for rtp_pick in ("rr1.5", "rr2", "rr3"):
        for toggle in ("r864", "full"):
            lab = f"scalp_M3_sym__{toggle}__rtp{rtp_pick}"
            if lab not in pools:
                continue
            nds = pools[lab]
            # component prefer_dxy=False for both (asia box historically noDXY; NDS noDXY was best)
            comps = [
                (f"NDS_{toggle}_{rtp_pick}", nds, False),
                ("Box_M5_asia", box_oo, False),
            ]
            pr = portfolio_cap8(m1, dxy, comps, oos_cut, n_tdays, dedupe_min=30)
            for r in pr:
                r["nds_toggle"] = toggle
                r["nds_rtp"] = rtp_pick
            port_rows.extend(pr)
            for r in pr:
                print(
                    f"  PORT {toggle}/{rtp_pick} dxy={r['port_dxy']}: "
                    f"n={r['OOS_n']} tpd={r['tpd']:.2f} WR={r['OOS_WR']:.2f} "
                    f"PF={r['OOS_PF']:.2f} R={r['OOS_R']:.3f} DD={r['OOS_DD']:.1f} "
                    f"streak={r['worst_streak']} mdl={r['max_daily_loss_pct']:.2f} "
                    f"MC={r['MC_pass']} → {r['verdict']}",
                    flush=True,
                )

    pdf = pd.DataFrame(port_rows)
    pdf.to_csv(OUT / "verify_portfolio.csv", index=False)

    # Write VERIFY.md
    lines = [
        "# Verification pass — r864 / full before watchdog",
        "",
        f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')} Asia/Tehran",
        f"OOS cut: {oos_cut} | OOS trading days: {n_tdays}",
        "",
        "## (1) Audit — lookahead / fill bias",
        "",
        "### Bug found & fixed",
        "- **LOOKAHEAD in `_scan_reentry864` (pre-fix):** SL used `max/min` of bars `leg[0] .. leg[0]+25`,",
        "  but order was armed at `leg.conf` (= piv + right ≈ +3). That peeked ~22 bars past arm time.",
        "- **Fix:** Arm only after a **new Flag** (first confirmed swing after leg1) confirms;",
        "  SL = newFlag ± buf; TP from (level−SL). Meta `audit=arm_after_new_flag`.",
        "- Legacy `sym` TP still allows fat planned RR (max ~1000R); **must use rr1.5/2/3 for live**.",
        "",
        "### Engine rules confirmed OK",
        "- Closed-bar arm; no fill on signal bar; market +1 M1 delay",
        "- Gap-through fills at worse open; fill-through SL/TP skipped",
        "- Same-bar SL/TP → **SL first** (worst case)",
        "- `size_mult` scales lots; commission × lots **per leg**",
        "",
        "### Planned RR by reentry_tp_mode (orders, pre-sim)",
        "```",
        json.dumps(findings[-1]["by_mode"], indent=2),
        "```",
        "",
        "## (2–3) scalp_M3_sym @cap8 strict — r864 / full × rtp × ±DXY",
        "",
        "| label | dxy | rtp | OOS_n | tpd | WR | PF | avgR | DD | WF+ | MC | san | top5%R | R_no5 | streak | mdl% | verd |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for _, r in rdf.sort_values(["toggle", "rtp", "dxy"]).iterrows():
        lines.append(
            f"| {r['toggle']} | {r['dxy']} | {r['rtp']} | {int(r['OOS_n'])} | {r['tpd']:.2f} | "
            f"{r['OOS_WR']:.2f} | {r['OOS_PF']:.2f} | {r['OOS_R']:.3f} | {r['OOS_DD']:.1f} | "
            f"{r['WF+']:.2f} | {r['MC_pass']} | {r['sanity_pass']} | "
            f"{(r['OOS_top5_share'] if pd.notna(r['OOS_top5_share']) else 0):.2f} | "
            f"{r['OOS_R_no_top5']:.3f} | {int(r['worst_streak'])} | {r['max_daily_loss_pct']:.2f} | "
            f"**{r['verdict']}** |"
        )

    lines += [
        "",
        "## (4) Portfolio = NDS(scalp_M3_sym capped-rtp) + SessionBox_M5 asia @cap8, 30m dedupe",
        "",
        "| NDS | rtp | port_dxy | n | tpd | WR | PF | avgR | DD | streak | mdl% | MC | verd |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in pdf.sort_values(["nds_toggle", "nds_rtp", "port_dxy"]).iterrows():
        lines.append(
            f"| {r['nds_toggle']} | {r['nds_rtp']} | {r['port_dxy']} | {int(r['OOS_n'])} | "
            f"{r['tpd']:.2f} | {r['OOS_WR']:.2f} | {r['OOS_PF']:.2f} | {r['OOS_R']:.3f} | "
            f"{r['OOS_DD']:.1f} | {int(r['worst_streak'])} | {r['max_daily_loss_pct']:.2f} | "
            f"{r['MC_pass']} | **{r['verdict']}** |"
        )

    # Go / no-go recommendation
    # Prefer: rtp rr1.5 or rr2, noDXY, KEEP or strong MAYBE, sanity pass, top5 share < 0.5, R_no5>0
    cand = rdf[
        (rdf["rtp"].isin(["rr1.5", "rr2", "rr3"]))
        & (rdf["dxy"] == False)
        & (rdf["verdict"].isin(["KEEP", "MAYBE"]))
    ].copy()
    # score
    def score(r):
        s = 0
        if r["verdict"] == "KEEP":
            s += 5
        if r["sanity_pass"]:
            s += 3
        if r["WF+"] >= 0.75:
            s += 2
        if r["MC_pass"] is not None and r["MC_pass"] >= 0.25:
            s += 2
        if r["OOS_R_no_top5"] > 0:
            s += 2
        if pd.notna(r["OOS_top5_share"]) and r["OOS_top5_share"] < 0.4:
            s += 1
        if r["sgb_daily5_ok"]:
            s += 1
        s += min(r["tpd"], 3.0)  # prefer ~2+/day
        return s

    lines += ["", "## Go / No-Go", ""]
    if len(cand) == 0:
        lines.append("**NO-GO** for paper-forward watchdog: no capped-TP cell KEEP/MAYBE without DXY after audit fix.")
        go = False
        rec = None
    else:
        cand["score"] = cand.apply(score, axis=1)
        best = cand.sort_values("score", ascending=False).iloc[0]
        # portfolio check for same
        port_match = pdf[
            (pdf["nds_toggle"] == best["toggle"])
            & (pdf["nds_rtp"] == best["rtp"])
            & (pdf["port_dxy"] == False)
        ]
        port_ok = False
        if len(port_match):
            pr = port_match.iloc[0]
            port_ok = pr["verdict"] in ("KEEP", "MAYBE") and pr["sgb_daily5_ok"] and (
                pr["MC_pass"] is None or pr["MC_pass"] >= 0.20
            )
        go = (
            best["verdict"] in ("KEEP", "MAYBE")
            and bool(best["sanity_pass"])
            and float(best["WF+"]) >= 0.5
            and float(best["OOS_R_no_top5"]) > 0
            and bool(best["sgb_daily5_ok"])
        )
        if go:
            lines.append("**GO (paper-forward only)** — capped reentry, audit-fixed arm.")
        else:
            lines.append("**NO-GO / CONDITIONAL** — see caveats; do not promote uncapped-sym reentry.")
        lines += [
            "",
            "### Recommended config",
            f"- Strategy: NDS_Course scalp M3 sym brk_p3 + **{best['toggle']}**",
            f"- `reentry_tp_mode={best['rtp']}` (NOT sym)",
            f"- Cap SL dist $8, risk 0.8%, fractional lots, DXY={'ON' if best['dxy'] else 'OFF'}",
            f"- Costs: strict 0.35/0.10",
            f"- OOS: n={int(best['OOS_n'])} tpd={best['tpd']:.2f} WR={best['OOS_WR']:.2f} "
            f"PF={best['OOS_PF']:.2f} R={best['OOS_R']:.3f} DD={best['OOS_DD']:.1f}% "
            f"WF+={best['WF+']:.2f} MC={best['MC_pass']} san={best['sanity_pass']}",
            f"- Top5 ablation: share={best['OOS_top5_share']} R_no5={best['OOS_R_no_top5']:.3f}",
            f"- Variant tag: `{best['variant']}`",
        ]
        if len(port_match):
            pr = port_match.iloc[0]
            lines += [
                "",
                "### Portfolio companion",
                f"- + SessionBox_M5 asia limit_mid rr1.5 @cap8 noDXY, 30m side-dedupe",
                f"- Port OOS: n={int(pr['OOS_n'])} tpd={pr['tpd']:.2f} PF={pr['OOS_PF']:.2f} "
                f"R={pr['OOS_R']:.3f} DD={pr['OOS_DD']:.1f} streak={int(pr['worst_streak'])} "
                f"mdl={pr['max_daily_loss_pct']:.2f}% MC={pr['MC_pass']} → {pr['verdict']}",
                f"- Include Box in watchdog: {'YES' if port_ok else 'NO (NDS-only first)'}",
            ]
        rec = {
            "go": bool(go),
            "toggle": best["toggle"],
            "rtp": best["rtp"],
            "dxy": bool(best["dxy"]),
            "variant": best["variant"],
            "port_include_box": bool(port_ok) if len(port_match) else False,
        }

    meta = {
        "elapsed_s": time.time() - t0,
        "n_tdays": n_tdays,
        "oos_cut": str(oos_cut),
        "recommendation": rec,
        "bug": "lookahead_reentry_SL_fixed_arm_after_new_flag",
    }
    (OUT / "verify_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    (OUT / "VERIFY.md").write_text("\n".join(lines) + "\n")
    print("DONE", meta, flush=True)
    print("Wrote", OUT / "VERIFY.md", flush=True)


if __name__ == "__main__":
    main()
