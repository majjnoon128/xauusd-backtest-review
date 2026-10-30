"""Shared helpers for Batch 2 strategies."""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Tuple


def zigzag_pivots(h, l, c, left: int, right: int) -> List[Tuple[int, float, str]]:
    """Alternating confirmed fractal pivots: (idx, price, 'H'|'L')."""
    n = len(h)
    raw = []
    for i in range(left, n - right):
        if all(h[i] >= h[i - j] for j in range(1, left + 1)) and all(h[i] > h[i + j] for j in range(1, right + 1)):
            raw.append((i, float(h[i]), "H"))
        if all(l[i] <= l[i - j] for j in range(1, left + 1)) and all(l[i] < l[i + j] for j in range(1, right + 1)):
            raw.append((i, float(l[i]), "L"))
    raw.sort(key=lambda x: x[0])
    out = []
    for p in raw:
        if not out:
            out.append(p); continue
        if p[2] == out[-1][2]:
            # keep more extreme
            if p[2] == "H" and p[1] >= out[-1][1]:
                out[-1] = p
            elif p[2] == "L" and p[1] <= out[-1][1]:
                out[-1] = p
        else:
            out.append(p)
    return out


def tema(series: pd.Series, n: int) -> pd.Series:
    """True TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))."""
    e1 = series.ewm(span=n, adjust=False).mean()
    e2 = e1.ewm(span=n, adjust=False).mean()
    e3 = e2.ewm(span=n, adjust=False).mean()
    return 3 * e1 - 3 * e2 + e3
