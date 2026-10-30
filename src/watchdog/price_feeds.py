"""Live price feeds for signal-only watchdog (batch-8/9).

Primary: Swissquote public BBO — poll gently every 5–10s to build M1 bars.
  XAU/USD + EUR/USD (dollar proxy = 1/EUR mid).
Fallback: gold-api.com /price/XAU (~tens of seconds lag, no WS).
Stale-feed check suppresses new signals when quotes age out.

Undocumented SQ rate limit/ToS — do not hammer. PAXG/XAUT unsuitable for $8 SL.
"""
from __future__ import annotations
import json, time, urllib.request
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from pathlib import Path
import pandas as pd

UA = {"User-Agent": "GrokBotWatchdog/1.0"}
SQ_BASE = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument"
GA_URL = "https://api.gold-api.com/price/XAU"

# Stale thresholds (seconds) — suppress signals if last good quote older
STALE_XAU_SEC = 30.0       # SQ should refresh every 5–10s; 30s = stale
STALE_EUR_SEC = 30.0
STALE_GA_FALLBACK_SEC = 90.0  # gold-api slower cadence


@dataclass
class Quote:
    source: str
    instrument: str
    bid: Optional[float]
    ask: Optional[float]
    mid: float
    ts_ms: Optional[int]
    recv_mono: float
    rtt_s: float
    profile: str = ""


@dataclass
class FeedHealth:
    ok: bool
    reason: str
    xau_age_s: Optional[float] = None
    eur_age_s: Optional[float] = None
    using_fallback: bool = False


def _http_get(url: str, timeout: float = 8.0) -> tuple[bytes, float]:
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), time.time() - t0


def _parse_sq(body: bytes, instrument: str, rtt: float) -> Quote:
    data = json.loads(body)
    items = data if isinstance(data, list) else [data]
    best = None
    for it in items:
        ts = it.get("ts")
        for p in it.get("spreadProfilePrices") or []:
            bid, ask = p.get("bid"), p.get("ask")
            if bid is None or ask is None:
                continue
            bid, ask = float(bid), float(ask)
            mid = (bid + ask) / 2.0
            prof = p.get("spreadProfile") or ""
            score = 0 if prof == "premium" else (1 if prof == "standard" else 2)
            cand = (score, bid, ask, mid, ts, prof)
            if best is None or cand[0] < best[0]:
                best = cand
    if best is None:
        raise RuntimeError(f"SQ {instrument}: no bid/ask")
    _, bid, ask, mid, ts, prof = best
    return Quote("swissquote_bbo", instrument, bid, ask, mid,
                 int(ts) if ts else None, time.monotonic(), rtt, prof)


def fetch_swissquote(instrument: str = "XAU/USD") -> Quote:
    body, rtt = _http_get(f"{SQ_BASE}/{instrument}")
    return _parse_sq(body, instrument, rtt)


def fetch_gold_api_xau() -> Quote:
    body, rtt = _http_get(GA_URL)
    d = json.loads(body)
    return Quote("gold_api", "XAU/USD", None, None, float(d["price"]),
                 None, time.monotonic(), rtt, d.get("updatedAt", ""))


class LiveFeed:
    """Gentle poller: SQ XAU+EUR every poll_sec; gold-api fallback for XAU; M1 OHLC builder."""

    def __init__(self, poll_sec: float = 8.0, m1_path: Optional[Path] = None):
        self.poll_sec = max(5.0, min(10.0, float(poll_sec)))
        self.last_xau: Optional[Quote] = None
        self.last_eur: Optional[Quote] = None
        self.using_ga = False
        self._m1_ticks: List[tuple] = []  # (recv_wall, mid)
        self._m1_bars: List[dict] = []
        self.m1_path = m1_path
        self._last_poll_mono = 0.0

    def poll_once(self) -> FeedHealth:
        """One gentle cycle: XAU then EUR from SQ; GA only if XAU SQ fails."""
        now = time.monotonic()
        # XAU
        try:
            self.last_xau = fetch_swissquote("XAU/USD")
            self.using_ga = False
        except Exception as e_sq:
            try:
                self.last_xau = fetch_gold_api_xau()
                self.using_ga = True
            except Exception as e_ga:
                return FeedHealth(False, f"xau_fetch_fail SQ={e_sq}; GA={e_ga}", using_fallback=True)
        # EUR for DXY proxy
        try:
            self.last_eur = fetch_swissquote("EUR/USD")
        except Exception as e:
            # EUR fail alone: still may trade if we allow, but dollar gate stale
            pass
        # record tick for M1
        if self.last_xau is not None:
            wall = time.time()
            self._m1_ticks.append((wall, self.last_xau.mid))
            self._rollup_m1(wall)
        self._last_poll_mono = now
        return self.health()

    def _rollup_m1(self, wall: float) -> None:
        """Build closed M1 bars from mid ticks (second-precision floor)."""
        if not self._m1_ticks:
            return
        # group by UTC minute
        by_min: Dict[int, List[float]] = {}
        for w, mid in self._m1_ticks:
            mkey = int(w) // 60
            by_min.setdefault(mkey, []).append(mid)
        cur = int(wall) // 60
        # emit fully closed minutes (< current)
        existing = {b["minute"] for b in self._m1_bars}
        for mkey, mids in sorted(by_min.items()):
            if mkey >= cur or mkey in existing:
                continue
            self._m1_bars.append({
                "minute": mkey,
                "time": pd.Timestamp(mkey * 60, unit="s", tz="UTC"),
                "open": mids[0], "high": max(mids), "low": min(mids), "close": mids[-1],
                "n_ticks": len(mids),
            })
        # trim tick buffer to last 3 minutes
        cutoff = wall - 180
        self._m1_ticks = [(w, m) for w, m in self._m1_ticks if w >= cutoff]
        if self.m1_path and self._m1_bars:
            self.m1_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(self._m1_bars).to_csv(self.m1_path, index=False)

    def m1_dataframe(self) -> pd.DataFrame:
        if not self._m1_bars:
            return pd.DataFrame(columns=["open", "high", "low", "close"])
        df = pd.DataFrame(self._m1_bars).set_index("time")[["open", "high", "low", "close"]]
        return df

    def eurusd_inv_mid(self) -> Optional[float]:
        if self.last_eur is None or self.last_eur.mid <= 0:
            return None
        return 1.0 / self.last_eur.mid

    def health(self) -> FeedHealth:
        now = time.monotonic()
        if self.last_xau is None:
            return FeedHealth(False, "no_xau_quote")
        xau_age = now - self.last_xau.recv_mono
        lim = STALE_GA_FALLBACK_SEC if self.using_ga else STALE_XAU_SEC
        if xau_age > lim:
            return FeedHealth(False, f"xau_stale age={xau_age:.1f}s>{lim}", xau_age_s=xau_age,
                              using_fallback=self.using_ga)
        eur_age = None
        if self.last_eur is not None:
            eur_age = now - self.last_eur.recv_mono
            if eur_age > STALE_EUR_SEC:
                return FeedHealth(False, f"eur_stale age={eur_age:.1f}s>{STALE_EUR_SEC}",
                                  xau_age_s=xau_age, eur_age_s=eur_age, using_fallback=self.using_ga)
        else:
            return FeedHealth(False, "no_eur_quote_dollar_gate", xau_age_s=xau_age,
                              using_fallback=self.using_ga)
        return FeedHealth(True, "ok", xau_age_s=xau_age, eur_age_s=eur_age,
                          using_fallback=self.using_ga)


def feed_allows_signals(feed: LiveFeed) -> FeedHealth:
    """Gate: suppress new signals when feed unhealthy/stale."""
    return feed.health()
