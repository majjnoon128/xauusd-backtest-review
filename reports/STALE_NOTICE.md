# Stale results notice (post-audit)

The following pre-fix artifacts must **not** be treated as current truth:

- Any `final_verdicts*.csv` KEEP rows generated before the engine audit fixes
- `fidelity_summary` / r864 IS R=+4.78 cells (excluded from union; not F3)
- Overlay/stage3 unions quoting tpd≈2.01 under the old trade-day denominator

**Source of truth now:**
- `reports/audit_rebacktest.csv`
- `reports/REBACKTEST_REPORT.md`
- `docs/AUDIT_RESPONSE.md`
