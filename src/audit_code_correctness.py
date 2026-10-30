#!/usr/bin/env python3
"""Independent code-correctness audit. Writes short JSON/MD under results/audit_code/."""
from __future__ import annotations
import json, sys
from pathlib import Path
from copy import deepcopy
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import (
    Order, simulate, sl_distance_price, SPREAD, SLIPPAGE,
    _can_fill_stop, _can_fill_limit, _fill_price, _resolve_exit, compute_stats,
)
from indicators import (
    resample_ohlc, atr_prior, bar_end, bullish_engulfing, bearish_engulfing,
    inside_bar, rsi, ema, atr, last_closed_value,
)
from strategies.nds_fib import generate_nds_fib, _zone_bounds
from strategies.sp2l import generate_sp2l
from strategies.idris import generate_idris
from strategies.pro_btb import generate_pro_btb
from strategies.micromap import generate_micromap
from strategies.amd_po3_ifvg import generate_amd_po3_ifvg, _asian_ranges, _find_fvgs
from strategies.common import apply_htf_gate, apply_dxy_gate
from run_final_batch import apply_confirmations, filter_cap, period_orders

OUT = ROOT / "results" / "audit_code"
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "data"


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


# ---------- 1) Static rule mismatches ----------
MISMATCHES = {
    "NDS_Fib": [
        {"sev": "note", "issue": "Impulse = 60% same-color M15 bars over 3-6 bars, not a clean swing structure. Mechanical approximation of 'M15 impulse'."},
        {"sev": "ok", "issue": "Fib zone math 0.62-0.78: long z_hi=high-0.62*move, z_lo=high-0.78*move — CORRECT retracement from impulse end."},
        {"sev": "note", "issue": "Entry allows low/high wick in zone OR close in zone; brief says 'retracement zone' — acceptable."},
        {"sev": "note", "issue": "SL buffer uses M15 ATR on M1 entry — slightly inconsistent TF but not a logic bug."},
    ],
    "SP2L": [
        {"sev": "BUG", "issue": "P-Gap/FVG is WAIVED when body move > 1.5*ATR (has_fvg=True without gap). Official: 'No gap means invalid'."},
        {"sev": "BUG", "issue": "Variant B (buy/sell stop) fires on any pullback candle (bearish OR broke prior extreme). Official: enter only when pullback candle takes prior candle's low/high."},
        {"sev": "note", "issue": "Spike candle-size gate is OR (all large OR total range) — looser than 'several large candles'."},
        {"sev": "ok", "issue": "SL behind spike origin extreme — matches official."},
    ],
    "Idris": [
        {"sev": "ok", "issue": "Pivot confirmation uses pivot_bar+3<=i — no lookahead on pivots."},
        {"sev": "ok", "issue": "Hidden bullish: HH-low + lower RSI; hidden bearish: LL-high + higher RSI — correct."},
        {"sev": "note", "issue": "Entry is market at IB close, not stop at IB high/low. Brief says 'Inside Bar trigger' — conservative interpretation."},
        {"sev": "note", "issue": "Zone = last closed H4 high/low; 'reaches zone' within 5 M1 bars + 0.15*ATR tol — approximation."},
    ],
    "ProBTB": [
        {"sev": "ok", "issue": "Mode5 = stop at breakout candle extreme after return touch — matches Amir mode list."},
        {"sev": "BUG", "issue": "ENGINE: stop/limit fills ignore gap-through — always fill at order price±costs, never at worse open. Optimistic for ProBTB m5 stops."},
        {"sev": "BUG", "issue": "FILTER not_extended: uses m15.iloc[searchsorted(arm)-1] close/EMA/ATR from FULL resample — unfinished M15 bar includes M1 AFTER arm_time (lookahead)."},
        {"sev": "note", "issue": "Breakout requires open near level + body>=0.3*ATR — extra constraints not in brief text."},
        {"sev": "ok", "issue": "Orders armed after return bar close; pending BO consumed — closed-bar OK."},
    ],
    "MicroMAP": [
        {"sev": "note", "issue": "Microchannel = monotonically non-rising highs (bull) — approximates 'lower highs' loosely (+0.05ATR slack)."},
        {"sev": "BUG", "issue": "H2 variant: Order.price=close[end+2] (market) but TP computed from high[end+1] stop level (entry var) — TP/risk inconsistent with fill price."},
        {"sev": "ok", "issue": "Single entry only (H1/IB/H2) — respects prop no-reentry."},
    ],
    "AMD_PO3_iFVG": [
        {"sev": "note", "issue": "Manipulation accepts close beyond Asian range, not only wick sweep+reject. Classic PO3 prefers liquidity grab wick."},
        {"sev": "ok", "issue": "Asian 00-07 UTC; London 07-10; NY 12-15 — correct for Dukascopy UTC."},
        {"sev": "ok", "issue": "iFVG = close through FVG opposite to manip; SL beyond manip extreme; TP opposite range — matches stated mechanical rules."},
        {"sev": "note", "issue": "FVG may form up to 12 bars after first sweep bar; first successful day/side wins."},
    ],
    "ENGINE": [
        {"sev": "BUG", "issue": "Stop gap-through: if open gaps past stop, fill should be at open±costs (worse), code uses stop±costs (better). Inflates stop-entry strategies."},
        {"sev": "ok", "issue": "Worst-case same-bar SL before TP — correct/conservative."},
        {"sev": "ok", "issue": "Market delay 1 M1 bar; no fill on signal bar — OK."},
        {"sev": "ok", "issue": "SL hard cap |entry-SL|+spread — matches $5/$7.5 rule."},
    ],
}


def fib_math_unit():
    # long impulse 100->200, 0.62-0.78 zone
    z_lo, z_hi = _zone_bounds("long", 200, 100, 0.62, 0.78)
    # 0.62 retrace from high = 200-62=138; 0.78 = 200-78=122
    assert abs(z_hi - 138) < 1e-9 and abs(z_lo - 122) < 1e-9
    z_lo2, z_hi2 = _zone_bounds("short", 200, 100, 0.62, 0.78)
    # short: from low up: 100+62=162, 100+78=178
    assert abs(z_lo2 - 162) < 1e-9 and abs(z_hi2 - 178) < 1e-9
    return {"long_zone": [z_lo, z_hi], "short_zone": [z_lo2, z_hi2], "pass": True}


def check_gap_through_bias(m1):
    """Count how often stop fill would be worse if gap-through used open."""
    # Use ProBTB m5 orders
    orders = generate_pro_btb(m1, use_dxy=False, use_vol=False, rr=2.0)
    m5_stops = [o for o in orders if "m5_stop_breakout" in o.variant]
    times = m1.index
    high, low, open_ = m1["high"].values, m1["low"].values, m1["open"].values
    n = len(times)
    gap_n = 0
    fill_n = 0
    optimistic_usd = []
    for o in m5_stops[:8000]:
        j = times.searchsorted(o.arm_time, side="left")
        expire = times.searchsorted(o.arm_time + pd.Timedelta(minutes=o.expire_minutes), side="right") - 1
        expire = min(max(expire, j), n - 1)
        for i in range(j, expire + 1):
            if not _can_fill_stop(o.side, o.price, low[i], high[i]):
                continue
            fill_n += 1
            coded = _fill_price(o.side, "stop", o.price, open_[i], SPREAD, SLIPPAGE)
            # gap-through honest: if open already past stop, fill at open + costs
            if o.side == "long":
                if open_[i] > o.price:
                    honest = open_[i] + SPREAD + SLIPPAGE
                    gap_n += 1
                    optimistic_usd.append(honest - coded)
                else:
                    honest = coded
            else:
                if open_[i] < o.price:
                    honest = open_[i] - SPREAD - SLIPPAGE
                    gap_n += 1
                    optimistic_usd.append(coded - honest)  # how much better coded was
                else:
                    honest = coded
            break
    return {
        "m5_orders_checked": min(8000, len(m5_stops)),
        "fills_found": fill_n,
        "gap_through_fills": gap_n,
        "gap_pct": round(100 * gap_n / fill_n, 2) if fill_n else 0,
        "mean_optimistic_price_adv_usd": float(np.mean(optimistic_usd)) if optimistic_usd else 0.0,
        "median_optimistic_price_adv_usd": float(np.median(optimistic_usd)) if optimistic_usd else 0.0,
    }


def verify_trade_conditions(m1, orders, strategy_name, n_samples=5):
    """For up to n_samples wins and losses from a quick simulate, verify SL/TP geometry and arm after signal."""
    cut = m1.index[int(len(m1) * 0.70)]
    oo = [o for o in orders if o.arm_time >= cut][:2000]
    if len(oo) < 20:
        oo = orders[:2000]
    tr, st = simulate(m1, oo, risk_pct=0.005, max_sl_dist=5.0, use_circuit_breaker=False)
    out = {"strategy": strategy_name, "sim_n": int(st["n_trades"]), "checks": []}
    if tr is None or tr.empty:
        out["note"] = "no trades under cap5"
        return out
    samples = []
    wins = tr[tr["pnl_usd"] > 0].head(n_samples)
    losses = tr[tr["pnl_usd"] <= 0].head(n_samples)
    samples_df = pd.concat([wins, losses])
    times = m1.index
    for _, row in samples_df.iterrows():
        chk = {
            "side": row["side"], "kind": row["kind"], "reason": row["reason"],
            "entry": float(row["entry"]), "sl": float(row["sl"]), "tp": float(row["tp"]),
            "entry_time": str(row["entry_time"]), "same_m1": bool(row["same_m1_entry_exit"]),
        }
        # geometry
        if row["side"] == "long":
            chk["sl_below_entry"] = row["sl"] < row["entry"]
            chk["tp_above_entry"] = row["tp"] > row["entry"]
            geom_ok = chk["sl_below_entry"] and chk["tp_above_entry"]
        else:
            chk["sl_above_entry"] = row["sl"] > row["entry"]
            chk["tp_below_entry"] = row["tp"] < row["entry"]
            geom_ok = chk["sl_above_entry"] and chk["tp_below_entry"]
        # entry bar exists
        ei = times.searchsorted(row["entry_time"], side="left")
        if ei < len(times) and times[ei] == row["entry_time"]:
            h, l = float(m1["high"].iloc[ei]), float(m1["low"].iloc[ei])
            if row["kind"] == "stop":
                # fill bar must touch stop level (order price ≈ entry - costs)
                # reconstruct: long stop fill = stop + spread + slip
                if row["side"] == "long":
                    stop_lvl = row["entry"] - SPREAD - SLIPPAGE
                    chk["bar_touches_stop"] = h >= stop_lvl - 1e-6
                else:
                    stop_lvl = row["entry"] + SPREAD + SLIPPAGE
                    chk["bar_touches_stop"] = l <= stop_lvl + 1e-6
            if row["reason"] == "SL":
                if row["side"] == "long":
                    chk["bar_or_path_hits_sl"] = True  # engine claims; spot-check fill bar or later
                    # at least somewhere from fill to exit low<=sl — trust exit_time bar
                    xi = times.searchsorted(row["exit_time"], side="left")
                    chk["exit_bar_low_le_sl"] = float(m1["low"].iloc[xi]) <= row["sl"] + 1e-6
                else:
                    xi = times.searchsorted(row["exit_time"], side="left")
                    chk["exit_bar_high_ge_sl"] = float(m1["high"].iloc[xi]) >= row["sl"] - 1e-6
            if row["reason"] == "TP":
                xi = times.searchsorted(row["exit_time"], side="left")
                if row["side"] == "long":
                    chk["exit_bar_high_ge_tp"] = float(m1["high"].iloc[xi]) >= row["tp"] - 1e-6
                else:
                    chk["exit_bar_low_le_tp"] = float(m1["low"].iloc[xi]) <= row["tp"] + 1e-6
        chk["geom_ok"] = geom_ok
        out["checks"].append(chk)
    out["geom_fail"] = sum(1 for c in out["checks"] if not c.get("geom_ok"))
    return out


def lookahead_not_ext_test(m1):
    """Measure how often not_extended uses unfinished M15 bar close vs last closed."""
    orders = generate_pro_btb(m1, rr=2.0)
    m5 = [o for o in orders if "m5_stop_breakout" in o.variant][:3000]
    m15 = resample_ohlc(m1, "15min")
    m15_ema = ema(m15["close"], 50)
    m15_atr = atr(m15, 14)
    leak = 0
    differ = 0
    for o in m5:
        t = o.arm_time
        mi = m15.index.searchsorted(t, side="right") - 1
        if mi < 50:
            continue
        # unfinished if bar_end of m15[mi] > t
        bar_start = m15.index[mi]
        bar_close_t = bar_start + pd.Timedelta(minutes=15)
        if bar_close_t > t:
            leak += 1
            # closed value
            closed = last_closed_value(m15["close"], t, 15)
            open_close = float(m15["close"].iloc[mi])
            if closed is not None and abs(closed - open_close) > 1e-9:
                differ += 1
    return {"checked": len(m5), "unfinished_m15_at_arm": leak, "close_differs_from_last_closed": differ,
            "leak_pct": round(100 * leak / max(len(m5), 1), 2)}


def shift_and_random(m1, orders, label, cap=5.0, shifts=(5, 15, 60), n_rand=3):
    """Shift arm_times; randomize sides keeping SL/TP distances. Compare OOS PF."""
    cut = m1.index[int(len(m1) * 0.70)]
    base = [o for o in orders if o.arm_time >= cut]
    base = filter_cap(base, cap)
    tr0, st0 = simulate(m1, base, risk_pct=0.005, max_sl_dist=cap, use_circuit_breaker=False)
    results = {"label": label, "baseline_oos": {k: st0[k] for k in ("n_trades", "win_rate", "profit_factor", "expectancy_r", "net_pnl")}}
    shift_rows = []
    for s in shifts:
        shifted = []
        for o in base:
            no = Order(
                arm_time=o.arm_time + pd.Timedelta(minutes=s),
                side=o.side, kind=o.kind, price=o.price, sl=o.sl, tp=o.tp,
                strategy=o.strategy, variant=o.variant, meta=dict(o.meta),
                expire_minutes=o.expire_minutes,
            )
            shifted.append(no)
        tr, st = simulate(m1, shifted, risk_pct=0.005, max_sl_dist=cap, use_circuit_breaker=False)
        shift_rows.append({"shift_min": s, "n": st["n_trades"], "pf": st["profit_factor"], "r": st["expectancy_r"], "wr": st["win_rate"]})
    results["shifts"] = shift_rows
    # random entry: keep times/kind but randomize price path via flipping side 50% and scrambling arm by ±rand
    rng = np.random.default_rng(42)
    rand_rows = []
    for k in range(n_rand):
        rand_o = []
        for o in base:
            # keep SL distance and RR, place at random M1 close near arm
            j = m1.index.searchsorted(o.arm_time, side="left")
            if j >= len(m1) - 10:
                continue
            jj = int(rng.integers(max(0, j - 30), min(len(m1) - 1, j + 30)))
            px = float(m1["close"].iloc[jj])
            risk = abs(o.price - o.sl)
            side = o.side if rng.random() < 0.5 else ("short" if o.side == "long" else "long")
            if side == "long":
                sl, tp = px - risk, px + abs(o.tp - o.price)
            else:
                sl, tp = px + risk, px - abs(o.tp - o.price)
            rand_o.append(Order(
                arm_time=m1.index[jj] + pd.Timedelta(minutes=1),
                side=side, kind=o.kind, price=px, sl=sl, tp=tp,
                strategy="RAND", variant=o.variant, expire_minutes=o.expire_minutes,
            ))
        tr, st = simulate(m1, rand_o, risk_pct=0.005, max_sl_dist=cap, use_circuit_breaker=False)
        rand_rows.append({"k": k, "n": st["n_trades"], "pf": st["profit_factor"], "r": st["expectancy_r"]})
    results["random"] = rand_rows
    # edge destroyed?
    base_pf = st0["profit_factor"]
    shift_pfs = [r["pf"] for r in shift_rows]
    results["edge_survives_shift"] = any(p >= base_pf * 0.9 and p > 1.05 for p in shift_pfs) if base_pf > 1 else False
    results["random_mean_pf"] = float(np.mean([r["pf"] for r in rand_rows])) if rand_rows else 0
    return results


def sp2l_fvg_waiver_rate(m1):
    """Replicate spike loop counting how often FVG was waived."""
    df = resample_ohlc(m1, "5min")
    a = atr_prior(df, 14).values
    ranges = (df["high"] - df["low"]).values
    from indicators import is_bull, is_bear
    bull, bear = is_bull(df).values, is_bear(df).values
    high, low, close, open_ = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    BODY_MULT, FVG_MULT = 0.8, 0.05
    n = len(df)
    real_fvg = waived = no = 0
    for i in range(30, min(n - 10, 20000)):
        atr_i = a[i]
        if np.isnan(atr_i) or atr_i <= 0:
            continue
        for spike_len in (2, 3, 4, 5):
            start = i - spike_len + 1
            if start < 1:
                continue
            if sum(bull[start:i+1]) >= max(2, spike_len - 1) and close[i] > close[start]:
                if not all(ranges[j] > BODY_MULT * atr_i for j in range(start, i+1)):
                    if (high[start:i+1].max() - low[start:i+1].min()) < 2.0 * atr_i:
                        continue
                has = False
                for k in range(start, i):
                    if k + 2 <= i and low[k+2] > high[k] and (low[k+2]-high[k]) >= FVG_MULT*atr_i:
                        has = True
                        break
                if has:
                    real_fvg += 1
                elif (close[i] - open_[start]) > 1.5 * atr_i:
                    waived += 1
                else:
                    no += 1
                break
    return {"real_fvg": real_fvg, "waived_no_gap": waived, "rejected_no_gap": no,
            "waiver_pct_of_accepted": round(100 * waived / max(real_fvg + waived, 1), 2)}


def same_bar_sl_stats(m1, orders, cap=5.0):
    cut = m1.index[int(len(m1) * 0.70)]
    oo = filter_cap([o for o in orders if o.arm_time >= cut], cap)
    tr, st = simulate(m1, oo, risk_pct=0.005, max_sl_dist=cap, use_circuit_breaker=False)
    if tr is None or tr.empty:
        return {}
    same = tr[tr["same_m1_entry_exit"]]
    same_sl = same[same["reason"] == "SL"]
    return {
        "n": int(len(tr)),
        "same_m1_pct": float(st["same_m1_pct"]),
        "same_m1_sl_n": int(len(same_sl)),
        "same_m1_sl_pct_of_trades": round(100 * len(same_sl) / len(tr), 2),
        "pf": st["profit_factor"], "wr": st["win_rate"],
    }


def main():
    report = {"mismatches": MISMATCHES}
    report["fib_unit"] = fib_math_unit()
    print("LOAD", flush=True)
    m1, dxy = load()
    cut = m1.index[int(len(m1) * 0.70)]
    print("SP2L waiver count...", flush=True)
    report["sp2l_fvg_waiver"] = sp2l_fvg_waiver_rate(m1)
    print("gap-through...", flush=True)
    report["gap_through_probtb_m5"] = check_gap_through_bias(m1)
    print("not_ext lookahead...", flush=True)
    report["not_ext_lookahead"] = lookahead_not_ext_test(m1)

    print("GENERATE samples...", flush=True)
    # lighter gens for sample verify
    nds = generate_nds_fib(m1, rr=1.5, zones=(("062_078", 0.62, 0.78),))
    idr = generate_idris(m1)
    sp = generate_sp2l(m1, use_htf=True)
    pb = generate_pro_btb(m1, rr=2.0)
    pb_m5 = [o for o in pb if "m5_stop_breakout" in o.variant]
    # apply KEEP filter
    pb_keep = apply_confirmations(pb_m5, m1, dxy, {"htf": True, "not_extended": True})
    mm = generate_micromap(m1)
    amd = generate_amd_po3_ifvg(m1, range_mode="asian", tf="M5", entry_mode="market", tp_mode="range")

    report["order_counts"] = {
        "NDS": len(nds), "Idris": len(idr), "SP2L": len(sp),
        "ProBTB_all": len(pb), "ProBTB_m5": len(pb_m5), "ProBTB_keep_filt": len(pb_keep),
        "MicroMAP": len(mm), "AMD": len(amd),
    }
    print("verify trades...", flush=True)
    report["sample_verify"] = {
        "NDS": verify_trade_conditions(m1, nds, "NDS"),
        "Idris": verify_trade_conditions(m1, idr, "Idris"),
        "SP2L": verify_trade_conditions(m1, sp, "SP2L"),
        "ProBTB_m5_keepfilt": verify_trade_conditions(m1, pb_keep, "ProBTB"),
        "MicroMAP": verify_trade_conditions(m1, mm, "MicroMAP"),
        "AMD": verify_trade_conditions(m1, amd, "AMD"),
    }
    print("shift/random KEEP...", flush=True)
    report["shift_random_ProBTB"] = shift_and_random(m1, pb_keep, "ProBTB_m5_htf_notext")
    report["shift_random_AMD"] = shift_and_random(m1, amd, "AMD_asian_m5_mkt_range")
    report["same_bar_ProBTB"] = same_bar_sl_stats(m1, pb_keep)
    report["same_bar_AMD"] = same_bar_sl_stats(m1, amd)

    (OUT / "audit_report.json").write_text(json.dumps(report, indent=2, default=str))
    # short summary txt
    lines = []
    lines.append("CODE AUDIT SUMMARY")
    bugs = []
    for strat, items in MISMATCHES.items():
        for it in items:
            if it["sev"] == "BUG":
                bugs.append(f"[{strat}] {it['issue']}")
    lines.append(f"BUGS_FLAGGED={len(bugs)}")
    for b in bugs:
        lines.append("BUG: " + b)
    lines.append(f"fib_unit_pass={report['fib_unit']['pass']}")
    lines.append(f"sp2l_waiver={report['sp2l_fvg_waiver']}")
    lines.append(f"gap_through={report['gap_through_probtb_m5']}")
    lines.append(f"not_ext_lookahead={report['not_ext_lookahead']}")
    lines.append(f"shift_ProBTB={json.dumps(report['shift_random_ProBTB'], default=str)[:500]}")
    lines.append(f"shift_AMD={json.dumps(report['shift_random_AMD'], default=str)[:500]}")
    lines.append(f"same_bar_ProBTB={report['same_bar_ProBTB']}")
    (OUT / "summary.txt").write_text("\n".join(lines))
    print("DONE", OUT, flush=True)
    print("\n".join(lines[:30]), flush=True)


if __name__ == "__main__":
    main()
