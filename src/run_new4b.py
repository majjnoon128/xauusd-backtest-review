#!/usr/bin/env python3
"""Re-eval 4 new strategies with atr_buf SL + proper per-variant IS→OOS."""
from __future__ import annotations
import json, sys
from pathlib import Path
from itertools import product
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT = ROOT / "results" / "new4"
OUT.mkdir(parents=True, exist_ok=True)

from engine import simulate, sl_distance_price, count_sl_cap_skips, Order
from monte_carlo import run_mc
from strategies import generate_orb, generate_asian_bo, generate_ema_pullback, generate_vwap_mr, generate_pro_btb
from strategies.common import apply_dxy_gate
from run_final_batch import load, filter_cap, period_orders, apply_confirmations, verdict_from

CAPS = (5.0, 7.5, 8.0)
OOS_CUT = pd.Timestamp("2026-07-02", tz="UTC")


def risk_pct(cap): return cap / 1000.0


def zero_days(tr, oos_idx):
    days = [d for d in pd.DatetimeIndex(oos_idx.normalize().unique()) if int(getattr(d, "day_of_week", d.dayofweek)) < 5]
    if not days: return 100.0
    traded = set(tr["day"].astype(str)) if tr is not None and len(tr) else set()
    return 100.0 * sum(1 for d in days if str(d.date()) not in traded) / len(days)


def sim(m1, orders, variant, cap, spread, slip, t0, t1, cb=True):
    oo = [o for o in orders if o.variant == variant and t0 <= o.arm_time < t1]
    skip = count_sl_cap_skips(oo, cap, spread)
    oo = [o for o in oo if sl_distance_price(o.price, o.sl, o.side, spread) <= cap + 1e-9]
    tr, st = simulate(m1, oo, risk_pct=risk_pct(cap), max_sl_dist=cap,
                      use_circuit_breaker=cb, spread=spread, slip=slip)
    return tr, st, skip


def wf(m1, orders, variant, cap, spread=0.35, slip=0.10):
    n=len(m1); warm=int(n*0.4); fold=(n-warm)//4
    pos=valid=0; rs=[]
    for k in range(4):
        o0=warm+k*fold; o1=warm+(k+1)*fold if k<3 else n
        tr,st,_=sim(m1,orders,variant,cap,spread,slip,m1.index[o0],m1.index[o1-1]+pd.Timedelta(minutes=1))
        if st["n_trades"]>=5:
            valid+=1; rs.append(round(st["expectancy_r"],3))
            if st["expectancy_r"]>0: pos+=1
    return (pos/valid if valid else 0.0), rs


def sanity(m1, orders, variant, cap, oos_cut):
    oo=[o for o in orders if o.variant==variant and o.arm_time>=oos_cut]
    oo=[o for o in oo if sl_distance_price(o.price,o.sl,o.side)<=cap+1e-9]
    _,st0=simulate(m1,oo,risk_pct=risk_pct(cap),max_sl_dist=cap,use_circuit_breaker=False)
    out={"base_pf":st0["profit_factor"],"base_n":st0["n_trades"]}
    for s in (15,60):
        sh=[Order(o.arm_time+pd.Timedelta(minutes=s),o.side,o.kind,o.price,o.sl,o.tp,o.strategy,o.variant,dict(o.meta),o.expire_minutes,o.max_hold_minutes) for o in oo]
        _,st=simulate(m1,sh,risk_pct=risk_pct(cap),max_sl_dist=cap,use_circuit_breaker=False)
        out[f"shift{s}_pf"]=st["profit_factor"]
    rng=np.random.default_rng(1); rands=[]
    for _ in range(2):
        ro=[]
        for o in oo:
            j=m1.index.searchsorted(o.arm_time,side="left")
            if j>=len(m1)-5: continue
            jj=int(rng.integers(max(0,j-40),min(len(m1)-1,j+40)))
            px=float(m1["close"].iloc[jj]); risk=abs(o.price-o.sl)
            side=o.side if rng.random()<0.5 else ("short" if o.side=="long" else "long")
            sl,tp=(px-risk,px+abs(o.tp-o.price)) if side=="long" else (px+risk,px-abs(o.tp-o.price))
            ro.append(Order(m1.index[jj]+pd.Timedelta(minutes=1),side,o.kind,px,sl,tp,"RAND",o.variant,{},30))
        _,st=simulate(m1,ro,risk_pct=risk_pct(cap),max_sl_dist=cap,use_circuit_breaker=False)
        rands.append(st["profit_factor"])
    out["rand_mean_pf"]=float(np.mean(rands)) if rands else None
    return out


def build(m1, dxy):
    pools={}
    print("ORB", flush=True)
    orb=[]
    for session,rmin,entry,slm,rr in product(
        ("london","ny"),(30,60),("stop","close_break"),("mid","atr_buf"),(1.5,2.0,0.0)):
        orb += generate_orb(m1,dxy,False,session,rmin,entry,slm,rr,True)
    pools["ORB"]=orb
    print(" ",len(orb), len({o.variant for o in orb}), flush=True)

    print("AsianBO", flush=True)
    asian=[]
    for mode,slm,rr,entry in product(("breakout","fade"),("atr_buf","mid"),(1.5,2.0),("stop","close_break")):
        if mode=="fade" and entry=="stop": continue
        asian += generate_asian_bo(m1,dxy,False,mode,slm,rr, entry if mode=="breakout" else "close_break","london_ny")
    pools["AsianBO"]=asian
    print(" ",len(asian), len({o.variant for o in asian}), flush=True)

    print("EMA_PB", flush=True)
    ema=[]
    for rule,trend,pb,slm in product(("1h","15min"),("ema50_200","slope50"),(20,50),("swing","atr")):
        ema += generate_ema_pullback(m1,dxy,False,rule,trend,pb,2.0,slm,False)
    for rule in ("1h","15min"):
        ema += generate_ema_pullback(m1,dxy,False,rule,"ema50_200",20,2.0,"swing",True)
    pools["EMA_PB"]=ema
    print(" ",len(ema), len({o.variant for o in ema}), flush=True)

    print("VWAP", flush=True)
    vw=[]
    for mode,sd,rr,tf in product(("fade2sd","trend_pb"),(2.0,2.5),(1.5,2.0),(False,True)):
        if mode=="trend_pb" and sd==2.5: continue
        vw += generate_vwap_mr(m1,dxy,False,mode,sd,rr,tf)
    pools["VWAP_MR"]=vw
    print(" ",len(vw), len({o.variant for o in vw}), flush=True)

    for n in list(pools):
        pools[n+"_DXY"]=apply_dxy_gate(pools[n], dxy, True)
        print(f"  {n}_DXY", len(pools[n+'_DXY']), flush=True)
    return pools


def main():
    m1,dxy=load()
    i=m1.index.searchsorted(OOS_CUT); oos_cut=m1.index[min(i,len(m1)-1)]
    print("cut", oos_cut, flush=True)
    pools=build(m1,dxy)
    rows=[]; candidates=[]

    for name,orders in pools.items():
        variants=sorted({o.variant for o in orders})
        print(f"SCAN {name} nvar={len(variants)}", flush=True)
        # IS rank @cap8 strict
        scored=[]
        for v in variants:
            tr,st,sk=sim(m1,orders,v,8.0,0.35,0.10,m1.index[0],oos_cut)
            if st["n_trades"]>=12:
                scored.append((st["expectancy_r"], st["profit_factor"], st["n_trades"], v, st))
        scored.sort(reverse=True)
        top=[s for s in scored[:4]]  # top 4 by IS R
        if not top and variants:
            # fallback any with most IS trades @9 soft — use uncapped-ish via cap8 anyway
            fallback=[]
            for v in variants:
                tr,st,_=sim(m1,orders,v,8.0,0.35,0.10,m1.index[0],oos_cut)
                fallback.append((st["n_trades"], v, st))
            fallback.sort(reverse=True)
            top=[(fallback[0][2]["expectancy_r"], fallback[0][2]["profit_factor"], fallback[0][0], fallback[0][1], fallback[0][2])]

        for _,__,___,v,is_st in top:
            for cap in CAPS:
                for cname,sp,sl in (("strict",0.35,0.10),("cheap",0.20,0.05)):
                    if cname=="cheap" and cap!=8.0: continue
                    tr,st,sk=sim(m1,orders,v,cap,sp,sl,oos_cut,m1.index[-1]+pd.Timedelta(minutes=1))
                    wfp,wfr=wf(m1,orders,v,cap,sp,sl)
                    mc=None
                    if cname=="strict" and tr is not None and len(tr)>=15 and st["profit_factor"]>=1.05:
                        mc_df=run_mc(tr["r_multiple"].values,n_sims=2000,risk_pcts=(risk_pct(cap),))
                        if len(mc_df): mc=float(mc_df.iloc[0]["pass_prob"])
                    verd,reason=verdict_from(st,wfp,mc)
                    row=dict(setup=name,variant=v,cap=cap,cost=cname,dxy="_DXY" in name,
                             is_n=is_st["n_trades"],is_r=is_st["expectancy_r"],is_pf=is_st["profit_factor"],
                             oos_n=st["n_trades"],oos_wr=st["win_rate"],oos_r=st["expectancy_r"],
                             oos_pf=st["profit_factor"],oos_dd=st["max_dd_pct"],oos_tpd=st["trades_per_day"],
                             zero_day_pct=zero_days(tr,m1[m1.index>=oos_cut].index),
                             skip_pct=sk["skip_pct"],wf_pos=wfp,wf_rs=wfr,mc_pass=mc,
                             verdict=verd,reason=reason)
                    rows.append(row)
                    if verd in ("KEEP","MAYBE") and cname=="strict":
                        candidates.append((name,v,cap,orders,tr,row))
                    if cname=="strict":
                        print(f"  {name}|{v[:42]}@{cap}: n={st['n_trades']} WR={st['win_rate']:.0%} PF={st['profit_factor']:.2f} R={st['expectancy_r']:+.2f} wf={wfp:.0%} {verd}", flush=True)

    df=pd.DataFrame(rows)
    df.to_csv(OUT/"verdicts_b.csv", index=False)

    # best per setup family (strict, prefer highest OOS score among KEEP/MAYBE else best PF with n>=15)
    summary_rows=[]
    for fam in ("ORB","AsianBO","EMA_PB","VWAP_MR"):
        sub=df[(df["cost"]=="strict") & (df["setup"].isin([fam, fam+"_DXY"]))]
        if sub.empty: continue
        good=sub[sub["verdict"].isin(["KEEP","MAYBE"])]
        pick=good.sort_values(["oos_r","oos_pf","oos_n"],ascending=False).iloc[0] if len(good) else sub.sort_values(["oos_pf","oos_n"],ascending=False).iloc[0]
        summary_rows.append(pick.to_dict())
    pd.DataFrame(summary_rows).to_csv(OUT/"best_per_family.csv", index=False)

    # Sanity
    sanity_out={}
    seen=set()
    for name,v,cap,orders,tr,row in candidates:
        key=f"{name}@{cap}"
        if name in seen: continue
        seen.add(name)
        print("SANITY", key, flush=True)
        sanity_out[name]=sanity(m1,orders,v,cap,oos_cut)
        sanity_out[name].update({k:row[k] for k in ("verdict","variant","cap","oos_pf","oos_n","oos_r")})
        if tr is not None and len(tr):
            tr.to_csv(OUT/f"trades_{name}_cap{cap}.csv", index=False)
    (OUT/"sanity_b.json").write_text(json.dumps(sanity_out, indent=2, default=str))

    # Combine with ProBTB M15 m4
    print("COMBINE ProBTB M15 m4", flush=True)
    pb=generate_pro_btb(m1,dxy,False,rr=2.0,rule="15min")
    pb_vs=[v for v in {o.variant for o in pb} if "m4_limit_broken" in v]
    combos=[]
    if pb_vs:
        pb_o=apply_confirmations([o for o in pb if o.variant==pb_vs[0]], m1, dxy, {"htf":True})
        for name,v,cap,orders,tr,row in candidates:
            a=period_orders(filter_cap([o for o in orders if o.variant==v],cap), oos_cut, m1.index[-1]+pd.Timedelta(minutes=1))
            b=period_orders(filter_cap(pb_o,cap), oos_cut, m1.index[-1]+pd.Timedelta(minutes=1))
            merged=sorted(a+b, key=lambda o:o.arm_time)
            trm,stm=simulate(m1,merged,risk_pct=risk_pct(cap),max_sl_dist=cap,use_circuit_breaker=True)
            # overlap 30m
            same=opp=0
            fa=pd.DataFrame([{"t":o.arm_time,"s":o.side} for o in a])
            fb=pd.DataFrame([{"t":o.arm_time,"s":o.side} for o in b])
            if len(fa) and len(fb):
                for _,r in fa.iterrows():
                    w=fb[(fb["t"]-r["t"]).abs()<=pd.Timedelta(minutes=30)]
                    same+=int((w["s"]==r["s"]).sum()); opp+=int((w["s"]!=r["s"]).sum())
            combos.append(dict(setup=name,variant=v,cap=cap,solo_pf=row["oos_pf"],solo_n=row["oos_n"],
                               merged_pf=stm["profit_factor"],merged_n=stm["n_trades"],merged_r=stm["expectancy_r"],
                               merged_dd=stm["max_dd_pct"],same30=same,opp30=opp))
            print(f"  {name}@{cap} merged PF={stm['profit_factor']:.2f} n={stm['n_trades']} same={same} opp={opp}", flush=True)
    pd.DataFrame(combos).to_csv(OUT/"combine_probtb_b.csv", index=False)

    # DXY help: compare best non-DXY vs DXY same family
    helps=[]
    for fam in ("ORB","AsianBO","EMA_PB","VWAP_MR"):
        for cap in CAPS:
            a=df[(df.setup==fam)&(df.cap==cap)&(df.cost=="strict")]
            b=df[(df.setup==fam+"_DXY")&(df.cap==cap)&(df.cost=="strict")]
            if a.empty or b.empty: continue
            # best variant each
            aa=a.sort_values(["oos_r","oos_pf"],ascending=False).iloc[0]
            bb=b.sort_values(["oos_r","oos_pf"],ascending=False).iloc[0]
            helps.append(dict(family=fam,cap=cap,base_v=aa.variant,base_pf=aa.oos_pf,base_r=aa.oos_r,base_n=aa.oos_n,
                              dxy_v=bb.variant,dxy_pf=bb.oos_pf,dxy_r=bb.oos_r,dxy_n=bb.oos_n,
                              helped=bool(bb.oos_pf>aa.oos_pf+0.05 and bb.oos_r>aa.oos_r)))
    pd.DataFrame(helps).to_csv(OUT/"dxy_help_b.csv", index=False)

    (OUT/"summary_b.json").write_text(json.dumps({
        "oos_cut":str(oos_cut), "n_rows":len(rows),
        "candidates":[r for r in rows if r["verdict"] in ("KEEP","MAYBE") and r["cost"]=="strict"],
        "sanity":sanity_out, "combos":combos, "helps":helps,
        "best_per_family":summary_rows,
    }, indent=2, default=str))
    print("DONE candidates", len([r for r in rows if r['verdict'] in ('KEEP','MAYBE') and r['cost']=='strict']), flush=True)


if __name__=="__main__":
    main()
