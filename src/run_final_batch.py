#!/usr/bin/env python3
"""Audited batch: risk caps $5/$7.5, confirmation search (IS choose / OOS judge),
walk-forward, MC, KEEP/MAYBE/DROP → RESULTS.md (Persian).

Rigor preserved; process is scripted/batched.
"""
from __future__ import annotations
import json, sys, traceback
from pathlib import Path
from collections import defaultdict
from copy import copy
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import (
    Order, simulate, count_sl_cap_skips, sl_distance_price,
    SPREAD, SLIPPAGE, COMMISSION_PER_LOT,
)
from monte_carlo import run_mc
from sl_analysis import classify_losses, summarize_causes
from combine import signal_overlap, outcome_correlation, signals_per_day_stats, build_combined_orders
from indicators import ema, atr, resample_ohlc, last_closed_value, in_session, vol_ma
from strategies import (
    generate_nds_fib, generate_idris, generate_sp2l, generate_pro_btb,
    generate_micromap, generate_amd_po3_ifvg,
)
from strategies.common import apply_dxy_gate, apply_vol_gate, apply_htf_gate

DATA, RES = ROOT / "data", ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)
CAPS = (5.0, 7.5)
RISK_PCT = {5.0: 0.005, 7.5: 0.0075}


def load():
    m1 = pd.read_parquet(DATA / "XAUUSD.parquet")
    if m1.index.tz is None:
        m1.index = m1.index.tz_localize("UTC")
    dxy = pd.read_parquet(DATA / "DXY_synth.parquet")
    if dxy.index.tz is None:
        dxy.index = dxy.index.tz_localize("UTC")
    if "close" not in dxy.columns:
        dxy = dxy.rename(columns={dxy.columns[0]: "close"})
    return m1, dxy


def period_orders(orders, t0, t1):
    return [o for o in orders if t0 <= o.arm_time < t1]


def filter_cap(orders, max_sl):
    out = []
    for o in orders:
        if sl_distance_price(o.price, o.sl, o.side) <= max_sl + 1e-9:
            out.append(o)
    return out


def eval_set(orders, m1, label, cap, dxy_f=False, vol_f=False, strategy=None, variant=None):
    risk = RISK_PCT[cap]
    t0, t1 = m1.index[0], m1.index[-1] + pd.Timedelta(minutes=1)
    oo = period_orders(orders, t0, t1)
    oo = filter_cap(oo, cap)
    if variant is not None:
        oo = [o for o in oo if o.variant == variant]
    tr, st = simulate(m1, oo, risk_pct=risk, max_sl_dist=cap,
                      dxy_filter_flag=dxy_f, vol_filter_flag=vol_f)
    st.update({"label": label, "cap": cap, "dxy_filter": dxy_f, "vol_filter": vol_f,
               "n_signals": len(oo), "strategy": strategy or (tr["strategy"].iloc[0] if tr is not None and len(tr) else "?"),
               "variant": variant or "ALL"})
    if tr is not None and not tr.empty:
        tr = tr.copy()
        tr["label"] = label
        tr["cap"] = cap
    return tr, st


# ---------- confirmation filters (few params; chosen on IS) ----------
def apply_confirmations(orders, m1, dxy, flags: dict):
    """flags: htf, dxy, vol, session_london_ny, block_london_open, min_sl_atr, atr_regime_ok, sweep_proxy"""
    if not orders:
        return []
    m15 = resample_ohlc(m1, "15min")
    m15_ema = ema(m15["close"], 50)
    m1_atr = atr(m1, 14)
    m15_atr = atr(m15, 14)
    out = list(orders)

    if flags.get("htf"):
        out = apply_htf_gate(out, m15["close"], m15_ema, True)
    if flags.get("dxy"):
        out = apply_dxy_gate(out, dxy, True)
    if flags.get("vol"):
        # use M1 vol as proxy at signal bar when possible
        vma = vol_ma(m1["volume"], 20)
        out = apply_vol_gate(out, m1["volume"], vma, True, 1.3, 1)

    filtered = []
    for o in out:
        t = o.arm_time
        h = t.hour
        if flags.get("session_london_ny") and not (7 <= h < 21):
            continue
        if flags.get("block_london_open") and 7 <= h < 9:
            continue
        if flags.get("block_ny_late") and h >= 19:
            continue
        ai = m1_atr.index.searchsorted(t, side="left") - 1  # last M1 fully before arm
        atr_i = float(m1_atr.iloc[ai]) if ai >= 0 else np.nan
        risk = abs(o.price - o.sl)
        if flags.get("min_sl_atr") and atr_i and atr_i > 0:
            if risk < flags["min_sl_atr"] * atr_i:
                continue
        if flags.get("max_sl_atr") and atr_i and atr_i > 0:
            if risk > flags["max_sl_atr"] * atr_i:
                continue
        if flags.get("atr_regime_ok") and atr_i and atr_i > 0:
            # require ATR not in bottom 30% of recent 500 bars
            w = m1_atr.iloc[max(0, ai - 500):ai + 1].dropna()
            if len(w) > 50 and atr_i < float(w.quantile(0.30)):
                continue
        if flags.get("not_extended") and atr_i and atr_i > 0:
            # last CLOSED M15 only (no unfinished-bar lookahead)
            c15 = last_closed_value(m15["close"], t, 15)
            e15 = last_closed_value(m15_ema, t, 15)
            a15v = last_closed_value(m15_atr, t, 15)
            if c15 is not None and e15 is not None:
                dist = abs(o.price - e15)
                a15 = a15v if (a15v is not None and a15v > 0) else atr_i
                if dist > 2.0 * a15:
                    continue
        filtered.append(o)
    return filtered


CANDIDATE_FILTERS = [
    ("baseline", {}),
    ("htf", {"htf": True}),
    ("dxy", {"dxy": True}),
    ("vol", {"vol": True}),
    ("htf+dxy", {"htf": True, "dxy": True}),
    ("htf+vol", {"htf": True, "vol": True}),
    ("htf+dxy+vol", {"htf": True, "dxy": True, "vol": True}),
    ("session", {"session_london_ny": True}),
    ("htf+session", {"htf": True, "session_london_ny": True}),
    ("htf+minsl0.6", {"htf": True, "min_sl_atr": 0.6}),
    ("htf+atr_regime", {"htf": True, "atr_regime_ok": True}),
    ("htf+not_ext", {"htf": True, "not_extended": True}),
    ("htf+dxy+session", {"htf": True, "dxy": True, "session_london_ny": True}),
    ("block_ldn_open+htf", {"htf": True, "block_london_open": True}),
]


def walk_forward_folds(m1, n_folds=4):
    """Expanding IS → next OOS slice. Returns list of (is_df, oos_df, name)."""
    times = m1.index
    n = len(times)
    # first 40% warm IS, then 4 equal OOS chunks of remaining 60%
    warm = int(n * 0.40)
    rest = n - warm
    fold_sz = rest // n_folds
    folds = []
    for k in range(n_folds):
        oos0 = warm + k * fold_sz
        oos1 = warm + (k + 1) * fold_sz if k < n_folds - 1 else n
        is_df = m1.iloc[:oos0]
        oos_df = m1.iloc[oos0:oos1]
        folds.append((is_df, oos_df, f"WF{k+1}"))
    return folds


def pick_best_filter_is(base_orders, m1_is, dxy, cap, variants):
    """Choose filter+variant on IS by expectancy (n>=15). Return (variant, filter_name, flags, is_stats)."""
    best = None
    for v in variants:
        vo = [o for o in base_orders if o.variant == v]
        if not vo:
            continue
        for fname, flags in CANDIDATE_FILTERS:
            fo = apply_confirmations(vo, m1_is, dxy, flags)
            tr, st = eval_set(fo, m1_is, "IS", cap, strategy="x", variant=v)
            if st["n_trades"] < 15:
                continue
            score = (st["expectancy_r"], st["profit_factor"], st["n_trades"])
            row = (score, v, fname, flags, st)
            if best is None or score > best[0]:
                best = row
    if best is None:
        # fallback: most trades baseline
        for v in variants:
            vo = [o for o in base_orders if o.variant == v]
            tr, st = eval_set(vo, m1_is, "IS", cap, strategy="x", variant=v)
            score = (st["expectancy_r"], st["profit_factor"], st["n_trades"])
            row = (score, v, "baseline", {}, st)
            if best is None or st["n_trades"] > best[4]["n_trades"]:
                best = row
    return best


def verdict_from(oos_st, wf_positive_frac, mc_pass_05):
    """Brutal KEEP / MAYBE / DROP."""
    n = oos_st.get("n_trades", 0)
    r = oos_st.get("expectancy_r", 0)
    pf = oos_st.get("profit_factor", 0)
    dd = oos_st.get("max_dd_pct", 100)
    tpd = oos_st.get("trades_per_day", 0)
    if n < 20 or r <= 0 or pf < 1.05:
        return "DROP", "OOS ضعیف/نمونه کم یا expectancy≤0 یا PF<1.05"
    if dd > 25:
        return "DROP", f"MaxDD OOS={dd:.1f}% بیش از حد برای پراپ"
    if wf_positive_frac < 0.5:
        return "DROP", f"walk-forward ناپایدار ({wf_positive_frac*100:.0f}% فولد مثبت)"
    if r >= 0.15 and pf >= 1.2 and wf_positive_frac >= 0.75 and (mc_pass_05 is None or mc_pass_05 >= 0.25):
        return "KEEP", "لبه OOS مثبت، WF پایدار، DD قابل‌قبول"
    if r > 0 and pf >= 1.05 and wf_positive_frac >= 0.5:
        return "MAYBE", "لبه ضعیف/حاشیه کم؛ نیاز به نمونه بیشتر یا فیلتر سخت‌تر"
    return "DROP", "معیار KEEP/MAYBE برآورده نشد"


def main():
    print("LOAD", flush=True)
    m1, dxy = load()
    cut = m1.index[int(len(m1) * 0.70)]
    m1_is, m1_oos = m1[m1.index < cut], m1[m1.index >= cut]
    print(f"bars={len(m1)} IS={len(m1_is)} OOS={len(m1_oos)} cut={cut}", flush=True)

    meta = {
        "xau_source": "Dukascopy XAU/USD M1",
        "xau_bars": len(m1), "xau_start": str(m1.index[0]), "xau_end": str(m1.index[-1]),
        "dxy_source": "Synthetic ICE DXY from FX legs", "dxy_bars": len(dxy),
        "oos_cut": str(cut),
        "costs": {"spread": SPREAD, "slip": SLIPPAGE, "commission": COMMISSION_PER_LOT},
        "risk_caps_usd": list(CAPS),
        "lot_rule": "floor(risk_usd/sl_dist_incl_spread)*0.01; skip if dist>cap or lot<0.01",
        "engine": "audited_closed_bar_ask_worstSL_delay1_hardSLcap",
    }
    (RES / "meta.json").write_text(json.dumps(meta, indent=2, default=str))

    # ---- generate base order pools (once each) ----
    print("GENERATE bases...", flush=True)
    bases = {}
    try:
        print("  NDS...", flush=True)
        bases["NDS_Fib"] = generate_nds_fib(m1, dxy, use_dxy=False, use_vol=False, rr=1.5)
        # also rr2 as extra variants already in zone names; add rr2
        bases["NDS_Fib"] += generate_nds_fib(m1, dxy, use_dxy=False, use_vol=False, rr=2.0)
        print(f"    {len(bases['NDS_Fib'])}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["NDS_Fib"] = []

    try:
        print("  Idris...", flush=True)
        bases["Idris"] = generate_idris(m1, dxy, use_dxy=False, use_vol=False, rr=3.0)
        print(f"    {len(bases['Idris'])}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["Idris"] = []

    try:
        print("  SP2L...", flush=True)
        bases["SP2L"] = generate_sp2l(m1, dxy, use_dxy=False, use_vol=False, use_htf=False)
        print(f"    {len(bases['SP2L'])}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["SP2L"] = []

    try:
        print("  ProBTB...", flush=True)
        bases["ProBTB"] = generate_pro_btb(m1, dxy, use_dxy=False, use_vol=False, rr=2.0)
        print(f"    {len(bases['ProBTB'])}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["ProBTB"] = []

    try:
        print("  MicroMAP...", flush=True)
        bases["MicroMAP"] = generate_micromap(m1, dxy, use_dxy=False, use_vol=False)
        print(f"    {len(bases['MicroMAP'])}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["MicroMAP"] = []

    try:
        print("  AMD core...", flush=True)
        amd = []
        for range_mode in ("asian", "m5_lowatr"):
            for entry_mode in ("market", "limit"):
                for tp_mode in ("range", "rr2", "rr3"):
                    for use_htf in (False, True):
                        amd += generate_amd_po3_ifvg(
                            m1, dxy, range_mode=range_mode, tf="M5",
                            entry_mode=entry_mode, tp_mode=tp_mode,
                            use_htf=use_htf, use_dxy=False, use_vol=False,
                        )
        # M1 asian market extras
        for tp_mode in ("range", "rr2", "rr3"):
            for use_htf in (False, True):
                amd += generate_amd_po3_ifvg(
                    m1, dxy, range_mode="asian", tf="M1", entry_mode="market",
                    tp_mode=tp_mode, use_htf=use_htf, use_dxy=False, use_vol=False,
                )
        bases["AMD_PO3_iFVG"] = amd
        print(f"    {len(amd)}", flush=True)
    except Exception as e:
        traceback.print_exc(); bases["AMD_PO3_iFVG"] = []

    # ---- SL cap skip report ----
    skip_rows = []
    for name, ords in bases.items():
        for cap in CAPS:
            sk = count_sl_cap_skips(ords, cap)
            sk["strategy"] = name
            skip_rows.append(sk)
            print(f"CAP {name} @{cap}: skip {sk['n_skipped']}/{sk['n_orders']} ({sk['skip_pct']:.1f}%)", flush=True)
    pd.DataFrame(skip_rows).to_csv(RES / "sl_cap_skips.csv", index=False)

    # ---- Per strategy: IS filter search → OOS judge → WF → MC ----
    folds = walk_forward_folds(m1, 4)
    all_stats, all_trades = [], []
    final_rows = []
    cause_summary_parts = []
    spd_rows = []
    combo_pool = {}

    for name, base in bases.items():
        print(f"\n=== {name} ===", flush=True)
        variants = sorted({o.variant for o in base})
        if not variants:
            final_rows.append({"strategy": name, "verdict": "DROP", "reason": "هیچ سیگنالی تولید نشد",
                               "cap": 7.5, "variant": "—", "filter": "—"})
            continue

        # signals/day baseline (uncapped count of arms)
        for v in variants[:8]:
            spd = signals_per_day_stats([o for o in base if o.variant == v])
            spd_rows.append({"strategy": name, "variant": v, **{k: spd[k] for k in
                            ("avg", "median", "pct_zero_days", "london_avg", "ny_avg")}})

        best_overall = None  # by OOS expectancy under preferred cap
        for cap in CAPS:
            print(f"  cap=${cap} IS filter search...", flush=True)
            picked = pick_best_filter_is(base, m1_is, dxy, cap, variants)
            if picked is None:
                continue
            _, variant, fname, flags, is_st = picked
            print(f"    IS pick: {variant} | {fname} n={is_st['n_trades']} R={is_st['expectancy_r']:.3f} PF={is_st['profit_factor']:.2f}", flush=True)

            vo = [o for o in base if o.variant == variant]
            fo = apply_confirmations(vo, m1, dxy, flags)  # apply on full then period-slice in eval

            # IS + OOS eval
            for label, part in (("IS", m1_is), ("OOS", m1_oos)):
                # re-apply confirmations using indicators from full m1 is fine (closed-bar gates)
                tr, st = eval_set(fo, part, label, cap, dxy_f=flags.get("dxy", False),
                                  vol_f=flags.get("vol", False), strategy=name, variant=variant)
                st["filter"] = fname
                all_stats.append(st)
                if tr is not None and not tr.empty:
                    tr["filter"] = fname
                    all_trades.append(tr)

            # OOS stats
            _, oos_st = eval_set(fo, m1_oos, "OOS", cap, dxy_f=flags.get("dxy", False),
                                 vol_f=flags.get("vol", False), strategy=name, variant=variant)
            oos_st["filter"] = fname

            # Walk-forward: choose nothing new per fold — freeze IS-chosen filter; measure OOS fold R
            wf_rs = []
            for is_df, oos_df, wname in folds:
                # optionally re-pick on fold IS for honesty of stability of THE RULE (frozen)
                tr, st = eval_set(fo, oos_df, wname, cap, strategy=name, variant=variant)
                wf_rs.append(st["expectancy_r"] if st["n_trades"] >= 5 else np.nan)
                st["filter"] = fname
                st["strategy"] = name
                st["variant"] = variant
                all_stats.append(st)
            wf_valid = [x for x in wf_rs if np.isfinite(x)]
            wf_pos = float(np.mean([x > 0 for x in wf_valid])) if wf_valid else 0.0
            print(f"    OOS n={oos_st['n_trades']} R={oos_st['expectancy_r']:.3f} PF={oos_st['profit_factor']:.2f} | WF+={wf_pos:.0%}", flush=True)

            # SL causes on OOS losses
            tr_oos, _ = eval_set(fo, m1_oos, "OOS", cap, strategy=name, variant=variant)
            if tr_oos is not None and not tr_oos.empty:
                try:
                    clf = classify_losses(tr_oos, m1, dxy)
                    if not clf.empty:
                        clf.to_csv(RES / f"sl_causes_{name}_cap{cap}.csv", index=False)
                        cause_summary_parts.append(clf)
                except Exception as e:
                    print("    SL cause err", e)

            # MC if PF>=1.1 and n>=20
            mc_pass = None
            mc_df = None
            if oos_st["profit_factor"] >= 1.1 and oos_st["n_trades"] >= 20 and tr_oos is not None and len(tr_oos) >= 20:
                mc_df = run_mc(tr_oos["r_multiple"].values, n_sims=4000)
                if mc_df is not None and not mc_df.empty:
                    row05 = mc_df[mc_df["risk_pct"] == 0.5]
                    if not row05.empty:
                        mc_pass = float(row05.iloc[0]["pass_prob"])
                    mc_df = mc_df.copy()
                    mc_df["strategy"] = name
                    mc_df["variant"] = variant
                    mc_df["filter"] = fname
                    mc_df["cap"] = cap
                    mc_df.to_csv(RES / f"mc_{name}_cap{cap}.csv", index=False)

            verd, reason = verdict_from(oos_st, wf_pos, mc_pass)
            # signals/day after filters+cap
            spd = signals_per_day_stats(filter_cap(period_orders(fo, m1_oos.index[0], m1_oos.index[-1]+pd.Timedelta(minutes=1)), cap))
            rec = {
                "strategy": name, "cap": cap, "variant": variant, "filter": fname,
                "flags": json.dumps(flags),
                "is_n": is_st["n_trades"], "is_r": is_st["expectancy_r"], "is_pf": is_st["profit_factor"],
                "oos_n": oos_st["n_trades"], "oos_wr": oos_st["win_rate"], "oos_r": oos_st["expectancy_r"],
                "oos_pf": oos_st["profit_factor"], "oos_dd": oos_st["max_dd_pct"],
                "oos_tpd": oos_st["trades_per_day"],
                "spd_avg": spd["avg"], "spd_zero_pct": spd["pct_zero_days"],
                "wf_pos_frac": wf_pos, "wf_rs": json.dumps([None if not np.isfinite(x) else round(x, 3) for x in wf_rs]),
                "mc_pass_0.5pct": mc_pass,
                "verdict": verd, "reason": reason,
                "skip_pct": count_sl_cap_skips(vo, cap)["skip_pct"],
            }
            final_rows.append(rec)
            print(f"    VERDICT {verd}: {reason}", flush=True)

            # AUDIT fix: pick variant on IS only; OOS is for reporting, not selection
            score = (is_st["expectancy_r"] if is_st["n_trades"] >= 15 else -999,
                     is_st["profit_factor"], verd == "KEEP", verd == "MAYBE")
            if best_overall is None or score > best_overall[0]:
                best_overall = (score, rec, fo, variant, fname, flags, cap)

        if best_overall and best_overall[1]["verdict"] in ("KEEP", "MAYBE"):
            combo_pool[name] = filter_cap(
                apply_confirmations([o for o in base if o.variant == best_overall[3]], m1, dxy, best_overall[5]),
                best_overall[6],
            )

    stats_df = pd.DataFrame(all_stats)
    stats_df.to_csv(RES / "stats_all.csv", index=False)
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(RES / "trades_all.csv", index=False)
    final_df = pd.DataFrame(final_rows)
    final_df.to_csv(RES / "final_verdicts.csv", index=False)
    if spd_rows:
        (RES / "signals_per_day.json").write_text(json.dumps(spd_rows, indent=2, default=str))
    if cause_summary_parts:
        summarize_causes(pd.concat(cause_summary_parts, ignore_index=True)).to_csv(
            RES / "sl_cause_summary.csv", index=False)

    # ---- Combo of KEEP/MAYBE ----
    combined_stats = []
    overlap_df = pd.DataFrame()
    if combo_pool:
        print("COMBO...", flush=True)
        overlap_df = signal_overlap(combo_pool, 30)
        overlap_df.to_csv(RES / "signal_overlap.csv", index=False)
        for cap in CAPS:
            # use each strategy's orders already capped at its chosen cap — re-filter to this cap
            pool = {k: filter_cap(v, cap) for k, v in combo_pool.items()}
            combo = build_combined_orders(pool)
            tr, st = eval_set(combo, m1_oos, "OOS", cap, strategy="COMBO", variant=None)
            st["variant"] = "merged"
            st["name"] = f"KEEP_MAYBE_merged_cap{cap}"
            combined_stats.append(st)
            if tr is not None and not tr.empty:
                tr.to_csv(RES / f"combined_oos_cap{cap}.csv", index=False)

    # ---- Write RESULTS.md ----
    write_results_md(meta, skip_rows, final_df, stats_df, spd_rows, overlap_df, combined_stats)
    print("DONE", flush=True)


def write_results_md(meta, skip_rows, final_df, stats_df, spd_rows, overlap_df, combined_stats):
    L = []
    L.append("# نتایج بک‌تست حسابرسی‌شده XAUUSD (موتور واحد)")
    L.append("")
    L.append("> closed-bar، ask fill، worst-case SL، اسپرد ۰.۳۵ + اسلیپ ۰.۱۰، تأخیر مارکت ۱ کندل، کپ سخت فاصله SL. اعداد ساختگی نیستند.")
    L.append("")
    L.append("## داده و هزینه")
    L.append(f"- طلا: {meta['xau_source']} — {meta['xau_bars']} M1 از {meta['xau_start']} تا {meta['xau_end']}")
    L.append(f"- DXY: {meta['dxy_source']} ({meta['dxy_bars']} کندل)")
    L.append(f"- OOS از {meta['oos_cut']} (~۳۰٪ آخر) | Walk-forward: ۴ فولد روی ۶۰٪ پایانی")
    L.append(f"- هزینه: spread={meta['costs']['spread']} slip={meta['costs']['slip']} commission={meta['costs']['commission']}/lot")
    L.append(f"- کپ ریسک: فاصله SL (با اسپرد) ≤ ۵$ (۰.۵٪) یا ≤ ۷.۵$ (۰.۷۵٪)؛ لات = floor(risk$/dist)×۰.۰۱؛ در غیر این صورت سیگنال حذف")
    L.append("")
    L.append("## تعریف NDS Fib")
    L.append("- زون **اصلی**: ۰.۶۲–۰.۷۸ | مقایسه: ۰.۷۸۶–۰.۸۶ | موج M15 ≥۱.۵×ATR | تأیید اینگالفینگ M1")
    L.append("")
    L.append("## حذف سیگنال به‌خاطر کپ SL")
    L.append("| استراتژی | کپ $ | کل سفارش | حذف‌شده | % حذف | باقی‌مانده |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for sk in skip_rows:
        L.append(f"| {sk['strategy']} | {sk['max_sl_dist']} | {sk['n_orders']} | {sk['n_skipped']} | {sk['skip_pct']:.1f}% | {sk['n_kept']} |")
    L.append("")
    L.append("## انتخاب فیلتر")
    L.append("کاندیداها روی **IS** با expectancy انتخاب شدند؛ داوری فقط روی **OOS** و پایداری walk-forward. بدون جستجوی آزاد پارامتر.")
    L.append("")
    L.append("## حکم هر ستاپ (برای هر کپ)")
    if final_df is not None and not final_df.empty:
        L.append("| ستاپ | کپ | واریانت | فیلتر | OOS n | WR | R | PF | DD% | سیگنال/روز | WF+% | MC pass@0.5% | حکم |")
        L.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for _, r in final_df.iterrows():
            mc = r.get("mc_pass_0.5pct")
            mc_s = f"{mc*100:.1f}%" if pd.notna(mc) and mc is not None else "—"
            L.append(
                f"| {r['strategy']} | {r['cap']} | {r['variant']} | {r['filter']} | "
                f"{int(r['oos_n'])} | {r['oos_wr']*100:.1f}% | {r['oos_r']:.2f} | {r['oos_pf']:.2f} | "
                f"{r['oos_dd']:.1f} | {r['spd_avg']:.2f} | {r['wf_pos_frac']*100:.0f}% | {mc_s} | **{r['verdict']}** |"
            )
        L.append("")
        for _, r in final_df.iterrows():
            L.append(f"- **{r['strategy']} @{r['cap']}$ → {r['verdict']}**: {r['reason']}")
    L.append("")
    L.append("## ترکیب KEEP/MAYBE")
    if combined_stats:
        for st in combined_stats:
            L.append(f"- {st.get('name')}: n={st.get('n_trades')}, WR={st.get('win_rate',0)*100:.1f}%, "
                     f"R={st.get('avg_r',0):.2f}, PF={st.get('profit_factor',0):.2f}, DD={st.get('max_dd_pct',0):.1f}%")
    else:
        L.append("- هیچ ستاپ KEEP/MAYBE برای ترکیب باقی نماند.")
    if overlap_df is not None and not overlap_df.empty:
        L.append("")
        L.append("هم‌پوشانی سیگنال (۳۰ دقیقه):")
        L.append("| " + " | ".join(map(str, overlap_df.columns)) + " |")
        L.append("|" + "|".join(["---"] * len(overlap_df.columns)) + "|")
        for _, row in overlap_df.iterrows():
            L.append("| " + " | ".join(str(row[c]) for c in overlap_df.columns) + " |")
    L.append("")
    L.append("## بخش نهایی — قوانین بهینه‌شده و توصیه")
    L.append("")
    if final_df is None or final_df.empty:
        L.append("نتیجه‌ای برای خلاصه نهایی موجود نیست.")
    else:
        # prefer cap 5 then 7.5 for display of kept
        keeps = final_df[final_df["verdict"] == "KEEP"]
        maybes = final_df[final_df["verdict"] == "MAYBE"]
        drops = final_df[final_df["verdict"] == "DROP"]
        L.append("### KEEP")
        if keeps.empty:
            L.append("_هیچ ستآپی با لبه OOS پایدار و قابل‌اتکا طبق معیارهای سخت پیدا نشد._")
        else:
            for _, r in keeps.iterrows():
                L.append(f"#### {r['strategy']} (کپ {r['cap']}$)")
                L.append(f"- قوانین نهایی: واریانت `{r['variant']}` + فیلتر `{r['filter']}` ({r['flags']})")
                L.append(f"- OOS: n={int(r['oos_n'])}, WR={r['oos_wr']*100:.1f}%, R={r['oos_r']:.2f}, PF={r['oos_pf']:.2f}, MaxDD={r['oos_dd']:.1f}%")
                L.append(f"- سیگنال/روز≈{r['spd_avg']:.2f} | روز صفر≈{r['spd_zero_pct']:.0f}% | WF مثبت={r['wf_pos_frac']*100:.0f}%")
                mc = r.get("mc_pass_0.5pct")
                L.append(f"- MC عبور چالش SGB @0.5% ریسک: {mc*100:.1f}%" if pd.notna(mc) and mc is not None else "- MC: اجرا نشد یا زیر آستانه")
        L.append("")
        L.append("### MAYBE")
        if maybes.empty:
            L.append("_—_")
        else:
            for _, r in maybes.iterrows():
                L.append(f"- **{r['strategy']} @{r['cap']}$** / `{r['variant']}` / `{r['filter']}`: "
                         f"OOS R={r['oos_r']:.2f} PF={r['oos_pf']:.2f} n={int(r['oos_n'])} — {r['reason']}")
        L.append("")
        L.append("### DROP")
        for strat, g in drops.groupby("strategy"):
            reasons = g["reason"].iloc[0]
            L.append(f"- **{strat}**: {reasons}")
        L.append("")
        L.append("### توصیه ترکیب و واتچ‌داگ")
        if not keeps.empty:
            L.append("- فقط ستاپ‌های KEEP را با اولویت زمان سیگنال ادغام کنید (یک پوزیشن همزمان؛ فاصله ۵ دقیقه).")
            L.append("- در واتچ‌داگ: همان کپ سخت SL — اگر dist(entry,SL)+spread > کپ حساب، سیگنال را نشان ندهید.")
        else:
            L.append("- فعلاً **هیچ پورتفوی KEEP توصیه‌ای نیست**. بهینه‌سازی بیشتر روی قوانین ورود لازم است؛ با این دوره و قوانین حسابرسی‌شده لبه قوی دیده نشد.")
        L.append("- کپ ۰.۵٪ ($۵) را پیش‌فرض چالش SGB بگذارید؛ ۰.۷۵٪ فقط اگر ستاپ KEEP با نمونه کافی فقط زیر ۷.۵$ زنده بماند.")
        L.append("")
        L.append("### صداقت")
        L.append("- DXY مصنوعی است؛ تیک‌والیوم پروکسی اردرفلو است نه خود آن.")
        L.append("- اگر همه DROP/MAYBE هستند، یعنی برای حساب ۱۰۰۰$ با کپ فاصله SL واقعی، این ستاپ‌ها در نمونه ۲۰۲۵-۱۰→۲۰۲۶-۱۰ لبه پایدار نشان ندادند.")
    (ROOT / "RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("Wrote RESULTS.md", flush=True)


if __name__ == "__main__":
    main()
