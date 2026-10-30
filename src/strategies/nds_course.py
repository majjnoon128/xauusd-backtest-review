"""NDS Course — mechanical 123Flag from Nodal Displacement Sequencing PDF.

Faithful to course Day-Trading checklist (pp.98–111):
  HTF M30: 3 rising peaks → short bias; 3 falling troughs → long bias
  LTF: P1<P2<P3 then F>P3 (short) / L1>L2>L3 then F<L3 (long)
  Entry after closed-bar displacement confirmation past the 3→F pullback extreme
  SL beyond Flag F; TP by rr / symmetry / 86.4% of structure
  Level 86.4% is the course number — NOT fib 0.62–0.78 (that was prior NDS_Fib).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, in_session, vol_ma
from strategies.common import apply_dxy_gate, apply_vol_gate, dedupe_orders


def _pivots(h: np.ndarray, l: np.ndarray, left: int = 3, right: int = 3):
    """Confirmed pivots: list of (conf_i, piv_i, price, kind) kind in ('H','L')."""
    n = len(h)
    out = []
    for i in range(left, n - right):
        w = h[i - left : i + right + 1]
        if h[i] == w.max() and (w == h[i]).sum() == 1:
            out.append((i + right, i, float(h[i]), "H"))
        w = l[i - left : i + right + 1]
        if l[i] == w.min() and (w == l[i]).sum() == 1:
            out.append((i + right, i, float(l[i]), "L"))
    out.sort(key=lambda x: (x[0], 0 if x[3] == "H" else 1))
    return out


def _htf_bias_series(m30: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """At each M30 bar end, bias from last 3 confirmed same-side pivots.
    short if last 3 highs ascending; long if last 3 lows descending; else 0.
    Indexed by M30 bar start; value known at bar_end = start+30m.
    """
    h = m30["high"].values
    l = m30["low"].values
    n = len(m30)
    bias = np.zeros(n, dtype=np.int8)
    highs, lows = [], []  # (piv_i, price)
    pivs = _pivots(h, l, left, right)
    pi = 0
    for conf in range(n):
        while pi < len(pivs) and pivs[pi][0] <= conf:
            _, piv_i, px, kind = pivs[pi]
            if kind == "H":
                highs.append((piv_i, px))
            else:
                lows.append((piv_i, px))
            pi += 1
        short_ok = (len(highs) >= 3 and highs[-3][1] < highs[-2][1] < highs[-1][1])
        long_ok = (len(lows) >= 3 and lows[-3][1] > lows[-2][1] > lows[-1][1])
        if short_ok and long_ok:
            b = -1 if highs[-1][0] >= lows[-1][0] else 1
        elif short_ok:
            b = -1
        elif long_ok:
            b = 1
        else:
            b = 0
        bias[conf] = b
    return pd.Series(bias, index=m30.index)


def _bias_at(bias_m30: pd.Series, t: pd.Timestamp) -> int:
    """Last closed M30 bias at time t (bar end <= t)."""
    deadline = t - pd.Timedelta(minutes=30)
    j = bias_m30.index.searchsorted(deadline, side="right") - 1
    if j < 0:
        return 0
    return int(bias_m30.iloc[j])


def _find_123flags(
    h: np.ndarray, l: np.ndarray, c: np.ndarray, atr: np.ndarray,
    left: int, right: int, min_atr: float, confirm: str,
) -> List[dict]:
    """Return list of flag events with confirmation bar index.
    Each: side, p1,p2,p3,f prices & idxs, conf_i, entry, sl, struct_h, pull_ext
    """
    pivs = _pivots(h, l, left, right)
    highs = [(p[1], p[2], p[0]) for p in pivs if p[3] == "H"]  # piv_i, px, conf_i
    lows = [(p[1], p[2], p[0]) for p in pivs if p[3] == "L"]
    events = []
    n = len(h)

    # SHORT setups: ascending highs then F
    for k in range(3, len(highs)):
        p1, p2, p3, f = highs[k - 3], highs[k - 2], highs[k - 1], highs[k]
        if not (p1[1] < p2[1] < p3[1] < f[1]):
            continue
        # need a pullback low between p3 and f
        pull = [x for x in lows if p3[0] < x[0] < f[0]]
        if not pull:
            continue
        pull_ext = min(x[1] for x in pull)  # lowest pullback
        struct_h = f[1] - p1[1]
        atr_v = atr[f[2]] if f[2] < len(atr) and not np.isnan(atr[f[2]]) else np.nan
        if np.isnan(atr_v) or atr_v <= 0 or struct_h < min_atr * atr_v:
            continue
        # confirmation: first closed bar after F conf that breaks pullback
        # at_f: enter on the bar where F pivot itself confirms (no displacement wait)
        start = f[2] + 1
        conf_i = None
        if confirm == "at_f":
            conf_i = f[2]
        else:
            for j in range(start, min(start + 40, n)):
                if confirm == "brk_p3":
                    if c[j] < p3[1]:
                        conf_i = j
                        break
                else:  # brk_pull
                    if c[j] < pull_ext or l[j] < pull_ext:
                        if c[j] < pull_ext:
                            conf_i = j
                            break
        if conf_i is None:
            continue
        entry = float(c[conf_i])
        sl = float(f[1] + 0.1 * atr_v)
        if sl <= entry:
            continue
        # T = lowest low pivot before P1 (start of T→P3 hook move)
        prior_lows = [x for x in lows if x[0] < p1[0]]
        t_px = min((x[1] for x in prior_lows), default=None)
        events.append({
            "side": "short", "conf_i": conf_i, "entry": entry, "sl": sl,
            "p1": p1[1], "p2": p2[1], "p3": p3[1], "f": f[1],
            "pull_ext": pull_ext, "struct_h": struct_h, "atr": atr_v,
            "f_i": f[0], "f_conf": f[2], "t_px": t_px,
        })

    # LONG setups
    for k in range(3, len(lows)):
        p1, p2, p3, f = lows[k - 3], lows[k - 2], lows[k - 1], lows[k]
        if not (p1[1] > p2[1] > p3[1] > f[1]):
            continue
        pull = [x for x in highs if p3[0] < x[0] < f[0]]
        if not pull:
            continue
        pull_ext = max(x[1] for x in pull)
        struct_h = p1[1] - f[1]
        atr_v = atr[f[2]] if f[2] < len(atr) and not np.isnan(atr[f[2]]) else np.nan
        if np.isnan(atr_v) or atr_v <= 0 or struct_h < min_atr * atr_v:
            continue
        start = f[2] + 1
        conf_i = None
        if confirm == "at_f":
            conf_i = f[2]
        else:
            for j in range(start, min(start + 40, n)):
                if confirm == "brk_p3":
                    if c[j] > p3[1]:
                        conf_i = j
                        break
                else:
                    if c[j] > pull_ext:
                        conf_i = j
                        break
        if conf_i is None:
            continue
        entry = float(c[conf_i])
        sl = float(f[1] - 0.1 * atr_v)
        if sl >= entry:
            continue
        prior_highs = [x for x in highs if x[0] < p1[0]]
        t_px = max((x[1] for x in prior_highs), default=None)
        events.append({
            "side": "long", "conf_i": conf_i, "entry": entry, "sl": sl,
            "p1": p1[1], "p2": p2[1], "p3": p3[1], "f": f[1],
            "pull_ext": pull_ext, "struct_h": struct_h, "atr": atr_v,
            "f_i": f[0], "f_conf": f[2], "t_px": t_px,
        })
    return events


def _tp_price(side: str, entry: float, sl: float, ev: dict, tp_mode: str) -> float:
    risk = abs(entry - sl)
    if tp_mode.startswith("rr"):
        rr = float(tp_mode[2:])
        return entry + rr * risk if side == "long" else entry - rr * risk
    if tp_mode == "sym":
        # symmetry ≈ height of P1→F (struct)
        d = ev["struct_h"]
        return entry + d if side == "long" else entry - d
    if tp_mode == "nd864":
        # Course: 86.4% of T→Node3 (hook close), NOT 86.4% of struct_h (P1→F).
        # Fall back to struct_h only if T/node3 missing (mechanical compat).
        t_px = ev.get("t_px")
        n3 = ev.get("p3")
        if t_px is not None and n3 is not None:
            hook_h = abs(float(n3) - float(t_px))
            d = 0.864 * hook_h
        else:
            d = 0.864 * ev["struct_h"]
        return entry + d if side == "long" else entry - d
    if tp_mode == "nd88":
        d = 0.88 * ev["struct_h"]
        return entry + d if side == "long" else entry - d
    if tp_mode == "nd78":
        d = 0.78 * ev["struct_h"]
        return entry + d if side == "long" else entry - d
    if tp_mode == "rr0.5":
        return entry + 0.5 * risk if side == "long" else entry - 0.5 * risk
    # default
    return entry + 1.5 * risk if side == "long" else entry - 1.5 * risk



def _htf_n3_tp(m30: pd.DataFrame, side: str, entry: float, asof: pd.Timestamp,
               left: int = 3, right: int = 3) -> Optional[float]:
    """Course step 12: full exit on HTF node 3 if already formed (closed-bar).
    Short → last of 3 descending M30 lows (S3); long → last of 3 ascending highs (N3).
    Only if target is on the profitable side of entry; else None.
    """
    # only pivots whose confirm bar end <= asof
    deadline = asof - pd.Timedelta(minutes=30)
    sub = m30[m30.index <= deadline]
    if len(sub) < 20:
        return None
    pivs = _pivots(sub["high"].values, sub["low"].values, left, right)
    if side == "short":
        lows = [float(px) for _, _, px, k in pivs if k == "L"]
        if len(lows) < 3:
            return None
        a, b, c = lows[-3], lows[-2], lows[-1]
        if a > b > c and c < entry:
            return c
        # fallback: deepest recent low below entry
        below = [x for x in lows[-6:] if x < entry]
        return min(below) if below else None
    else:
        highs = [float(px) for _, _, px, k in pivs if k == "H"]
        if len(highs) < 3:
            return None
        a, b, c = highs[-3], highs[-2], highs[-1]
        if a < b < c and c > entry:
            return c
        above = [x for x in highs[-6:] if x > entry]
        return max(above) if above else None


def _open_node_tp1(side: str, entry: float, ev: dict) -> Optional[float]:
    """Course step 4: first TP on open nodes — mechanical: pullback extreme (open swing)."""
    pe = float(ev["pull_ext"])
    if side == "short" and pe < entry - 0.05:
        return pe
    if side == "long" and pe > entry + 0.05:
        return pe
    return None


def _scan_reentry864(
    h, l, c, times, atr, piv_highs, piv_lows, ev, side, bar_m, pivot_lr, buf_mode, hold_min, tag_base,
    reentry_tp_mode: str = "rr1.5",
) -> List[Order]:
    """Course steps 5–6: after first drop D from F, limit re-entry at F−0.136·D (short).

    Closed-bar / no-lookahead rules (audit-fixed):
      1) Leg1 = earliest opposite pivot with piv_i > F and conf_i > primary conf.
      2) New Flag = earliest same-side pivot AFTER leg1 with conf > leg1.conf
         (course: SL above/below new Flag — must exist before arm).
      3) Arm at new-Flag confirm bar end only; SL/TP use prices known by then.
      4) TP default capped to rr1.5/2/3 of (level−SL); `sym` = full leg (legacy, fat-tail).
    """
    from engine import Order
    f_px = float(ev["f"])
    conf_i = int(ev["conf_i"])
    n = len(h)

    if side == "short":
        cands = [(piv_i, px, conf) for piv_i, px, conf in piv_lows if piv_i > ev["f_i"] and conf > conf_i]
    else:
        cands = [(piv_i, px, conf) for piv_i, px, conf in piv_highs if piv_i > ev["f_i"] and conf > conf_i]
    if not cands:
        return []
    leg = sorted(cands, key=lambda x: x[2])[0]  # earliest confirm
    leg_px = float(leg[1])
    leg_conf = int(leg[2])
    leg_i = int(leg[0])

    if side == "short":
        D = f_px - leg_px
        if D < 0.3:
            return []
        level = f_px - 0.136 * D
        # new Flag = first confirmed swing HIGH after leg1 (no lookahead past its conf)
        flags = [(pi, px, cf) for pi, px, cf in piv_highs if pi > leg_i and cf > leg_conf]
        if not flags:
            return []
        nf = sorted(flags, key=lambda x: x[2])[0]
        micro_f = float(nf[1])
        arm_i = int(nf[2])
        atr_v = atr[arm_i] if arm_i < len(atr) and not np.isnan(atr[arm_i]) else D * 0.1
        buf = 0.20 if buf_mode == "fixed02" else max(0.1 * float(atr_v), 0.15)
        sl = micro_f + buf
        if sl <= level:
            return []
        risk = sl - level
        if reentry_tp_mode.startswith("rr"):
            rr = float(reentry_tp_mode[2:])
            tp = level - rr * risk
        elif reentry_tp_mode == "sym":
            tp = level - D  # legacy fat-tail
        else:
            tp = level - 1.5 * risk
        if tp >= level:
            return []
        if arm_i >= n - 1:
            return []
        arm = bar_end(times[arm_i], bar_m)
        if not in_session(arm):
            return []
        return [Order(
            arm_time=arm, side="short", kind="limit", price=float(level),
            sl=float(sl), tp=float(tp), strategy="NDS_Course",
            variant=tag_base,
            meta={"leg": "reentry864", "f": f_px, "D": D, "leg_px": leg_px,
                  "micro_f": micro_f, "size_mult": 1.0, "parent_f": f_px,
                  "reentry_tp_mode": reentry_tp_mode, "audit": "arm_after_new_flag"},
            expire_minutes=90, max_hold_minutes=hold_min,
        )]

    # long (mirror)
    D = leg_px - f_px
    if D < 0.3:
        return []
    level = f_px + 0.136 * D
    flags = [(pi, px, cf) for pi, px, cf in piv_lows if pi > leg_i and cf > leg_conf]
    if not flags:
        return []
    nf = sorted(flags, key=lambda x: x[2])[0]
    micro_f = float(nf[1])
    arm_i = int(nf[2])
    atr_v = atr[arm_i] if arm_i < len(atr) and not np.isnan(atr[arm_i]) else D * 0.1
    buf = 0.20 if buf_mode == "fixed02" else max(0.1 * float(atr_v), 0.15)
    sl = micro_f - buf
    if sl >= level:
        return []
    risk = level - sl
    if reentry_tp_mode.startswith("rr"):
        rr = float(reentry_tp_mode[2:])
        tp = level + rr * risk
    elif reentry_tp_mode == "sym":
        tp = level + D
    else:
        tp = level + 1.5 * risk
    if tp <= level:
        return []
    if arm_i >= n - 1:
        return []
    arm = bar_end(times[arm_i], bar_m)
    if not in_session(arm):
        return []
    return [Order(
        arm_time=arm, side="long", kind="limit", price=float(level),
        sl=float(sl), tp=float(tp), strategy="NDS_Course",
        variant=tag_base,
        meta={"leg": "reentry864", "f": f_px, "D": D, "leg_px": leg_px,
              "micro_f": micro_f, "size_mult": 1.0, "parent_f": f_px,
              "reentry_tp_mode": reentry_tp_mode, "audit": "arm_after_new_flag"},
        expire_minutes=90, max_hold_minutes=hold_min,
    )]



def _scan_reentry864_v2(
    h, l, c, times, atr, piv_highs, piv_lows, ev, side, bar_m, pivot_lr, buf_mode, hold_min, tag_base,
    reentry_tp_mode: str = "rr1.5",
    confirm: str = "brk_p3",
    min_atr: float = 1.0,
    zone_atr: float = 0.5,
    all_events: Optional[List[dict]] = None,
) -> List[Order]:
    """SPEC_v2 / course p.110–111: after first drop D, wait for a NEW 123Flag whose
    Flag sits near the 86.4% retrace of D; enter at that Flag after its confirm.

    Closed-bar / no-lookahead:
      1) Leg1 = earliest opposite pivot with conf > primary conf.
      2) Level = F ± 0.136·D (86.4% retrace toward F).
      3) Among later 123Flag events same side, pick earliest whose F is within
         zone_atr·ATR of Level AND whose conf_i > leg1.conf (and > primary).
      4) Arm at that event conf bar end; SL beyond its Flag; TP rr/sym of (entry−SL).
    """
    from engine import Order
    f_px = float(ev["f"])
    conf_i = int(ev["conf_i"])
    n = len(h)

    if side == "short":
        cands = [(piv_i, px, conf) for piv_i, px, conf in piv_lows if piv_i > ev["f_i"] and conf > conf_i]
    else:
        cands = [(piv_i, px, conf) for piv_i, px, conf in piv_highs if piv_i > ev["f_i"] and conf > conf_i]
    if not cands:
        return []
    leg = sorted(cands, key=lambda x: x[2])[0]
    leg_px = float(leg[1])
    leg_conf = int(leg[2])
    D = (f_px - leg_px) if side == "short" else (leg_px - f_px)
    if D < 0.3:
        return []
    level = (f_px - 0.136 * D) if side == "short" else (f_px + 0.136 * D)

    later = all_events if all_events is not None else _find_123flags(h, l, c, atr, pivot_lr, pivot_lr, min_atr, confirm)
    matched = []
    for ev2 in later:
        if ev2["side"] != side:
            continue
        if int(ev2["conf_i"]) <= leg_conf or int(ev2["f_conf"]) <= conf_i:
            continue
        if int(ev2["f_i"]) <= int(leg[0]):
            continue
        atr_v = float(ev2["atr"])
        if abs(float(ev2["f"]) - level) > zone_atr * max(atr_v, 0.1):
            continue
        matched.append(ev2)
    if not matched:
        return []
    ev2 = sorted(matched, key=lambda e: e["conf_i"])[0]
    arm_i = int(ev2["conf_i"])
    if arm_i >= n - 1:
        return []
    entry = float(ev2["entry"])
    atr_v = float(ev2["atr"])
    buf = 0.20 if buf_mode == "fixed02" else max(0.1 * atr_v, 0.15)
    if side == "short":
        sl = float(ev2["f"]) + buf
        if sl <= entry:
            return []
        risk = sl - entry
        if reentry_tp_mode.startswith("rr"):
            rr = float(reentry_tp_mode[2:])
            tp = entry - rr * risk
        elif reentry_tp_mode == "sym":
            tp = entry - D
        else:
            tp = entry - 1.5 * risk
        if tp >= entry:
            return []
    else:
        sl = float(ev2["f"]) - buf
        if sl >= entry:
            return []
        risk = entry - sl
        if reentry_tp_mode.startswith("rr"):
            rr = float(reentry_tp_mode[2:])
            tp = entry + rr * risk
        elif reentry_tp_mode == "sym":
            tp = entry + D
        else:
            tp = entry + 1.5 * risk
        if tp <= entry:
            return []
    arm = bar_end(times[arm_i], bar_m)
    if not in_session(arm):
        return []
    return [Order(
        arm_time=arm, side=side, kind="market", price=float(entry),
        sl=float(sl), tp=float(tp), strategy="NDS_Course",
        variant=tag_base,
        meta={"leg": "reentry864_v2", "f": f_px, "D": D, "leg_px": leg_px,
              "level": level, "f2": float(ev2["f"]), "size_mult": 1.0,
              "reentry_tp_mode": reentry_tp_mode, "audit": "new_123flag_near_864"},
        expire_minutes=30, max_hold_minutes=hold_min,
    )]


def generate_nds_course(
    m1: pd.DataFrame,
    dxy=None,
    use_dxy: bool = False,
    use_vol: bool = False,
    style: str = "day",          # day | scalp | ctx_M5 | ctx_M15
    entry_tf: str = "M5",        # M1 | M3 | M5 | M15
    tp_mode: str = "rr1.5",      # rr0.5 | rr1.5 | rr2.0 | sym | nd864 | nd88 | nd78
    confirm: str = "brk_pull",   # brk_pull | brk_p3 | brk_rally12
    min_atr: float = 1.0,
    pivot_lr: int = 3,
    vol_mult: float = 1.3,
    family: str = "course",      # course | schematic
    nd_zone: bool = False,       # require prior-leg symmetry ratio in [0.78,0.96]
    req_smi: bool = False,       # F must break SMI high/low (range between p2-p3)
    equal_top: bool = False,     # wait for 2nd equal high/low then break
    hold_min: int = 240,
    sl_buf_mode: str = "atr01",   # atr01 | fixed02  (course: SL beyond Flag)
    use_partial: bool = False,     # course steps 4/10: 1/3 at open-node TP1, 2/3 at final
    use_reentry864: bool = False,  # course steps 5–6: 2nd entry at F−0.136·D
    use_htf_n3_tp: bool = False,   # course step 12: final TP = HTF node 3 if formed
    reentry_tp_mode: str = "rr1.5",  # rr1.5|rr2|rr3|sym — cap reentry TP (sym=legacy fat)
    reentry_mode: str = "v1",  # v1=limit@86.4 after swing Flag; v2=new 123Flag near 86.4 zone (SPEC_v2)
) -> List[Order]:
    """course=PDF checklist; schematic=map.pdf ND 78-96 / SMI / equal-top / nd88."""
    if confirm == "brk_rally12":
        confirm = "brk_pull"  # alias: break of final-rally 1-2 = pullback extreme
    _tf = {"M1": ("1min", 1), "M3": ("3min", 3), "M5": ("5min", 5), "M15": ("15min", 15)}
    if entry_tf not in _tf:
        raise ValueError(f"unsupported entry_tf={entry_tf}")
    rule, bar_m = _tf[entry_tf]
    df = m1 if entry_tf == "M1" else resample_ohlc(m1, rule)
    atr = atr_prior(df, 14).values
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)

    bias_series = None
    bias_min = 30
    m30 = resample_ohlc(m1, "30min")
    # style: day(=M30) | day_H1 | day_H4 | scalp | ctx_M5 | ctx_M15
    if style in ("day", "day_M30"):
        bias_series = _htf_bias_series(m30, pivot_lr, pivot_lr)
        bias_min = 30
    elif style == "day_H1":
        bias_series = _htf_bias_series(resample_ohlc(m1, "1h"), pivot_lr, pivot_lr)
        bias_min = 60
    elif style == "day_H4":
        bias_series = _htf_bias_series(resample_ohlc(m1, "4h"), pivot_lr, pivot_lr)
        bias_min = 240
    elif style == "ctx_M5":
        bias_series = _htf_bias_series(resample_ohlc(m1, "5min"), pivot_lr, pivot_lr)
        bias_min = 5
    elif style == "ctx_M15":
        bias_series = _htf_bias_series(resample_ohlc(m1, "15min"), pivot_lr, pivot_lr)
        bias_min = 15

    events = _find_123flags(h, l, c, atr, pivot_lr, pivot_lr, min_atr, confirm)

    # prior major swing for ND zone: last opposite pivot before p1
    pivs = _pivots(h, l, pivot_lr, pivot_lr)
    highs = [(p[1], p[2], p[0]) for p in pivs if p[3] == "H"]
    lows = [(p[1], p[2], p[0]) for p in pivs if p[3] == "L"]

    tag = f"{family}_{style}_{entry_tf}_{tp_mode}_{confirm}_a{min_atr}"
    if pivot_lr != 3:
        tag += f"_lr{pivot_lr}"
    if sl_buf_mode != "atr01":
        tag += f"_sl{sl_buf_mode}"
    if nd_zone:
        tag += "_ndz"
    if req_smi:
        tag += "_smi"
    if equal_top:
        tag += "_eq"
    if use_partial:
        tag += "_pe"
    if use_reentry864:
        tag += "_r864"
        if reentry_mode == "v2":
            tag += "v2"
        if reentry_tp_mode != "rr1.5":
            tag += f"_rtp{reentry_tp_mode}"
    if use_htf_n3_tp:
        tag += "_htf"
    orders: List[Order] = []

    for ev in events:
        i = ev["conf_i"]
        ts = times[i]
        if not in_session(ts):
            continue
        side = ev["side"]
        if bias_series is not None:
            arm_probe = bar_end(ts, bar_m)
            # reuse _bias_at with dynamic minutes
            deadline = arm_probe - pd.Timedelta(minutes=bias_min)
            j = bias_series.index.searchsorted(deadline, side="right") - 1
            b = int(bias_series.iloc[j]) if j >= 0 else 0
            if side == "short" and b != -1:
                continue
            if side == "long" and b != 1:
                continue

        # schematic ND zone: F sits in 78–96% of recent lookback range (cycle-end band)
        if nd_zone or family == "schematic":
            f_i = ev["f_i"]
            lb = { "M1": 120, "M3": 100, "M5": 80, "M15": 40 }.get(entry_tf, 80)
            a0 = max(0, f_i - lb)
            rh, rl = float(h[a0:f_i+1].max()), float(l[a0:f_i+1].min())
            rng = rh - rl
            if rng <= 0:
                continue
            pos = (ev["f"] - rl) / rng  # 1=top of window
            # short: F in upper 78–96%; long: F in lower 4–22% (=78–96% down)
            if side == "short":
                ok = (0.78 - 1e-9) <= pos <= (0.96 + 1e-9)
            else:
                ok = (0.04 - 1e-9) <= pos <= (0.22 + 1e-9)
            if not ok:
                continue
            # also allow equal-high case just above 0.96 clipped to window high
            ev = dict(ev)
            ev["nd_ratio"] = pos if side == "short" else (1.0 - pos)

        # SMI: compressed range between p2 and p3 indices — F must break that range extreme
        if req_smi:
            # approximate: between structural mid — use pull_ext and p2/p3
            # require F beyond a mid-range high of bars between an inferred p2 and p3 window
            # Use: range high of bars from conf of p2-like to p3 — we only have prices; skip if struct shallow vs atr
            if ev["struct_h"] < 1.2 * ev["atr"]:
                continue
            # F must exceed p3 by at least 0.15 ATR (already F>p3); require pullback depth into mid of p2-p3
            mid = 0.5 * (ev["p2"] + ev["p3"])
            if side == "short":
                if not (ev["pull_ext"] < mid):
                    continue
            else:
                if not (ev["pull_ext"] > mid):
                    continue

        entry, sl = ev["entry"], ev["sl"]
        # Recompute SL buffer per mode (course: above/below Flag)
        atr_v = ev["atr"]
        if sl_buf_mode == "fixed02":
            buf = 0.20
        else:
            buf = 0.1 * atr_v
        if side == "short":
            sl = float(ev["f"] + buf)
            if sl <= entry:
                continue
        else:
            sl = float(ev["f"] - buf)
            if sl >= entry:
                continue
        # equal top: look ahead is forbidden — instead require that at confirmation,
        # there were TWO highs near F before conf (second already formed, closed)
        if equal_top:
            atr_v = ev["atr"]
            tol = 0.15 * atr_v
            if side == "short":
                near = [x for x in highs if ev["f_i"] - 30 <= x[0] <= ev["f_i"] and abs(x[1] - ev["f"]) <= tol]
                if len(near) < 2:
                    continue
            else:
                near = [x for x in lows if ev["f_i"] - 30 <= x[0] <= ev["f_i"] and abs(x[1] - ev["f"]) <= tol]
                if len(near) < 2:
                    continue

        # Final TP: HTF node-3 if toggle + available, else tp_mode
        tp = _tp_price(side, entry, sl, ev, tp_mode)
        if use_htf_n3_tp:
            htf_tp = _htf_n3_tp(m30, side, entry, bar_end(ts, bar_m), pivot_lr, pivot_lr)
            if htf_tp is not None:
                # only replace if further (or equal) in trade direction vs min 0.5R
                risk0 = abs(entry - sl)
                if side == "short" and htf_tp < entry:
                    tp = htf_tp if (entry - htf_tp) >= 0.5 * risk0 else tp
                elif side == "long" and htf_tp > entry:
                    tp = htf_tp if (htf_tp - entry) >= 0.5 * risk0 else tp
        if side == "long" and tp <= entry:
            continue
        if side == "short" and tp >= entry:
            continue
        arm = bar_end(ts, bar_m)
        mh = 120 if family == "schematic" else hold_min
        # Volume gate must check Flag spike bar F (course), not breakout-confirm bar.
        f_bar_ts = times[ev["f_i"]] if 0 <= ev["f_i"] < n else ts
        base_meta = {
            "signal_bar": f_bar_ts,  # F bar for vol gate
            "confirm_bar": ts,
            "f": ev["f"], "p3": ev["p3"], "t_px": ev.get("t_px"),
            "struct_h": ev["struct_h"], "pull_ext": ev["pull_ext"],
            "family": family, "nd_ratio": ev.get("nd_ratio"),
        }
        if use_partial:
            tp1 = _open_node_tp1(side, entry, ev)
            risk0 = abs(entry - sl)
            ok1 = False
            if tp1 is not None:
                r1 = abs(entry - tp1)
                # need TP1 between entry and final TP, and >= 0.25R
                if side == "short" and tp < tp1 < entry and r1 >= 0.25 * risk0:
                    ok1 = True
                if side == "long" and entry < tp1 < tp and r1 >= 0.25 * risk0:
                    ok1 = True
            if ok1:
                m1_ = dict(base_meta, leg="partial_1of3", size_mult=1.0 / 3.0, tp_kind="open_node")
                m2_ = dict(base_meta, leg="partial_2of3", size_mult=2.0 / 3.0, tp_kind="final")
                orders.append(Order(
                    arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=float(tp1),
                    strategy="NDS_Course", variant=tag, meta=m1_,
                    expire_minutes=30, max_hold_minutes=mh,
                ))
                orders.append(Order(
                    arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                    strategy="NDS_Course", variant=tag, meta=m2_,
                    expire_minutes=30, max_hold_minutes=mh,
                ))
            else:
                orders.append(Order(
                    arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                    strategy="NDS_Course", variant=tag,
                    meta=dict(base_meta, leg="full", size_mult=1.0),
                    expire_minutes=30, max_hold_minutes=mh,
                ))
        else:
            orders.append(Order(
                arm_time=arm, side=side, kind="market", price=entry, sl=sl, tp=tp,
                strategy="NDS_Course", variant=tag,
                meta=dict(base_meta, leg="full", size_mult=1.0),
                expire_minutes=30, max_hold_minutes=mh,
            ))

        if use_reentry864:
            if reentry_mode == "v2":
                orders.extend(_scan_reentry864_v2(
                    h, l, c, times, atr, highs, lows, ev, side, bar_m, pivot_lr,
                    sl_buf_mode, mh, tag, reentry_tp_mode=reentry_tp_mode,
                    confirm=confirm, min_atr=min_atr, all_events=events,
                ))
            else:
                orders.extend(_scan_reentry864(
                    h, l, c, times, atr, highs, lows, ev, side, bar_m, pivot_lr,
                    sl_buf_mode, mh, tag, reentry_tp_mode=reentry_tp_mode,
                ))

    orders = dedupe_orders(orders, {"M1": 20, "M3": 30, "M5": 45, "M15": 60}.get(entry_tf, 45))
    if use_vol and "volume" in df.columns:
        vma = vol_ma(df["volume"], 20)
        orders = apply_vol_gate(orders, df["volume"], vma, True, vol_mult, bar_m)
    return apply_dxy_gate(orders, dxy, use_dxy)


def nds_course_signal(
    m1: pd.DataFrame,
    now: Optional[pd.Timestamp] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Live watchdog helper: last armed signal at/before now, if any."""
    if now is None:
        now = m1.index[-1] + pd.Timedelta(minutes=1)
    # only need recent history for speed
    cut = now - pd.Timedelta(days=5)
    sub = m1[m1.index >= cut]
    if len(sub) < 200:
        sub = m1
    orders = generate_nds_course(sub, **kwargs)
    recent = [o for o in orders if o.arm_time <= now]
    if not recent:
        return None
    o = max(recent, key=lambda x: x.arm_time)
    return {
        "arm_time": o.arm_time, "side": o.side, "entry": o.price,
        "sl": o.sl, "tp": o.tp, "variant": o.variant, "meta": o.meta,
    }



def generate_nds_mechanical(m1, dxy=None, **kwargs):
    """NDS_Mechanical: fully mechanical 123Flag (current course defaults, struct-based TP)."""
    kwargs.setdefault("family", "course")
    kwargs.setdefault("use_partial", False)
    kwargs.setdefault("use_reentry864", False)
    return generate_nds_course(m1, dxy, **kwargs)


def generate_nds_fidelity(m1, dxy=None, **kwargs):
    """NDS_Fidelity: closer to course — Hook 86.4 TP, vol on F, optional partial+reentry+HTF N3."""
    kwargs.setdefault("family", "course")
    kwargs.setdefault("tp_mode", "nd864")
    kwargs.setdefault("use_vol", True)
    kwargs.setdefault("use_partial", True)
    kwargs.setdefault("use_reentry864", True)
    kwargs.setdefault("use_htf_n3_tp", True)
    kwargs.setdefault("style", "day")
    return generate_nds_course(m1, dxy, **kwargs)
