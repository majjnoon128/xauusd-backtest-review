# Executor report — 2026-10-30 18:38:54.234966+03:30

## Frequency (Amir)
**≥3 signals/day = MINIMUM, not a cap.** All rigor-pass components kept; overlap-dedupe only.

## Max union result
       variant      tpd    OOS_R verdict  robust
MAX_ALL_ROBUST 2.011765 0.295102    KEEP    True
  MAX_dedup60s 2.011765 0.295102    KEEP    True
  MAX_dedup15m 2.000000 0.249958    KEEP    True
  MAX_dedup60m 1.929412 0.245623    KEEP    True

**~2.0 tpd** after 5m same-side dedupe under EURUSD_inv — **below 3/day minimum**. Not pruning.

## Feeds
- Primary: Swissquote BBO XAU+EUR every 5–10s → M1 + EURUSD_inv; stale suppresses signals
- Fallback: gold-api
- Module: `src/watchdog/price_feeds.py`

## DXY proxy
EURUSD_inv does not kill shortlist edge (`results/final/dxy_proxy/REPORT.md`).

## WATCHDOG
`docs/WATCHDOG_SPEC_FINAL.md` — signal-only, SGB gates, lot formula, feeds, stale, frequency MINIMUM.
