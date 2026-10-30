# Research batch-4 standalone results

Generated: 2026-10-30 18:16:15.706294+03:30

Priority: TTRBOM + LiqRaid(asia). LiqRaid level_type is a counted MT axis.


## Table

 family                         variant  n_orders  IS_n      IS_R    IS_PF  OOS_n   OOS_WR     OOS_R   OOS_PF    OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5
 TTRBOM            ttrbom_M5_mm_n12_bom       210    18  0.242596 1.604699     12 0.250000 -0.585060 0.272299  6.228843 0.141176 0.00      NaN             5 0.782000    DROP   False    False  -1.087049
 TTRBOM         ttrbom_M5_rr1.5_n12_bom       210    18  0.298152 1.564083     12 0.250000 -0.460060 0.422334  5.903183 0.141176 0.00      NaN             5 0.782000    DROP   False    False  -1.087049
 TTRBOM           ttrbom_M5_rr2_n12_bom       210    18  0.481712 1.935878     12 0.250000 -0.335060 0.571889  5.577523 0.141176 0.00      NaN             5 0.782000    DROP   False    False  -1.087049
 TTRBOM            ttrbom_M5_mm_n16_bom        74     3  0.252390 1.650106      5 0.800000  0.512106 3.196938  0.781910 0.058824 0.00      NaN             1 0.781910    DROP   False    False   0.000000
 TTRBOM          ttrbom_M5_mm_n12_trend       105    12 -0.087329 0.813224      9 0.222222 -0.638712 0.237562  5.336306 0.105882 0.00      NaN             7 0.782000    DROP   False    False  -1.089251
 TTRBOM            ttrbom_M1_mm_n20_bom      1376   108  0.003625 0.968572     91 0.549451 -0.010924 0.957281  6.006164 1.070588 0.25   0.4264             5 1.556082    DROP   False    False  -0.065214
LiqRaid     liqraid_asia_rr1.5_kzlondon        62    20  0.145714 1.198908     13 0.307692 -0.358674 0.500280  4.391705 0.152941 0.00      NaN             5 0.780435    DROP   False    False  -1.122803
LiqRaid       liqraid_asia_rr2_kzlondon        62    20  0.362549 1.573462     13 0.230769 -0.435597 0.469888  5.542276 0.152941 0.00      NaN             7 0.780435    DROP   False    False  -1.131557
LiqRaid liqraid_asia_rr1.5_kzlondon_htf        33    13  0.428524 1.917216      7 0.000000 -1.125365 0.000000  4.558822 0.082353 0.00      NaN             7 0.780435    DROP   False    False  -1.176118
LiqRaid    liqraid_eqh_eql_rr1.5_kzboth       400   141 -0.062153 0.883712     66 0.469697  0.059046 1.071587  3.641900 0.776471 0.25   0.7710             3 1.551053    DROP   False    False  -0.052452
LiqRaid    liqraid_pdh_pdl_rr1.5_kzboth        63    16 -0.865456 0.113056     15 0.333333 -0.277588 0.601166  2.693930 0.176471 0.00   0.0076             3 0.781772    DROP   False    False  -1.109062
LiqRaid  liqraid_eqh_eql_rr1.5_kzlondon       356   117 -0.102745 0.830170     60 0.466667  0.052275 1.060069  3.641900 0.705882 0.50   0.7486             3 1.551053   MAYBE   False    False  -0.071999
LiqRaid     liqraid_pdh_pdl_rr1.5_kzany       155    48 -0.169021 0.719531     37 0.513514  0.173922 1.249373  3.829990 0.435294 0.50   0.9746             5 0.781932   MAYBE   False    False  -0.020818
    MTR                 mtr_lhhl_M5_rr2       554   211 -0.131382 0.806416     92 0.304348 -0.183739 0.745712 14.162956 1.082353 0.25   0.0902             9 1.556778    DROP   False    False  -0.304637
    MTR               mtr_lhhl_M5_rr1.5       554   215 -0.170973 0.739661     93 0.376344 -0.155766 0.744790 12.960139 1.094118 0.00   0.0630             5 1.556778    DROP   False    False  -0.245292
    MTR                mtr_lhhl_M15_rr2        58    23 -0.163589 0.742905     11 0.363636  0.077977 1.108339  3.074282 0.129412 0.50      NaN             4 0.780028    DROP   False    False  -1.106045
    MTR               mtr_lhhl_M5_rr2.5       554   206 -0.202366 0.731393     90 0.255556 -0.255338 0.679704 17.775081 1.058824 0.00   0.0560            16 1.556778    DROP   False    False  -0.412626
    MTR                 mtr_lhhl_M1_rr2      4049   677 -0.196229 0.763730    295 0.322034 -0.233358 0.682352 39.085761 3.470588 0.00   0.0508            13 1.545005    DROP   False    False  -0.270370
Climax2              clx2_M5_rr1.5_lb20        79    37 -0.173999 0.737407     16 0.625000  0.442115 1.995614  2.301352 0.188235 0.50   1.0000             3 0.781127    DROP   False    False   0.000846
Climax2                clx2_M5_rr2_lb20        79    37 -0.228053 0.691196     16 0.500000  0.379615 1.664354  3.059953 0.188235 0.25   0.9958             4 0.781127    DROP   False    False  -0.316794
Climax2              clx2_M5_rr1.5_lb30        68    31 -0.144583 0.781375     15 0.600000  0.376813 1.785554  2.301352 0.176471 0.50   1.0000             3 0.781127    DROP   False    False  -0.138135
Climax2               clx2_M15_rr2_lb20        13     2 -1.100776 0.000000      8 0.500000  0.397999 1.688798  1.539996 0.094118 1.00      NaN             2 0.779944    DROP   False    False  -1.116546
Climax2              clx2_M1_rr1.5_lb20       657   336 -0.196218 0.727120    147 0.408163 -0.301053 0.618733 23.275573 1.729412 0.25   0.0068             8 1.548644    DROP   False    False  -0.360889


## Promote / Robust

none


## Per-family best OOS_R (n≥10)

- TTRBOM: ttrbom_M1_mm_n20_bom tpd=1.07 PF=0.96 R=-0.011 V=DROP rob=False
- LiqRaid: liqraid_pdh_pdl_rr1.5_kzany tpd=0.44 PF=1.25 R=0.174 V=MAYBE rob=False
- MTR: mtr_lhhl_M15_rr2 tpd=0.13 PF=1.11 R=0.078 V=DROP rob=False
- Climax2: clx2_M5_rr1.5_lb20 tpd=0.19 PF=2.00 R=0.442 V=DROP rob=False