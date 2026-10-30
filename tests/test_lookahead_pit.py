"""Point-in-time / truncation tests: no unfinished HTF bar reads."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))
from indicators import last_closed_value, resample_ohlc, ema
from optimize import apply_quality_filters
from engine import Order


def _synth_m1(n=2000):
    idx = pd.date_range("2026-01-05", periods=n, freq="min", tz="UTC")
    rng = np.random.default_rng(0)
    px = 2000 + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame({
        "open": px, "high": px + 0.5, "low": px - 0.5, "close": px, "volume": 100
    }, index=idx)


def test_last_closed_m15_no_unfinished():
    m1 = _synth_m1(800)  # covers past 10:07
    m15 = resample_ohlc(m1, "15min")
    t = pd.Timestamp("2026-01-05 10:07", tz="UTC")
    c = last_closed_value(m15["close"], t, 15)
    # deadline = 09:52 → last closed left-labeled bar starts at 09:45 (ends 10:00)
    expected_start = pd.Timestamp("2026-01-05 09:45", tz="UTC")
    forming = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    assert expected_start in m15.index
    assert c == float(m15.loc[expected_start, "close"])
    assert forming in m15.index
    assert c != float(m15.loc[forming, "close"])


def test_truncation_equals_full_at_t():
    m1 = _synth_m1(2000)
    m1 = m1[(m1.index.hour >= 8) & (m1.index.hour < 16) & (m1.index.dayofweek < 5)]
    assert len(m1) >= 200
    t_cut = m1.index[len(m1) // 2]
    orders = []
    for ts in m1.index[100::30]:
        orders.append(Order(
            arm_time=ts + pd.Timedelta(minutes=1), side="long", kind="market",
            price=float(m1.loc[ts, "close"]), sl=float(m1.loc[ts, "close"]) - 3,
            tp=float(m1.loc[ts, "close"]) + 4.5, strategy="T", variant="pit",
        ))
    full = apply_quality_filters(orders, m1, None, require_htf=True, require_dxy=False)
    full_at = [o for o in full if o.arm_time <= t_cut]
    trunc = apply_quality_filters(
        [o for o in orders if o.arm_time <= t_cut],
        m1[m1.index <= t_cut], None, require_htf=True, require_dxy=False,
    )
    a = {(o.arm_time, o.side, round(o.price, 4)) for o in full_at}
    b = {(o.arm_time, o.side, round(o.price, 4)) for o in trunc}
    assert a == b, f"PIT mismatch: only_full={a-b} only_trunc={b-a}"
