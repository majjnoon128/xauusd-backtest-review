# Positive / conditional components mined from all Amir setups (2026-10-30)

Only components that showed **any** IS or OOS edge under the audited engine, or are structural building blocks reused in KEEP/MAYBE shapes. Full DROP families omitted except as “do not reuse.”

## KEEP / promote cores (use as portfolio building blocks)
| Component | Source | Shape | OOS notes (strict @cap8) |
|---|---|---|---|
| Candle22 H/L + DXY | mr.fotzi reel + batch3 | `c22_h22_rr2` + DXY | n=31 WR42% PF1.21 tpd0.36 — **KEEP / promote** |
| Spike50 mid-body + RR3 + DXY | amir__forex + batch3 | `spike50_M15_rr3` + DXY | n≈55 R0.34 PF1.96 tpd0.65 — MAYBE; with C22 agreement **P3 promote** tpd0.96 PF1.68 |
| Spike50 RR1.5 | same | `spike50_M15_rr1.5` | tpd≈1.13 PF1.52 MAYBE (higher frequency, lower quality) |
| NDS_sym_M5 + DXY | course 123Flag | `course_scalp_M5_sym_brk_p3` +DXY | n=22 R0.28 PF1.55 tpd0.26 KEEP (IS often ≤0 → not robust by IS&OOS) |
| SessionBox Asia M5 | ICT3 / mehraninvest | `box_M5_limit_mid_rr1.5_disp…` asia | n=25 R0.39 PF1.69 tpd0.29 KEEP OOS; **IS≤0 → observe-only** |

## Conditional helpers (helped in at least one hyp; not standalone)
| Component | Effect |
|---|---|
| **DXY confirmation** | Lifted Candle22 and Spike50; **hurt** SessionBox |
| Prior-day H/L proximity | Soft help for NDS r864 near-PD (MAYBE); Box near-PD too few trades |
| Circuit breaker 2-loss / 1% day | Risk control; same R path at 0.5% vs 0.8% on Box |
| 30m same-side dedupe | Required for multi-setup portfolios |

## Tested but do **not** reuse as primary
- NDS reentry864 / full (sym TP): lookahead bug inflated results; post-fix **not promote**
- TP-magnet retargets (pd|c22|spike): hurt expectancy
- Box+DXY, Box near c22: hurt or starve sample
- TEMA, SMA channel, Overlap BO, BOS+Grab+CHoCH, NY magnet, Gartley (fragile), Ichimoku, BB+div, H1 pin, Daily box, Supertrend, NY ORB, Sess17, Iran1630, Hour candle, Fake BO, Trend50, FX24 sessions, Fib OTE/78, LiqSweep iFVG, ProBTB (post-audit), SP2L, MicroMAP, Idris, Arsalan EMA (thin MAYBE only @5)

## Structural ideas still worth encoding (from course / reels)
1. 123Flag + displacement confirm (NDS core)
2. Second entry only via **new 123Flag near 86.4%** of first drop (SPEC_v2) — test as `r864v2`
3. Partial 1/3 at open node (prop-safe as size_mult; no scale-in)
4. Session Asia box → MSS/FVG (Box)
5. Spike wick + 50% body level as entry/TP magnet (Spike50)
6. Fixed hour candle levels (22:00) as S/R (Candle22)
7. Risk = 10% of SGB daily 5% → 0.5% per trade (optional)

## Frequency reality (honest)
Best **robust promote** portfolio so far: Spike50_rr3 + Candle22 + DXY agreement ≈ **0.96 tpd**, PF **1.68**. No audited combination cleared ~3 robust tpd under $8 SL cap.
