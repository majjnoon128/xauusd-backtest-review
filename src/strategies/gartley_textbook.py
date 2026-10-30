"""gartley_textbook: classic Gartley via zigzag pivots.
AB=0.618 XA, BC 0.382–0.886 AB, D=0.786 XA (also 1.27–1.618 BC alt);
limit at D, SL beyond X / buf beyond D; TP 0.382/0.618 AD. M5/M15/H1.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order
from indicators import atr_prior, resample_ohlc, bar_end
from strategies.common import dedupe_orders
from strategies.batch2_helpers import zigzag_pivots


def _near(x, target, tol):
    return abs(x - target) <= tol


def generate_gartley(
    m1: pd.DataFrame,
    tf: str = "M15",
    pivot: int = 3,
    tol: float = 0.08,
    d_mode: str = "xa786",   # xa786 | bc_ext
    sl_mode: str = "beyond_x",  # beyond_x | buf_d
    tp_fib: float = 0.618,   # of AD
) -> List[Order]:
    bar = {"M5": 5, "M15": 15, "H1": 60}[tf]
    df = resample_ohlc(m1, f"{bar}min")
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    times = df.index
    a = atr_prior(df, 14).values
    piv = zigzag_pivots(h, l, c, pivot, pivot)
    variant = f"gartley_{tf}_p{pivot}_t{tol:g}_{d_mode}_sl{sl_mode}_tp{tp_fib:g}"
    orders: List[Order] = []

    for k in range(4, len(piv)):
        # need X A B C then D forming / confirmed as next pivot
        X, A, B, C = piv[k - 4], piv[k - 3], piv[k - 2], piv[k - 1]
        # bullish Gartley: X low, A high, B low, C high, D low
        bull = X[2] == "L" and A[2] == "H" and B[2] == "L" and C[2] == "H"
        bear = X[2] == "H" and A[2] == "L" and B[2] == "H" and C[2] == "L"
        if not (bull or bear):
            continue
        XA = abs(A[1] - X[1])
        AB = abs(B[1] - A[1])
        BC = abs(C[1] - B[1])
        if XA < 1e-6 or AB < 1e-6:
            continue
        if not _near(AB / XA, 0.618, tol):
            continue
        r_bc = BC / AB
        if not (0.382 - tol <= r_bc <= 0.886 + tol):
            continue

        # Expected D
        if bull:
            d_xa = A[1] - 0.786 * XA
            d_bc_lo = B[1] - 1.618 * BC
            d_bc_hi = B[1] - 1.27 * BC
        else:
            d_xa = A[1] + 0.786 * XA
            d_bc_lo = B[1] + 1.27 * BC
            d_bc_hi = B[1] + 1.618 * BC

        if d_mode == "xa786":
            d_price = d_xa
        else:
            d_price = 0.5 * (d_bc_lo + d_bc_hi)

        # D confirmed as next pivot after C matching type
        D = piv[k]
        if bull and D[2] != "L":
            continue
        if bear and D[2] != "H":
            continue
        if not _near(D[1], d_price, tol * XA):
            # also accept if D near xa786 OR within BC ext band
            ok = _near(D[1], d_xa, tol * XA)
            if bull:
                ok = ok or (d_bc_lo - tol * XA <= D[1] <= d_bc_hi + tol * XA)
            else:
                ok = ok or (d_bc_lo - tol * XA <= D[1] <= d_bc_hi + tol * XA)
            if d_mode == "bc_ext":
                ok = (min(d_bc_lo, d_bc_hi) - tol * XA <= D[1] <= max(d_bc_lo, d_bc_hi) + tol * XA)
            if not ok:
                continue

        conf = D[0] + pivot  # confirmation bar
        if conf >= len(times) - 1:
            continue
        if int(getattr(times[conf], "day_of_week", times[conf].dayofweek)) >= 5:
            continue
        atr_v = a[conf]
        if np.isnan(atr_v) or atr_v <= 0:
            continue

        side = "long" if bull else "short"
        px = float(D[1])
        buf = max(0.15 * atr_v, 0.15)
        if sl_mode == "beyond_x":
            sl = float(X[1]) - buf if bull else float(X[1]) + buf
        else:
            sl = px - buf if bull else px + buf
        if (bull and sl >= px) or (not bull and sl <= px):
            continue
        risk = abs(px - sl)
        if risk < 0.25:
            continue
        # TP along AD
        AD = abs(D[1] - A[1])
        if bull:
            tp = D[1] + tp_fib * AD
        else:
            tp = D[1] - tp_fib * AD
        if abs(tp - px) / risk < 1.0:
            continue

        arm = bar_end(times[conf], bar)
        orders.append(Order(
            arm_time=arm, side=side, kind="limit", price=float(px),
            sl=float(sl), tp=float(tp),
            strategy="Gartley", variant=variant,
            meta={"X": X[1], "A": A[1], "B": B[1], "C": C[1], "D": D[1]},
            expire_minutes=bar * 30, max_hold_minutes=bar * 80,
        ))

    return dedupe_orders(orders, bar * 2)


def generate_gartley_family(m1: pd.DataFrame) -> Dict[str, List[Order]]:
    pools = {}
    for tf in ("M5", "M15", "H1"):
        for piv in (2, 3, 5):
            for tol in (0.06, 0.10):
                for dm in ("xa786", "bc_ext"):
                    for slm in ("beyond_x", "buf_d"):
                        for tp in (0.382, 0.618):
                            # prune
                            if piv == 5 and tf == "M5" and tol == 0.06:
                                continue
                            if dm == "bc_ext" and slm == "buf_d" and tp == 0.382:
                                continue
                            print(f" gartley {tf} p{piv} t{tol} {dm} {slm} tp{tp}", flush=True)
                            oo = generate_gartley(m1, tf, piv, tol, dm, slm, tp)
                            if oo:
                                pools[oo[0].variant] = oo
                                print(f"  n={len(oo)}", flush=True)
    return pools
