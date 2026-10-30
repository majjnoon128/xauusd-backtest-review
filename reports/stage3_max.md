# Max union — 3/day is MINIMUM not cap

Generated: 2026-10-30 18:37:43.550887+03:30

Dollar proxy: EURUSD_inv. Components kept if robust+OOS_R>0 (or KEEP+MC rigor).

Dedupe = same-side overlap window only (concurrent-risk), NOT frequency pruning.


## Per-component

family                                   variant  n_orders  IS_n      IS_R    IS_PF  OOS_n   OOS_WR    OOS_R   OOS_PF   OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5                        base          overlay
     C                  F3_nds_M5_sym|atr_regime       161    68  0.041974 0.942666     59 0.338983 0.150879 1.279082 8.962255 0.694118 0.50   0.8138            10 1.554008   MAYBE    True     True  -0.279522               F3_nds_M5_sym       atr_regime
     C                   F3_nds_M5_sym|dxy_align        64    29  0.071681 0.957050     21 0.476190 0.682154 2.458636 2.536796 0.247059 1.00   0.9996             3 0.781835    KEEP    True     True  -0.279119               F3_nds_M5_sym        dxy_align
     C                       F3_nds_M5_sym|mh30s       162    68  0.041974 0.942666     60 0.333333 0.129084 1.248172 8.962255 0.705882 0.50   0.7862            10 1.554008   MAYBE    True     True  -0.295472               F3_nds_M5_sym            mh30s
     C                        F3_nds_M5_sym|none       162    68  0.041974 0.942666     60 0.333333 0.129084 1.248172 8.962255 0.705882 0.50   0.7862            10 1.554008   MAYBE    True     True  -0.295472               F3_nds_M5_sym             none
     C             F7_spike3d_c22d_or|atr_regime       228   116  0.033827 0.801581     80 0.312500 0.302378 1.740721 8.614887 0.941176 0.75   0.9890            10 1.532855    KEEP    True     True   0.079570          F7_spike3d_c22d_or       atr_regime
     C                  F7_spike3d_c22d_or|mh30s       231   117  0.030874 0.793353     82 0.304878 0.273140 1.678748 9.304174 0.964706 0.75   0.9816            10 1.535655    KEEP    True     True   0.054220          F7_spike3d_c22d_or            mh30s
     C          F7_spike3d_c22d_or|ex_partial_be       462   118 -0.009687 0.727996     85 0.447059 0.126951 1.562968 6.564780 1.000000 0.75   0.9748             9 1.535655   MAYBE   False    False   0.025900          F7_spike3d_c22d_or    ex_partial_be
     C                   F7_spike3d_c22d_or|none       231   117  0.030874 0.793353     82 0.304878 0.273140 1.678748 9.304174 0.964706 0.75   0.9816            10 1.535655    KEEP    True     True   0.054220          F7_spike3d_c22d_or             none
     C       brk_M5_M1_rr1.5_k1|sess_overlap+dxy       112    50  0.065246 1.107358     28 0.535714 0.197992 1.358022 2.880146 0.329412 0.50   0.9822             3 0.779130   MAYBE    True     True  -0.066799          brk_M5_M1_rr1.5_k1 sess_overlap+dxy
     C liqraid_pdh_pdl_rr1.5_kzany|ex_partial_be       310    48  0.018479 1.005356     37 0.621622 0.133381 1.246388 2.818796 0.435294 0.75   0.9856             2 0.781864   MAYBE    True     True   0.010189 liqraid_pdh_pdl_rr1.5_kzany    ex_partial_be


## Unions

family        variant  n_orders  IS_n     IS_R    IS_PF  OOS_n   OOS_WR    OOS_R   OOS_PF   OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5  n_raw  n_dedup  n_parts  dedup_window_s
   MAX MAX_ALL_ROBUST       657   243 0.073939 0.949536    171 0.432749 0.295102 1.709050 8.344960 2.011765 0.75   0.9868             8 1.616435    KEEP    True     True   0.162467   3093     1109        9             NaN
   MAX   MAX_dedup60s       660   243 0.073939 0.949536    171 0.432749 0.295102 1.709050 8.344960 2.011765 0.75   0.9868             8 1.616435    KEEP    True     True   0.162467   3093     1112        9            60.0
   MAX   MAX_dedup15m       646   240 0.043105 0.895213    170 0.423529 0.249958 1.545655 8.344960 2.000000 0.75   0.9736             8 1.616435    KEEP    True     True   0.116200   3093     1096        9           900.0
   MAX   MAX_dedup60m       595   229 0.073949 0.967102    164 0.414634 0.245623 1.571425 8.444058 1.929412 0.75   0.9754             8 1.553370    KEEP    True     True   0.106681   3093     1011        9          3600.0


## Honest signals/day

- Raw OR merge (no dedupe): orders=3093

- After 5m same-side dedupe: tpd=2.01 OOS_R=0.295 rob=True

If tpd ≥ 3 under rigor, that meets Amir's MINIMUM; do not cut further.
