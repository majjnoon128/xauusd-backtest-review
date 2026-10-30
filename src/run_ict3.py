#!/usr/bin/env python3
"""Backtest ICT3: Silver Bullet, LiqSweepMSS, SessionBoxMSS. Same audited protocol."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "ict3"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order
from monte_carlo import run_mc
from strategies import (
    generate_silver_bullet, generate_liq_sweep_mss, generate_session_box_mss,
    generate_pro_btb, generate_asian_bo,
)
from strategies.common import apply_dxy_gate
from run_final_batch import load, filter_cap, period_orders, apply_confirmations, verdict_from

CAPS = (5.0, 7.5, 8.0)
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")


def risk_pct(cap): return cap / 1000.0


def zero_days(tr, oos_idx):
    days = [d for d in pd.DatetimeIndex(oos_idx.normalize().unique())
            if int(getattr(d, "day_of_week", d.dayofweek)) < 5]
    if not days:
        return 100.0
    traded = set(tr["day"].astype(str)) if tr is not None and len(tr) else set()
    return 100.0 * sum(1 for d in days if str(d.date()) not in traded) / len(days)


def buy_sell_split(tr):
    if tr is None or len(tr) == 0:
        return {"buy_n": 0, "sell_n": 0, "buy_pct": None, "sell_wr": None, "buy_wr": None}
    b = tr[tr["side"] == "long"]
    s = tr[tr["side"] == "short"]
    def wr(x):
        if len(x) == 0:
            return None
        return float((x["r_multiple"] > 0).mean())
    return {"buy_n": int(len(b)), "sell_n": int(len(s)),
            "buy_pct": float(len(b) / len(tr)), "buy_wr": wr(b), "sell_wr": wr(s)}


def sim(m1, orders, variant, cap, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    skip = count_sl_cap_skips(oo, cap, spread)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=cb, spread=spread, slip=slip)
    return tr, st, skip


def wf(m1, orders, variant, cap, spread=0.35, slip=0.10):
    n = len(m1); warm = int(n * 0.4); fold = (n - warm) // 4
    pos = valid = 0; rs = []
    for k in range(4):
        o0 = warm + k * fold; o1 = warm + (k + 1) * fold if k < 3 else n
        tr, st, _ = sim(m1, orders, variant, cap, spread, slip,
                        m1.index[o0], m1.index[o1 - 1] + pd.Timedelta(minutes=1))
        if st["n_trades"] >= 5:
            valid += 1; rs.append(round(st["expectancy_r"], 3))
            if st["expectancy_r"] > 0:
                pos += 1
    return (pos / valid if valid else 0.0), rs


def sanity(m1, orders, variant, cap, oos_cut):
    oo = [o for o in orders if o.variant == variant and o.arm_time >= oos_cut]
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side) <= cap + 1e-9]
    _, st0 = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
    out = {"base_pf": st0["profit_factor"], "base_n": st0["n_trades"]}
    for s in (15, 60):
        sh = [Order(o.arm_time + pd.Timedelta(minutes=s), o.side, o.kind, o.price, o.sl, o.tp,
                    o.strategy, o.variant, dict(o.meta), o.expire_minutes, o.max_hold_minutes)
              for o in oo]
        _, st = simulate(m1, sh, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
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
            ro.append(Order(m1.index[jj] + pd.Timedelta(minutes=1), side, o.kind, px, sl, tp,
                            "RAND", o.variant, {}, 30))
        _, st = simulate(m1, ro, risk_pct=risk_pct(cap), max_sl_dist=cap, use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"] = float(np.mean(rands)) if rands else None
    # pass if base beats rand and shift doesn't collapse to 0
    out["pass"] = bool(
        out["base_n"] >= 15 and out["base_pf"] >= 1.05
        and out["rand_mean_pf"] is not None and out["base_pf"] > out["rand_mean_pf"] + 0.1
        and out.get("shift15_pf", 0) > 0.3
    )
    return out


def build(m1, dxy):
    pools = {}
    print("SilverBullet", flush=True)
    sb = []
    for entry, tp, d, mss in product(("limit_mid", "market"),
                                     ("rr1.5", "rr2", "liq"),
                                     (0.8, 1.0),
                                     ("reclaim", "either")):
        sb += generate_silver_bullet(m1, dxy, False, entry, tp, d, 2, mss, "atr_buf")
    pools["SilverBullet"] = sb
    print(" ", len(sb), len({o.variant for o in sb}), flush=True)

    print("LiqSweepMSS", flush=True)
    ls = []
    for level, sess, entry, tp in product(
            ("asian", "prev_day", "both"),
            ("london", "ny", "both"),
            ("limit_mid", "market"),
            ("rr1.5", "rr2", "liq")):
        # keep grid small: skip some combos
        if level == "both" and sess != "both":
            continue
        if entry == "market" and tp == "liq":
            continue
        ls += generate_liq_sweep_mss(m1, dxy, False, level, sess, entry, tp, 1.0, "atr_buf")
    pools["LiqSweepMSS"] = ls
    print(" ", len(ls), len({o.variant for o in ls}), flush=True)

    print("SessionBoxMSS", flush=True)
    bx = []
    for entry, tp, req, d in product(
            ("limit_mid", "market"),
            ("rr1.5", "rr2", "box_opp"),
            (True, False),
            (0.8, 1.0)):
        if not req and d == 1.0:
            continue
        bx += generate_session_box_mss(m1, dxy, False, entry, tp, req, d, "atr_buf")
    pools["SessionBoxMSS"] = bx
    print(" ", len(bx), len({o.variant for o in bx}), flush=True)

    for n in list(pools):
        pools[n + "_DXY"] = apply_dxy_gate(pools[n], dxy, True)
        print(f"  {n}_DXY", len(pools[n + '_DXY']), flush=True)
    return pools


def main():
    m1, dxy = load()
    i = m1.index.searchsorted(OOS_CUT)
    oos_cut = m1.index[min(i, len(m1) - 1)]
    print("cut", oos_cut, "bars", len(m1), flush=True)
    pools = build(m1, dxy)
    rows = []; candidates = []

    for name, orders in pools.items():
        variants = sorted({o.variant for o in orders})
        print(f"SCAN {name} nvar={len(variants)}", flush=True)
        scored = []
        for v in variants:
            tr, st, sk = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
            if st["n_trades"] >= 10:
                scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st))
        scored.sort(reverse=True)
        top = scored[:5]
        if not top and variants:
            fb = []
            for v in variants:
                tr, st, _ = sim(m1, orders, v, 8.0, 0.35, 0.10, m1.index[0], oos_cut)
                fb.append((st["n_trades"], st["expectancy_r"], v, st))
            fb.sort(reverse=True)
            top = [(fb[0][1], fb[0][3]["profit_factor"], fb[0][0], fb[0][2], fb[0][3])]

        for _, __, ___, v, is_st in top:
            for cap in CAPS:
                for cname, sp, sl in (("strict", 0.35, 0.10), ("cheap", 0.20, 0.05)):
                    if cname == "cheap" and cap != 8.0:
                        continue
                    tr, st, sk = sim(m1, orders, v, cap, sp, sl, oos_cut,
                                     m1.index[-1] + pd.Timedelta(minutes=1))
                    wfp, wfr = wf(m1, orders, v, cap, sp, sl)
                    mc = None
                    if cname == "strict" and tr is not None and len(tr) >= 15 and st["profit_factor"] >= 1.05:
                        mc_df = run_mc(tr["r_multiple"].values, n_sims=2000, risk_pcts=(risk_pct(cap),))
                        if len(mc_df):
                            mc = float(mc_df.iloc[0]["pass_prob"])
                    verd, reason = verdict_from(st, wfp, mc)
                    bs = buy_sell_split(tr)
                    row = dict(
                        setup=name, variant=v, cap=cap, cost=cname, dxy="_DXY" in name,
                        is_n=is_st["n_trades"], is_r=is_st["expectancy_r"], is_pf=is_st["profit_factor"],
                        oos_n=st["n_trades"], oos_wr=st["win_rate"], oos_r=st["expectancy_r"],
                        oos_pf=st["profit_factor"], oos_dd=st["max_dd_pct"], oos_tpd=st["trades_per_day"],
                        zero_day_pct=zero_days(tr, m1[m1.index >= oos_cut].index),
                        skip_pct=sk["skip_pct"], wf_pos=wfp, wf_rs=wfr, mc_pass=mc,
                        verdict=verd, reason=reason, **bs,
                    )
                    rows.append(row)
                    if verd in ("KEEP", "MAYBE") and cname == "strict":
                        candidates.append((name, v, cap, orders, tr, row))
                    if cname == "strict":
                        print(
                            f"  {name}|{v[:40]}@{cap}: n={st['n_trades']} WR={st['win_rate']:.0%} "
                            f"PF={st['profit_factor']:.2f} R={st['expectancy_r']:+.2f} "
                            f"buy={bs['buy_n']}/sell={bs['sell_n']} wf={wfp:.0%} {verd}",
                            flush=True,
                        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "verdicts.csv", index=False)

    summary = []
    for fam in ("SilverBullet", "LiqSweepMSS", "SessionBoxMSS"):
        sub = df[(df["cost"] == "strict") & (df["setup"].isin([fam, fam + "_DXY"]))]
        if sub.empty:
            continue
        good = sub[sub["verdict"].isin(["KEEP", "MAYBE"])]
        pick = (good.sort_values(["oos_r", "oos_pf", "oos_n"], ascending=False).iloc[0]
                if len(good) else
                sub.sort_values(["oos_pf", "oos_n"], ascending=False).iloc[0])
        summary.append(pick.to_dict())
    pd.DataFrame(summary).to_csv(OUT / "best_per_family.csv", index=False)

    sanity_out = {}
    seen = set()
    for name, v, cap, orders, tr, row in candidates:
        if name in seen:
            continue
        seen.add(name)
        print("SANITY", name, flush=True)
        sanity_out[name] = sanity(m1, orders, v, cap, oos_cut)
        sanity_out[name].update({k: row[k] for k in ("verdict", "variant", "cap", "oos_pf", "oos_n", "oos_r")})
        # demote if sanity fail
        if row["verdict"] in ("KEEP", "MAYBE") and not sanity_out[name].get("pass"):
            sanity_out[name]["demoted_to"] = "DROP"
            sanity_out[name]["demote_reason"] = "sanity fail (shift/rand)"
        if tr is not None and len(tr):
            tr.to_csv(OUT / f"trades_{name}_cap{cap}.csv", index=False)
    # Also sanity near-misses: best PF with n>=15 even if DROP
    for fam in ("SilverBullet", "LiqSweepMSS", "SessionBoxMSS"):
        for dxy_s in (fam, fam + "_DXY"):
            if dxy_s in seen:
                continue
            sub = df[(df.setup == dxy_s) & (df.cost == "strict") & (df.oos_n >= 15)]
            if sub.empty:
                continue
            pick = sub.sort_values(["oos_pf", "oos_r"], ascending=False).iloc[0]
            if pick.oos_pf < 1.0:
                continue
            print("SANITY near", dxy_s, flush=True)
            orders = pools[dxy_s]
            sanity_out[dxy_s + "_near"] = sanity(m1, orders, pick.variant, float(pick.cap), oos_cut)
            seen.add(dxy_s)
    (OUT / "sanity.json").write_text(json.dumps(sanity_out, indent=2, default=str))

    # Combine with ProBTB M15 m4 and Asian fade+DXY near-miss
    print("COMBINE", flush=True)
    pb = generate_pro_btb(m1, dxy, False, rr=2.0, rule="15min")
    pb_vs = [v for v in {o.variant for o in pb} if "m4_limit_broken" in v]
    asian = generate_asian_bo(m1, dxy, False, "fade", "atr_buf", 1.5, "close_break", "london_ny")
    asian = apply_dxy_gate(asian, dxy, True)
    asian_v = sorted({o.variant for o in asian})[0] if asian else None
    combos = []
    peers = []
    if pb_vs:
        pb_o = apply_confirmations([o for o in pb if o.variant == pb_vs[0]], m1, dxy, {"htf": True})
        peers.append(("ProBTB_M15_m4", pb_o, 8.0))
    if asian_v:
        peers.append(("AsianFade_DXY", [o for o in asian if o.variant == asian_v], 8.0))

    # candidates + top near-miss per family for combine
    combine_src = list(candidates)
    for fam in ("SilverBullet", "LiqSweepMSS", "SessionBoxMSS"):
        for dxy_s in (fam, fam + "_DXY"):
            sub = df[(df.setup == dxy_s) & (df.cost == "strict") & (df.cap == 8.0)]
            if sub.empty:
                continue
            pick = sub.sort_values(["oos_pf", "oos_n"], ascending=False).iloc[0]
            if pick.oos_n < 10:
                continue
            if not any(c[0] == dxy_s for c in combine_src):
                combine_src.append((dxy_s, pick.variant, 8.0, pools[dxy_s], None, pick.to_dict()))

    for name, v, cap, orders, tr, row in combine_src:
        a = period_orders(filter_cap([o for o in orders if o.variant == v], cap),
                          oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
        for peer_name, peer_orders, peer_cap in peers:
            b = period_orders(filter_cap(peer_orders, peer_cap),
                              oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
            merged = sorted(a + b, key=lambda o: o.arm_time)
            trm, stm = simulate(m1, merged, risk_pct=risk_pct(cap), max_sl_dist=cap,
                                use_circuit_breaker=True)
            same = opp = 0
            fa = pd.DataFrame([{"t": o.arm_time, "s": o.side} for o in a])
            fb = pd.DataFrame([{"t": o.arm_time, "s": o.side} for o in b])
            if len(fa) and len(fb):
                for _, r in fa.iterrows():
                    w = fb[(fb["t"] - r["t"]).abs() <= pd.Timedelta(minutes=30)]
                    same += int((w["s"] == r["s"]).sum())
                    opp += int((w["s"] != r["s"]).sum())
            combos.append(dict(
                setup=name, variant=v, cap=cap, peer=peer_name,
                solo_pf=row.get("oos_pf"), solo_n=row.get("oos_n"),
                merged_pf=stm["profit_factor"], merged_n=stm["n_trades"],
                merged_r=stm["expectancy_r"], merged_dd=stm["max_dd_pct"],
                same30=same, opp30=opp,
            ))
            print(f"  {name}+{peer_name}@{cap}: merged PF={stm['profit_factor']:.2f} n={stm['n_trades']} "
                  f"same={same} opp={opp}", flush=True)
    pd.DataFrame(combos).to_csv(OUT / "combine.csv", index=False)

    helps = []
    for fam in ("SilverBullet", "LiqSweepMSS", "SessionBoxMSS"):
        for cap in CAPS:
            a = df[(df.setup == fam) & (df.cap == cap) & (df.cost == "strict")]
            b = df[(df.setup == fam + "_DXY") & (df.cap == cap) & (df.cost == "strict")]
            if a.empty or b.empty:
                continue
            aa = a.sort_values(["oos_r", "oos_pf"], ascending=False).iloc[0]
            bb = b.sort_values(["oos_r", "oos_pf"], ascending=False).iloc[0]
            helps.append(dict(
                family=fam, cap=cap,
                base_v=aa.variant, base_pf=aa.oos_pf, base_r=aa.oos_r, base_n=aa.oos_n,
                dxy_v=bb.variant, dxy_pf=bb.oos_pf, dxy_r=bb.oos_r, dxy_n=bb.oos_n,
                helped=bool(bb.oos_pf > aa.oos_pf + 0.05 and bb.oos_r > aa.oos_r),
            ))
    pd.DataFrame(helps).to_csv(OUT / "dxy_help.csv", index=False)

    # Final demotions
    final = {}
    for s in summary:
        name = s["setup"].replace("_DXY", "")
        key = s["setup"]
        verd = s["verdict"]
        san = sanity_out.get(key) or sanity_out.get(name)
        if verd in ("KEEP", "MAYBE") and san and not san.get("pass", True):
            verd = "DROP"
            reason = "sanity demotion"
        else:
            reason = s.get("reason")
        final[key] = {**{k: s[k] for k in s if k in (
            "setup", "variant", "cap", "oos_n", "oos_wr", "oos_r", "oos_pf", "oos_dd",
            "oos_tpd", "zero_day_pct", "wf_pos", "mc_pass", "buy_n", "sell_n", "dxy")},
            "verdict_auto": s["verdict"], "verdict_final": verd, "reason": reason}

    (OUT / "summary.json").write_text(json.dumps({
        "oos_cut": str(oos_cut), "n_rows": len(rows),
        "candidates": [r for r in rows if r["verdict"] in ("KEEP", "MAYBE") and r["cost"] == "strict"],
        "sanity": sanity_out, "combos": combos, "helps": helps,
        "best_per_family": summary, "final": final,
    }, indent=2, default=str))
    print("DONE candidates",
          len([r for r in rows if r["verdict"] in ("KEEP", "MAYBE") and r["cost"] == "strict"]),
          flush=True)


if __name__ == "__main__":
    main()
