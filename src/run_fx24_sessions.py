#!/usr/bin/env python3
"""FX24 Daily Sessions Algorithm — frequency + tradable rules on XAUUSD."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_final_batch import load, verdict_from
from engine import Order, simulate, sl_distance_price
from indicators import resample_ohlc, bar_end
from audit_runner import OOS_CUT, oos_trading_days, tpd_true, is_rank, sim, wf, COST_ROWS
from strategies.common import apply_dxy_gate, dedupe_orders

OUT = ROOT / "results" / "batch3" / "fx24_sessions"
OUT.mkdir(parents=True, exist_ok=True)


def sess_ohlc(m1, day, h0, h1):
    a = day + pd.Timedelta(hours=h0)
    b = day + pd.Timedelta(hours=h1)
    seg = m1[(m1.index >= a) & (m1.index < b)]
    if len(seg) < 30:
        return None
    return dict(o=float(seg["open"].iloc[0]), h=float(seg["high"].max()),
                l=float(seg["low"].min()), c=float(seg["close"].iloc[-1]),
                start=a, end=b)


def classify_asia(a, med_asia):
    rng = a["h"] - a["l"]
    body = abs(a["c"] - a["o"])
    direction = 1 if a["c"] > a["o"] else (-1 if a["c"] < a["o"] else 0)
    is_range = (body / max(rng, 1e-6) < 0.35) or (rng < 0.85 * med_asia) or (rng < 1.5)
    return ("range" if is_range else "trend"), direction, rng


def sess_dir(s):
    return 1 if s["c"] > s["o"] else (-1 if s["c"] < s["o"] else 0)


def vs_prior(cur, prior_h, prior_l, prior_dir):
    cd = sess_dir(cur)
    if prior_dir > 0 and cur["c"] > prior_h:
        return "cont"
    if prior_dir < 0 and cur["c"] < prior_l:
        return "cont"
    if prior_dir > 0 and cur["c"] < prior_l:
        return "rev"
    if prior_dir < 0 and cur["c"] > prior_h:
        return "rev"
    if cd == 0 or prior_dir == 0:
        return "flat"
    return "cont" if cd == prior_dir else "rev"


def main():
    m1, dxy = load()
    dates = [d for d in pd.Index(m1.index.normalize().unique()) if d.dayofweek < 5]
    asia_ranges = []
    for d in dates:
        a = sess_ohlc(m1, d, 0, 7)
        if a:
            asia_ranges.append(a["h"] - a["l"])
    med_asia = float(np.median(asia_ranges)) if asia_ranges else 5.0

    rows = []
    for d in dates:
        asia = sess_ohlc(m1, d, 0, 7)
        lon = sess_ohlc(m1, d, 7, 12)
        ny = sess_ohlc(m1, d, 12, 21)
        if not asia or not lon or not ny:
            continue
        a_type, a_dir, a_rng = classify_asia(asia, med_asia)
        lon_broke_hi = lon["h"] > asia["h"]
        lon_broke_lo = lon["l"] < asia["l"]
        if a_type == "range":
            if lon_broke_hi or lon_broke_lo:
                l_rel = "fake" if asia["l"] <= lon["c"] <= asia["h"] else "cont"
            else:
                l_rel = "flat"
        else:
            l_rel = vs_prior(lon, asia["h"], asia["l"], a_dir)
        l_dir = sess_dir(lon)
        n_rel = vs_prior(ny, lon["h"], lon["l"], l_dir)
        if a_type == "range" and l_rel == "fake" and n_rel == "cont":
            scen = 1
        elif a_type == "trend" and l_rel == "cont" and n_rel == "cont":
            scen = 2
        elif a_type == "trend" and l_rel == "cont" and n_rel == "rev":
            scen = 3
        else:
            scen = 0
        rows.append(dict(day=str(d.date()), a_type=a_type, a_dir=a_dir, a_rng=a_rng,
                         l_rel=l_rel, l_dir=l_dir, n_rel=n_rel, scen=scen))

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "scenario_days.csv", index=False)
    ar, at = df[df.a_type == "range"], df[df.a_type == "trend"]
    stats = {
        "n_days": len(df), "med_asia_range": med_asia,
        "asia_range_pct": float((df.a_type == "range").mean()),
        "asia_trend_pct": float((df.a_type == "trend").mean()),
        "scenario_n": {str(k): int(v) for k, v in df.scen.value_counts().items()},
        "scenario_freq": {str(k): float(v) for k, v in df.scen.value_counts(normalize=True).items()},
        "P_lon_fake_given_asia_range": float((ar.l_rel == "fake").mean()) if len(ar) else None,
        "P_lon_cont_given_asia_range": float((ar.l_rel == "cont").mean()) if len(ar) else None,
        "P_lon_cont_given_asia_trend": float((at.l_rel == "cont").mean()) if len(at) else None,
        "P_lon_rev_given_asia_trend": float((at.l_rel == "rev").mean()) if len(at) else None,
        "P_ny_cont_uncond": float((df.n_rel == "cont").mean()),
        "P_ny_rev_uncond": float((df.n_rel == "rev").mean()),
        "P_ny_cont_after_asia_range_lon_fake": float((df[(df.a_type=="range")&(df.l_rel=="fake")].n_rel=="cont").mean()) if len(df[(df.a_type=="range")&(df.l_rel=="fake")]) else None,
        "P_ny_cont_after_asia_trend_lon_cont": float((df[(df.a_type=="trend")&(df.l_rel=="cont")].n_rel=="cont").mean()) if len(df[(df.a_type=="trend")&(df.l_rel=="cont")]) else None,
        "P_ny_rev_after_asia_trend_lon_cont": float((df[(df.a_type=="trend")&(df.l_rel=="cont")].n_rel=="rev").mean()) if len(df[(df.a_type=="trend")&(df.l_rel=="cont")]) else None,
        "baseline_lon_fake": float((df.l_rel == "fake").mean()),
    }
    (OUT / "freq_stats.json").write_text(json.dumps(stats, indent=2))
    print("FREQ", json.dumps(stats, indent=2), flush=True)

    def gen(rule, rr):
        orders = []
        for d in dates:
            asia = sess_ohlc(m1, d, 0, 7)
            if not asia:
                continue
            a_type, a_dir, _ = classify_asia(asia, med_asia)
            if rule == "r1_fade_lon" and a_type == "range":
                lon_m5 = resample_ohlc(m1[(m1.index >= asia["end"]) & (m1.index < d + pd.Timedelta(hours=12))], "5min")
                for t, r in lon_m5.iterrows():
                    c, h, l = float(r["close"]), float(r["high"]), float(r["low"])
                    side = sl = None; px = c
                    if c > asia["h"]:
                        side, sl = "short", h + 0.15
                    elif c < asia["l"]:
                        side, sl = "long", l - 0.15
                    if side is None:
                        continue
                    risk = abs(px - sl)
                    if risk < 0.2 or risk > 20:
                        break
                    tp = px - rr * risk if side == "short" else px + rr * risk
                    orders.append(Order(bar_end(t, 5), side, "market", px, sl, tp, "FX24", f"r1_fade_lon_rr{rr:g}", {}, 90, 240))
                    break
            elif rule == "r2_lon_cont" and a_type == "trend" and a_dir != 0:
                lon_m5 = resample_ohlc(m1[(m1.index >= asia["end"]) & (m1.index < d + pd.Timedelta(hours=12))], "5min")
                for t, r in lon_m5.iterrows():
                    c = float(r["close"]); px = c; side = sl = None
                    if a_dir > 0 and c > asia["h"]:
                        side = "long"; sl = asia["l"] if (asia["h"] - asia["l"]) <= 8 else c - 2.0
                    elif a_dir < 0 and c < asia["l"]:
                        side = "short"; sl = asia["h"] if (asia["h"] - asia["l"]) <= 8 else c + 2.0
                    if side is None:
                        continue
                    risk = abs(px - sl)
                    if risk < 0.2:
                        break
                    tp = px + rr * risk if side == "long" else px - rr * risk
                    orders.append(Order(bar_end(t, 5), side, "market", px, sl, tp, "FX24", f"r2_lon_cont_rr{rr:g}", {}, 90, 240))
                    break
            elif rule == "r3_ny_cont":
                lon = sess_ohlc(m1, d, 7, 12)
                if not lon:
                    continue
                l_dir = sess_dir(lon)
                if l_dir == 0:
                    continue
                ny_m5 = resample_ohlc(m1[(m1.index >= lon["end"]) & (m1.index < d + pd.Timedelta(hours=18))], "5min")
                for t, r in ny_m5.iterrows():
                    c = float(r["close"]); px = c
                    if l_dir > 0:
                        side = "long"; sl = lon["l"] if (c - lon["l"]) <= 10 else c - 2.5
                    else:
                        side = "short"; sl = lon["h"] if (lon["h"] - c) <= 10 else c + 2.5
                    risk = abs(px - sl)
                    if risk < 0.3:
                        continue
                    tp = px + rr * risk if side == "long" else px - rr * risk
                    orders.append(Order(bar_end(t, 5), side, "market", px, sl, tp, "FX24", f"r3_ny_cont_rr{rr:g}", {}, 120, 300))
                    break
        return dedupe_orders(orders, 60)

    pools = {}
    for rule in ("r1_fade_lon", "r2_lon_cont", "r3_ny_cont"):
        for rr in (1.5, 2.0, 3.0):
            oo = gen(rule, rr)
            if oo:
                pools[oo[0].variant] = oo
                print(f"  {oo[0].variant} n={len(oo)}", flush=True)

    oos_cut = m1.index[min(m1.index.searchsorted(OOS_CUT), len(m1) - 1)]
    n_tdays = len(oos_trading_days(m1, oos_cut))
    scored = is_rank(m1, pools, oos_cut)
    best_v = scored[0][3] if scored else None
    variants = [v for _, _, _, v in scored[:6]]
    strict_rows, lenient_rows = [], []
    for v in variants:
        base = pools[v]
        for use_dxy in (False, True):
            orders = apply_dxy_gate(base, dxy, use_dxy) if use_dxy else list(base)
            for cap in (5.0, 8.0):
                for cost_name, spread, slip in COST_ROWS:
                    if cost_name == "cheap" and cap != 8.0:
                        continue
                    tr, st, sk = sim(m1, orders, v, cap, spread, slip, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                    wf_frac, _ = wf(m1, orders, v, cap, spread, slip)
                    ver, reason = verdict_from(st, wf_frac, None)
                    strict_rows.append(dict(family="FX24Sessions", variant=v, is_best=v == best_v,
                        dxy=use_dxy, cap=cap, cost=cost_name, OOS_n=st["n_trades"],
                        OOS_WR=st.get("win_rate"), OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                        tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=sk.get("skip_pct"), verdict=ver))
                    print(f"STRICT {v} dxy={int(use_dxy)} @{cap}/{cost_name} n={st['n_trades']} R={st.get('expectancy_r')} → {ver}", flush=True)
            for lab, cap in (("8", 8.0), ("12", 12.0), ("uncapped", None)):
                if cap is None:
                    oo2 = [o for o in orders if o.arm_time >= oos_cut]
                    tr, st = simulate(m1, oo2, risk_pct=0.008, max_sl_dist=1e9, use_circuit_breaker=True, spread=0.25, slip=0.05)
                    skp = 0.0
                else:
                    tr, st, sk = sim(m1, orders, v, cap, 0.25, 0.05, oos_cut, m1.index[-1] + pd.Timedelta(minutes=1))
                    skp = sk.get("skip_pct")
                lenient_rows.append(dict(family="FX24Sessions", variant=v, is_best=v == best_v,
                    dxy=use_dxy, cap_label=lab, OOS_n=st["n_trades"], OOS_WR=st.get("win_rate"),
                    OOS_R=st.get("expectancy_r"), OOS_PF=st.get("profit_factor"),
                    tpd=tpd_true(st["n_trades"], n_tdays), skip_pct=skp))
                print(f"LENIENT {v} dxy={int(use_dxy)} @{lab} n={st['n_trades']} R={st.get('expectancy_r')} PF={st.get('profit_factor')}", flush=True)

    pd.DataFrame(strict_rows).to_csv(OUT / "summary_strict.csv", index=False)
    pd.DataFrame(lenient_rows).to_csv(OUT / "summary_lenient.csv", index=False)
    (OUT / "chosen.json").write_text(json.dumps({"best_is": best_v, "top": scored[:8]}, indent=2, default=str))
    # diagnosis
    prim = [r for r in strict_rows if r["variant"] == best_v and r["cap"] == 8 and r["cost"] == "strict" and not r["dxy"]]
    diag = "unknown"
    if prim:
        pr = prim[0]
        unc = [r for r in lenient_rows if r["variant"] == best_v and r["cap_label"] == "uncapped" and not r["dxy"]]
        if pr["OOS_n"] < 10 and (pr.get("skip_pct") or 0) > 0.4:
            diag = "edge_killed_by_SL_cap"
        elif (pr.get("OOS_R") or 0) <= 0:
            diag = "no_edge_at_all" if not unc or (unc[0].get("OOS_R") or 0) <= 0 else "edge_killed_by_SL_cap_or_costs"
        elif (pr.get("OOS_PF") or 0) < 1.05:
            diag = "costs_eat_edge"
        elif pr["OOS_n"] < 20:
            diag = "too_few_trades"
        else:
            diag = "fails_other_KEEP_gates"
    (OUT / "diagnosis.json").write_text(json.dumps({"best_is": best_v, "diagnosis": diag, "freq": stats}, indent=2, default=str))
    print("FX24 DONE", best_v, diag, flush=True)


if __name__ == "__main__":
    main()
