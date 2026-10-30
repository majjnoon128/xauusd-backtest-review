# Audit Response — ChatGPT + Claude findings

Status: engine correctness fixes landed; focused rebacktest at SL cap $8; watchdog **frozen**.

Primary commit: [`d4b4531`](https://github.com/majjnoon128/xauusd-backtest-review/commit/d4b4531061e8f83f917f4528cccdf6c5b0d0a619) (engine+MC+optimize+NDS+tests+report). Follow-ups may append.

| # | Finding | Agree? | Fix | Test |
|---|---|---|---|---|
| 1 | Bid/ask unbalanced | **Agree** | Explicit bid/ask for long/short × entry/exit × mkt/limit/stop; buy-stop on ask; short SL/TP on ask | `tests/test_engine_audit.py` |
| 2 | Gap trades dropped | **Agree** | Book fill; immediate `SL_GAP`/`TP_GAP` at open | `test_gap_through_sl_not_dropped` |
| 3 | R ignores costs | **Agree** | `r_multiple = net_pnl / actual_risk_usd`; also `r_gross` | `test_r_includes_costs` |
| 4 | Partial exits dropped by concurrency | **Agree** | `Order.legs` → one position, split lots at 0.01; flag `full_nosplit` | `test_partial_legs_both_execute` |
| 5 | Min-hold defers SL | **Agree** | SL always live; 30s rule = accounting (`sub30s_profit_*`) | `test_sl_always_live_no_min_hold_deferral` |
| 6 | Drop-any-overlap concurrency | **Agree** | Open-risk portfolio ≤3% + daily/max loss gates | `test_concurrency_respects_3pct` |
| 7 | tpd uses trade-days only | **Agree** | `calendar_days` / weekday count in denominator | `test_trades_per_day_uses_all_weekdays` |
| 8 | Lookahead in `optimize.py` | **Agree** | `last_closed_value` for M15/DXY/ATR | `tests/test_lookahead_pit.py` |
| 9 | NDS hook 864 / vol-on-F / HTF | **Agree** | `t_px`→Node3 for nd864; `signal_bar`=F bar; styles `day_H1`/`day_H4`; `NDS_Mechanical` / `NDS_Fidelity` | code review |
| 10 | MC target 10% / iid bootstrap | **Agree** | target 8%, 30d, min 5 days, block bootstrap, empirical tpd, risk 0.8% | `monte_carlo.py` |
| 11 | OOS-based selection | **Agree** | Pre-registered list; IS-only survivors; holdout 2025-10→12 reserved | `run_audit_rebacktest.py` |
| 12 | Re-run + union | **In progress** | See `reports/REBACKTEST_REPORT.md` | — |
| C-a | Stale KEEP CSVs | **Agree** | New `audit_rebacktest.csv` is SoT; mark old verdicts stale in report | — |
| C-b | F3 contaminated by r864 | **Disagree** | F3 = scalp M5 sym, `use_reentry864=False`. r864 fidelity rows excluded from union | overlays source |
| C-c | tpd=1.00 bug | **Agree** | same as #7 | — |
| C-d | KEEP without n gate | **Agree** | IS gate n≥20; final KEEP needs n≥100 or bootstrap (pending full rerun) | — |
| C-e | SL cap inconsistent | **Agree** | Re-run at cap 8 + uncapped diagnostic | rebacktest |
| C-f | Intrabar sticky flags / modes | **Agree** | First-touch; modes `sl_first`/`tp_first`/`random` | `test_intrabar_modes_differ_when_both_hit` |
| C-g | PDH/C22/DXY/HTF | **Partial** | PDH keyed by next day (OK). C22 uses fixed **UTC** 22:00 (not NY DST). DXY via `last_closed_value`. `_pivots` arm at i+right (OK) | — |
| C-h | KEEP gates / MC 0.8% / multiple testing | **Agree (protocol)** | risk 0.8%; document expected false KEEPs in report; full Bonferroni pending | — |
| C-i | NDS M3 sym at cap 8 | **Agree** | Included in preregistered + uncapped diagnostic | rebacktest |
| C-j | Raw vs deduped + R/day; XAG | **Partial** | R/day in report. SGB XAG: public rules page fetch inconclusive this turn — **not** added | — |

## Watchdog
Frozen until REBACKTEST_REPORT accepted and union passes honesty bar.
