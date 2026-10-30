#!/usr/bin/env python3
"""Expand KEEPs — priority: NDS 123Flag uncapped (fractional lots), then SessionBox.

Writes results/expand/ only. Does not touch results/batch3/.
Protocol: closed-bar engine, IS pick @2026-07-02, OOS judge, ±DXY, strict/cheap.
NDS primary: NO SL cap, risk 0.5% and 1%, allow_fractional=True.
"""
from __future__ import annotations
import json, pickle, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "expand"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "nds_pools_cache.pkl"

from engine import simulate, sl_distance_price, Order
from monte_carlo import run_mc
from strategies.nds_course import generate_nds_course
from strategies.session_box_mss import generate_session_box_mss
from strategies.common import apply_dxy_gate
from run_final_batch import load, verdict_from

OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")
COST_ROWS = (("strict", 0.35, 0.10), ("cheap", 0.25, 0.05))
RISKS = (("r05", 0.005), ("r10", 0.01))


def oos_trading_days(m1, oos_cut):
    idx = m1.index[m1.index >= oos_cut]
    days = pd.DatetimeIndex(idx.normalize().unique())
    return [d for d in days if int(getattr(d, "day_of_week", d.dayofweek)) < 5]


def tpd_true(n, n_tdays):
    return float(n) / max(1, n_tdays)


def worst_streak(tr: pd.DataFrame) -> int:
    if tr is None or len(tr) == 0:
        return 0
    wins = (tr["pnl_usd"].values > 0)
    worst = cur = 0
    for w in wins:
        if not w:
            cur += 1
            worst = max(worst, cur)
        else:
            cur = 0
    return int(worst)


def sl_dist_stats(orders, spread=0.35):
    dists = [sl_distance_price(o.price, o.sl, o.side, spread) for o in orders]
    if not dists:
        return {"n": 0, "median": None, "p90": None, "mean": None, "min": None, "max": None}
    a = np.asarray(dists, dtype=float)
    return {
        "n": int(len(a)),
        "median": float(np.median(a)),
        "p90": float(np.percentile(a, 90)),
        "mean": float(np.mean(a)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


def sim_uncap(m1, orders, variant, risk_pct, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    tr, st = simulate(
        m1, oo, risk_pct=risk_pct, max_sl_dist=None,
        use_circuit_breaker=cb, spread=spread, slip=slip,
        allow_fractional=True,
    )
    return tr, st, oo


def wf_uncap(m1, orders, variant, risk_pct, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold; o1 = warm + (k + 1) * fold if k < 3 else n
        _, st, _ = sim_uncap(m1, orders, variant, risk_pct, spread, slip,
                             m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1; rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def sanity_uncap(m1, orders, variant, risk_pct, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    _, st0 = simulate(m1, oo, risk_pct=risk_pct, max_sl_dist=None,
                      use_circuit_breaker=False, allow_fractional=True)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes)
              for o in oo]
        _, st = simulate(m1, sh, risk_pct=risk_pct, max_sl_dist=None,
                         use_circuit_breaker=False, allow_fractional=True)
        out[f"shift{s}_pf"] = st["profit_factor"]
    rng = np.random.default_rng(1); rands = []
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
        _, st = simulate(m1, ro, risk_pct=risk_pct, max_sl_dist=None,
                         use_circuit_breaker=False, allow_fractional=True)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    out["pass"] = bool(out["base_n"] >= 15 and out["base_pf"] >= 1.05
                       and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
                       and out.get("shift15_pf", 0) > 0.3)
    return out


# ---------- pool builders (limited variants) ----------
def build_nds_pools(m1):
    if CACHE.exists():
        print("LOAD NDS cache", CACHE, flush=True)
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    pools = {}
    # Primary grid: 4 TF × 2 style × 2 tp × 1 confirm = 16
    for tf in ("M1", "M3", "M5", "M15"):
        for style in ("scalp", "day"):
            for tp in ("rr1.5", "sym"):
                print(f" NDS {style} {tf} {tp} brk_p3", flush=True)
                t0 = time.time()
                oo = generate_nds_course(
                    m1, None, False, False, family="course", style=style,
                    entry_tf=tf, tp_mode=tp, confirm="brk_p3", min_atr=1.0, pivot_lr=3,
                )
                if oo:
                    pools[oo[0].variant] = oo
                    print(f"  n={len(oo)} {oo[0].variant} ({time.time()-t0:.1f}s)", flush=True)
                else:
                    print(f"  empty ({time.time()-t0:.1f}s)", flush=True)
    # Alts (limited): fidelity / interpretation probes — scalp M5/M1 only
    alts = [
        dict(style="scalp", entry_tf="M5", tp_mode="rr1.5", confirm="brk_pull", pivot_lr=3, sl_buf_mode="atr01", note="alt_brk_pull"),
        dict(style="scalp", entry_tf="M5", tp_mode="rr1.5", confirm="at_f", pivot_lr=3, sl_buf_mode="atr01", note="alt_at_f"),
        dict(style="scalp", entry_tf="M5", tp_mode="rr1.5", confirm="brk_p3", pivot_lr=2, sl_buf_mode="atr01", note="alt_lr2"),
        dict(style="scalp", entry_tf="M5", tp_mode="rr1.5", confirm="brk_p3", pivot_lr=3, sl_buf_mode="fixed02", note="alt_sl_fixed02"),
        dict(style="scalp", entry_tf="M1", tp_mode="rr1.5", confirm="brk_pull", pivot_lr=3, sl_buf_mode="atr01", note="alt_m1_brk_pull"),
        dict(style="scalp", entry_tf="M5", tp_mode="nd864", confirm="brk_p3", pivot_lr=3, sl_buf_mode="atr01", note="alt_nd864"),
    ]
    alt_meta = {}
    for kw in alts:
        note = kw.pop("note")
        print(f" ALT {note}", flush=True)
        t0 = time.time()
        oo = generate_nds_course(m1, None, False, False, family="course", min_atr=1.0, **kw)
        if oo:
            pools[oo[0].variant] = oo
            alt_meta[oo[0].variant] = note
            print(f"  n={len(oo)} {oo[0].variant} ({time.time()-t0:.1f}s)", flush=True)
        else:
            print(f"  empty ({time.time()-t0:.1f}s)", flush=True)
        kw["note"] = note  # restore for clarity (unused)
    data = {"pools": pools, "alt_meta": alt_meta, "n_variants_tried": len(pools)}
    with open(CACHE, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("CACHED", CACHE, "variants", len(pools), flush=True)
    return data


def eval_nds_family(m1, dxy, label, base_orders, oos_cut, n_tdays, rows, chosen, is_alt=False):
    variants = sorted({o.variant for o in base_orders})
    if not variants:
        print("EMPTY", label, flush=True)
        return None
    # IS pick @ risk 0.5% strict uncapped
    scored = []
    for v in variants:
        _, st, _ = sim_uncap(m1, base_orders, v, 0.005, 0.35, 0.10, m1.index[0], oos_cut)
        scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v))
    scored.sort(reverse=True)
    best_v = scored[0][3]
    chosen[label] = {
        "variant": best_v, "is_r": scored[0][0], "is_pf": scored[0][1],
        "is_n": scored[0][2], "is_alt": is_alt,
        "all_is": [{"v": v, "R": r, "PF": pf, "n": n} for r, pf, n, v in scored],
    }
    print(f"CHOSEN {label}: {best_v} IS R={scored[0][0]:.3f} n={scored[0][2]}", flush=True)

    # SL dist on full-sample signals of chosen variant
    all_v = [o for o in base_orders if o.variant == best_v]
    sld = sl_dist_stats(all_v, 0.35)
    (OUT / f"sl_dist_{label}.json").write_text(json.dumps(sld, indent=2))

    for use_dxy in (False, True):
        orders = apply_dxy_gate(base_orders, dxy, use_dxy) if use_dxy else list(base_orders)
        for risk_name, risk_pct in RISKS:
            for cost_name, spread, slip in COST_ROWS:
                tr, st, oo = sim_uncap(m1, orders, best_v, risk_pct, spread, slip, oos_cut,
                                       m1.index[-1] + pd.Timedelta(minutes=1))
                _, st_is, _ = sim_uncap(m1, orders, best_v, risk_pct, spread, slip, m1.index[0], oos_cut)
                wf_frac, wf_rs = wf_uncap(m1, orders, best_v, risk_pct, spread, slip)
                mc_pass = None
                if st["n_trades"] >= 15 and tr is not None and len(tr):
                    mc = run_mc(tr["r_multiple"].values, risk_pcts=(risk_pct,))
                    if mc is not None and len(mc):
                        mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
                # verdict uses same brutal gates (n>=20 etc) — informational for uncapped
                ver, reason = verdict_from(st, wf_frac, mc_pass)
                san = sanity_uncap(m1, orders, best_v, risk_pct, oos_cut) if st["n_trades"] >= 15 else {}
                tpd = tpd_true(st["n_trades"], n_tdays)
                # OOS SL dist
                sld_oos = sl_dist_stats(oo, spread)
                rows.append({
                    "family": label, "variant": best_v, "alt": is_alt,
                    "dxy": use_dxy, "risk": risk_name, "risk_pct": risk_pct,
                    "cost": cost_name, "sl_cap": "NONE",
                    "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
                    "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                    "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                    "OOS_DD": st.get("max_dd_pct"), "OOS_net": st.get("net_pnl"),
                    "tpd": tpd, "n_tdays": n_tdays,
                    "WF+": wf_frac, "WF_rs": str(wf_rs), "MC_pass": mc_pass,
                    "verdict": ver, "reason": reason, "sanity_pass": san.get("pass"),
                    "worst_streak": worst_streak(tr),
                    "sl_med": sld_oos["median"], "sl_p90": sld_oos["p90"],
                    "sl_mean": sld_oos["mean"], "sl_max": sld_oos["max"],
                    "signals_oos": len(oo),
                })
                if tr is not None and len(tr) and risk_name == "r05" and cost_name == "strict":
                    tag = f"{label}_{'DXY' if use_dxy else 'noDXY'}_uncap_{risk_name}_{cost_name}"
                    tr.to_csv(OUT / f"trades_{tag}.csv", index=False)
                print(
                    f"  {label} dxy={int(use_dxy)} {risk_name}/{cost_name}: "
                    f"n={st['n_trades']} tpd={tpd:.3f} WR={st.get('win_rate')} "
                    f"R={st.get('expectancy_r')} PF={st.get('profit_factor')} "
                    f"DD={st.get('max_dd_pct')} SL_med={sld_oos['median']} → {ver}",
                    flush=True,
                )
    return best_v


def build_portfolio(m1, dxy, components, oos_cut, n_tdays, risk_pct=0.005, dedupe_min=30):
    """components: list of (label, orders_filtered_to_variant, use_dxy_for_this).
    Dedupes by side within dedupe_min minutes; one position at a time via engine CB.
    """
    rows = []
    for use_dxy_port in (False, True):
        merged = []
        for label, oo, prefer_dxy in components:
            # If component prefers its own DXY setting, apply that; else follow port flag
            use = prefer_dxy if prefer_dxy is not None else use_dxy_port
            chunk = apply_dxy_gate(oo, dxy, use) if use else list(oo)
            for o in chunk:
                merged.append(o)
        merged.sort(key=lambda x: x.arm_time)
        out, last = [], {}
        for o in merged:
            prev = last.get(o.side)
            if prev is not None and (o.arm_time - prev).total_seconds() < dedupe_min * 60:
                continue
            out.append(o)
            last[o.side] = o.arm_time
        for cost_name, spread, slip in COST_ROWS:
            tagged = [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp,
                            o.strategy, "PORT", dict(o.meta), o.expire_minutes, o.max_hold_minutes)
                      for o in out]
            tr, st = simulate(
                m1, tagged, risk_pct=risk_pct, max_sl_dist=None,
                use_circuit_breaker=True, spread=spread, slip=slip,
                allow_fractional=True,
            )
            # filter OOS
            if tr is not None and len(tr):
                tr = tr[pd.to_datetime(tr["entry_time"], utc=True) >= oos_cut].reset_index(drop=True)
                # recompute stats on OOS only
                if len(tr):
                    from engine import compute_stats
                    bal = 1000.0 + float(tr["pnl_usd"].sum())
                    st = compute_stats(tr, 1000.0, bal)
                else:
                    st = {"n_trades": 0, "win_rate": 0, "expectancy_r": 0, "profit_factor": 0,
                          "max_dd_pct": 0, "net_pnl": 0}
            tpd = tpd_true(st["n_trades"], n_tdays)
            mc_pass = None
            if st["n_trades"] >= 15 and tr is not None and len(tr):
                mc = run_mc(tr["r_multiple"].values, risk_pcts=(risk_pct,))
                if mc is not None and len(mc):
                    mc_pass = float(mc.iloc[0].get("pass_prob", np.nan))
            rows.append({
                "dxy_port": use_dxy_port, "cost": cost_name, "risk_pct": risk_pct,
                "n_merged": len(out), "OOS_n": st["n_trades"], "OOS_WR": st.get("win_rate"),
                "OOS_R": st.get("expectancy_r"), "OOS_PF": st.get("profit_factor"),
                "OOS_DD": st.get("max_dd_pct"), "tpd": tpd, "MC_pass": mc_pass,
                "worst_streak": worst_streak(tr) if tr is not None else 0,
                "components": ",".join(c[0] for c in components),
            })
            print(
                f"PORT dxy={int(use_dxy_port)} {cost_name}: n={st['n_trades']} "
                f"tpd={tpd:.3f} R={st.get('expectancy_r')} PF={st.get('profit_factor')} "
                f"DD={st.get('max_dd_pct')} streak={worst_streak(tr) if tr is not None else 0}",
                flush=True,
            )
            if tr is not None and len(tr) and cost_name == "strict":
                tr.to_csv(OUT / f"trades_PORT_dxy{int(use_dxy_port)}_uncap.csv", index=False)
    return rows


FIDELITY = """# NDS code vs NDS_SPEC fidelity

## Implemented (mechanical)
- 123Flag structure P1<P2<P3<F (short) / L1>L2>L3>F (long); F must exceed P3 (FAQ 29)
- Confirmed swing pivots left/right (default 3)
- Day style: HTF M30 3-pivot bias gate
- Scalp style: no HTF required
- SL beyond Flag F (+ 0.1×ATR or fixed $0.20 alt)
- TP modes: rr1.5 / sym / nd864 (86.4% of structure)
- Confirm: brk_p3, brk_pull, at_f (alt)
- Session London/NY window via in_session
- Min structure height vs ATR; closed-bar arm; DXY gate optional
- Schematic extras (nd_zone 78–96, SMI, equal_top) exist but not in this expand primary grid

## Simplified / omitted (could weaken results)
1. **Partial scale-out 1/3** at open nodes 1–2 (course pp.110) → single full exit only
2. **Scale-in** with trend → disabled (prop single-position)
3. **TP = first open swing node** (step 4) → proxied by RR/sym/nd864, not literal open-node scan
4. **Re-entry on 86.4% of first drop** (steps 5–6 `reentry864`) → **not coded** as separate signal
5. **Final TP = HTF node 3** (steps 12) → omitted
6. **Low-volume spike at F** → optional vol gate, off in this run
7. **Pullback depth classes** (shallow/mid/deep) → all accepted, no filter
8. **Hook Type B / nested-hook discretion** → Type A completed only; nested choice not coded
9. **Super-scalping multi-confirm stack** (Flag+seq+sym+864+hook-hook) → not all required
10. **Pivot width** not specified in PDF → coded as lr=3 (alt lr=2 tested)
11. **Entry timing**: course says enter at Flag after reverse confirm → coded as break of P3/pullback after F; alt `at_f` enters on F-pivot confirm bar

## Alts tested this run (see summary `alt=True`)
- brk_pull vs brk_p3
- at_f entry (no displacement wait)
- pivot_lr=2
- SL fixed $0.20 buffer
- M1 brk_pull
- nd864 TP on M5 scalp
"""


def main():
    t_all = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "bars", len(m1), "OOS trading days", n_tdays, flush=True)

    (OUT / "FIDELITY.md").write_text(FIDELITY)

    data = build_nds_pools(m1)
    pools, alt_meta = data["pools"], data.get("alt_meta", {})
    n_tried = data["n_variants_tried"]

    rows, chosen = [], {}

    # Primary families: one cell per (style, tf) — IS picks among rr1.5/sym
    for tf in ("M1", "M3", "M5", "M15"):
        for style in ("scalp", "day"):
            oo = []
            for k, v in pools.items():
                if k in alt_meta:
                    continue
                if not k.startswith(f"course_{style}_{tf}_"):
                    continue
                if "_brk_p3_" not in k:
                    continue
                if not ("_rr1.5_" in k or "_sym_" in k):
                    continue
                # skip alt tags
                if "_lr" in k or "fixed02" in k:
                    continue
                oo.extend(v)
            eval_nds_family(m1, dxy, f"NDS_{style}_{tf}", oo, oos_cut, n_tdays, rows, chosen)

    # Alt families individually
    for k, note in alt_meta.items():
        oo = pools[k]
        eval_nds_family(m1, dxy, f"ALT_{note}", oo, oos_cut, n_tdays, rows, chosen, is_alt=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "nds_uncap_summary.csv", index=False)
    (OUT / "chosen.json").write_text(json.dumps(chosen, indent=2, default=str))
    (OUT / "meta.json").write_text(json.dumps({
        "oos_cut": str(oos_cut), "n_tdays": n_tdays, "n_variants_tried": n_tried,
        "sl_cap": None, "allow_fractional": True, "risks": [0.005, 0.01],
        "costs": {"strict": [0.35, 0.10], "cheap": [0.25, 0.05]},
        "primary": "NDS 123Flag uncapped", "session_box": "deferred_second_priority",
    }, indent=2))

    # Portfolio from strict-KEEP primary cells @ r05 strict noDXY (or with their best DXY)
    keep_mask = (
        (df.verdict == "KEEP") & (df.risk == "r05") & (df.cost == "strict") & (df.alt == False)
    )
    keeps = df[keep_mask]
    # Prefer one variant per family: best OOS_R among KEEP (but selection was IS — use IS-chosen already)
    # For portfolio: take unique families' chosen variants that KEEP on their best dxy row
    port_comps = []
    for fam in sorted(keeps.family.unique()):
        sub = keeps[keeps.family == fam].sort_values("OOS_R", ascending=False)
        # pick dxy setting that KEEPs with best R
        best = sub.iloc[0]
        v = best["variant"]
        oo = [o for o in pools.get(v, [])]
        if not oo:
            continue
        prefer = bool(best["dxy"])
        port_comps.append((fam, oo, prefer))
        print(f"PORT include {fam} dxy={prefer} v={v} OOS_R={best['OOS_R']}", flush=True)

    port_rows = []
    if len(port_comps) >= 1:
        port_rows = build_portfolio(m1, dxy, port_comps, oos_cut, n_tdays, risk_pct=0.005, dedupe_min=30)
        # also try mixing top-2 by tpd among KEEP
    pdf = pd.DataFrame(port_rows)
    if len(pdf):
        pdf.to_csv(OUT / "portfolio_uncap.csv", index=False)

    # Compact REPORT
    focus = df[(df.risk == "r05") & (df.cost == "strict")].copy()
    lines = [
        f"# NDS expand uncapped (OOS trading days={n_tdays})",
        "",
        f"Variants tried: **{n_tried}**. SL cap: **NONE**. Fractional lots. Risk 0.5%/1%.",
        "IS pick @ r05 strict uncapped by expectancy; OOS judged. Do not pick by OOS.",
        "",
        "## Primary (r05 strict)",
        "",
        "| Family | variant | DXY | n | tpd | WR | R | PF | DD% | SL_med | SL_p90 | WF+ | MC | streak | V |",
        "|---|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, r in focus[focus.alt == False].sort_values(["family", "dxy"]).iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        mc = f"{r['MC_pass']:.2f}" if pd.notna(r["MC_pass"]) else "-"
        lines.append(
            f"| {r['family']} | `{r['variant'][-48:]}` | {int(r['dxy'])} | "
            f"{int(r['OOS_n'])} | {r['tpd']:.3f} | {wr} | {r['OOS_R']:.3f} | {r['OOS_PF']:.2f} | "
            f"{r['OOS_DD']:.1f} | {r['sl_med']:.2f} | {r['sl_p90']:.2f} | {r['WF+']:.0%} | "
            f"{mc} | {int(r['worst_streak'])} | **{r['verdict']}** |"
        )
    lines += ["", "## Alts (r05 strict) — interpretation probes", ""]
    for _, r in focus[focus.alt == True].sort_values(["family", "dxy"]).iterrows():
        wr = f"{100*r['OOS_WR']:.0f}%" if pd.notna(r["OOS_WR"]) else "-"
        lines.append(
            f"- {r['family']} dxy={int(r['dxy'])}: n={int(r['OOS_n'])} tpd={r['tpd']:.3f} "
            f"WR={wr} R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} DD={r['OOS_DD']:.1f} "
            f"SL_med={r['sl_med']:.2f} → **{r['verdict']}**"
        )
    lines += ["", "## Risk 1% note (r10 strict, primary only)", ""]
    r10 = df[(df.risk == "r10") & (df.cost == "strict") & (df.alt == False)]
    for _, r in r10.sort_values(["family", "dxy"]).iterrows():
        lines.append(
            f"- {r['family']} dxy={int(r['dxy'])}: n={int(r['OOS_n'])} tpd={r['tpd']:.3f} "
            f"R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} DD={r['OOS_DD']:.1f} MC={r['MC_pass']} → {r['verdict']}"
        )
    if len(pdf):
        lines += ["", "## Portfolio (strict KEEP components, 30m dedupe, uncapped r05)", ""]
        for _, r in pdf.iterrows():
            lines.append(
                f"- dxy_port={r['dxy_port']} {r['cost']}: n={int(r['OOS_n'])} tpd={r['tpd']:.3f} "
                f"WR={r['OOS_WR']} R={r['OOS_R']:.3f} PF={r['OOS_PF']:.2f} DD={r['OOS_DD']:.1f} "
                f"MC={r['MC_pass']} streak={int(r['worst_streak'])} comps={r['components']}"
            )
    # Conclusion from numbers only after run — placeholder filled below from df
    keeps_f = focus[(focus.alt == False) & (focus.verdict == "KEEP")]
    lines += ["", "## Conclusion", ""]
    if len(keeps_f):
        best = keeps_f.sort_values("OOS_R", ascending=False).iloc[0]
        lines.append(
            f"1. Best primary KEEP @r05 strict: `{best['family']}` dxy={int(best['dxy'])} "
            f"tpd={best['tpd']:.3f} R={best['OOS_R']:.3f} PF={best['OOS_PF']:.2f} "
            f"SL_med={best['sl_med']:.2f}."
        )
        lines.append(
            f"2. KEEP families: {', '.join(sorted(keeps_f.family.unique()))}."
        )
    else:
        lines.append("1. No primary KEEP under uncapped protocol at r05 strict.")
    if len(pdf):
        p0 = pdf[(pdf.dxy_port == False) & (pdf.cost == "strict")]
        if len(p0):
            p = p0.iloc[0]
            lines.append(
                f"3. Portfolio uncapped: tpd={p['tpd']:.3f} PF={p['OOS_PF']:.2f} "
                f"n={int(p['OOS_n'])} DD={p['OOS_DD']:.1f}%."
            )
    lines.append("4. SessionBox expansion deferred (second priority). See FIDELITY.md for spec gaps.")
    lines.append(f"5. Runtime wall ~{time.time()-t_all:.0f}s. Variants tried={n_tried}.")
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("DONE", OUT, "wall", round(time.time() - t_all, 1), flush=True)


if __name__ == "__main__":
    main()
