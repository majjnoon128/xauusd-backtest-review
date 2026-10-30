"""Forex Factory weekly JSON calendar — Tier-1 (High impact) ± window filter.
Source: https://nfs.faireconomy.media/ff_calendar_thisweek.json
Cache ≥30–60 min; ≤2 downloads / 5 min. No invented stats.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional, Set
import pandas as pd
from engine import Order

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "calendar" / "ff_thisweek.json"
TIER1_COUNTRIES = {"USD", "XAU"}  # gold + USD macro; extend carefully


def load_ff_events(path: Optional[Path] = None) -> pd.DataFrame:
    p = Path(path) if path else DEFAULT_CACHE
    if not p.exists():
        return pd.DataFrame(columns=["ts", "country", "title", "impact"])
    raw = json.loads(p.read_text())
    rows = []
    for e in raw:
        try:
            ts = pd.Timestamp(e["date"])
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
        except Exception:
            continue
        rows.append({
            "ts": ts,
            "country": e.get("country") or "",
            "title": e.get("title") or "",
            "impact": e.get("impact") or "",
        })
    return pd.DataFrame(rows)


def tier1_timestamps(
    events: pd.DataFrame,
    countries: Optional[Set[str]] = None,
) -> List[pd.Timestamp]:
    if events.empty:
        return []
    countries = countries or TIER1_COUNTRIES
    m = (events["impact"] == "High") & (events["country"].isin(countries))
    return list(events.loc[m, "ts"])


def filter_news_window(
    orders: List[Order],
    events: Optional[pd.DataFrame] = None,
    window_minutes: int = 30,
    countries: Optional[Set[str]] = None,
) -> List[Order]:
    """Drop orders whose arm_time is within ±window of a Tier-1 High event."""
    if events is None:
        events = load_ff_events()
    times = tier1_timestamps(events, countries)
    if not times:
        return orders  # no calendar → pass-through (honest: cannot filter)
    w = pd.Timedelta(minutes=window_minutes)
    out = []
    for o in orders:
        t = pd.Timestamp(o.arm_time)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        else:
            t = t.tz_convert("UTC")
        blocked = False
        for et in times:
            if abs(t - et) <= w:
                blocked = True
                break
        if not blocked:
            out.append(o)
    return out
