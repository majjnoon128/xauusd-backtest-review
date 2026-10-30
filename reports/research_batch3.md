# Research batch-3 standalone results

Generated: 2026-10-30 18:15:31.615470+03:30

Protocol: strict 0.35/0.10, cap $8. Priority PDHL+Trap. Quant appendix rigor kept.


## Table

    family                    variant  n_orders  IS_n      IS_R    IS_PF  OOS_n   OOS_WR     OOS_R   OOS_PF    OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5
      PDHL      pdhl_rr1.5_kzboth_htf        15     2 -1.077810 0.000000      5 0.200000 -0.623960 0.304564  1.527474 0.058824 0.00      NaN             2 0.780514    DROP   False    False   0.000000
      PDHL        pdhl_rr2_kzboth_htf        15     2 -1.077810 0.000000      5 0.200000 -0.523960 0.414533  1.527474 0.058824 0.00      NaN             2 0.780514    DROP   False    False   0.000000
      PDHL      pdhl_rr1.5_kznyam_htf        10     2 -1.077810 0.000000      3 0.000000 -1.105379 0.000000  1.541922 0.035294 0.00      NaN             3 0.780514    DROP   False    False   0.000000
      PDHL    pdhl_rr1.5_kzboth_nohtf        63    16 -0.865456 0.113056     15 0.333333 -0.277588 0.601166  2.693930 0.176471 0.00   0.0076             3 0.781772    DROP   False    False  -1.109062
      PDHL     pdhl_rr1.5_kzany_nohtf       155    48 -0.169021 0.719531     37 0.513514  0.173922 1.249373  3.829990 0.435294 0.50   0.9746             5 0.781932   MAYBE   False    False  -0.020818
FailedTrap            trap_M5_rr1.5_q     21660   888 -0.045885 0.897035    417 0.446043 -0.030702 0.910880 17.812010 4.905882 0.50   0.3866             8 1.553255    DROP   False    False  -0.048328
FailedTrap              trap_M5_rr2_q     21660   741 -0.037209 0.919380    306 0.323529 -0.186303 0.708080 37.850637 3.600000 0.25   0.0886            14 1.552357    DROP   False    False  -0.221257
FailedTrap   trap_M5_rr1.5_q_traponly     13832   760 -0.188337 0.742514    317 0.350158 -0.296102 0.606155 47.284390 3.729412 0.00   0.0084             8 1.558704    DROP   False    False  -0.323561
FailedTrap           trap_M5_rr1.5_nq     24200   948 -0.004647 0.960186    400 0.432500 -0.065359 0.863242 21.821512 4.705882 0.25   0.2628             7 1.552357    DROP   False    False  -0.084187
FailedTrap   trap_M1_rr1.5_q_traponly     66823   644 -0.606145 0.387684    293 0.307167 -0.585089 0.374270 60.975605 3.447059 0.00   0.0002            18 1.630729    DROP   False    False  -0.619149
     Fakey   fakey_M5_rr2_e0.5_mother       631   127 -0.315765 0.595770     77 0.324675 -0.205595 0.710982 13.418756 0.905882 0.00   0.0610            10 1.553150    DROP   False    False  -0.353092
     Fakey fakey_M5_rr1.5_e0.5_mother       631   129 -0.358601 0.518944     77 0.350649 -0.251121 0.638478 14.605582 0.905882 0.00   0.0130            10 1.553150    DROP   False    False  -0.367205
     Fakey   fakey_M5_rr2_e0.3_signal      1608   493 -0.043327 0.912672    242 0.342975 -0.118406 0.807445 20.741662 2.847059 0.00   0.1924             9 1.550972    DROP   False    False  -0.161442
     Fakey     fakey_M5_rr2_e1_mother       502    99 -0.294891 0.614156     63 0.349206 -0.148205 0.774276 10.736221 0.741176 0.00   0.1192             6 1.549205    DROP   False    False  -0.326437
     Fakey  fakey_M15_rr2_e0.5_mother        44    11 -0.584431 0.393971      5 0.000000 -0.997999 0.000000  2.774054 0.058824 0.00      NaN             5 1.550414    DROP   False    False   0.000000
       ORV      orv_london_M5_rr2_2nd        13     4 -0.075900 0.830284      7 0.142857 -0.680326 0.293242  3.809533 0.082353 0.00      NaN             5 0.780055    DROP   False    False  -1.155631
       ORV          orv_ny_M5_rr2_2nd         6     2 -1.080949 0.000000      3 0.666667  0.888448 3.190552  0.000000 0.035294 0.00      NaN             1 0.781977    DROP   False    False   0.000000
       ORV    orv_london_M5_rr1.5_2nd        13     4  0.167750 1.267385      7 0.428571 -0.037469 0.934438  1.550514 0.082353 0.00      NaN             2 0.780055    DROP   False    False  -1.144669
       ORV        orv_ny_M5_rr1.5_1st        14     6 -1.094905 0.000000      4 0.250000 -0.480613 0.429603  2.306555 0.047059 0.00      NaN             3 0.781749    DROP   False    False   0.000000
       ORV      orv_london_M5_rr2_1st        25     9 -0.644796 0.247204      9 0.222222 -0.450349 0.467840  4.550958 0.105882 0.00      NaN             6 0.779251    DROP   False    False  -1.135956
   Breaker         brk_M5_M5_rr1.5_k1       511   209 -0.131014 0.801586    122 0.426230 -0.048277 0.908856 12.563784 1.435294 0.00   0.3290             6 1.550727    DROP   False    False  -0.111118
   Breaker           brk_M5_M5_rr2_k1       511   207 -0.102685 0.847739    119 0.378151 -0.001184 0.986934 10.046672 1.400000 0.25   0.5336             8 1.550727    DROP   False    False  -0.085543
   Breaker         brk_M5_M1_rr1.5_k1       674   292 -0.070360 0.875305    134 0.485075  0.062423 1.085674  5.195322 1.576471 0.75   0.7754             4 1.553820   MAYBE   False    False   0.009767
   Breaker        brk_M15_M5_rr1.5_k1       122    49 -0.439317 0.444184     29 0.275862 -0.433125 0.435713  7.831172 0.341176 0.00   0.0004             7 1.547681    DROP   False    False  -0.813849
   Breaker      brk_M5_M5_rr1.5_k0.75       893   320 -0.186907 0.726086    166 0.421687 -0.065614 0.878151 14.724814 1.952941 0.25   0.2638             8 1.551907    DROP   False    False  -0.111822


## Promote / Robust

none


## Non-DROP

 family                variant  n_orders  IS_n      IS_R    IS_PF  OOS_n   OOS_WR    OOS_R   OOS_PF   OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5
   PDHL pdhl_rr1.5_kzany_nohtf       155    48 -0.169021 0.719531     37 0.513514 0.173922 1.249373 3.829990 0.435294 0.50   0.9746             5 0.781932   MAYBE   False    False  -0.020818
Breaker     brk_M5_M1_rr1.5_k1       674   292 -0.070360 0.875305    134 0.485075 0.062423 1.085674 5.195322 1.576471 0.75   0.7754             4 1.553820   MAYBE   False    False   0.009767


## Per-family best OOS_R (n≥10)

- PDHL: pdhl_rr1.5_kzany_nohtf tpd=0.44 PF=1.25 R=0.174 V=MAYBE rob=False
- FailedTrap: trap_M5_rr1.5_q tpd=4.91 PF=0.91 R=-0.031 V=DROP rob=False
- Fakey: fakey_M5_rr2_e0.3_signal tpd=2.85 PF=0.81 R=-0.118 V=DROP rob=False
- ORV: no sized OOS
- Breaker: brk_M5_M1_rr1.5_k1 tpd=1.58 PF=1.09 R=0.062 V=MAYBE rob=False