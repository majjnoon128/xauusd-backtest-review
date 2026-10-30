# Batch-6 overlay results on survivors

Generated: 2026-10-30 18:25:16.903762+03:30

Bases=7 recipes=12 (pre-registered). Rows=84. US10Y/news skipped.


## Promote / Robust (signal candidates for Stage-3 unions)

                          base          overlay verdict     IS_R    OOS_R   OOS_PF      tpd  OOS_n  IS_n  robust  promote  WF+  MC_pass
                 F3_nds_M5_sym        dxy_align    KEEP 0.269499 0.895654 2.941876 0.247059     21    29    True     True 1.00   1.0000
            F7_spike3d_c22d_or       atr_regime   MAYBE 0.012733 0.301880 1.739794 0.941176     80   108    True     True 0.50   0.9876
            F7_spike3d_c22d_or             none   MAYBE 0.000720 0.272654 1.677742 0.964706     82   110    True     True 0.50   0.9796
            F7_spike3d_c22d_or            mh30s   MAYBE 0.000720 0.272654 1.677742 0.964706     82   110    True     True 0.50   0.9796
            brk_M5_M1_rr1.5_k1 sess_overlap+dxy    KEEP 0.021678 0.239728 1.454312 0.341176     29    54    True     True 0.75   0.9926
                 F3_nds_M5_sym       atr_regime   MAYBE 0.041974 0.150879 1.279082 0.694118     59    68    True     True 0.50   0.8138
   liqraid_pdh_pdl_rr1.5_kzany    ex_partial_be   MAYBE 0.018479 0.133381 1.246388 0.435294     37    48    True     True 0.75   0.9856
                 F3_nds_M5_sym             none   MAYBE 0.041974 0.129084 1.248172 0.705882     60    68    True     True 0.50   0.7862
                 F3_nds_M5_sym            mh30s   MAYBE 0.041974 0.129084 1.248172 0.705882     60    68    True     True 0.50   0.7862
            F7_spike3d_c22d_or    ex_partial_be   MAYBE 0.002917 0.102952 1.422881 1.000000     85   111    True     True 0.75   0.9526
liqraid_eqh_eql_rr1.5_kzlondon        dxy_align   MAYBE 0.022747 0.088941 1.135671 0.423529     36    65    True     True 0.75   0.8538


## KEEP (not necessarily robust)

                       base          overlay verdict      IS_R    OOS_R   OOS_PF      tpd  OOS_n  IS_n  robust  promote  WF+  MC_pass
liqraid_pdh_pdl_rr1.5_kzany         adr_fill    KEEP -0.243996 0.412182 1.873535 0.270588     23    32   False    False 0.75   1.0000
        mit_M15_M5_rr1.5_k1    ex_partial_be    KEEP -0.128420 0.225853 1.670562 0.270588     23    46   False    False 0.75   0.9994
              F3_nds_M5_sym        dxy_align    KEEP  0.269499 0.895654 2.941876 0.247059     21    29    True     True 1.00   1.0000
         brk_M5_M1_rr1.5_k1        dxy_align    KEEP -0.069210 0.205715 1.382297 0.858824     73   147   False    False 0.75   0.9828
         brk_M5_M1_rr1.5_k1 sess_overlap+dxy    KEEP  0.021678 0.239728 1.454312 0.341176     29    54    True     True 0.75   0.9926


## Best OOS_R per base (OOS_n≥10)

- `F3_nds_M5_sym` + `dxy_align`: R=0.896 PF=2.94 tpd=0.25 V=KEEP rob=True prom=True
- `F7_spike3d_c22d_or` + `dxy_align`: R=0.432 PF=2.14 tpd=0.79 V=MAYBE rob=False prom=False
- `liqraid_pdh_pdl_rr1.5_kzany` + `adr_fill`: R=0.412 PF=1.87 tpd=0.27 V=KEEP rob=False prom=False
- `liqraid_eqh_eql_rr1.5_kzlondon` + `dxy_align`: R=0.089 PF=1.14 tpd=0.42 V=MAYBE rob=True prom=True
- `brk_M5_M1_rr1.5_k1` + `sess_overlap+dxy`: R=0.240 PF=1.45 tpd=0.34 V=KEEP rob=True prom=True
- `clx2_M5_rr1.5_lb20` + `none`: R=0.442 PF=2.00 tpd=0.19 V=DROP rob=False prom=False
- `mit_M15_M5_rr1.5_k1` + `dxy_align`: R=0.236 PF=1.40 tpd=0.15 V=DROP rob=False prom=False


## Honest frequency

Robust positive rows: 11. Max single-component tpd among robust: 1.00.

Union frequency is NOT additive (same days/sessions). ≥3 tpd robust still not demonstrated.



## Full table

                          base                       overlay verdict      IS_R     OOS_R     OOS_PF      tpd  OOS_n  IS_n  robust  promote      WF+  MC_pass
                 F3_nds_M5_sym                     dxy_align    KEEP  0.269499  0.895654   2.941876 0.247059     21    29    True     True 1.000000   1.0000
                 F3_nds_M5_sym                    atr_regime   MAYBE  0.041974  0.150879   1.279082 0.694118     59    68    True     True 0.500000   0.8138
                 F3_nds_M5_sym                      adr_fill   MAYBE -0.102953  0.132273   1.289337 0.588235     50    56   False    False 0.500000   0.7864
                 F3_nds_M5_sym                          none   MAYBE  0.041974  0.129084   1.248172 0.705882     60    68    True     True 0.500000   0.7862
                 F3_nds_M5_sym                         mh30s   MAYBE  0.041974  0.129084   1.248172 0.705882     60    68    True     True 0.500000   0.7862
                 F3_nds_M5_sym                    ex_trail15    DROP -0.113303 -0.034213   1.035657 0.705882     60    68   False    False 0.500000   0.3892
                 F3_nds_M5_sym    sess_overlap+ex_partial_be    DROP -0.012167 -0.044849   0.803115 0.058824      5    11   False    False 0.000000      NaN
                 F3_nds_M5_sym                 ex_partial_be    DROP  0.104543 -0.062072   0.902953 0.729412     62    69   False    False 0.750000   0.1656
                 F3_nds_M5_sym                  sess_overlap    DROP  0.054678 -0.361062   0.532503 0.058824      5    11   False    False 0.000000      NaN
                 F3_nds_M5_sym              sess_overlap+atr    DROP  0.054678 -0.361062   0.532503 0.058824      5    11   False    False 0.000000      NaN
                 F3_nds_M5_sym                sess_london_ny    DROP  0.103313 -0.658940   0.358138 0.082353      7    14   False    False 0.000000      NaN
                 F3_nds_M5_sym              sess_overlap+dxy    DROP  0.814281 -0.756359   0.000000 0.011765      1     6   False    False 0.000000      NaN
                 F3_nds_M5_sym stack_overlap_atr_dxy_partial    DROP  0.358400 -0.756359   0.000000 0.011765      1     6   False    False 0.000000      NaN
            F7_spike3d_c22d_or                     dxy_align   MAYBE -0.035410  0.432421   2.140771 0.788235     67    83   False    False 0.500000   0.9974
            F7_spike3d_c22d_or                    atr_regime   MAYBE  0.012733  0.301880   1.739794 0.941176     80   108    True     True 0.500000   0.9876
            F7_spike3d_c22d_or                    ex_trail15   MAYBE -0.021876  0.276432   1.920876 0.988235     84   109   False    False 0.500000   0.9882
            F7_spike3d_c22d_or                          none   MAYBE  0.000720  0.272654   1.677742 0.964706     82   110    True     True 0.500000   0.9796
            F7_spike3d_c22d_or                         mh30s   MAYBE  0.000720  0.272654   1.677742 0.964706     82   110    True     True 0.500000   0.9796
            F7_spike3d_c22d_or                      adr_fill   MAYBE -0.123740  0.267286   1.741035 0.800000     68    83   False    False 0.500000   0.9794
            F7_spike3d_c22d_or                 ex_partial_be   MAYBE  0.002917  0.102952   1.422881 1.000000     85   111    True     True 0.750000   0.9526
            F7_spike3d_c22d_or                sess_london_ny    DROP -0.272272 -0.077642   1.066104 0.211765     18    22   False    False 0.333333   0.2608
            F7_spike3d_c22d_or              sess_overlap+dxy    DROP  0.023212 -0.162235   1.100382 0.105882      9    12   False    False 0.500000      NaN
            F7_spike3d_c22d_or              sess_overlap+atr    DROP -0.174353 -0.196680   0.889711 0.129412     11    16   False    False 0.000000      NaN
            F7_spike3d_c22d_or                  sess_overlap    DROP -0.182433 -0.251468   0.808237 0.141176     12    17   False    False 0.000000      NaN
            F7_spike3d_c22d_or stack_overlap_atr_dxy_partial    DROP  0.053659 -0.384457   0.505816 0.105882      9    11   False    False 0.500000      NaN
            F7_spike3d_c22d_or    sess_overlap+ex_partial_be    DROP -0.182433 -0.418134   0.371962 0.141176     12    17   False    False 0.500000      NaN
            brk_M5_M1_rr1.5_k1              sess_overlap+dxy    KEEP  0.021678  0.239728   1.454312 0.341176     29    54    True     True 0.750000   0.9926
            brk_M5_M1_rr1.5_k1                     dxy_align    KEEP -0.069210  0.205715   1.382297 0.858824     73   147   False    False 0.750000   0.9828
            brk_M5_M1_rr1.5_k1 stack_overlap_atr_dxy_partial   MAYBE -0.117477  0.101797   1.235067 0.341176     29    55   False    False 0.500000   0.9486
            brk_M5_M1_rr1.5_k1                      adr_fill   MAYBE -0.061716  0.074229   1.102948 1.388235    118   262   False    False 0.750000   0.8064
            brk_M5_M1_rr1.5_k1                          none   MAYBE -0.070360  0.062423   1.085674 1.576471    134   292   False    False 0.750000   0.7754
            brk_M5_M1_rr1.5_k1                    atr_regime   MAYBE -0.066850  0.062423   1.085674 1.576471    134   291   False    False 0.750000   0.7754
            brk_M5_M1_rr1.5_k1                         mh30s   MAYBE -0.070360  0.062423   1.085674 1.576471    134   292   False    False 0.750000   0.7754
            brk_M5_M1_rr1.5_k1                 ex_partial_be   MAYBE -0.130259  0.045835   1.089256 1.682353    143   310   False    False 0.500000   0.7576
            brk_M5_M1_rr1.5_k1                    ex_trail15   MAYBE -0.084628  0.041304   1.056027 1.552941    132   292   False    False 0.750000   0.6968
            brk_M5_M1_rr1.5_k1    sess_overlap+ex_partial_be    DROP -0.113159 -0.047687   0.878544 0.729412     62   115   False    False 0.500000   0.2276
            brk_M5_M1_rr1.5_k1                  sess_overlap    DROP -0.014023 -0.078046   0.845830 0.717647     61   111   False    False 0.250000   0.2288
            brk_M5_M1_rr1.5_k1              sess_overlap+atr    DROP -0.014023 -0.078046   0.845830 0.717647     61   111   False    False 0.250000   0.2288
            brk_M5_M1_rr1.5_k1                sess_london_ny    DROP -0.062945 -0.121247   0.789926 0.776471     66   128   False    False 0.250000   0.1110
            clx2_M5_rr1.5_lb20              sess_overlap+dxy    DROP -0.283719  1.395981 999.000000 0.047059      4     6   False    False 0.000000      NaN
            clx2_M5_rr1.5_lb20                     dxy_align    DROP -0.141564  0.967111   5.771880 0.070588      6    18   False    False 0.000000      NaN
            clx2_M5_rr1.5_lb20 stack_overlap_atr_dxy_partial    DROP -0.450385  0.895981 999.000000 0.047059      4     6   False    False 0.000000      NaN
            clx2_M5_rr1.5_lb20                          none    DROP -0.173999  0.442115   1.995614 0.188235     16    37   False    False 0.500000   1.0000
            clx2_M5_rr1.5_lb20                    atr_regime    DROP -0.173999  0.442115   1.995614 0.188235     16    37   False    False 0.500000   1.0000
            clx2_M5_rr1.5_lb20                         mh30s    DROP -0.173999  0.442115   1.995614 0.188235     16    37   False    False 0.500000   1.0000
            clx2_M5_rr1.5_lb20                    ex_trail15    DROP -0.117152  0.353956   1.791114 0.188235     16    37   False    False 0.500000   1.0000
            clx2_M5_rr1.5_lb20                  sess_overlap    DROP -0.341418  0.309096   1.654503 0.082353      7    13   False    False 1.000000      NaN
            clx2_M5_rr1.5_lb20                sess_london_ny    DROP -0.416895  0.309096   1.654503 0.082353      7    18   False    False 1.000000      NaN
            clx2_M5_rr1.5_lb20              sess_overlap+atr    DROP -0.341418  0.309096   1.654503 0.082353      7    13   False    False 1.000000      NaN
            clx2_M5_rr1.5_lb20                      adr_fill    DROP -0.136267  0.305123   1.592464 0.164706     14    33   False    False 0.500000      NaN
            clx2_M5_rr1.5_lb20                 ex_partial_be    DROP -0.225679  0.254615   1.708957 0.188235     16    37   False    False 0.250000   0.9998
            clx2_M5_rr1.5_lb20    sess_overlap+ex_partial_be    DROP -0.341418  0.023381   1.055813 0.082353      7    13   False    False 1.000000      NaN
liqraid_eqh_eql_rr1.5_kzlondon                     dxy_align   MAYBE  0.022747  0.088941   1.135671 0.423529     36    65    True     True 0.750000   0.8538
liqraid_eqh_eql_rr1.5_kzlondon                          none   MAYBE -0.102745  0.052275   1.060069 0.705882     60   117   False    False 0.500000   0.7486
liqraid_eqh_eql_rr1.5_kzlondon                    atr_regime   MAYBE -0.102745  0.052275   1.060069 0.705882     60   117   False    False 0.500000   0.7486
liqraid_eqh_eql_rr1.5_kzlondon                      adr_fill   MAYBE -0.125785  0.052275   1.060069 0.705882     60   107   False    False 0.500000   0.7486
liqraid_eqh_eql_rr1.5_kzlondon                         mh30s   MAYBE -0.102745  0.052275   1.060069 0.705882     60   117   False    False 0.500000   0.7486
liqraid_eqh_eql_rr1.5_kzlondon                    ex_trail15    DROP -0.110265  0.042963   1.043143 0.705882     60   117   False    False 0.500000   0.7138
liqraid_eqh_eql_rr1.5_kzlondon                 ex_partial_be    DROP -0.193813 -0.030800   0.908913 0.717647     61   120   False    False 0.250000   0.3062
   liqraid_pdh_pdl_rr1.5_kzany stack_overlap_atr_dxy_partial    DROP  0.917807  0.878211 999.000000 0.011765      1     2   False    False 0.000000      NaN
   liqraid_pdh_pdl_rr1.5_kzany                      adr_fill    KEEP -0.243996  0.412182   1.873535 0.270588     23    32   False    False 0.750000   1.0000
   liqraid_pdh_pdl_rr1.5_kzany                          none   MAYBE -0.169021  0.173922   1.249373 0.435294     37    48   False    False 0.500000   0.9746
   liqraid_pdh_pdl_rr1.5_kzany                    ex_trail15   MAYBE -0.198338  0.173922   1.249373 0.435294     37    48   False    False 0.500000   0.9746
   liqraid_pdh_pdl_rr1.5_kzany                         mh30s   MAYBE -0.169021  0.173922   1.249373 0.435294     37    48   False    False 0.500000   0.9746
   liqraid_pdh_pdl_rr1.5_kzany                    atr_regime   MAYBE -0.169021  0.140898   1.184292 0.423529     36    48   False    False 0.500000   0.9430
   liqraid_pdh_pdl_rr1.5_kzany                 ex_partial_be   MAYBE  0.018479  0.133381   1.246388 0.435294     37    48    True     True 0.750000   0.9856
   liqraid_pdh_pdl_rr1.5_kzany    sess_overlap+ex_partial_be    DROP  0.917807  0.101240   1.188774 0.058824      5     2   False    False 0.000000      NaN
   liqraid_pdh_pdl_rr1.5_kzany                sess_london_ny    DROP  0.167807 -0.028169   0.930639 0.082353      7     2   False    False 0.000000      NaN
   liqraid_pdh_pdl_rr1.5_kzany                  sess_overlap    DROP  0.167807 -0.098760   0.843890 0.058824      5     2   False    False 0.000000      NaN
   liqraid_pdh_pdl_rr1.5_kzany              sess_overlap+atr    DROP  0.167807 -0.098760   0.843890 0.058824      5     2   False    False 0.000000      NaN
   liqraid_pdh_pdl_rr1.5_kzany                     dxy_align    DROP  0.212916 -0.207341   0.654545 0.129412     11    19   False    False 0.500000      NaN
           mit_M15_M5_rr1.5_k1                     dxy_align    DROP -0.000924  0.236200   1.396583 0.152941     13    27   False    False 0.500000      NaN
           mit_M15_M5_rr1.5_k1                 ex_partial_be    KEEP -0.128420  0.225853   1.670562 0.270588     23    46   False    False 0.750000   0.9994
           mit_M15_M5_rr1.5_k1              sess_overlap+dxy    DROP -0.543827  0.137942   1.216991 0.047059      4     9   False    False 0.000000      NaN
           mit_M15_M5_rr1.5_k1                      adr_fill   MAYBE -0.251840  0.087918   1.148753 0.258824     22    40   False    False 0.500000   0.8592
           mit_M15_M5_rr1.5_k1                    ex_trail15   MAYBE -0.177565  0.067733   1.116277 0.270588     23    46   False    False 0.500000   0.8092
           mit_M15_M5_rr1.5_k1                          none   MAYBE -0.150160  0.036501   1.051829 0.270588     23    46   False    False 0.500000   0.6770
           mit_M15_M5_rr1.5_k1                    atr_regime   MAYBE -0.150160  0.036501   1.051829 0.270588     23    46   False    False 0.500000   0.6770
           mit_M15_M5_rr1.5_k1                         mh30s   MAYBE -0.150160  0.036501   1.051829 0.270588     23    46   False    False 0.500000   0.6770
           mit_M15_M5_rr1.5_k1    sess_overlap+ex_partial_be    DROP -0.264960 -0.006547   1.069295 0.082353      7    18   False    False 0.000000      NaN
           mit_M15_M5_rr1.5_k1                  sess_overlap    DROP -0.320515 -0.077975   0.926367 0.082353      7    18   False    False 0.000000      NaN
           mit_M15_M5_rr1.5_k1                sess_london_ny    DROP -0.193723 -0.077975   0.926367 0.082353      7    21   False    False 0.000000      NaN
           mit_M15_M5_rr1.5_k1              sess_overlap+atr    DROP -0.320515 -0.077975   0.926367 0.082353      7    18   False    False 0.000000      NaN
           mit_M15_M5_rr1.5_k1 stack_overlap_atr_dxy_partial    DROP -0.432715 -0.112058   0.776380 0.047059      4     9   False    False 0.000000      NaN