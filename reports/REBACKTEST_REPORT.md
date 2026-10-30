# Rebacktest Report (post-audit engine)

Generated: 2026-10-30T15:57:39.341800+00:00

## Protocol

- Engine: bid/ask explicit, gap booked, net R, SL always live, concurrent risk ≤3%, calendar-day tpd
- SL cap: **$8** (plus uncapped diagnostic for NDS M3)
- Risk sizing: **0.8%** ($8 on $1k)
- Holdout: 2025-10-01 → 2025-12-31 (reserved)
- IS: 2026-01-01 → 2026-06-30 (selection only)
- OOS: 2026-07-01 → 2026-10-28
- Pre-registered list fixed in `src/run_audit_rebacktest.py` before interpreting holdout

## Component results (cap $8)

```
 n_trades  win_rate     avg_r  expectancy_r  profit_factor  max_dd_pct     net_pnl  final_balance  trades_per_day  trading_days  same_m1_n  same_m1_pct  sub30s_profit_usd  avg_r_gross  sub30s_profit_pct_of_target     slice  cap  n_orders                  name
       44  0.227273  0.049966      0.049966       1.137638    7.953772   26.966493    1026.966493        0.343750           128          2     0.045455              0.000     0.062781                     0.000000        IS  8.0       223         F3_nds_M5_sym
       62  0.338710  0.282265      0.282265       1.393571    6.495240  102.029793    1102.029793        0.720930            86          0     0.000000              0.000     0.173974                     0.000000       OOS  8.0       168         F3_nds_M5_sym
       28  0.357143 -0.026911     -0.026911       0.928156    5.290283   -7.919486     992.080514        0.424242            66          0     0.000000              0.000     0.086720                     0.000000   HOLDOUT  8.0       101         F3_nds_M5_sym
       78  0.256410 -0.256438     -0.256438       0.654036   15.508585 -123.356879     876.643121        0.609375           128          8     0.102564              4.890    -0.125138                     0.061125        IS  8.0       385      nds_scalp_M3_sym
       97  0.268041 -0.272425     -0.272425       0.711822   16.090921 -120.599286     879.400714        1.127907            86          8     0.082474              0.000    -0.207456                     0.000000       OOS  8.0       268      nds_scalp_M3_sym
       67  0.313433  0.077467      0.077467       1.137880    5.322498   38.150271    1038.150271        1.015152            66          8     0.119403              0.000     0.212739                     0.000000   HOLDOUT  8.0       176      nds_scalp_M3_sym
        5  0.600000  1.013498      1.013498       3.748437    0.408137   29.658836    1029.658836        0.039062           128          0     0.000000              0.000     1.097867                     0.000000        IS  8.0        49 NDS_Mechanical_day_M5
       13  0.153846 -0.607371     -0.607371       0.223314    5.964751  -50.695350     949.304650        0.151163            86          0     0.000000              0.000    -0.645542                     0.000000       OOS  8.0        43 NDS_Mechanical_day_M5
        4  0.750000  0.893891      0.893891       6.879015    0.386478   23.341664    1023.341664        0.060606            66          0     0.000000              0.000     1.034902                     0.000000   HOLDOUT  8.0        20 NDS_Mechanical_day_M5
        1  0.000000 -1.052738     -1.052738       0.000000    0.000000   -5.988489     994.011511        0.007812           128          1     1.000000              0.000    -1.115864                     0.000000        IS  8.0        28   NDS_Fidelity_day_M5
        2  0.000000 -1.015526     -1.015526       0.000000    0.639554  -13.093143     986.906857        0.023256            86          0     0.000000              0.000    -1.010030                     0.000000       OOS  8.0        29   NDS_Fidelity_day_M5
        0  0.000000  0.000000      0.000000       0.000000    0.000000    0.000000    1000.000000        0.000000            66          0     0.000000              0.000     0.000000                     0.000000   HOLDOUT  8.0        13   NDS_Fidelity_day_M5
       63  0.142857 -0.380622     -0.380622       0.597110   13.376483 -122.206946     877.793054        0.492188           128         18     0.285714              0.000    -0.161273                     0.000000        IS  8.0       137    F7_spike3d_c22d_or
       85  0.282353  0.236547      0.236547       1.337899    9.754259  143.166707    1143.166707        0.988372            86         15     0.176471              0.000     0.137114                     0.000000       OOS  8.0       122    F7_spike3d_c22d_or
       38  0.236842 -0.132159     -0.132159       0.873861    7.031647  -21.409689     978.590311        0.575758            66          8     0.210526              0.000     0.048243                     0.000000   HOLDOUT  8.0        50    F7_spike3d_c22d_or
       76  0.315789 -0.279339     -0.279339       0.585335   12.608782 -124.943000     875.057000        0.593750           128          8     0.105263             11.985    -0.281526                     0.149812        IS  8.0       282       brk_M5_M1_rr1.5
      152  0.434211  0.004321      0.004321       1.026265    8.728295   12.911500    1012.911500        1.767442            86          4     0.026316              0.000     0.015026                     0.000000       OOS  8.0       257       brk_M5_M1_rr1.5
      118  0.381356 -0.125948     -0.125948       0.804903   14.866934  -83.499000     916.501000        1.787879            66          2     0.016949              0.000    -0.121834                     0.000000   HOLDOUT  8.0       174       brk_M5_M1_rr1.5
       30  0.366667 -0.142499     -0.142499       0.775521    4.283767  -25.569000     974.431000        0.234375           128          1     0.033333              7.005    -0.127181                     0.087562        IS  8.0        61       liqraid_pdh_pdl
       42  0.547619  0.293954      0.293954       1.663298    2.282494   79.320500    1079.320500        0.488372            86          0     0.000000              0.000     0.323467                     0.000000       OOS  8.0        69       liqraid_pdh_pdl
       17  0.294118 -0.318128     -0.318128       0.516143    6.013645  -38.200500     961.799500        0.257576            66          1     0.058824              0.000    -0.312722                     0.000000   HOLDOUT  8.0        43       liqraid_pdh_pdl
       62  0.338710  0.282265      0.282265       1.393571    6.495240  102.029793    1102.029793        0.720930            86          0     0.000000              0.000     0.173974                     0.000000 OOS_UNION  8.0       168     UNION_IS_positive
```

## Union (IS-positive only)

- members: ['F3_nds_M5_sym']
- OOS n=62 tpd=0.721 avgR_net=0.282 PF=1.39 DD=6.5%
- MC(8%/30d/block, risk 0.8%): pass=0.491 bust=0.021 timeout=0.428 median_days=15.0

## Verdict on ≥3 signals/day

**NOT MET** on OOS union: tpd=0.72 (need ≥3 with positive net R and DD≤12%).
Do not invent signals. Need more independent families after engine fix.

R/day (net) ≈ 0.203; prop rough need ≈ 0.45 R/day at 0.8% risk over ~22 days.

## Notes

- F3_nds_M5_sym is NOT derived from r864 (`use_reentry864=False`).
- Fidelity r864 high-IS-R rows excluded from union.
- Only IS survivor under n≥20 & avgR>0 was F3; F7/breaker/liqraid failed IS expectancy gate (even if OOS looked ok — avoids OOS shopping).
- NDS M3 uncapped OOS: n=94 tpd≈1.09 avgR≈-0.27 (not a rescue).
- Multi-year Dukascopy 2023–2024 not downloaded this turn; holdout = late-2025 within current file.
- Stale pre-fix KEEP CSVs: treat `reports/audit_rebacktest.csv` + this file as source of truth; prior `final_verdicts` / fidelity KEEP rows are **stale**.
- Watchdog remains **FROZEN**.