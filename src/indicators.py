"""Closed-bar-safe helpers."""
from __future__ import annotations
import numpy as np
import pandas as pd


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Left-labeled bars: index = period start; bar closes at start+rule."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open", "high", "low", "close"])
    return out


def bar_end(ts: pd.Timestamp, rule_minutes: int) -> pd.Timestamp:
    return ts + pd.Timedelta(minutes=rule_minutes)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def atr_prior(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR known at bar i using data through i-1 (prior-bar ATR)."""
    return atr(df, n).shift(1)


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def body(df: pd.DataFrame) -> pd.Series:
    return (df["close"] - df["open"]).abs()


def is_bull(df: pd.DataFrame) -> pd.Series:
    return df["close"] > df["open"]


def is_bear(df: pd.DataFrame) -> pd.Series:
    return df["close"] < df["open"]


def bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_bear = is_bear(df).shift(1)
    curr_bull = is_bull(df)
    eng = (df["open"] <= df["close"].shift(1)) & (df["close"] >= df["open"].shift(1))
    return prev_bear.fillna(False) & curr_bull & eng.fillna(False)


def bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_bull = is_bull(df).shift(1)
    curr_bear = is_bear(df)
    eng = (df["open"] >= df["close"].shift(1)) & (df["close"] <= df["open"].shift(1))
    return prev_bull.fillna(False) & curr_bear & eng.fillna(False)


def inside_bar(df: pd.DataFrame) -> pd.Series:
    return (df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))


def pivot_confirmed(high: pd.Series, low: pd.Series, left: int = 5, right: int = 5):
    """At confirmation bar conf=i+right, pivot bar is i. Arrays indexed by conf bar."""
    n = len(high)
    ph_bar = np.full(n, -1, dtype=int)
    pl_bar = np.full(n, -1, dtype=int)
    ph_px = np.full(n, np.nan)
    pl_px = np.full(n, np.nan)
    hv, lv = high.values, low.values
    for i in range(left, n - right):
        w = hv[i - left : i + right + 1]
        if hv[i] == w.max() and (w == hv[i]).sum() == 1:
            conf = i + right
            ph_bar[conf] = i
            ph_px[conf] = hv[i]
        w = lv[i - left : i + right + 1]
        if lv[i] == w.min() and (w == lv[i]).sum() == 1:
            conf = i + right
            pl_bar[conf] = i
            pl_px[conf] = lv[i]
    return ph_bar, pl_bar, ph_px, pl_px


def vol_ma(volume: pd.Series, n: int = 20) -> pd.Series:
    return volume.rolling(n, min_periods=n).mean()


def in_session(ts: pd.Timestamp) -> bool:
    h = ts.hour
    dow = getattr(ts, "day_of_week", ts.dayofweek)
    return ((7 <= h < 16) or (12 <= h < 21)) and dow < 5




def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return (macd_line, signal_line, hist)."""
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    line = ef - es
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist


def stoch(high: pd.Series, low: pd.Series, close: pd.Series,
          k: int = 14, d: int = 3, smooth: int = 3):
    """Stochastic %K (smoothed) and %D. Returns (k_line, d_line)."""
    lowest = low.rolling(k, min_periods=k).min()
    highest = high.rolling(k, min_periods=k).max()
    raw_k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    k_line = raw_k.rolling(smooth, min_periods=smooth).mean()
    d_line = k_line.rolling(d, min_periods=d).mean()
    return k_line, d_line


def in_tokyo_london(ts: pd.Timestamp) -> bool:
    """UTC Tokyo(~00-09) + London(~07-16) → 00-16 weekdays."""
    h = ts.hour
    dow = getattr(ts, "day_of_week", ts.dayofweek)
    return dow < 5 and (0 <= h < 16)


def last_closed_value(series: pd.Series, t: pd.Timestamp, bar_minutes: int):
    """Last bar whose period END <= t. Left-labeled → start <= t - bar_minutes."""
    deadline = t - pd.Timedelta(minutes=bar_minutes)
    j = series.index.searchsorted(deadline, side="right") - 1
    if j < 0:
        return None
    return float(series.iloc[j])
