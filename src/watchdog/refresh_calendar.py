"""Refresh FF weekly calendar with local cache + rate-limit guard."""
from __future__ import annotations
import json, time, urllib.request
from pathlib import Path

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE = Path(__file__).resolve().parents[2] / "data" / "calendar" / "ff_thisweek.json"
META = CACHE.with_suffix(".meta.json")
MIN_REFRESH_SEC = 30 * 60  # 30 min


def refresh(force: bool = False) -> Path:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if META.exists() and not force:
        meta = json.loads(META.read_text())
        if now - meta.get("fetched_at", 0) < MIN_REFRESH_SEC:
            return CACHE
    req = urllib.request.Request(URL, headers={"User-Agent": "GrokBotWatchdog/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    CACHE.write_bytes(raw)
    META.write_text(json.dumps({"fetched_at": now, "bytes": len(raw), "url": URL}, indent=2))
    return CACHE


if __name__ == "__main__":
    p = refresh()
    print("cached", p, "n", len(json.loads(p.read_text())))
