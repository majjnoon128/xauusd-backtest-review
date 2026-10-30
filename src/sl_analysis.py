"""Classify why losing trades hit SL; quantify share of each cause."""
from __future__ import annotations
import numpy as np
import pandas as pd
from indicators import ema, atr, resample_ohlc


CAUSES = [
    "against_htf_trend",
    "asian_or_low_vol_session",
    "sl_too_tight_vs_atr",
    "entry_extended",
    "weak_shallow_move",
    "dxy_disagreement",
    "london_open_whipsaw",
    "ny_late_session",
    "other",
]


def classify_losses(trades: pd.DataFrame, m1: pd.DataFrame, dxy: pd.DataFrame | None) -> pd.DataFrame:
    """Add cause columns to losing trades (reason==SL)."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    losses = trades[trades["reason"] == "SL"].copy()
    if losses.empty:
        return losses

    m15 = resample_ohlc(m1, "15min")
    m15["ema50"] = ema(m15["close"], 50)
    m15_atr = atr(m15, 14)
    m1_atr = atr(m1, 14)

    dxy_bear = None
    if dxy is not None and not dxy.empty:
        d = dxy.copy()
        d["ema50"] = ema(d["close"], 50)
        dxy_bear = d["close"] < d["ema50"]

    causes = []
    for _, row in losses.iterrows():
        t = pd.Timestamp(row["entry_time"])
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        side = row["side"]
        entry = float(row["entry"])
        sl = float(row["sl"])
        tags = []

        # HTF trend
        mi = m15.index.searchsorted(t, side="right") - 1
        if mi >= 50:
            trend_up = float(m15["close"].iloc[mi]) > float(m15["ema50"].iloc[mi])
            if side == "long" and not trend_up:
                tags.append("against_htf_trend")
            if side == "short" and trend_up:
                tags.append("against_htf_trend")

        # Session
        h = t.hour
        if h < 7 or (h >= 21):
            tags.append("asian_or_low_vol_session")
        if 7 <= h < 9:
            tags.append("london_open_whipsaw")
        if h >= 19:
            tags.append("ny_late_session")

        # SL vs ATR
        ai = m1_atr.index.searchsorted(t, side="right") - 1
        atr_i = float(m1_atr.iloc[ai]) if ai >= 0 and not np.isnan(m1_atr.iloc[ai]) else np.nan
        risk = abs(entry - sl)
        if atr_i and atr_i > 0 and risk < 0.5 * atr_i:
            tags.append("sl_too_tight_vs_atr")

        # Entry extended: distance from M15 EMA > 1.5 ATR
        if mi >= 50 and atr_i and atr_i > 0:
            dist = abs(entry - float(m15["ema50"].iloc[mi]))
            if dist > 1.5 * float(m15_atr.iloc[mi] if not np.isnan(m15_atr.iloc[mi]) else atr_i):
                tags.append("entry_extended")

        # Weak move: risk itself tiny relative to gold price (< 0.05%)
        if risk / entry < 0.0003:
            tags.append("weak_shallow_move")

        # DXY disagreement
        if dxy_bear is not None:
            di = dxy_bear.index.searchsorted(t, side="right") - 1
            if di >= 0:
                bear = bool(dxy_bear.iloc[di])
                if side == "long" and not bear:
                    tags.append("dxy_disagreement")
                if side == "short" and bear:
                    tags.append("dxy_disagreement")

        if not tags:
            tags = ["other"]
        causes.append({"primary": tags[0], "all_tags": "|".join(tags), **{c: (c in tags) for c in CAUSES}})

    cause_df = pd.DataFrame(causes)
    out = pd.concat([losses.reset_index(drop=True), cause_df], axis=1)
    return out


def summarize_causes(classified: pd.DataFrame) -> pd.DataFrame:
    if classified is None or classified.empty:
        return pd.DataFrame()
    rows = []
    for (strat, variant), g in classified.groupby(["strategy", "variant"]):
        n = len(g)
        row = {"strategy": strat, "variant": variant, "n_losses": n}
        for c in CAUSES:
            if c in g.columns:
                row[c] = float(g[c].mean())
                row[f"{c}_n"] = int(g[c].sum())
        rows.append(row)
    return pd.DataFrame(rows)
