#!/usr/bin/env python3
"""Backtest 4 new strategies on fixed engine. Outputs → results/new4/."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import simulate, sl_distance_price, count_sl_cap_skips, Order, SPREAD, SLIPPAGE
from monte_carlo import run_mc
from combine import signal_overlap
from strategies import (
    generate_orb, generate_asian_bo, generate_ema_pullback, generate_vwap_mr, generate_pro_btb,
)
from run_final_batch import load, filter_cap, period_orders, apply_confirmations, verdict_from

OUT = ROOT / "results" / "new4"
OUT.mkdir(parents=True, exist_ok=True)
CAPS = (5.0, 7.5, 8.0)
COST = {"strict": (0.35, 0.10), "cheap": (0.20, 0.05)}
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")  # as requested; fallback if missing


def risk_pct(cap):
    return cap / 1000.0


def zero_signal_days(tr, oos_index):
    if tr is None or tr.empty:
        days = pd.DatetimeIndex(oos_index.normalize().unique())
        days = days[days.dayofweek < 5]
        return 100.0
    traded = set(tr["day"].astype(str))
    days = pd.DatetimeIndex(oos_index.normalize().unique())
    days = [d for d in days if d.dayofweek < 5]
    zero = sum(1 for d in days if str(d.date()) not in traded)
    return 100.0 * zero / max(len(days), 1)


def eval_variant(m1, orders, variant, cap, spread, slip, dxy_flag, oos_cut):
    oo = [o for o in orders if o.variant == variant]
    oo = period_orders(oo, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
    skip = count_sl_cap_skips(oo, cap, spread)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=True, spread=spread, slip=slip, dxy_filter_flag=dxy_flag)
    return tr, st, skip


def eval_is(m1, orders, variant, cap, spread, slip, oos_cut):
    oo = [o for o in orders if o.variant == variant]
    oo = period_orders(oo, m1.index[0], oos_cut)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=True, spread=spread, slip=slip)
    return st


def walk_forward(m1, orders, variant, cap, spread, slip):
    n = len(m1); warm = int(n * 0.40); fold = (n - warm) // 4
    pos = valid = 0
    rs = []
    for k in range(4):
        o0 = warm + k * fold
        o1 = warm + (k + 1) * fold if k < 3 else n
        t0, t1 = m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1)
        oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
        oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
        tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                          use_circuit_breaker=True, spread=spread, slip=slip)
        if st["n_trades"] >= 5:
            valid += 1
            rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def shift_random(m1, orders, variant, cap, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side) <= cap + 1e-9]
    tr0, st0 = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    # shift arm +15/+60 keep prices
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes) for o in oo]
        _, st = simulate(m1, sh, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        out[f"shift{s}_pf"] = st["profit_factor"]
    rng = np.random.default_rng(0)
    rands = []
    for k in range(2):
        ro = []
        for o in oo:
            j = m1.index.searchsorted(o.arm_time, side="left")
            if j >= len(m1) - 5:
                continue
            jj = int(rng.integers(max(0, j - 40), min(len(m1) - 1, j + 40)))
            px = float(m1["close"].iloc[jj])
            risk = abs(o.price - o.sl)
            side = o.side if rng.random() < 0.5 else ("short" if o.side == "long" else "long")
            if side == "long":
                sl, tp = px - risk, px + abs(o.tp - o.price)
            else:
                sl, tp = px + risk, px - abs(o.tp - o.price)
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, o.kind, px, sl, tp,
                            "RAND", o.variant, {}, o.expire_minutes))
        _, st = simulate(m1, ro, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    return out


def build_pools(m1, dxy):
    pools = {}
    # ORB small grid: sessions × range × entry × sl × rr × atr
    print("  ORB...", flush=True)
    orb = []
    # small IS grid: 2 sess × {30,60} × stop/close × opposite × {1.5,2,eod} × atr on
    for session, rmin, entry, rr in product(
        ("london", "ny"), (30, 60), ("stop", "close_break"), (1.5, 2.0, 0.0),
    ):
        orb += generate_orb(m1, dxy, False, session, rmin, entry, "opposite", rr, True)
    # mid-SL only for best-looking session/range
    for session, rmin, rr in product(("london", "ny"), (30,), (2.0,)):
        orb += generate_orb(m1, dxy, False, session, rmin, "stop", "mid", rr, True)
    pools["ORB"] = orb
    print(f"    orders={len(orb)} variants={len({o.variant for o in orb})}", flush=True)

    print("  AsianBO...", flush=True)
    asian = []
    for mode, slm, rr, entry, win in product(
        ("breakout", "fade"), ("opposite", "mid"), (1.5, 2.0),
        ("stop", "close_break"), ("london_ny",),
    ):
        if mode == "fade" and entry == "stop":
            continue  # fade only close_break reclaim
        asian += generate_asian_bo(m1, dxy, False, mode, slm, rr, entry if mode == "breakout" else "close_break", win)
    pools["AsianBO"] = asian
    print(f"    orders={len(asian)} variants={len({o.variant for o in asian})}", flush=True)

    print("  EMA_PB...", flush=True)
    ema_o = []
    for rule, trend, pb, rr, slm in product(
        ("1h", "15min"), ("ema50_200", "slope50"), (20, 50), (2.0,), ("swing", "atr"),
    ):
        ema_o += generate_ema_pullback(m1, dxy, False, rule, trend, pb, rr, slm, False)
    # one trailing variant each TF
    for rule in ("1h", "15min"):
        ema_o += generate_ema_pullback(m1, dxy, False, rule, "ema50_200", 20, 2.0, "swing", True)
    pools["EMA_PB"] = ema_o
    print(f"    orders={len(ema_o)} variants={len({o.variant for o in ema_o})}", flush=True)

    print("  VWAP...", flush=True)
    vw = []
    for mode, sd, rr, tf in product(
        ("fade2sd", "trend_pb"), (2.0, 2.5), (1.5, 2.0), (False, True),
    ):
        if mode == "trend_pb" and sd == 2.5:
            continue
        vw += generate_vwap_mr(m1, dxy, False, mode, sd, rr, tf)
    pools["VWAP_MR"] = vw
    print(f"    orders={len(vw)} variants={len({o.variant for o in vw})}", flush=True)

    # DXY versions: apply gate on copies
    print("  DXY gates...", flush=True)
    from strategies.common import apply_dxy_gate
    for name in list(pools.keys()):
        pools[name + "_DXY"] = apply_dxy_gate(pools[name], dxy, True)
        print(f"    {name}_DXY={len(pools[name+'_DXY'])}", flush=True)
    return pools


def pick_best_is(m1, orders, oos_cut, cap=8.0):
    """Pick variant on IS by expectancy (n>=20) under strict costs @cap."""
    variants = sorted({o.variant for o in orders})
    best = None
    for v in variants:
        st = eval_is(m1, orders, v, cap, 0.35, 0.10, oos_cut)
        if st["n_trades"] < 15:
            continue
        score = (st["expectancy_r"], st["profit_factor"], st["n_trades"])
        row = (score, v, st)
        if best is None or score > best[0]:
            best = row
    if best is None:
        # fallback most trades
        for v in variants:
            st = eval_is(m1, orders, v, cap, 0.35, 0.10, oos_cut)
            row = ((st["expectancy_r"], st["profit_factor"], st["n_trades"]), v, st)
            if best is None or st["n_trades"] > best[2]["n_trades"]:
                best = row
    return best


def main():
    print("LOAD", flush=True)
    m1, dxy = load()
    oos_cut = OOS_CUT
    if oos_cut not in m1.index and oos_cut < m1.index[0]:
        oos_cut = m1.index[int(len(m1) * 0.70)]
    # align to first bar on/after cut
    i = m1.index.searchsorted(oos_cut)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    print(f"bars={len(m1)} oos_cut={oos_cut}", flush=True)

    pools = build_pools(m1, dxy)
    rows = []
    keep_orders = {}

    for name, orders in pools.items():
        print(f"EVAL {name}...", flush=True)
        if not orders:
            continue
        best = pick_best_is(m1, orders, oos_cut, cap=8.0)
        if best is None:
            continue
        _, variant, is_st = best
        for cap in CAPS:
            for cname, (sp, sl) in COST.items():
                if cname == "cheap" and cap != 8.0:
                    continue  # one cheap row
                tr, st, skip = eval_variant(m1, orders, variant, cap, sp, sl, "DXY" in name, oos_cut)
                wf, wf_rs = walk_forward(m1, orders, variant, cap, sp, sl)
                mc = None
                if tr is not None and len(tr) >= 15 and st["profit_factor"] >= 1.05 and cname == "strict":
                    mc_df = run_mc(tr["r_multiple"].values, n_sims=2500, risk_pcts=(risk_pct(cap),))
                    if len(mc_df):
                        mc = float(mc_df.iloc[0]["pass_prob"])
                verd, reason = verdict_from(st, wf, mc if cap == 5.0 else mc)
                # for non-0.5% MC still report
                zday = zero_signal_days(tr, m1[m1.index >= oos_cut].index)
                row = {
                    "setup": name, "variant": variant, "cap": cap, "cost": cname,
                    "is_n": is_st["n_trades"], "is_r": is_st["expectancy_r"], "is_pf": is_st["profit_factor"],
                    "oos_n": st["n_trades"], "oos_wr": st["win_rate"], "oos_r": st["expectancy_r"],
                    "oos_pf": st["profit_factor"], "oos_dd": st["max_dd_pct"], "oos_tpd": st["trades_per_day"],
                    "zero_day_pct": zday, "skip_pct": skip["skip_pct"],
                    "wf_pos": wf, "wf_rs": wf_rs, "mc_pass": mc,
                    "verdict": verd, "reason": reason, "dxy": "DXY" in name,
                }
                rows.append(row)
                print(f"  {name} {variant[:40]} @{cap}/{cname}: n={st['n_trades']} PF={st['profit_factor']:.2f} R={st['expectancy_r']:+.2f} {verd}", flush=True)
                if verd in ("KEEP", "MAYBE") and cname == "strict" and cap in (5.0, 7.5, 8.0):
                    key = f"{name}@{cap}"
                    keep_orders[key] = {
                        "orders": [o for o in orders if o.variant == variant],
                        "variant": variant, "cap": cap, "tr": tr, "row": row,
                    }
                    if tr is not None and len(tr):
                        tr.to_csv(OUT / f"trades_{name}_cap{cap}.csv", index=False)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "verdicts.csv", index=False)

    # Sanity on KEEP/MAYBE
    sanity = {}
    for key, info in keep_orders.items():
        if info["row"]["verdict"] not in ("KEEP", "MAYBE"):
            continue
        # only once per setup prefer cap 8
        name = info["row"]["setup"]
        if name in sanity:
            continue
        print(f"SANITY {key}...", flush=True)
        sanity[name] = shift_random(m1, info["orders"], info["variant"], info["cap"], oos_cut)
        sanity[name]["verdict"] = info["row"]["verdict"]
        sanity[name]["cap"] = info["cap"]
        sanity[name]["variant"] = info["variant"]
    (OUT / "sanity.json").write_text(json.dumps(sanity, indent=2, default=str))

    # Combine with ProBTB M15 m4
    print("ProBTB M15 m4 reference + overlap...", flush=True)
    pb = generate_pro_btb(m1, dxy, False, rr=2.0, rule="15min")
    pb_v = [v for v in {o.variant for o in pb} if "m4_limit_broken" in v]
    pb_v = pb_v[0] if pb_v else None
    combos = []
    if pb_v:
        pb_o = [o for o in pb if o.variant == pb_v]
        pb_o = apply_confirmations(pb_o, m1, dxy, {"htf": True})
        for key, info in keep_orders.items():
            if info["row"]["cost"] != "strict" if "cost" in info["row"] else False:
                pass
            if info["row"]["verdict"] not in ("KEEP", "MAYBE"):
                continue
            cap = info["cap"]
            a = period_orders(filter_cap(info["orders"], cap), oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
            # tag strategy name on orders already
            b = period_orders(filter_cap(pb_o, cap), oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
            # overlap
            # build fake trade dfs for overlap helper — use arm times
            fa = pd.DataFrame([{"entry_time": o.arm_time, "side": o.side, "strategy": o.strategy} for o in a])
            fb = pd.DataFrame([{"entry_time": o.arm_time, "side": o.side, "strategy": "ProBTB"} for o in b])
            if fa.empty or fb.empty:
                continue
            # simple overlap count 30m
            same = opp = 0
            for _, r in fa.iterrows():
                w = fb[(fb["entry_time"] - r["entry_time"]).abs() <= pd.Timedelta(minutes=30)]
                for _, q in w.iterrows():
                    if q["side"] == r["side"]:
                        same += 1
                    else:
                        opp += 1
            # merged sim: concatenate orders, one position engine already sequential
            merged = sorted(a + b, key=lambda o: o.arm_time)
            tr, st = simulate(m1, merged, risk_pct=risk_pct(cap), max_sl_dist=cap,
                              use_circuit_breaker=True)
            combos.append({
                "with": info["row"]["setup"], "probtb_variant": pb_v, "cap": cap,
                "same_side_30m": same, "opp_30m": opp,
                "merged_n": st["n_trades"], "merged_pf": st["profit_factor"],
                "merged_r": st["expectancy_r"], "merged_dd": st["max_dd_pct"],
                "solo_pf": info["row"]["oos_pf"], "solo_n": info["row"]["oos_n"],
            })
            print(f"  combo {info['row']['setup']}@{cap}: merged PF={st['profit_factor']:.2f} n={st['n_trades']} same={same} opp={opp}", flush=True)
    pd.DataFrame(combos).to_csv(OUT / "combine_probtb_m15.csv", index=False)

    # DXY help summary
    dxy_help = []
    bases = [r for r in rows if not r["dxy"] and r["cost"] == "strict"]
    for r in bases:
        twin = [x for x in rows if x["dxy"] and x["setup"] == r["setup"] + "_DXY"
                and x["cap"] == r["cap"] and x["cost"] == "strict"]
        # setup names are ORB vs ORB_DXY
        twin = [x for x in rows if x["setup"] == r["setup"] + "_DXY" and x["cap"] == r["cap"] and x["cost"] == "strict"]
        if not twin:
            # try match
            twin = [x for x in rows if x["dxy"] and x["setup"].startswith(r["setup"].split("_")[0])
                    and x["cap"] == r["cap"] and x["cost"] == "strict" and x["setup"] != r["setup"]]
        # simpler: pair ORB with ORB_DXY
        alt_name = r["setup"] + "_DXY"
        twin = [x for x in rows if x["setup"] == alt_name and x["cap"] == r["cap"] and x["cost"] == "strict"]
        if twin:
            t = twin[0]
            dxy_help.append({
                "setup": r["setup"], "cap": r["cap"],
                "base_pf": r["oos_pf"], "dxy_pf": t["oos_pf"],
                "base_n": r["oos_n"], "dxy_n": t["oos_n"],
                "helped": t["oos_pf"] > r["oos_pf"] + 0.05 and t["oos_r"] > r["oos_r"],
            })
    pd.DataFrame(dxy_help).to_csv(OUT / "dxy_help.csv", index=False)

    summary = {
        "oos_cut": str(oos_cut),
        "verdicts": rows,
        "sanity": sanity,
        "combos": combos,
        "dxy_help": dxy_help,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("DONE", flush=True)
    # print table
    show = df[(df["cost"] == "strict")].copy()
    cols = ["setup", "variant", "cap", "oos_n", "oos_wr", "oos_r", "oos_pf", "oos_dd", "oos_tpd", "zero_day_pct", "wf_pos", "mc_pass", "verdict"]
    print(show[cols].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
