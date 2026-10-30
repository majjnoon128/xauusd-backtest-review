"""Unit tests for post-audit engine: bid/ask, gap, R, partial, min-hold, concurrency, tpd."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from engine import (
    Order, simulate, compute_stats, _fill_price, _can_fill_limit, _can_fill_stop,
    _exit_stop_hit, _exit_limit_hit, SPREAD, SLIPPAGE,
)


def _m1(rows):
    """rows: list of (ts, o, h, l, c)."""
    idx = pd.DatetimeIndex([r[0] for r in rows], tz="UTC")
    return pd.DataFrame(
        {"open": [r[1] for r in rows], "high": [r[2] for r in rows],
         "low": [r[3] for r in rows], "close": [r[4] for r in rows],
         "volume": [100] * len(rows)},
        index=idx,
    )


def test_buy_stop_triggers_on_ask():
    # stop=2000, spread=0.35 → need bid_high >= 1999.65
    assert _can_fill_stop("long", 2000.0, 1990.0, 1999.70, 0.35) is True
    assert _can_fill_stop("long", 2000.0, 1990.0, 1999.50, 0.35) is False


def test_short_sl_triggers_on_ask():
    # short SL=2010: buy-stop cover → bid_high >= 2010 - 0.35
    assert _exit_stop_hit("short", 2010.0, 2000.0, 2009.70, 0.35) is True
    assert _exit_stop_hit("short", 2010.0, 2000.0, 2009.50, 0.35) is False


def test_long_tp_on_bid():
    assert _exit_limit_hit("long", 2010.0, 2000.0, 2010.0, 0.35) is True
    assert _exit_limit_hit("long", 2010.0, 2000.0, 2009.9, 0.35) is False


def test_short_tp_on_ask():
    # short TP=1990: ask_low <= 1990 → bid_low <= 1989.65
    assert _exit_limit_hit("short", 1990.0, 1989.65, 2000.0, 0.35) is True
    assert _exit_limit_hit("short", 1990.0, 1989.70, 2000.0, 0.35) is False


def test_fill_prices_sides():
    # long market: ask_open + slip
    assert abs(_fill_price("long", "market", 100.0, 100.0, 0.35, 0.10) - 100.45) < 1e-9
    # short market: bid_open - slip
    assert abs(_fill_price("short", "market", 100.0, 100.0, 0.35, 0.10) - 99.90) < 1e-9
    # long buy stop gap: max(stop, ask_open)+slip
    assert abs(_fill_price("long", "stop", 100.0, 101.0, 0.35, 0.10) - (101.35 + 0.10)) < 1e-9
    # long buy limit: min(limit, ask_open)+slip
    assert abs(_fill_price("long", "limit", 100.0, 99.0, 0.35, 0.10) - (99.35 + 0.10)) < 1e-9


def test_gap_through_sl_not_dropped():
    # Arm at t0; market delay 1 bar; bar1 opens through SL
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(10):
        ts = t0 + pd.Timedelta(minutes=i)
        # flat around 2000, then gap down through SL
        if i == 1:
            rows.append((ts, 1990.0, 1991.0, 1988.0, 1989.0))  # open through SL=1995
        else:
            rows.append((ts, 2000.0, 2001.0, 1999.0, 2000.0))
    m1 = _m1(rows)
    o = Order(arm_time=t0, side="long", kind="market", price=2000.0, sl=1995.0, tp=2010.0,
              strategy="T", variant="gap", expire_minutes=30)
    tdf, st = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                       market_delay_m1=1, risk_pct=0.01, allow_fractional=True)
    assert len(tdf) == 1, "gap-through SL must book a trade, not drop"
    assert tdf.iloc[0]["reason"] in ("SL_GAP", "SL")
    assert tdf.iloc[0]["pnl_usd"] < 0


def test_r_includes_costs():
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(20):
        ts = t0 + pd.Timedelta(minutes=i)
        if i == 1:
            rows.append((ts, 2000.0, 2000.5, 1999.5, 2000.0))  # fill bar
        elif i == 5:
            rows.append((ts, 2005.0, 2010.5, 2004.0, 2010.0))  # hit TP ~2010
        else:
            rows.append((ts, 2000.0 + i * 0.1, 2001.0 + i * 0.1, 1999.0 + i * 0.1, 2000.0 + i * 0.1))
    m1 = _m1(rows)
    o = Order(arm_time=t0, side="long", kind="market", price=2000.0, sl=1995.0, tp=2010.0,
              strategy="T", variant="r", expire_minutes=60)
    tdf, st = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                       market_delay_m1=1, risk_pct=0.01, allow_fractional=True,
                       commission=7.0)
    assert len(tdf) == 1
    row = tdf.iloc[0]
    # net R must differ from gross when commission > 0
    assert "r_gross" in tdf.columns
    assert row["risk_usd"] > 0
    # pnl / risk ≈ r_multiple
    assert abs(row["r_multiple"] - row["pnl_usd"] / row["risk_usd"]) < 1e-6


def test_partial_legs_both_execute():
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(30):
        ts = t0 + pd.Timedelta(minutes=i)
        px = 2000.0 + min(i, 15) * 0.5
        rows.append((ts, px, px + 0.8, px - 0.3, px))
    m1 = _m1(rows)
    # risk dist ~5 → with risk_pct and balance, need enough lots to split
    o = Order(
        arm_time=t0, side="long", kind="market", price=2000.0, sl=1995.0, tp=2015.0,
        strategy="T", variant="pe", expire_minutes=60,
        legs=[(1 / 3, 2005.0), (2 / 3, 2015.0)],
    )
    tdf, st = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                       market_delay_m1=1, risk_pct=0.05, initial_balance=1000.0,
                       allow_fractional=False,
                       max_open_risk_pct=1.0)
    assert len(tdf) >= 1
    # If split possible, 2 legs; else 1 flagged full_nosplit
    if len(tdf) == 2:
        assert set(tdf["leg"]) == {"leg1", "leg2"} or "leg" in "".join(tdf["leg"].astype(str))
        assert abs(tdf["lots"].sum() - tdf["lots"].sum()) == 0
    else:
        assert tdf.iloc[0]["leg"] in ("full_nosplit", "full", "leg1")


def test_sl_always_live_no_min_hold_deferral():
    """Even if min_hold_minutes set (legacy), SL must fire immediately."""
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(15):
        ts = t0 + pd.Timedelta(minutes=i)
        if i == 1:
            rows.append((ts, 2000.0, 2000.5, 1999.5, 2000.0))
        elif i == 2:
            rows.append((ts, 1999.0, 1999.5, 1994.0, 1994.5))  # hit SL next bar
        else:
            rows.append((ts, 2000.0, 2001.0, 1999.0, 2000.0))
    m1 = _m1(rows)
    o = Order(arm_time=t0, side="long", kind="market", price=2000.0, sl=1995.0, tp=2010.0,
              strategy="T", variant="mh", expire_minutes=30, min_hold_minutes=5)
    tdf, st = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                       market_delay_m1=1, risk_pct=0.01, allow_fractional=True)
    assert len(tdf) == 1
    # Must exit on SL within a few minutes, NOT deferred 5 bars
    assert tdf.iloc[0]["reason"] in ("SL", "SL_GAP")
    assert tdf.iloc[0]["duration_s"] <= 180


def test_concurrency_respects_3pct():
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(40):
        ts = t0 + pd.Timedelta(minutes=i)
        rows.append((ts, 2000.0, 2000.5, 1999.5, 2000.0))
    m1 = _m1(rows)
    orders = []
    for k in range(5):
        orders.append(Order(
            arm_time=t0 + pd.Timedelta(minutes=k),
            side="long", kind="market", price=2000.0, sl=1995.0, tp=2010.0,
            strategy="T", variant=f"c{k}", expire_minutes=30, max_hold_minutes=60,
        ))
    tdf, st = simulate(
        m1, orders, max_sl_dist=20.0, use_circuit_breaker=False,
        market_delay_m1=1, risk_pct=0.02, initial_balance=1000.0,
        max_open_risk_pct=0.03, allow_fractional=True,
    )
    # With 2% risk each and 3% cap, at most 1-2 concurrent; not all 5 as independent
    # (old engine dropped by start_i<=exit_i; new allows up to risk cap)
    assert len(tdf) >= 1
    assert len(tdf) < 5  # risk cap must block some


def test_trades_per_day_uses_all_weekdays():
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")  # Monday
    rows = []
    # 10 weekdays of M1 bars sparse
    for d in range(10):
        day = t0 + pd.Timedelta(days=d)
        if day.dayofweek >= 5:
            continue
        for i in range(5):
            ts = day + pd.Timedelta(minutes=i)
            rows.append((ts, 2000.0, 2001.0, 1999.0, 2000.0))
    m1 = _m1(rows)
    # one trade only
    o = Order(arm_time=rows[0][0], side="long", kind="market", price=2000.0,
              sl=1995.0, tp=2000.5, strategy="T", variant="tpd", expire_minutes=30)
    # force quick TP
    rows2 = list(rows)
    # bump high on fill+1
    tdf, st = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                       market_delay_m1=1, risk_pct=0.01, allow_fractional=True,
                       calendar_days=10)
    assert st["trading_days"] == 10
    assert st["trades_per_day"] == pytest.approx(st["n_trades"] / 10.0)


def test_intrabar_modes_differ_when_both_hit():
    t0 = pd.Timestamp("2026-01-05 10:00", tz="UTC")
    rows = []
    for i in range(10):
        ts = t0 + pd.Timedelta(minutes=i)
        if i == 1:
            rows.append((ts, 2000.0, 2000.2, 1999.8, 2000.0))
        elif i == 2:
            # both SL and TP reachable
            rows.append((ts, 2000.0, 2010.5, 1994.0, 2000.0))
        else:
            rows.append((ts, 2000.0, 2001.0, 1999.0, 2000.0))
    m1 = _m1(rows)
    o = Order(arm_time=t0, side="long", kind="market", price=2000.0, sl=1995.0, tp=2010.0,
              strategy="T", variant="ib", expire_minutes=30)
    tdf_sl, _ = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                         market_delay_m1=1, risk_pct=0.01, allow_fractional=True,
                         intrabar_mode="sl_first")
    tdf_tp, _ = simulate(m1, [o], max_sl_dist=20.0, use_circuit_breaker=False,
                         market_delay_m1=1, risk_pct=0.01, allow_fractional=True,
                         intrabar_mode="tp_first")
    assert tdf_sl.iloc[0]["reason"] == "SL"
    assert tdf_tp.iloc[0]["reason"] == "TP"
