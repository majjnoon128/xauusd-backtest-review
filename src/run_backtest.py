#!/usr/bin/env python3
"""Audited pipeline: closed-bar Order engine, 6 strategies ± DXY ± vol, SL, OOS, combo, MC."""
from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import Order, simulate, SPREAD, SLIPPAGE, COMMISSION_PER_LOT
from monte_carlo import run_mc
from sl_analysis import classify_losses, summarize_causes
from optimize import apply_quality_filters
from combine import signal_overlap, outcome_correlation, signals_per_day_stats, build_combined_orders
from strategies import (
    generate_nds_fib, generate_idris, generate_sp2l, generate_pro_btb,
    generate_micromap, generate_amd_po3_ifvg,
)

DATA = ROOT / "data"
RES = ROOT / "results"
RES.mkdir(parents=True, exist_ok=True)


def load_data():
    xau = pd.read_parquet(DATA / "XAUUSD.parquet")
    if xau.index.tz is None:
        xau.index = xau.index.tz_localize("UTC")
    dxy = pd.read_parquet(DATA / "DXY_synth.parquet")
    if dxy.index.tz is None:
        dxy.index = dxy.index.tz_localize("UTC")
    # DXY may be 15m close-only — ensure OHLC-ish
    if "close" not in dxy.columns:
        dxy = dxy.rename(columns={dxy.columns[0]: "close"})
    return xau, dxy


def split_oos(m1, oos_frac=0.30):
    cut = m1.index[int(len(m1) * (1 - oos_frac))]
    return m1[m1.index < cut], m1[m1.index >= cut], cut


def filter_orders_period(orders, t0, t1):
    return [o for o in orders if t0 <= o.arm_time < t1]


def eval_orders(name, orders, m1_part, label, use_dxy, use_vol, variant=None):
    if variant is not None:
        orders = [o for o in orders if o.variant == variant]
        vname = variant
    else:
        vname = "ALL"
    # only arms that fall in this period
    t0, t1 = m1_part.index[0], m1_part.index[-1] + pd.Timedelta(minutes=1)
    orders = filter_orders_period(orders, t0, t1)
    trades, stats = simulate(
        m1_part, orders,
        dxy_filter_flag=use_dxy, vol_filter_flag=use_vol,
    )
    stats.update({
        "strategy": name, "variant": vname, "dxy_filter": use_dxy,
        "vol_filter": use_vol, "label": label, "n_signals": len(orders),
    })
    if trades is not None and not trades.empty:
        trades = trades.copy()
        trades["strategy"] = name
        trades["variant"] = trades["variant"] if "variant" in trades.columns else vname
        trades["dxy_filter"] = use_dxy
        trades["vol_filter"] = use_vol
        trades["label"] = label
    return trades, stats


def write_results_md(meta, stats_df, cause_summary, spd_rows, overlap_df, corr_df,
                     opt_compare, combined_stats, mc_df, weaknesses):
    lines = []
    lines.append("# نتایج بک‌تست حسابرسی‌شده استراتژی‌های طلا (XAUUSD)")
    lines.append("")
    lines.append("> موتور واحد با قوانین closed-bar، پر کردن ask، بدترین‌حالت SL، اسپرد ۰.۳۵ + اسلیپ ۰.۱۰، تأخیر ۱ کندل برای مارکت. اعداد اختراع نشده‌اند.")
    lines.append("")
    lines.append("## منبع داده و دوره")
    lines.append(f"- طلا: `{meta['xau_source']}` — {meta['xau_bars']} کندل M1 از {meta['xau_start']} تا {meta['xau_end']}")
    lines.append(f"- دلار: `{meta['dxy_source']}` — {meta['dxy_bars']} کندل")
    lines.append(f"- برش out-of-sample: از {meta['oos_cut']} به بعد (~۳۰٪ آخر)")
    lines.append(f"- هزینه: اسپرد {meta['costs']['spread_usd']}$ + اسلیپیج {meta['costs']['slippage_usd']}$ + کمیسیون {meta['costs']['commission_per_lot']}$/لات")
    lines.append(f"- ریسک هر ترید: {meta['risk_per_trade']*100:.1f}% + مدارشکن (۲ ضرر متوالی یا ۱٪ افت روز)")
    lines.append("")
    lines.append("## تعریف‌های ماشینی")
    lines.append("- **NDS Fib:** موج M15 ≥۱.۵×ATR؛ زون اصلی ۰.۶۲–۰.۷۸ (مقایسه: ۰.۷۸۶–۰.۸۶)؛ تأیید اینگالفینگ M1 بسته‌شده؛ مارکت بعد از بسته شدن + تأخیر ۱")
    lines.append("- **ادریس:** H4 بسته‌شده + واگرایی مخفی RSI روی پیوت تأییدشده + اینساید بار؛ مارکت بعد از بسته شدن")
    lines.append("- **SP2L (M5):** اسپایک + FVG؛ ورود A مارکت / B استاپ بعد از بسته شدن اصلاح؛ فیلتر HTF اختیاری")
    lines.append("- **Pro BTB (M5):** شکست پیوت + برگشت؛ ۶ حالت ورود؛ سفارش بعد از بسته شدن کندل برگشت مسلح می‌شود")
    lines.append("- **MicroMAP (M5):** اسپایک + کانال فشرده؛ فقط یک ورود H1/IB/H2")
    lines.append("- **AMD/PO3 + iFVG:** انباشت = رنج آسیا ۰۰–۰۷ UTC (یا N کندل M5 کم‌نوسان)؛ دستکاری = سوئیپ یک‌طرف در پنجره لندن/نیویورک؛ توزیع = FVG هم‌جهت دستکاری که قیمت خلاف‌جهت از آن کلوز می‌کند (iFVG)؛ ورود مارکت/لیمیت بعد از کلوز اینورژن؛ SL پشت اکستریم دستکاری؛ TP رنج مقابل / ۱:۲ / ۱:۳")
    lines.append("- **فیلتر DXY:** لانگ فقط وقتی DXY بسته‌شده زیر EMA50؛ شورت برعکس")
    lines.append("- **پروکسی تیک‌والیوم:** حجم کندل سیگنال > ۱.۳× میانگین ۲۰")
    lines.append("")

    lines.append("## جدول رتبه‌بندی (OOS)")
    oos = stats_df[stats_df["label"] == "OOS"].copy() if stats_df is not None and not stats_df.empty else pd.DataFrame()
    if not oos.empty:
        oos = oos.sort_values(["expectancy_r", "n_trades"], ascending=[False, False])
        lines.append("| استراتژی | واریانت | DXY | Vol | معاملات | وین‌ریت | میانگین R | PF | MaxDD% | ترید/روز |")
        lines.append("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
        for _, r in oos.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['variant']} | {bool(r['dxy_filter'])} | {bool(r.get('vol_filter', False))} | "
                f"{int(r['n_trades'])} | {r['win_rate']*100:.1f}% | {r['avg_r']:.2f} | "
                f"{r['profit_factor']:.2f} | {r['max_dd_pct']:.1f} | {r['trades_per_day']:.2f} |"
            )
    else:
        lines.append("_نتیجه OOS خالی بود._")
    lines.append("")

    lines.append("## مقایسه IS در برابر OOS (بدون DXY، بدون Vol)")
    if stats_df is not None and not stats_df.empty:
        lines.append("| استراتژی | واریانت | IS n / WR / R / PF | OOS n / WR / R / PF |")
        lines.append("|---|---|---|---|")
        base = stats_df[(stats_df["dxy_filter"] == False) & (stats_df.get("vol_filter", False) == False)] if "vol_filter" in stats_df.columns else stats_df[stats_df["dxy_filter"] == False]
        for strat, g in base.groupby("strategy"):
            o = g[g["label"] == "OOS"]
            if o.empty:
                continue
            best = o.sort_values("expectancy_r", ascending=False).iloc[0]
            v = best["variant"]
            irow = g[(g["label"] == "IS") & (g["variant"] == v)]
            def fmt(row):
                if row is None or (hasattr(row, "empty") and row.empty):
                    return "—"
                r = row.iloc[0] if hasattr(row, "iloc") else row
                return f"{int(r['n_trades'])} / {r['win_rate']*100:.0f}% / {r['avg_r']:.2f} / {r['profit_factor']:.2f}"
            lines.append(f"| {strat} | {v} | {fmt(irow)} | {fmt(best.to_frame().T)} |")
    lines.append("")

    lines.append("## حکم فیلتر DXY و Vol")
    if stats_df is not None and not stats_df.empty:
        lines.append("| استراتژی | واریانت | پایه (n,R,PF) | +DXY | +Vol | +DXY+Vol |")
        lines.append("|---|---|---|---|---|---|")
        oos = stats_df[stats_df["label"] == "OOS"]
        keys = oos[["strategy", "variant"]].drop_duplicates()
        for _, k in keys.iterrows():
            def pick(dxy, vol):
                m = oos[(oos["strategy"] == k["strategy"]) & (oos["variant"] == k["variant"])
                        & (oos["dxy_filter"] == dxy)]
                if "vol_filter" in oos.columns:
                    m = m[m["vol_filter"] == vol]
                if m.empty:
                    return "—"
                r = m.iloc[0]
                return f"{int(r['n_trades'])}/{r['avg_r']:.2f}/{r['profit_factor']:.2f}"
            lines.append(f"| {k['strategy']} | {k['variant']} | {pick(False, False)} | {pick(True, False)} | {pick(False, True)} | {pick(True, True)} |")
    lines.append("")

    lines.append("## علت‌های حد ضرر (SL)")
    if cause_summary is not None and not cause_summary.empty:
        lines.append("| استراتژی | واریانت | n_SL | against_HTF | asian/lowvol | SL_tight | extended | dxy_disagree | london_whip |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in cause_summary.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['variant']} | {int(r['n_losses'])} | "
                f"{r.get('against_htf_trend',0)*100:.0f}% | {r.get('asian_or_low_vol_session',0)*100:.0f}% | "
                f"{r.get('sl_too_tight_vs_atr',0)*100:.0f}% | {r.get('entry_extended',0)*100:.0f}% | "
                f"{r.get('dxy_disagreement',0)*100:.0f}% | {r.get('london_open_whipsaw',0)*100:.0f}% |"
            )
    lines.append("")

    lines.append("## سیگنال در روز")
    if spd_rows:
        lines.append("| استراتژی | واریانت | میانگین/روز | میانه | % روز صفر | لندن | نیویورک |")
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for r in spd_rows:
            lines.append(
                f"| {r['strategy']} | {r['variant']} | {r['avg']:.2f} | {r['median']:.1f} | "
                f"{r['pct_zero_days']:.0f}% | {r['london_avg']:.2f} | {r['ny_avg']:.2f} |"
            )
    lines.append("")

    lines.append("## هم‌پوشانی و همبستگی")
    if overlap_df is not None and not overlap_df.empty:
        lines.append(overlap_df.to_markdown(index=False))
    lines.append("")
    if corr_df is not None and not corr_df.empty:
        lines.append("همبستگی PnL روزانه:")
        lines.append(corr_df.round(2).to_markdown())
    lines.append("")

    lines.append("## فیلترهای کیفیت (OOS)")
    if opt_compare is not None and not opt_compare.empty:
        lines.append(opt_compare.to_markdown(index=False))
    lines.append("")

    lines.append("## ترکیب پورتفو (OOS)")
    if combined_stats:
        for cs in combined_stats:
            lines.append(f"- **{cs.get('name','combo')}**: n={cs.get('n_trades',0)}, WR={cs.get('win_rate',0)*100:.1f}%, "
                         f"R={cs.get('avg_r',0):.2f}, PF={cs.get('profit_factor',0):.2f}, DD={cs.get('max_dd_pct',0):.1f}%")
    lines.append("")

    lines.append("## مونت‌کارلو (فقط واریانت‌هایی با PF OOS ≥ ۱.۱)")
    if mc_df is not None and not mc_df.empty:
        lines.append(mc_df.to_markdown(index=False))
    else:
        lines.append("_هیچ واریانتی آستانه PF≥۱.۱ روی OOS را رد نکرد؛ MC اجرا نشد یا خالی بود._")
    lines.append("")

    lines.append("## نقاط ضعف و محدودیت‌ها")
    for w in weaknesses:
        lines.append(f"- {w}")
    lines.append("")
    lines.append("## حکم نهایی")
    # honest top-line from OOS
    if stats_df is not None and not stats_df.empty:
        oos = stats_df[stats_df["label"] == "OOS"]
        pos = oos[(oos["n_trades"] >= 20) & (oos["expectancy_r"] > 0) & (oos["profit_factor"] >= 1.0)]
        if pos.empty:
            lines.append("هیچ واریانتی با ≥۲۰ ترید OOS و expectancy مثبت و PF≥۱ پیدا نشد. "
                         "با قوانین حسابرسی‌شده، لبه قوی و پایدار در این دوره دیده نشد.")
        else:
            best = pos.sort_values("expectancy_r", ascending=False).iloc[0]
            lines.append(
                f"بهترین OOS قابل‌قبول: **{best['strategy']} / {best['variant']}** "
                f"(DXY={bool(best['dxy_filter'])}, Vol={bool(best.get('vol_filter', False))}): "
                f"n={int(best['n_trades'])}, WR={best['win_rate']*100:.1f}%, R={best['avg_r']:.2f}, "
                f"PF={best['profit_factor']:.2f}, DD={best['max_dd_pct']:.1f}%. "
                "این به معنی تضمین سود نیست؛ فقط بهترین نتیجه در این نمونه است."
            )
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", ROOT / "RESULTS.md")


def main():
    print("Loading data...")
    m1, dxy = load_data()
    m1_is, m1_oos, cut = split_oos(m1, 0.30)
    print(f"M1={len(m1)} IS={len(m1_is)} OOS={len(m1_oos)} cut={cut}")

    meta = {
        "xau_source": "Dukascopy XAU/USD M1",
        "xau_bars": len(m1),
        "xau_start": str(m1.index[0]),
        "xau_end": str(m1.index[-1]),
        "dxy_source": "Synthetic ICE DXY from FX legs",
        "dxy_bars": len(dxy),
        "oos_cut": str(cut),
        "costs": {"spread_usd": SPREAD, "slippage_usd": SLIPPAGE, "commission_per_lot": COMMISSION_PER_LOT},
        "risk_per_trade": 0.005,
        "engine": "audited_closed_bar_ask_worstSL_delay1",
    }
    (RES / "meta.json").write_text(json.dumps(meta, indent=2, default=str))

    all_stats = []
    all_trades = []
    orders_cache = {}  # (strat, dxy, vol, extra) -> orders
    spd_rows = []
    weaknesses = []

    def run_variant_set(name, orders, use_dxy, use_vol):
        variants = sorted({o.variant for o in orders}) or ["none"]
        for label, part in (("IS", m1_is), ("OOS", m1_oos)):
            for v in variants:
                tr, st = eval_orders(name, orders, part, label, use_dxy, use_vol, variant=v)
                all_stats.append(st)
                if tr is not None and not tr.empty:
                    all_trades.append(tr)

    # ---- Generate base configs ----
    configs = []
    for use_dxy in (False, True):
        for use_vol in (False, True):
            configs.append(("NDS_Fib", dict(use_dxy=use_dxy, use_vol=use_vol, rr=1.5)))
            configs.append(("NDS_Fib", dict(use_dxy=use_dxy, use_vol=use_vol, rr=2.0)))
            configs.append(("Idris", dict(use_dxy=use_dxy, use_vol=use_vol, rr=3.0)))
            configs.append(("SP2L", dict(use_dxy=use_dxy, use_vol=use_vol, use_htf=True)))
            configs.append(("SP2L_noHTF", dict(use_dxy=use_dxy, use_vol=use_vol, use_htf=False)))
            configs.append(("ProBTB", dict(use_dxy=use_dxy, use_vol=use_vol, rr=2.0)))
            configs.append(("MicroMAP", dict(use_dxy=use_dxy, use_vol=use_vol)))

    # AMD configs: range_mode × tf × entry × tp × htf × dxy × vol (subset to keep runtime sane)
    amd_cfgs = []
    for range_mode in ("asian", "m5_lowatr"):
        for tf in ("M5", "M1"):
            for entry_mode in ("market", "limit"):
                for tp_mode in ("range", "rr2", "rr3"):
                    for use_htf in (False, True):
                        for use_dxy in (False, True):
                            for use_vol in (False, True):
                                amd_cfgs.append(dict(
                                    range_mode=range_mode, tf=tf, entry_mode=entry_mode,
                                    tp_mode=tp_mode, use_htf=use_htf, use_dxy=use_dxy, use_vol=use_vol,
                                ))
    # Too many: prioritize core grid first — asian/M5/market+limit × tp × htf × dxy × vol
    amd_cfgs = [c for c in amd_cfgs if not (c["tf"] == "M1" and c["range_mode"] == "m5_lowatr")]
    # Still a lot (2*2*2*3*2*2*2 = 192 for asian+m5 with both TF...). Cut M1 to asian only market.
    amd_core = []
    for range_mode in ("asian", "m5_lowatr"):
        for entry_mode in ("market", "limit"):
            for tp_mode in ("range", "rr2", "rr3"):
                for use_htf in (False, True):
                    for use_dxy in (False, True):
                        for use_vol in (False, True):
                            amd_core.append(dict(
                                range_mode=range_mode, tf="M5", entry_mode=entry_mode,
                                tp_mode=tp_mode, use_htf=use_htf, use_dxy=use_dxy, use_vol=use_vol,
                            ))
    # Add a few M1 asian market variants
    for tp_mode in ("range", "rr2", "rr3"):
        for use_htf in (False, True):
            for use_dxy in (False, True):
                amd_core.append(dict(
                    range_mode="asian", tf="M1", entry_mode="market",
                    tp_mode=tp_mode, use_htf=use_htf, use_dxy=use_dxy, use_vol=False,
                ))

    print(f"AMD configs: {len(amd_core)}")

    generators = {
        "NDS_Fib": lambda kw: generate_nds_fib(m1, dxy, **kw),
        "Idris": lambda kw: generate_idris(m1, dxy, **kw),
        "SP2L": lambda kw: generate_sp2l(m1, dxy, **kw),
        "SP2L_noHTF": lambda kw: generate_sp2l(m1, dxy, **{**kw, "use_htf": False}),
        "ProBTB": lambda kw: generate_pro_btb(m1, dxy, **kw),
        "MicroMAP": lambda kw: generate_micromap(m1, dxy, **kw),
    }

    # Deduplicate generation: generate once per unique kwargs fingerprint for non-AMD
    print("Generating strategy orders...")
    seen = set()
    for name, kw in configs:
        key = (name, tuple(sorted(kw.items())))
        if key in seen:
            continue
        seen.add(key)
        try:
            print(f"  {name} {kw} ...", flush=True)
            ords = generators[name](kw)
            print(f"    -> {len(ords)} orders")
            orders_cache[key] = ords
            # signals/day for base no-filter
            if not kw.get("use_dxy") and not kw.get("use_vol"):
                by_v = defaultdict(list)
                for o in ords:
                    by_v[o.variant].append(o)
                for v, ol in by_v.items():
                    spd = signals_per_day_stats(ol)
                    spd_rows.append({"strategy": name, "variant": v, **{k: spd[k] for k in
                                    ("avg", "median", "pct_zero_days", "london_avg", "ny_avg")}})
            run_variant_set(name, ords, kw.get("use_dxy", False), kw.get("use_vol", False))
        except Exception as e:
            traceback.print_exc()
            weaknesses.append(f"{name} generation failed: {e}")

    print("Generating AMD/PO3+iFVG (base scans then DXY/Vol gates)...")
    from strategies.common import apply_dxy_gate, apply_vol_gate
    from indicators import resample_ohlc, vol_ma
    # Unique base keys without dxy/vol
    base_keys = []
    seen_b = set()
    for kw in amd_core:
        bk = (kw["range_mode"], kw["tf"], kw["entry_mode"], kw["tp_mode"], kw["use_htf"])
        if bk not in seen_b:
            seen_b.add(bk)
            base_keys.append(bk)
    print(f"  AMD base scans: {len(base_keys)} (from {len(amd_core)} configs)")
    amd_base = {}
    for i, bk in enumerate(base_keys):
        range_mode, tf, entry_mode, tp_mode, use_htf = bk
        print(f"  AMD base {i+1}/{len(base_keys)} {bk}", flush=True)
        try:
            ords = generate_amd_po3_ifvg(
                m1, dxy, range_mode=range_mode, tf=tf, entry_mode=entry_mode,
                tp_mode=tp_mode, use_htf=use_htf, use_dxy=False, use_vol=False,
            )
            amd_base[bk] = ords
            print(f"    -> {len(ords)} orders")
            if not use_htf:
                by_v = defaultdict(list)
                for o in ords:
                    by_v[o.variant].append(o)
                for v, ol in by_v.items():
                    spd = signals_per_day_stats(ol)
                    spd_rows.append({"strategy": "AMD_PO3_iFVG", "variant": v, **{k: spd[k] for k in
                                    ("avg", "median", "pct_zero_days", "london_avg", "ny_avg")}})
        except Exception as e:
            traceback.print_exc()
            weaknesses.append(f"AMD base {bk} failed: {e}")
            amd_base[bk] = []

    # Precompute vol series per TF
    m5 = resample_ohlc(m1, "5min")
    vol_series = {
        "M5": (m5["volume"], vol_ma(m5["volume"], 20), 5) if "volume" in m5.columns else None,
        "M1": (m1["volume"], vol_ma(m1["volume"], 20), 1) if "volume" in m1.columns else None,
    }

    for kw in amd_core:
        bk = (kw["range_mode"], kw["tf"], kw["entry_mode"], kw["tp_mode"], kw["use_htf"])
        ords = list(amd_base.get(bk, []))
        if kw.get("use_vol"):
            vs = vol_series.get(kw["tf"])
            if vs is not None:
                ords = apply_vol_gate(ords, vs[0], vs[1], True, 1.3, vs[2])
            else:
                ords = []
        if kw.get("use_dxy"):
            ords = apply_dxy_gate(ords, dxy, True)
        key = ("AMD_PO3_iFVG", tuple(sorted(kw.items())))
        orders_cache[key] = ords
        run_variant_set("AMD_PO3_iFVG", ords, kw.get("use_dxy", False), kw.get("use_vol", False))

    stats_df = pd.DataFrame(all_stats)
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    stats_df.to_csv(RES / "stats_all.csv", index=False)
    if not trades_df.empty:
        trades_df.to_csv(RES / "trades_all.csv", index=False)
    print(f"Stats rows={len(stats_df)} trade rows={len(trades_df)}")

    # ---- SL analysis on OOS baseline (no dxy no vol) ----
    print("SL cause analysis...")
    cause_parts = []
    if not trades_df.empty:
        oos_tr = trades_df[(trades_df["label"] == "OOS") & (trades_df["dxy_filter"] == False)]
        if "vol_filter" in oos_tr.columns:
            oos_tr = oos_tr[oos_tr["vol_filter"] == False]
        for strat, g in oos_tr.groupby("strategy"):
            try:
                clf = classify_losses(g, m1, dxy)
                if not clf.empty:
                    clf.to_csv(RES / f"sl_causes_{strat}.csv", index=False)
                    cause_parts.append(clf)
            except Exception as e:
                weaknesses.append(f"SL analysis {strat}: {e}")
    cause_summary = summarize_causes(pd.concat(cause_parts, ignore_index=True)) if cause_parts else pd.DataFrame()
    if not cause_summary.empty:
        cause_summary.to_csv(RES / "sl_cause_summary.csv", index=False)

    # ---- Quality filters on top OOS candidates ----
    print("Quality filter compare...")
    opt_rows = []
    if not stats_df.empty:
        oos = stats_df[(stats_df["label"] == "OOS") & (stats_df["dxy_filter"] == False)]
        if "vol_filter" in oos.columns:
            oos = oos[oos["vol_filter"] == False]
        oos = oos[oos["variant"] != "ALL"].sort_values("n_trades", ascending=False)
        # pick up to 8 most-traded variants across strategies
        picked = []
        for strat, g in oos.groupby("strategy"):
            top = g.sort_values("n_trades", ascending=False).head(2)
            for _, r in top.iterrows():
                picked.append((r["strategy"], r["variant"]))
        for strat, variant in picked[:12]:
            # find matching orders in cache
            base_ords = None
            for key, ords in orders_cache.items():
                if key[0] == strat or (strat == "SP2L_noHTF" and key[0] == "SP2L_noHTF"):
                    # prefer no dxy no vol
                    kw = dict(key[1])
                    if kw.get("use_dxy") or kw.get("use_vol"):
                        continue
                    subset = [o for o in ords if o.variant == variant]
                    if subset:
                        base_ords = subset
                        break
            if not base_ords:
                continue
            for tag, filt_kw in [
                ("baseline", dict(require_htf=False, require_dxy=False)),
                ("htf", dict(require_htf=True, require_dxy=False)),
                ("htf+dxy", dict(require_htf=True, require_dxy=True)),
                ("htf+minsl", dict(require_htf=True, require_dxy=False, min_sl_atr=0.8)),
            ]:
                fo = apply_quality_filters(base_ords, m1, dxy, **filt_kw)
                tr, st = eval_orders(strat, fo, m1_oos, "OOS", filt_kw.get("require_dxy", False), False, variant=variant)
                opt_rows.append({
                    "strategy": strat, "variant": variant, "filter": tag,
                    "n_signals": st["n_signals"], "n_trades": st["n_trades"],
                    "win_rate": st["win_rate"], "avg_r": st["avg_r"],
                    "profit_factor": st["profit_factor"], "max_dd_pct": st["max_dd_pct"],
                })
    opt_compare = pd.DataFrame(opt_rows)
    if not opt_compare.empty:
        opt_compare.to_csv(RES / "opt_compare.csv", index=False)

    # ---- Combination ----
    print("Portfolio combination...")
    combined_stats = []
    overlap_df = pd.DataFrame()
    corr_df = pd.DataFrame()
    try:
        # pick best OOS variant per strategy (no dxy/vol, n>=10)
        by_strat_orders = {}
        if not stats_df.empty:
            oos = stats_df[(stats_df["label"] == "OOS") & (stats_df["dxy_filter"] == False)]
            if "vol_filter" in oos.columns:
                oos = oos[oos["vol_filter"] == False]
            oos = oos[oos["variant"] != "ALL"]
            for strat, g in oos.groupby("strategy"):
                g2 = g[g["n_trades"] >= 5].sort_values("expectancy_r", ascending=False)
                if g2.empty:
                    g2 = g.sort_values("n_trades", ascending=False)
                if g2.empty:
                    continue
                best_v = g2.iloc[0]["variant"]
                # find orders
                for key, ords in orders_cache.items():
                    if key[0] != strat:
                        continue
                    kw = dict(key[1])
                    if kw.get("use_dxy") or kw.get("use_vol"):
                        continue
                    subset = [o for o in ords if o.variant == best_v]
                    if subset:
                        by_strat_orders[strat] = subset
                        break
        if by_strat_orders:
            overlap_df = signal_overlap(by_strat_orders, 30)
            overlap_df.to_csv(RES / "signal_overlap.csv", index=False)
            combo = build_combined_orders(by_strat_orders)
            tr, st = eval_orders("COMBO", combo, m1_oos, "OOS", False, False, variant=None)
            st["name"] = "best_variants_merged"
            st["variant"] = "merged"
            combined_stats.append(st)
            if tr is not None and not tr.empty:
                tr.to_csv(RES / "combined_oos_trades.csv", index=False)
                # rebuild strategy tags from original
                corr_src = []
                for strat, ords in by_strat_orders.items():
                    t2, _ = eval_orders(strat, ords, m1_oos, "OOS", False, False)
                    if t2 is not None and not t2.empty:
                        corr_src.append(t2)
                if corr_src:
                    corr_df = outcome_correlation(pd.concat(corr_src, ignore_index=True))
                    corr_df.to_csv(RES / "daily_pnl_corr.csv")
    except Exception as e:
        traceback.print_exc()
        weaknesses.append(f"combo failed: {e}")

    # ---- Monte Carlo for PF>=1.1 OOS ----
    print("Monte Carlo...")
    mc_rows = []
    if not stats_df.empty and not trades_df.empty:
        oos_s = stats_df[stats_df["label"] == "OOS"]
        cand = oos_s[(oos_s["profit_factor"] >= 1.1) & (oos_s["n_trades"] >= 20) & (oos_s["variant"] != "ALL")]
        for _, r in cand.iterrows():
            mask = (
                (trades_df["strategy"] == r["strategy"]) &
                (trades_df["variant"] == r["variant"]) &
                (trades_df["label"] == "OOS") &
                (trades_df["dxy_filter"] == r["dxy_filter"])
            )
            if "vol_filter" in trades_df.columns:
                mask &= trades_df["vol_filter"] == r.get("vol_filter", False)
            sub = trades_df[mask]
            if len(sub) < 15:
                continue
            mc = run_mc(sub["r_multiple"].values, n_sims=3000)
            if mc is None or mc.empty:
                continue
            mc = mc.copy()
            mc["strategy"] = r["strategy"]
            mc["variant"] = r["variant"]
            mc["dxy"] = r["dxy_filter"]
            mc["vol"] = r.get("vol_filter", False)
            mc_rows.append(mc)
    mc_df = pd.concat(mc_rows, ignore_index=True) if mc_rows else pd.DataFrame()
    if not mc_df.empty:
        mc_df.to_csv(RES / "monte_carlo.csv", index=False)

    # Speeds
    (RES / "signals_per_day.json").write_text(json.dumps(spd_rows, indent=2, default=str))

    weaknesses.append(
        "داده DXY مصنوعی از پایه‌های FX است نه ICE نقدی؛ پروکسی تیک‌والیوم جایگزین اردرفلو واقعی نیست."
    )
    weaknesses.append(
        "قوانین ICT/AMD ساده‌سازی ماشینی‌اند؛ انتخاب دستی تریدر ممکن است فرق کند."
    )
    weaknesses.append(
        "اسپرد/اسلیپ ثابت‌اند؛ در خبر و سشن کم‌نقد ممکن است بدتر باشد."
    )

    write_results_md(meta, stats_df, cause_summary, spd_rows, overlap_df, corr_df,
                     opt_compare, combined_stats, mc_df, weaknesses)
    print("DONE")


if __name__ == "__main__":
    main()
