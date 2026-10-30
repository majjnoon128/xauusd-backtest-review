# FINAL — SGB $1K watchdog (Tehran 2026-10-30 18:39)

## Deliverable
- Spec: `docs/WATCHDOG_SPEC_FINAL.md` (synced → results/final + expand)
- Shortlist JSON: `results/final/WATCHDOG_SHORTLIST.json`
- Gates (signal-only): `src/watchdog/gates.py`
- Feeds: `src/watchdog/price_feeds.py` — Swissquote BBO 5–10s primary (XAU+EUR), gold-api fallback, stale suppresses signals
- Monday checklist: `docs/MONDAY_GOLIVE_CHECKLIST.md`

## Mode
Signal-only + manual MT5 execution (EA/VPS banned). Lot: floor(risk$/((SL+spread+commission)×100)) to 0.01; Amir must confirm contract size. Daily 5% @ 00:00 UTC; max 12% static; concurrent ≤3%; min hold 30s.

## Dollar filter
No free live DXY. Live = EURUSD inverse (SQ EUR/USD). Proxy compare vs DXY_synth: **0 kills**. Shortlist viable on free feeds.

## Frequency (Amir: ≥3/day = MINIMUM, not cap)
All rigor-pass components kept; overlap-dedupe only.
Max union OOS tpd ≈ **2.01** (`results/final/stage3_max/`) — **below 3/day minimum**. Do not invent signals; need more validating families under audit+$8 SL.

## Primary shortlist
All robust+OOS_R>0 components (see SHORTLIST.json). Prefer OR-union with 5m same-side dedupe for concurrent risk.
