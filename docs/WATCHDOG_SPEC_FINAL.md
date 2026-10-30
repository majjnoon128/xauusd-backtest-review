# WATCHDOG_SPEC_FINAL — SGB $1K XAUUSD.X (Tehran)

Strict engine: closed bars, gap-through, worst-case M1 SL, spread proxy 0.35 / slip 0.10 (research).
Live symbol: **XAUUSD.X** (official SGB announcement). Metals leverage **1:100**.

## Compliance mode (mandatory)

**Watchdog is signal-only with manual execution.**

- Trading EA / auto-execution: **banned** by official SGB (rulesca/rulescb).
- VPS: **banned**.
- Money-management EA: allowed — watchdog may size/risk-check/alert but **must not place or manage orders**.
- Operator (Amir) executes fills manually in MT5 after each alert.
- This mode is the compliant deployment path for the prop account.


## Live infra (batch-8) — feeds / news / alerts

| Need | Option | Notes |
|---|---|---|
| XAU M1 | **MT5 Python + demo/live terminal** (preferred) | Symbol `XAUUSD.X`; matches execution |
| XAU M1 | Finnhub free forex WS/REST | Personal license; needs API key |
| XAU M1 | Twelve Data Basic | 8 credits/min, 800/day; trial XAU/USD |
| Dollar filter | **EURUSD inverse** (no free live DXY) | Finnhub/Twelve/MT5 EURUSD or yfinance `EURUSD=X`. **Not** Yahoo `DX-Y.NYB` / `GC=F` (≈30m delay) |
| News Tier-1 | Forex Factory JSON | `nfs.faireconomy.media/ff_calendar_thisweek.json`; `impact==High`; cache ≥1h; ≤2 downloads/5min; ±30m window |
| Alerts | **Bale** `tapi.bale.ai` | Preferred for operator in Iran; signal-only text |
| Alerts | Telegram `api.telegram.org` | Call from **server outside Iran**; client in IR often needs circumvention |

Proxy compare: EURUSD_inv does **not** kill shortlist edge → watchdog viable on free feeds (`results/final/dxy_proxy/REPORT.md`).


## Keyless live XAU (batch-9 — verified from NL box)

| Priority | Source | URL / notes |
|---|---|---|
| **1 spot BBO** | Swissquote public BBO | `https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD` — bid/ask+ts; RTT~0.6s; **no official public docs / undocumented rate limit** — poll gently |
| **2 spot** | gold-api.com | `https://api.gold-api.com/price/XAU` — no key; cadence tens of seconds; ToS bans multi-req/sec spam |
| M1 candles (proxy) | Binance data-api `PAXGUSDT` 1m + WS | Tokenized gold ≠ broker XAUUSD; sample gap up to ~0.26% — **not for SGB scalp sizing** |
| Fail from NL | Dukascopy bi5/freeserv, goldprice.org, metals.live | Do not rely |

Code: `src/watchdog/price_feeds.py` (`fetch_swissquote_xau`, `fetch_gold_api_xau`, `fetch_best_spot`).

**Still preferred for execution parity:** MT5 terminal feed on `XAUUSD.X` when available. Keyless feeds are for alert context / backup mid — operator still executes on broker price.

## Official Plan A gates (sarmayegozarebartar.com/rulesca/ — verified 2026-10-30)

| Gate | Value | Watchdog action |
|---|---|---|
| Phase targets | 8% then 4% | Display progress only |
| Min trading days | 5 per phase | Count days with ≥1 opened trade |
| Phase time | 30 / 60 calendar days from first trade | Countdown |
| **Daily loss** | **5%** of **start-of-day balance**; reset at **server midnight** (~**03:30 Tehran** / 00:00 UTC) | Soft-block new signals when equity **or** balance would breach `SOD × 0.95` (even if slippage causes it) |
| **Max loss** | **12% static** from start balance (floor **$880** on $1K) | Hard-block when equity **or** balance ≤ floor |
| **Concurrent / single risk** | **≤ 3%** of live balance ($30 on $1K) | Refuse new signal if `sum(open_planned_risk) + new_risk > 0.03 × live_balance` |
| **Tick-scalp** | Profitable holds **< 30 s** may not exceed **20% of phase target** ($16 on A phase-1 $80) | Prefer winners hold ≥ 30 s; alert if a winner closed <30 s; track tick-scalp PnL cap |
| Soft personal CB | 2 consecutive losses **or** 1% daily DD | Pause signals for the day |
| News | Allowed (firm not liable for slip/spread) | Optional Tier-1 ±30m filter when calendar present |
| Hold overnight/weekend | Allowed | — |

Official site is the final authority over aggregators.

## Lot formula (contract size not published — verify in MT5)

Assumptions until Amir confirms MT5 Specification → Contract size / Tick size / Tick value:

- Contract size **100 troy oz** per 1.00 lot (common MT5 gold; **unconfirmed for SGB**)
- Quote USD; volume step **0.01**
- Spread / commission: **not published** — pass live values from MT5

```
effective_sl_$ = SL_distance_$ + spread_$ + commission_per_oz_equiv_$
# commission: if quoted $/lot round-turn, convert: commission_$ / 100 per oz-equiv dollar of price
lots = floor_to_0.01( risk_$ / (effective_sl_$ × 100) )
```

Steering form (preferred):

```
lots = floor( risk_$ / ((SL_distance_$ + spread_$ + commission_$) × 100 oz) )  → step 0.01
```

where `commission_$` is expressed as an equivalent price-distance cost for the trade (or fold RT commission into the denominator consistently).

### 0.01 granularity problem (explicit)

On $1K with risk budget $8 and min lot 0.01:

| SL $ | Theoretical lots | Actual lots | Actual risk (price only) |
|---|---|---|---|
| 2 | 0.04 | 0.04 | $8 |
| 4 | 0.02 | 0.02 | $8 |
| 6 | 0.0133… | **0.01 or 0.02** | **$6 or $12** — cannot hit $8 |
| 8 | 0.01 | 0.01 | $8 |

**Amir must read Contract size from MT5** before live. If contract ≠ 100, replace `100` in the formula.

Project soft cap remains SL distance ≤ $8 at the 0.01-lot scale used in research; live concurrent hard cap is still 3%.

## 30-second minimum hold

- Model in research: `Order.min_hold_minutes = 1` (1 M1 bar).
- Live watchdog: after a manual fill, do **not** advise flattening a winner before 30 s elapsed (tick-scalp cap).
- Track cumulative PnL of winners closed <30 s; warn at 80% of $16; hard-warn at $16.

## Surviving components + overlays

Bases that may receive the **fixed** pre-registered overlay recipes (counted for multiple testing):

See `results/final/overlays/SURVIVORS.md` and `results/final/overlays/REPORT.md`.

Baseline promotes from final push: **F3_nds_M5_sym**, **F7_spike3d_c22d_or**.

Overlay recipes (only these):

`sess_overlap`, `sess_london_ny`, `atr_regime`, `adr_fill`, `dxy_align`,
`sess_overlap+atr`, `sess_overlap+dxy`, `ex_partial_be`, `ex_trail15`, `mh30s`,
`sess_overlap+ex_partial_be`, `stack_overlap_atr_dxy_partial`.

- **US10Y**: skipped (no free intraday source).
- **Tier-1 news ±30m**: skipped unless a calendar file is provided; academic abstracts support the *existence* of news effects (Elder 2012 8:30 ET set; Awartani 2024 FOMC 5-min) but give **no exact windows** — keep session/news params as pre-registered practitioner overlays only.
- **NDS public Persian notes**: fidelity cross-check only; **PDF / NDS_SPEC_v2 wins** on conflict.

## Honest frequency note

Under audited strict engine + $8 SL cap, the **≥3 signals/day MINIMUM** was **not** reached by research batches 1–5 alone. Path forward: overlays on survivors + unions of promoted components only; do not loosen audit rules.

### Live sizing edge case

With `spread_$=0.30` and `SL=8`, `floor(8/((8+0.30)×100))=0` — **no legal lot** under a hard $8 all-in budget.
Operator choices (manual): (a) tighten structural SL, (b) accept 0.01 lot with risk+spread ≈$8.30 (still under 3%/$30 concurrent), (c) raise risk budget toward concurrent cap. Watchdog must surface this, never auto-place.

## Promoted overlay candidates (from `results/final/overlays/REPORT.md`)

Prefer for Stage-3 unions (still signal-only):
- `F3_nds_M5_sym` + `atr_regime` / `mh30s`
- `F7_spike3d_c22d_or` + `atr_regime` / `mh30s` / `ex_partial_be`
- `brk_M5_M1_rr1.5_k1` + `sess_overlap+dxy` (robust+promote)
- `liqraid_pdh_pdl_rr1.5_kzany` + `ex_partial_be` (robust) or `adr_fill` (KEEP, higher R, not robust)

## Stage-3 pre-registered unions (results/final/stage3/)

Dedup same-side within 5 minutes. Robust+promote:

| Union | OOS_R | PF | tpd | notes |
|---|---|---|---|---|
| U3_F3dxy_F7atr | ~0.42 | ~1.93 | ~1.11 | best expectancy |
| U2_F7atr_brkdxy | ~0.30 | ~1.71 | ~1.25 | F7 atr + breaker overlap+dxy |
| U4_F3atr_F7atr_brkdxy | ~0.27 | ~1.66 | ~1.69 | highest robust tpd in set |
| U5_F7atr_liqpartial | ~0.29 | ~1.78 | ~1.29 | MAYBE but robust |

**Honest:** even the best robust union is **~1.7 signals/day**, not 3. Do not claim 3/day under audited rules. Prefer U4 for frequency or U3 for R; operator still executes manually.

Primary live shortlist (signal-only alerts):
1. `U4_F3atr_F7atr_brkdxy` or `U3_F3dxy_F7atr`
2. Fallback singles: `F7|atr_regime`, `F3|dxy_align`, `brk|sess_overlap+dxy`
NDS public cross-check detail: `docs/NDS_PUBLIC_CROSSCHECK.md` (PDF wins; SL=Flag not “node 3”).

## Free live data stack (batch-8 research — no invented SLA)

### Price (XAU M1 + dollar proxy)
- **Preferred if Windows host available:** MT5 Python (`MetaTrader5`) + demo/live terminal on same broker family as SGB (`XAUUSD.X`). Matches execution symbol.
- **Without terminal:** Finnhub free forex (REST+WS, personal) or Twelve Data Basic for `XAU/USD` + `EUR/USD` — respect credit ceilings (Twelve: 8/min, 800/day).
- **DXY raw realtime free:** scarce → use **EURUSD as dollar proxy** (already used in research as `DXY_synth` / inverse gate). Yahoo `DX-Y.NYB` / `GC=F` are **~30 min delayed** — not for live scalp alerts.
- OANDA practice stream is technically strong but **account opening for Iran residents is effectively closed**.

### News Tier-1 calendar
- **FF weekly JSON (no key):** `https://nfs.faireconomy.media/ff_calendar_thisweek.json`
- Cache locally ≥30–60 min; **≤2 downloads / 5 minutes** or FF returns Request Denied.
- Tier-1 filter: `impact == "High"` and `country in {USD}` (± CNY optional); window **±30 minutes** (pre-registered).
- Live cache path: `data/calendar/ff_thisweek.json`
- Overlay recipes: `news_tier1_pm30`, `sess_overlap+news` (counted). **Historical IS/OOS** needs a multi-week archive; thisweek-only → filter pass-through in research.

### Alerts (signal-only — still no order placement)
- **Bale Bot** preferred for operator in Iran (`https://tapi.bale.ai/bot<TOKEN>/...`); server may be outside IR.
- Telegram API from **server outside Iran**; client inside IR usually needs circumvention.
- Text ≤4096 chars; ~1 msg/s per chat (Telegram FAQ); Bale rate is interaction-based officially.

### Explicit risks
No free feed guarantees sub-second scalp SLA. Personal-use licenses, rate caps, and plan changes apply. FF JSON has no formal API contract.

## DXY live vs EURUSD-inverse (decision gate)

- Research used `DXY_synth` (ICE-like basket from FX legs on box).
- **No free live DXY** found (batch-8). Live proxy: **EURUSD inverse** (`1/EURUSD`; Dukascopy history on box; yfinance `EURUSD=X` for live — not `DX-Y.NYB` / `GC=F`, which are ~30 min delayed).
- Mandatory comparison: `results/final/dxy_proxy/REPORT.md` — every DXY-filtered final pick re-run under both sources.
- **If EUR proxy kills edge → those filters are not watchdog-viable on free feeds.** Prefer components robust under **both**.

## DXY proxy compare result (2026-10-30 18:32 +0330)

Source: `results/final/dxy_proxy/REPORT.md`. EURUSD_inv = 1/EURUSD (Dukascopy). corr_ret≈0.97 vs DXY_synth.

| Label | synth OOS_R | EUR_inv OOS_R | ΔR | Flag |
|---|---|---|---|---|
| F7_base | 0.273 | 0.273 | +0.000 | OK |
| F3_dxy_align | 0.896 | 0.682 | -0.213 | WEAKENED |
| F7_atr_regime | 0.302 | 0.302 | +0.000 | OK |
| brk_sess_overlap+dxy | 0.240 | 0.198 | -0.042 | OK |
| brk_dxy_align | 0.206 | 0.203 | -0.003 | OK |
| U3_F3dxy_F7atr | 0.417 | 0.420 | +0.004 | OK |
| U2_F7atr_brkdxy | 0.297 | 0.286 | -0.010 | OK |
| U4_F3atr_F7atr_brkdxy | 0.274 | 0.306 | +0.031 | OK |

**Watchdog viability:** EURUSD-inverse does **not** kill the shortlist edge. U3/U4/U2/F7 remain robust+positive under both. `F3_dxy_align` weakens (R 0.90→0.68) but stays KEEP/robust — usable.

**Live rule:** when raw DXY unavailable, gate with **EURUSD inverse** (Finnhub/Twelve/`EURUSD=X` / MT5 EURUSD). Do not use delayed Yahoo DX-Y.NYB for this filter.

## Primary live feed policy (batch-9 + Amir)

1. **Primary:** Swissquote public BBO polled **every 5–10 s** (gentle) for `XAU/USD` **and** `EUR/USD`.
   - Build **M1 bars** from XAU mids (`LiveFeed` in `src/watchdog/price_feeds.py`).
   - Dollar gate = **1/EUR mid** from same SQ endpoint (EURUSD inverse).
2. **Fallback XAU:** gold-api.com if SQ XAU fails (slower; ~tens of seconds).
3. **Stale-feed suppress:** if XAU age >30s (SQ) / >90s (GA) or EUR age >30s → **no new signals** (`advise_signal(feed_ok=False)`).
4. PAXG/XAUT: **off** for sizing ($1–10 gap vs spot vs $8 SL).
5. Undocumented SQ ToS/rate limit — never hammer; align with رها `sq-monitor` (~10s).

## Frequency policy (Amir clarification)

- **≥3 signals/day is a MINIMUM**, not a cap.
- **Do not prune** profitable robust components to limit frequency.
- Keep **all** components that pass rigor (robust IS&OOS+ / WF / MC).
- **Dedupe only** simultaneous or overlapping same-side signals (window for concurrent-risk ≤3% and daily-loss gates).
- Report resulting signals/day honestly after overlap-dedupe.

### Max-union result (`results/final/stage3_max/`, EURUSD_inv)

All rigor-pass components OR-merged; 5m same-side dedupe only:

| Dedup window | OOS tpd | OOS_R | robust |
|---|---|---|---|
| 5m | **~2.01** | ~0.29 | True |
| 15m | ~2.00 | ~0.25 | True |
| 60m | ~1.93 | ~0.25 | True |

**Honest:** even with **all** robust components kept (no frequency prune), audited tpd ≈ **2.0**, still **below the 3/day minimum**. Do not invent trades; gap is real under $8 SL + strict engine. Path to ≥3: more rigor-passing families only (not loosening audit).
