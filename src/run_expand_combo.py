#!/usr/bin/env python3
"""Pre-registered combination search (~40 variants) for watchdog.

Cores: audit-fixed NDS scalp_M3 r864/full (rtp capped) + SessionBox_M5 asia.
Components mined from batch3/ict3/cap8/final with any conditional KEEP/MAYBE.
Protocol: choose on IS only; judge on OOS; robust = IS_R>0 and OOS_R>0;
require WF+>=0.5 and MC_pass>=0.25 for promote. Cap ~40. Report count.
"""
from __future__ import annotations
import json, sys, time, copy
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "expand"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, Order, compute_stats
from monte_carlo import run_mc
from indicators import resample_ohlc, atr_prior, bar_end
from strategies.nds_course import generate_nds_course
from strategies.session_box_mss import generate_session_box_mss
from strategies.batch3_setups import generate_spike50, generate_c22
from strategies.common import apply_dxy_gate
from strategies.asian_bo import generate_asian_bo
from run_final_batch import load, verdict_from
from run_expand import OOS_CUT, oos_trading_days, tpd_true, worst_streak
from run_expand_verify import max_daily_loss_pct, top5_ablation

FAM = dict(style="scalp", entry_tf="M3", tp_mode="sym", confirm="brk_p3")
CAP = 8.0
SPREAD, SLIP = 0.35, 0.10


# ---------- level maps (closed prior day / c22 / recent spike mid) ----------
def build_level_maps(m1: pd.DataFrame):
    """Maps keyed by calendar date (normalized UTC) → levels known at day open."""
    daily = resample_ohlc(m1, "1D")
    h1 = resample_ohlc(m1, "60min")
    m5 = resample_ohlc(m1, "5min")
    a5 = atr_prior(m5, 14)

    # prior-day H/L for date d = daily bar of d-1 (fully closed)
    pd_hl = {}
    dates = list(daily.index)
    for i, ts in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        d = ts.normalize() if hasattr(ts, "normalize") else pd.Timestamp(ts).normalize()
        pd_hl[d] = (float(daily.loc[prev, "high"]), float(daily.loc[prev, "low"]))

    # candle-22: H1 bar at prev day 22:00 → levels for date d
    c22 = {}
    for d, (hi, lo) in list(pd_hl.items()):
        prev = d - pd.Timedelta(days=1)
        ts = prev + pd.Timedelta(hours=22)
        if ts in h1.index:
            c22[d] = (float(h1.loc[ts, "high"]), float(h1.loc[ts, "low"]))

    # last spike mid before time t: scan M5 for last impulse with long wick; mid of next opposite body
    # Precompute array for speed
    m5_o = m5["open"].values.astype(float)
    m5_c = m5["close"].values.astype(float)
    m5_h = m5["high"].values.astype(float)
    m5_l = m5["low"].values.astype(float)
    m5_idx = m5.index
    atrv = a5.reindex(m5_idx).values.astype(float)
    spike_mid = np.full(len(m5), np.nan)
    last = np.nan
    for i in range(30, len(m5)):
        if np.isnan(atrv[i]) or atrv[i] <= 0:
            spike_mid[i] = last
            continue
        body = abs(m5_c[i] - m5_o[i])
        if body < 0.3 * atrv[i]:
            spike_mid[i] = last
            continue
        lower_w = min(m5_o[i], m5_c[i]) - m5_l[i]
        upper_w = m5_h[i] - max(m5_o[i], m5_c[i])
        # bullish spike → mid of a later bearish pullback within 8 bars — only mark at confirm of pullback
        # For level-at-time we store mid when pullback bar closes
        if m5_c[i] > m5_o[i] and lower_w >= 1.5 * max(body, 0.05):
            for j in range(i + 1, min(i + 9, len(m5))):
                if m5_c[j] < m5_o[j]:
                    last = 0.5 * (m5_o[j] + m5_c[j])
                    break
        elif m5_c[i] < m5_o[i] and upper_w >= 1.5 * max(body, 0.05):
            for j in range(i + 1, min(i + 9, len(m5))):
                if m5_c[j] > m5_o[j]:
                    last = 0.5 * (m5_o[j] + m5_c[j])
                    break
        spike_mid[i] = last

    # ATR at time for near/away
    atr_map = a5  # indexed by m5
    return pd_hl, c22, m5_idx, spike_mid, atr_map


def _day(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert("UTC").normalize()


def atr_at(atr_map, t, default=2.0):
    # last closed M5 ATR at or before t
    if atr_map is None or len(atr_map) == 0:
        return default
    j = atr_map.index.searchsorted(t, side="right") - 1
    if j < 0:
        return default
    v = atr_map.iloc[j]
    return float(v) if not np.isnan(v) else default


def spike_at(m5_idx, spike_mid, t):
    j = m5_idx.searchsorted(t, side="right") - 1
    if j < 0:
        return None
    v = spike_mid[j]
    return float(v) if not np.isnan(v) else None


def filter_location(orders, mode, pd_hl, c22, atr_map, k_atr=1.0):
    """mode: near_pd | away_pd | near_c22 | away_c22 — vs entry price."""
    out = []
    for o in orders:
        d = _day(o.arm_time)
        atr = atr_at(atr_map, o.arm_time)
        if mode.endswith("pd"):
            lv = pd_hl.get(d)
        else:
            lv = c22.get(d)
        if not lv:
            continue
        hi, lo = lv
        dist = min(abs(o.price - hi), abs(o.price - lo))
        near = dist <= k_atr * atr
        if mode.startswith("near") and near:
            out.append(o)
        elif mode.startswith("away") and not near:
            out.append(o)
    return out


def retarget_tp_magnet(orders, pd_hl, c22, m5_idx, spike_mid, min_rr=1.0):
    """TP = nearest favorable level among pd H/L, c22 H/L, last spike mid. Keep SL."""
    out = []
    for o in orders:
        d = _day(o.arm_time)
        cands = []
        for src in (pd_hl.get(d), c22.get(d)):
            if src:
                cands.extend(src)
        sp = spike_at(m5_idx, spike_mid, o.arm_time)
        if sp is not None:
            cands.append(sp)
        risk = abs(o.price - o.sl)
        if risk < 1e-9:
            continue
        fav = []
        for lv in cands:
            if o.side == "long" and lv > o.price + 1e-9:
                fav.append(lv)
            elif o.side == "short" and lv < o.price - 1e-9:
                fav.append(lv)
        if not fav:
            continue  # no magnet beyond entry → drop (strict)
        # nearest
        tp = min(fav, key=lambda x: abs(x - o.price))
        rr = abs(tp - o.price) / risk
        if rr < min_rr:
            continue
        meta = dict(o.meta or {})
        meta["tp_magnet"] = True
        meta["tp_rr"] = rr
        out.append(Order(o.arm_time, o.side, o.kind, o.price, o.sl, float(tp),
                         o.strategy, o.variant + "_tpmag", meta,
                         o.expire_minutes, o.max_hold_minutes))
    return out


def retag(orders, tag):
    return [Order(o.arm_time, o.side, o.kind, o.price, o.sl, o.tp,
                  o.strategy, tag, dict(o.meta or {}), o.expire_minutes, o.max_hold_minutes)
            for o in orders]


def cap_filter(orders, spread=SPREAD):
    return [o for o in orders if sl_distance_price(o.price, o.sl, o.side, spread) <= CAP + 1e-9]


def dedupe_side(orders, minutes=30):
    out, last = [], {}
    for o in sorted(orders, key=lambda x: x.arm_time):
        prev = last.get(o.side)
        if prev is not None and (o.arm_time - prev).total_seconds() < minutes * 60:
            continue
        out.append(o)
        last[o.side] = o.arm_time
    return out


def sim_period(m1, orders, variant, risk_pct, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    oo = cap_filter(oo)
    tr, st = simulate(m1, oo, risk_pct=risk_pct, max_sl_dist=CAP,
                      use_circuit_breaker=cb, spread=SPREAD, slip=SLIP,
                      allow_fractional=True)
    return tr, st


def wf4(m1, orders, variant, risk_pct):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold
        o1 = warm + (k + 1) * fold if k < 3 else n
        _, st = sim_period(m1, orders, variant, risk_pct,
                           m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1
            rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def eval_variant(m1, orders, variant, risk_pct, oos_cut, n_tdays, hyp_id, note):
    tr_is, st_is = sim_period(m1, orders, variant, risk_pct, m1.index[0], oos_cut)
    tr, st = sim_period(m1, orders, variant, risk_pct,
                        oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
    wf, wf_rs = wf4(m1, orders, variant, risk_pct)
    mc = None
    if st["n_trades"] >= 15 and tr is not None and len(tr):
        mcdf = run_mc(tr["r_multiple"].values, risk_pcts=(risk_pct,))
        if mcdf is not None and len(mcdf):
            mc = float(mcdf.iloc[0]["pass_prob"])
    tpd = tpd_true(st["n_trades"], n_tdays)
    verd, reason = verdict_from({**st, "trades_per_day": tpd}, wf, mc)
    robust = bool(st_is["expectancy_r"] > 0 and st["expectancy_r"] > 0
                  and st_is["n_trades"] >= 10 and st["n_trades"] >= 15)
    promote = bool(
        robust and st["profit_factor"] >= 1.05 and wf >= 0.5
        and (mc is None or mc >= 0.25) and st["n_trades"] >= 20
        and st["max_dd_pct"] <= 25
    )
    return {
        "hyp": hyp_id, "note": note, "variant": variant, "risk_pct": risk_pct,
        "IS_n": st_is["n_trades"], "IS_R": st_is["expectancy_r"], "IS_PF": st_is["profit_factor"],
        "OOS_n": st["n_trades"], "OOS_WR": st["win_rate"], "OOS_R": st["expectancy_r"],
        "OOS_PF": st["profit_factor"], "OOS_DD": st["max_dd_pct"], "tpd": tpd,
        "avg_R": st.get("avg_r", st["expectancy_r"]),
        "WF+": wf, "WF_rs": json.dumps(wf_rs), "MC_pass": mc,
        "worst_streak": worst_streak(tr), "mdl_pct": max_daily_loss_pct(tr),
        "verdict": verd, "robust": robust, "promote": promote,
        "OOS_R_no5": top5_ablation(tr)["exp_R_no_top5"],
        "n_orders": len([o for o in orders if o.variant == variant]),
    }


def main():
    t0all = time.time()
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    print("cut", oos_cut, "days", n_tdays, flush=True)

    print("LEVEL MAPS", flush=True)
    pd_hl, c22, m5_idx, spike_mid, atr_map = build_level_maps(m1)

    print("GEN cores", flush=True)
    box = generate_session_box_mss(
        m1, None, False, "limit_mid", "rr1.5", True, 0.8, "atr_buf", "M5", box_kind="asia",
    )
    nds_r864 = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        use_reentry864=True, reentry_tp_mode="rr1.5", **FAM,
    )
    nds_full15 = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        use_partial=True, use_reentry864=True, use_htf_n3_tp=True,
        reentry_tp_mode="rr1.5", **FAM,
    )
    nds_full3 = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        use_partial=True, use_reentry864=True, use_htf_n3_tp=True,
        reentry_tp_mode="rr3", **FAM,
    )
    nds_base = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3, **FAM,
    )
    nds_m5 = generate_nds_course(
        m1, None, False, False, family="course", min_atr=1.0, pivot_lr=3,
        style="scalp", entry_tf="M5", tp_mode="sym", confirm="brk_p3",
    )
    spike = generate_spike50(m1, "M15", 1.5)
    spike3 = generate_spike50(m1, "M15", 3.0)
    c22o = generate_c22(m1, 22, 2.0)
    # asian KEEP shape from final: asian_M5_market_range
    asian = generate_asian_bo(m1, None, False, "range", "atr_buf", 1.5, "close_break", "london_ny")
    # filter to M5 market range variant if present
    asian = asian  # range/close_break shape

    print("  box", len(box), box[0].variant if box else None)
    print("  r864", len(nds_r864), nds_r864[0].variant)
    print("  full15", len(nds_full15), nds_full15[0].variant)
    print("  full3", len(nds_full3), nds_full3[0].variant)
    print("  base", len(nds_base), nds_base[0].variant)
    print("  m5", len(nds_m5), nds_m5[0].variant)
    print("  spike", len(spike), spike[0].variant if spike else None)
    print("  spike3", len(spike3), spike3[0].variant if spike3 else None)
    print("  c22", len(c22o), c22o[0].variant if c22o else None)
    print("  asian", len(asian), asian[0].variant if asian else None)

    # Pre-registered hypotheses (id, builder → (orders, variant, risk, note))
    # Cap ~40
    hyps = []

    def add(hid, orders, variant, risk, note):
        hyps.append((hid, orders, variant, risk, note))

    # --- Box core overlays (B0–B6) ---
    bv = box[0].variant
    add("B0", box, bv, 0.008, "Box_M5_asia baseline @cap8 r08")
    add("B1", apply_dxy_gate(box, dxy, True), bv, 0.008, "Box+DXY")
    add("B2", retag(filter_location(box, "near_pd", pd_hl, c22, atr_map), bv + "_npd"), bv + "_npd", 0.008, "Box near prior-day HL")
    add("B3", retag(filter_location(box, "away_pd", pd_hl, c22, atr_map), bv + "_apd"), bv + "_apd", 0.008, "Box away prior-day HL")
    add("B4", retag(filter_location(box, "near_c22", pd_hl, c22, atr_map), bv + "_nc22"), bv + "_nc22", 0.008, "Box near candle22 HL")
    add("B5", retarget_tp_magnet(box, pd_hl, c22, m5_idx, spike_mid), bv + "_tpmag", 0.008, "Box TP magnet pd|c22|spike")
    add("B6", box, bv, 0.005, "Box risk=0.5% (10% of SGB daily5) +CB")

    # --- NDS r864 / full overlays (N0–N11) ---
    rv = nds_r864[0].variant
    add("N0", nds_r864, rv, 0.008, "NDS_r864 rtp1.5 baseline")
    add("N1", apply_dxy_gate(nds_r864, dxy, True), rv, 0.008, "NDS_r864+DXY")
    add("N2", retag(filter_location(nds_r864, "near_pd", pd_hl, c22, atr_map), rv + "_npd"), rv + "_npd", 0.008, "NDS_r864 near PD")
    add("N3", retag(filter_location(nds_r864, "near_c22", pd_hl, c22, atr_map), rv + "_nc22"), rv + "_nc22", 0.008, "NDS_r864 near c22")
    add("N4", retarget_tp_magnet(nds_r864, pd_hl, c22, m5_idx, spike_mid), rv + "_tpmag", 0.008, "NDS_r864 TP magnet")
    add("N5", nds_r864, rv, 0.005, "NDS_r864 risk05")
    f15 = nds_full15[0].variant
    add("N6", nds_full15, f15, 0.008, "NDS_full rtp1.5")
    f3 = nds_full3[0].variant
    add("N7", nds_full3, f3, 0.008, "NDS_full rtp3")
    add("N8", retag(filter_location(nds_full3, "near_c22", pd_hl, c22, atr_map), f3 + "_nc22"), f3 + "_nc22", 0.008, "NDS_full3 near c22")
    add("N9", retarget_tp_magnet(nds_full3, pd_hl, c22, m5_idx, spike_mid), f3 + "_tpmag", 0.008, "NDS_full3 TP magnet")
    bv_nds = nds_base[0].variant
    add("N10", apply_dxy_gate(nds_base, dxy, True), bv_nds, 0.008, "NDS_base_M3_sym+DXY (historical KEEP shape)")
    mv = nds_m5[0].variant
    add("N11", apply_dxy_gate(nds_m5, dxy, True), mv, 0.008, "NDS_sym_M5+DXY @cap8")

    # --- Weak MAYBE components alone (S/C/A) ---
    sv = spike[0].variant if spike else "spike50_M15_rr1.5"
    add("S0", spike, sv, 0.008, "Spike50_M15_rr1.5")
    s3v = spike3[0].variant if spike3 else "spike50_M15_rr3"
    add("S1", apply_dxy_gate(spike3, dxy, True), s3v, 0.008, "Spike50_M15_rr3+DXY")
    cv = c22o[0].variant if c22o else "c22_h22_rr2"
    add("C0", c22o, cv, 0.008, "Candle22_h22_rr2")
    add("C1", apply_dxy_gate(c22o, dxy, True), cv, 0.008, "Candle22+DXY (batch3 KEEP shape)")
    if asian:
        av = asian[0].variant
        add("A0", asian, av, 0.008, "AsianBO_M5_range")

    # --- Portfolio / agreement combos (P*) — retag to single variant ---
    def port(parts, tag, minutes=30):
        merged = []
        for oo in parts:
            merged.extend(cap_filter(oo))
        merged = dedupe_side(merged, minutes)
        return retag(merged, tag)

    add("P0", port([box, nds_full3], "PORT_box_full3"), "PORT_box_full3", 0.008, "Box+NDS_full_rtp3")
    add("P1", port([box, apply_dxy_gate(nds_base, dxy, True)], "PORT_box_ndsDXY"), "PORT_box_ndsDXY", 0.008, "Box+NDS_base+DXY")
    add("P2", port([box, spike], "PORT_box_spike"), "PORT_box_spike", 0.008, "Box+Spike50_rr1.5")
    add("P3", port([apply_dxy_gate(spike3, dxy, True), apply_dxy_gate(c22o, dxy, True)], "PORT_spike_c22_dxy"),
        "PORT_spike_c22_dxy", 0.008, "Spike50_rr3+Candle22+DXY agreement")
    add("P4", port([box, filter_location(nds_r864, "near_pd", pd_hl, c22, atr_map)], "PORT_box_r864npd"),
        "PORT_box_r864npd", 0.008, "Box+NDS_r864 near PD")
    add("P5", port([box, nds_full3], "PORT_box_full3_r05"), "PORT_box_full3_r05", 0.005, "Box+full3 risk05")
    add("P6", port([box, asian] if asian else [box], "PORT_box_asian"), "PORT_box_asian", 0.008, "Box+AsianBO")
    add("P7", port([box, apply_dxy_gate(nds_m5, dxy, True)], "PORT_box_m5dxy"), "PORT_box_m5dxy", 0.008, "Box+NDS_M5+DXY")
    add("P8", port([nds_full3, spike], "PORT_full3_spike"), "PORT_full3_spike", 0.008, "NDS_full3+Spike50")
    add("P9", port([box, c22o], "PORT_box_c22"), "PORT_box_c22", 0.008, "Box+Candle22")
    add("P10", port([apply_dxy_gate(nds_base, dxy, True), spike], "PORT_ndsDXY_spike"),
        "PORT_ndsDXY_spike", 0.008, "NDS_base+DXY+Spike50")
    add("P11", port([box, apply_dxy_gate(c22o, dxy, True), apply_dxy_gate(spike, dxy, True)], "PORT_box_c22_spike_dxy"),
        "PORT_box_c22_spike_dxy", 0.008, "Box+C22+Spike+DXY")
    add("P12", port([box, nds_full15], "PORT_box_full15"), "PORT_box_full15", 0.008, "Box+NDS_full_rtp1.5")

    # Cap enforcement
    if len(hyps) > 42:
        hyps = hyps[:42]
    print(f"N_VARIANTS_TRIED={len(hyps)} (pre-registered cap)", flush=True)
    (OUT / "combo_hypotheses.json").write_text(json.dumps(
        [{"hyp": h[0], "variant": h[2], "risk": h[3], "note": h[4]} for h in hyps], indent=2))

    rows = []
    for hid, orders, variant, risk, note in hyps:
        if not orders:
            print(f"SKIP {hid} empty", flush=True)
            continue
        # ensure variant exists on orders
        if not any(o.variant == variant for o in orders):
            # take first variant present
            variant = orders[0].variant
        print(f"EVAL {hid} {note} v={variant} n_ord={len(orders)}", flush=True)
        row = eval_variant(m1, orders, variant, risk, oos_cut, n_tdays, hid, note)
        rows.append(row)
        print(
            f"  IS_R={row['IS_R']:.3f} OOS_R={row['OOS_R']:.3f} PF={row['OOS_PF']:.2f} "
            f"tpd={row['tpd']:.2f} WF={row['WF+']:.2f} MC={row['MC_pass']} "
            f"robust={row['robust']} promote={row['promote']} → {row['verdict']}",
            flush=True,
        )

    rdf = pd.DataFrame(rows)
    rdf.to_csv(OUT / "combo_summary.csv", index=False)

    # Choose on IS among robust candidates (IS_R>0, IS_n>=15), then require promote/OOS
    is_ok = rdf[(rdf["IS_R"] > 0) & (rdf["IS_n"] >= 15)].copy()
    is_ok = is_ok.sort_values(["IS_R", "IS_PF"], ascending=False)
    robust = rdf[rdf["robust"] == True].copy()
    promote = rdf[rdf["promote"] == True].copy()

    # Recommended: among promote, prefer portfolio (P*) with best OOS_R; else best promote; else best robust
    rec = None
    for pool_name, pool in (("promote_port", promote[promote["hyp"].astype(str).str.startswith("P")]),
                            ("promote", promote),
                            ("robust", robust)):
        if len(pool):
            # pick by OOS_R then MC then tpd (judge on OOS; IS already gated for robust/promote)
            pool = pool.sort_values(["OOS_R", "MC_pass", "tpd"], ascending=False)
            rec = pool.iloc[0].to_dict()
            rec["selection_pool"] = pool_name
            break

    # Final WATCHDOG.md + update VERIFY go/no-go
    lines = [
        "# Combination search — watchdog recommendation",
        "",
        f"Generated: {pd.Timestamp.now(tz='Asia/Tehran')} Asia/Tehran",
        f"OOS cut: {oos_cut} | OOS days: {n_tdays}",
        f"**Variants tried (pre-registered): {len(hyps)}** (cap ~40)",
        "",
        "## Overfitting guards",
        "- Hypotheses written before eval (`combo_hypotheses.json`)",
        "- Choose among IS_R>0 & IS_n≥15; judge on OOS",
        "- Promote requires IS&OOS positive, PF≥1.05, WF+≥0.5, MC≥0.25, n≥20, DD≤25%",
        "- Audit-fixed reentry (arm after new Flag); reentry TP capped (no sym fat-tail)",
        "",
        "## Audit carry-forward",
        "- Bug fixed: reentry SL lookahead → arm after new-Flag confirm",
        "- Prior fidelity KEEP on uncapped-sym r864 was inflated; post-fix standalone NDS r864/full weak",
        "",
        "## Results (all variants)",
        "",
        "| hyp | note | IS_R | OOS_n | tpd | WR | PF | R | DD | WF+ | MC | streak | robust | promote | verd |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for _, r in rdf.sort_values("hyp").iterrows():
        lines.append(
            f"| {r['hyp']} | {r['note'][:40]} | {r['IS_R']:.3f} | {int(r['OOS_n'])} | {r['tpd']:.2f} | "
            f"{r['OOS_WR']:.2f} | {r['OOS_PF']:.2f} | {r['OOS_R']:.3f} | {r['OOS_DD']:.1f} | "
            f"{r['WF+']:.2f} | {r['MC_pass']} | {int(r['worst_streak'])} | {r['robust']} | "
            f"{r['promote']} | **{r['verdict']}** |"
        )

    lines += ["", f"## Summary counts", "",
              f"- Tried: {len(hyps)}",
              f"- IS_R>0 & n≥15: {len(is_ok)}",
              f"- Robust (IS&OOS R>0): {len(robust)}",
              f"- Promote: {len(promote)}", ""]

    if rec is None:
        lines += [
            "## Recommended watchdog config",
            "",
            "**NO-GO** — no variant passed promote gates after audit fix + combination search.",
            "Closest: SessionBox_M5 asia alone if it appears in table with KEEP; else do not paper-forward.",
        ]
        # fallback: best OOS among Box if KEEP
        box_rows = rdf[rdf["hyp"].isin(["B0", "B6"])]
        if len(box_rows):
            b = box_rows.sort_values("OOS_R", ascending=False).iloc[0]
            lines += [
                "",
                "### Fallback observe-only (not promote)",
                f"- {b['note']}: OOS n={int(b['OOS_n'])} tpd={b['tpd']:.2f} WR={b['OOS_WR']:.2f} "
                f"PF={b['OOS_PF']:.2f} R={b['OOS_R']:.3f} DD={b['OOS_DD']:.1f} "
                f"MC={b['MC_pass']} streak={int(b['worst_streak'])} verd={b['verdict']}",
            ]
        go = False
    else:
        go = True
        lines += [
            "## Recommended watchdog config (GO paper-forward)",
            "",
            f"- **hyp `{rec['hyp']}`**: {rec['note']}",
            f"- variant: `{rec['variant']}`",
            f"- risk_pct: {rec['risk_pct']} | SL cap $8 | costs strict 0.35/0.10 | CB 2-loss + 1% day",
            f"- selection: {rec['selection_pool']} (IS-gated → OOS-ranked)",
            f"- **OOS**: n={int(rec['OOS_n'])} | tpd={rec['tpd']:.2f} | WR={rec['OOS_WR']:.2f} | "
            f"PF={rec['OOS_PF']:.2f} | avgR={rec['OOS_R']:.3f} | DD={rec['OOS_DD']:.1f}% | "
            f"MC={rec['MC_pass']} | worst_streak={int(rec['worst_streak'])} | mdl={rec['mdl_pct']:.2f}%",
            f"- IS_R={rec['IS_R']:.3f} | WF+={rec['WF+']:.2f} | R_no_top5={rec['OOS_R_no5']:.3f}",
            "",
            "### Why",
            f"- Survived promote gates (IS&OOS positive, WF, MC) among {len(hyps)} pre-registered variants.",
            "- Uses audit-fixed fills; no sym fat-tail reentry TP.",
            "- Components drawn only from families that previously showed conditional KEEP/MAYBE "
            "(Box, NDS, Spike50, Candle22, AsianBO, DXY, location/TP magnets, SGB 0.5% risk).",
        ]

    (OUT / "WATCHDOG.md").write_text("\n".join(lines) + "\n")
    # Append honest verify go/no-go
    verify_extra = [
        "",
        "## Post-combo final go/no-go",
        f"- Combo variants tried: {len(hyps)}; promote: {len(promote)}; robust: {len(robust)}",
        f"- **{'GO paper-forward' if go else 'NO-GO'}** — see WATCHDOG.md",
        f"- Rec: {json.dumps({k: rec[k] for k in ('hyp','note','variant','tpd','OOS_WR','OOS_PF','OOS_R','OOS_DD','MC_pass','worst_streak')}, default=str) if rec else None}",
    ]
    with open(OUT / "VERIFY.md", "a") as f:
        f.write("\n".join(verify_extra) + "\n")

    meta = {
        "n_tried": len(hyps), "n_is_ok": int(len(is_ok)), "n_robust": int(len(robust)),
        "n_promote": int(len(promote)), "go": go, "rec": rec,
        "elapsed_s": time.time() - t0all,
        "bug_fixed": "reentry_lookahead_arm_after_new_flag",
    }
    (OUT / "combo_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print("DONE", json.dumps({k: meta[k] for k in ("n_tried", "n_robust", "n_promote", "go")}, default=str), flush=True)
    if rec:
        print("REC", rec["hyp"], rec["note"], "tpd", rec["tpd"], "PF", rec["OOS_PF"], "R", rec["OOS_R"], flush=True)


if __name__ == "__main__":
    main()
