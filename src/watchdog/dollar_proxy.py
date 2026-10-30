"""Dollar strength proxy for live watchdog when raw DXY is unavailable.

Live: use EURUSD (MT5 / Finnhub / Twelve / yfinance EURUSD=X) inverted.
Do NOT use Yahoo DX-Y.NYB or GC=F (≈30 min delay per Yahoo delay table).
Research parity: data/EURUSD.parquet → 1/close as DXY-like series.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"


def eurusd_to_dxy_like(eur: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame with close=1/EURUSD.close (optional OHLC inverted)."""
    if eur.index.tz is None:
        eur = eur.copy()
        eur.index = eur.index.tz_localize("UTC")
    close = eur["close"].astype(float)
    out = (1.0 / close).to_frame("close")
    if all(c in eur.columns for c in ("open", "high", "low")):
        out["open"] = 1.0 / eur["open"].astype(float)
        out["high"] = 1.0 / eur["low"].astype(float)
        out["low"] = 1.0 / eur["high"].astype(float)
    return out


def load_research_proxy(prefer: str = "EURUSD_inv") -> tuple[pd.DataFrame, str]:
    """Load dollar series for gating. prefer: EURUSD_inv | DXY_synth."""
    if prefer == "DXY_synth":
        dxy = pd.read_parquet(DATA / "DXY_synth.parquet")
        if dxy.index.tz is None:
            dxy.index = dxy.index.tz_localize("UTC")
        if "close" not in dxy.columns:
            dxy = dxy.rename(columns={dxy.columns[0]: "close"})
        return dxy, "DXY_synth"
    eur = pd.read_parquet(DATA / "EURUSD.parquet")
    return eurusd_to_dxy_like(eur), "EURUSD_inv"
