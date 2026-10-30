"""Tom Hougaard (fundex24) daily continuation rules.

Broker day = UTC calendar day (same as rest of engine / Dukascopy M1).
Rule A bear: Fri high < Thu high → Mon target = Fri low. Bull mirror: Fri low > Thu low → Mon target Fri high.
Rule B bear: Wed high < Mon high (Tue ignored) → Thu target = Wed low. Bull mirror similarly.
Stats: touch frequency of target on target day vs baseline prior-day extreme touch.
Tradable: on target day, after M5/M15 swing sweep of recent high (for shorts), MSS/engulf confirm,
SL above sweep, TP=target or fixed RR with target as filter.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end, bullish_engulfing, bearish_engulfing
from strategies.common import dedupe_orders
from strategies.ict_helpers import swing_highs_lows, last_swing_before


def _daily_ohlc(m1: pd.DataFrame) -> pd.DataFrame:
    """UTC day bars — broker day boundary for this project."""
    return resample_ohlc(m1, "1D")


def hougaard_signals(daily: pd.DataFrame) -> List[dict]:
    """Emit {target_date, side, target_px, rule, cond_high/low...} for each applicable setup."""
    # index is day start UTC
    rows = []
    by_date = {ts.date(): (ts, float(r.high), float(r.low), float(r.open), float(r.close))
               for ts, r in daily.iterrows()}
    dates = sorted(by_date.keys())
    # map date -> weekday 0=Mon
    for i, d in enumerate(dates):
        ts, h, l, o, c = by_date[d]
        wd = ts.day_of_week if hasattr(ts, "day_of_week") else ts.dayofweek
        # Rule A: need Fri setup → Monday target. Look at Friday bars.
        if wd == 4:  # Friday
            # find Thursday
            thu = None
            for j in range(i - 1, max(-1, i - 5), -1):
                t2 = list(by_date.keys())[j] if False else dates[j]
                ts2 = by_date[dates[j]][0]
                if (ts2.day_of_week if hasattr(ts2, "day_of_week") else ts2.dayofweek) == 3:
                    thu = dates[j]; break
            if thu is not None:
                _, th, tl, _, _ = by_date[thu]
                # next Monday
                mon = None
                for j in range(i + 1, min(len(dates), i + 4)):
                    ts2 = by_date[dates[j]][0]
                    if (ts2.day_of_week if hasattr(ts2, "day_of_week") else ts2.dayofweek) == 0:
                        mon = dates[j]; break
                if mon is not None:
                    if h < th:
                        rows.append({"target_date": mon, "side": "short", "target_px": l,
                                     "rule": "A", "setup_date": d, "ref_high": th, "setup_high": h, "setup_low": l})
                    if l > tl:
                        rows.append({"target_date": mon, "side": "long", "target_px": h,
                                     "rule": "A", "setup_date": d, "ref_low": tl, "setup_high": h, "setup_low": l})
        # Rule B: Wed vs Mon → Thursday target
        if wd == 2:  # Wednesday
            mon = None
            for j in range(i - 1, max(-1, i - 5), -1):
                ts2 = by_date[dates[j]][0]
                if (ts2.day_of_week if hasattr(ts2, "day_of_week") else ts2.dayofweek) == 0:
                    mon = dates[j]; break
            thu = None
            for j in range(i + 1, min(len(dates), i + 4)):
                ts2 = by_date[dates[j]][0]
                if (ts2.day_of_week if hasattr(ts2, "day_of_week") else ts2.dayofweek) == 3:
                    thu = dates[j]; break
            if mon is not None and thu is not None:
                _, mh, ml, _, _ = by_date[mon]
                if h < mh:
                    rows.append({"target_date": thu, "side": "short", "target_px": l,
                                 "rule": "B", "setup_date": d, "ref_high": mh, "setup_high": h, "setup_low": l})
                if l > ml:
                    rows.append({"target_date": thu, "side": "long", "target_px": h,
                                 "rule": "B", "setup_date": d, "ref_low": ml, "setup_high": h, "setup_low": l})
    return rows


def pure_stats(m1: pd.DataFrame) -> dict:
    """Touch rates for rules vs baseline prior-day low/high touch."""
    daily = _daily_ohlc(m1)
    by_date = {ts.date(): (float(r.high), float(r.low)) for ts, r in daily.iterrows()}
    sigs = hougaard_signals(daily)
    out = {"day_boundary": "UTC calendar day (Dukascopy M1 left-labeled 00:00 UTC)", "rules": {}}
    for rule in ("A", "B"):
        for side in ("short", "long"):
            ss = [s for s in sigs if s["rule"] == rule and s["side"] == side]
            hits = 0
            for s in ss:
                td = s["target_date"]
                if td not in by_date:
                    continue
                th, tl = by_date[td]
                if side == "short" and tl <= s["target_px"]:
                    hits += 1
                elif side == "long" and th >= s["target_px"]:
                    hits += 1
            key = f"rule{rule}_{side}"
            out["rules"][key] = {"n": len(ss), "touches": hits,
                                 "rate": hits / len(ss) if ss else None}
    # baseline: each day, touch prior-day low / high
    dates = sorted(by_date.keys())
    base_lo = base_hi = n = 0
    for i in range(1, len(dates)):
        n += 1
        ph, pl = by_date[dates[i - 1]]
        h, l = by_date[dates[i]]
        if l <= pl: base_lo += 1
        if h >= ph: base_hi += 1
    out["baseline"] = {
        "n_days": n,
        "touch_prior_low": base_lo, "rate_prior_low": base_lo / n if n else None,
        "touch_prior_high": base_hi, "rate_prior_high": base_hi / n if n else None,
    }
    return out


def generate_hougaard(
    m1: pd.DataFrame,
    rule: str = "B",            # A | B | both
    side_mode: str = "both",    # short | long | both
    entry_tf: str = "M5",       # M5 | M15
    confirm: str = "engulf",    # engulf | mss
    tp_mode: str = "target",    # target | rr2 (target as filter: must have RR>=1 to target)
    atr_buf: float = 0.1,
) -> List[Order]:
    daily = _daily_ohlc(m1)
    sigs = hougaard_signals(daily)
    rules = ("A", "B") if rule == "both" else (rule,)
    sigs = [s for s in sigs if s["rule"] in rules]
    if side_mode != "both":
        sigs = [s for s in sigs if s["side"] == side_mode]
    # index by target date
    by_td: Dict = {}
    for s in sigs:
        by_td.setdefault(s["target_date"], []).append(s)

    bar_m = 5 if entry_tf == "M5" else 15
    df = resample_ohlc(m1, f"{bar_m}min")
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    times = df.index
    n = len(df)
    a = atr_prior(df, 14).values
    shi, sli = swing_highs_lows(h, l, 2, 2)
    bull_eng = bullish_engulfing(df).values
    bear_eng = bearish_engulfing(df).values

    variant = f"hougaard_{rule}_{side_mode}_{entry_tf}_{confirm}_{tp_mode}"
    orders: List[Order] = []
    used = set()

    for i in range(20, n - 1):
        ts = times[i]
        if int(getattr(ts, "day_of_week", ts.dayofweek)) >= 5:
            continue
        day = ts.date()
        if day not in by_td or day in used:
            continue
        atr_v = a[i]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        for s in by_td[day]:
            side = s["side"]
            target = s["target_px"]
            # sweep recent swing
            if side == "short":
                sw = last_swing_before(shi, i)
                if sw is None or h[i] < h[sw]:
                    continue  # need sweep of swing high this bar
                # confirmation
                if confirm == "engulf" and not bear_eng[i]:
                    continue
                if confirm == "mss":
                    # close back below last swing low after sweep — use close < open and close < prior mid
                    if not (c[i] < o[i] and c[i] < 0.5 * (h[sw] + l[max(sw - 1, 0)])):
                        continue
                px = float(c[i])
                buf = max(atr_buf * atr_v, 0.15)
                sl = float(h[i]) + buf
                if sl <= px:
                    continue
            else:
                sw = last_swing_before(sli, i)
                if sw is None or l[i] > l[sw]:
                    continue
                if confirm == "engulf" and not bull_eng[i]:
                    continue
                if confirm == "mss":
                    if not (c[i] > o[i] and c[i] > 0.5 * (h[max(sw - 1, 0)] + l[sw])):
                        continue
                px = float(c[i])
                buf = max(atr_buf * atr_v, 0.15)
                sl = float(l[i]) - buf
                if sl >= px:
                    continue

            risk = abs(px - sl)
            if risk < 0.20:
                continue
            if tp_mode == "target":
                if side == "short" and target >= px - risk:
                    continue  # RR<1
                if side == "long" and target <= px + risk:
                    continue
                tp = target
                rr = abs(tp - px) / risk
                if rr < 1.0:
                    continue
            else:  # rr2 with target as filter (must be able to reach target at least 1R away)
                if side == "short" and not (target < px - risk):
                    continue
                if side == "long" and not (target > px + risk):
                    continue
                tp = px - 2 * risk if side == "short" else px + 2 * risk

            arm = bar_end(ts, bar_m)
            orders.append(Order(
                arm_time=arm, side=side, kind="market", price=px, sl=float(sl), tp=float(tp),
                strategy="Hougaard", variant=variant,
                meta={"rule": s["rule"], "target_date": str(day), "target": target},
                expire_minutes=20, max_hold_minutes=600,
            ))
            used.add(day)
            break

    return dedupe_orders(orders, 60)


def generate_hougaard_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for rule in ("A", "B", "both"):
        for side in ("both", "short", "long"):
            for tf in ("M5", "M15"):
                for conf in ("engulf", "mss"):
                    for tp in ("target", "rr2"):
                        print(f" hougaard {rule} {side} {tf} {conf} {tp}", flush=True)
                        oo = generate_hougaard(m1, rule, side, tf, conf, tp)
                        if oo:
                            pools[oo[0].variant] = oo
                            print(f"  n={len(oo)}", flush=True)
    return pools
