| Family | Result file | #var | Best variant (by OOS R) | cap | IS n/R | OOS n/WR/R/PF | tpd | WF+ | Verdict (best row / any row) | Why |
|---|---|---|---|---|---|---|---|---|---|---|
| AMD_PO3_iFVG | audit_code/rerun_verdicts.csv | 1 | asian_M5_market_rr2 | 7.50 | 29.00/-0.39 | 26/0.23/-0.42/0.47 | 1.00 | 0.25 | DROP/DROP | no edge IS or OOS |
| Idris | audit_code/rerun_verdicts.csv | 1 | h4_rsi_ib_rr3.0 | 5.00 | 26.00/-0.29 | 5/0.40/-0.10/1.39 | 1.00 | 0.75 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| MicroMAP | audit_code/rerun_verdicts.csv | 1 | H1_rr1.5 | 7.50 | 25.00/-0.53 | 8/0.00/-1.18/0.00 | 1.00 | 0.25 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| NDS_Fib | audit_code/rerun_verdicts.csv | 2 | 062_078_rr1.5 | 5.00 | 64.00/0.06 | 25/0.28/-0.47/0.39 | 1.09 | 0.25 | DROP/DROP | IS edge failed OOS |
| ProBTB | audit_code/rerun_verdicts.csv | 1 | M5_m1_limit_breakeven_rr2.0 | 5.00 | 264.00/-0.01 | 177/0.28/-0.00/0.88 | 2.53 | 0.50 | DROP/DROP | no edge IS or OOS |
| SP2L | audit_code/rerun_verdicts.csv | 2 | M5_A_rr1.0 | 7.50 | 65.00/0.03 | 44/0.43/-0.16/0.73 | 1.38 | 0.50 | DROP/DROP | IS edge failed OOS |
| BBDiv | batch3/bb_div/summary_strict.csv | 4 | bbdiv_M5_rr2 | 8.00 | 522.00/-0.08 | 276/0.34/-0.05/0.88 | 3.25 | 0.25 | DROP/DROP | no edge IS or OOS |
| Candle22 | batch3/candle22/summary_strict.csv | 4 | c22_h22_rr2 | 5.00 | 2.00/0.48 | 1/1.00/1.82/999.00 | 0.01 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| Casper1C | batch3/casper1c/summary_strict.csv | 2 | casper_h13_rr2 | 5.00 | nan/nan | 37/0.43/0.13/0.92 | 0.44 | nan | DROP/MAYBE | weak (PF/WF/MC gate) |
| DailyBox | batch3/daily_box/summary_strict.csv | 3 | dbox_pin_rr1.5 | 8.00 | 22.00/-0.14 | 13/0.46/0.05/0.72 | 0.15 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| FX24Sessions | batch3/fx24_sessions/summary_strict.csv | 6 | r1_fade_lon_rr2 | 8.00 | nan/nan | 8/0.50/0.15/0.67 | 0.09 | nan | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| H1Pin | batch3/h1_pin/summary_strict.csv | 5 | h1pin_h7_rr5 | 5.00 | 44.00/-0.76 | 21/0.29/0.32/1.13 | 0.25 | 0.25 | DROP/MAYBE | weak (PF/WF/MC gate) |
| H4M15PB | batch3/h4_m15_pb/summary_strict.csv | 3 | h4m15_rr2 | 5.00 | 29.00/-0.16 | 20/0.45/0.18/1.34 | 0.24 | 1.00 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| Ichimoku | batch3/ichimoku/summary_strict.csv | 5 | ichi_M5_rr1.5_f2 | 8.00 | 422.00/-0.14 | 229/0.43/-0.04/0.90 | 2.69 | 0.25 | DROP/DROP | no edge IS or OOS |
| LonFractal | batch3/lon_fractal/summary_strict.csv | 6 | lonfrac_rsi_rr2 | 5.00 | nan/nan | 7/0.71/1.16/4.71 | 0.08 | nan | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| NineAM | batch3/nine_am/summary_strict.csv | 5 | nineam_h13_M1_rr3 | 5.00 | 58.00/-0.18 | 25/0.32/0.34/1.50 | 0.29 | 0.50 | MAYBE/KEEP | OOS+ but IS<=0 → not robust |
| NYOpp | batch3/ny_opp/summary_strict.csv | 3 | nyopp_h13_rr2 | 8.00 | nan/nan | 17/0.41/0.08/1.21 | 0.20 | nan | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| NYORB | batch3/ny_orb/summary_strict.csv | 5 | nyorb_r15_rr1.5 | 8.00 | 67.00/-0.02 | 43/0.44/0.14/1.06 | 0.51 | 0.75 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| SessOpen | batch3/sess_open/summary_strict.csv | 5 | sessopen_h4_rr2 | 8.00 | 11.00/-0.20 | 2/1.00/1.84/999.00 | 0.02 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Spike50 | batch3/spike50/summary_strict.csv | 5 | spike50_M15_rr3 | 5.00 | 56.00/0.11 | 38/0.29/0.56/3.05 | 0.45 | 0.75 | KEEP/KEEP | survived (see robust/IS) |
| Supertrend | batch3/supertrend/summary_strict.csv | 4 | st_M5_p10_m3_rr2 | 8.00 | 26.00/-0.19 | 24/0.38/0.10/1.11 | 0.28 | 1.00 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| FakeBO | batch4/fake_bo/summary_strict.csv | 6 | fakebo_M30_rr2 | 8.00 | nan/nan | 30/0.40/0.03/0.89 | 0.35 | nan | DROP/DROP | weak (PF/WF/MC gate) |
| HourCandle | batch4/hour_candle/summary_strict.csv | 8 | hour12_M5_rr3 | 5.00 | nan/nan | 3/0.33/0.63/1.70 | 0.04 | nan | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Iran1630 | batch4/iran1630/summary_strict.csv | 6 | ir1630_boxsl_rr2 | 5.00 | nan/nan | 21/0.29/-0.12/0.61 | 0.25 | nan | DROP/DROP | IS edge failed OOS |
| Sess17 | batch4/sess17/summary_strict.csv | 8 | s17_tehran_est_stop_box_rr1 | 5.00 | nan/nan | 3/0.33/0.33/2.01 | 0.04 | nan | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Trend50 | batch4/trend50/summary_strict.csv | 8 | t50_M15_f0.618_rr3 | 5.00 | nan/nan | 1/1.00/2.94/999.00 | 0.01 | nan | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| MTFSMC_M5 | cap8_compare/summary.csv | 1 | mtf_M5_smt_ext_sw2 | 8.00 | 5.00/0.47 | 3/0.67/1.79/5.48 | 0.04 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| NDS_nd864_M1 | cap8_compare/summary.csv | 1 | course_scalp_M1_nd864_brk_p3_a1.0 | 8.00 | 500.00/-0.10 | 287/0.34/-0.30/0.60 | 3.38 | 0.50 | DROP/DROP | no edge IS or OOS |
| NDS_nd864_M5 | cap8_compare/summary.csv | 1 | course_scalp_M5_nd864_brk_p3_a1.0 | 5.00 | 8.00/-0.11 | 6/0.50/1.36/2.62 | 0.07 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| NDS_rr15_M1 | cap8_compare/summary.csv | 1 | course_scalp_M1_rr1.5_brk_pull_a1.0 | 8.00 | 287.00/-0.01 | 193/0.37/-0.09/0.82 | 2.27 | 0.25 | DROP/DROP | no edge IS or OOS |
| NDS_rr15_M5 | cap8_compare/summary.csv | 1 | course_scalp_M5_rr1.5_brk_p3_a1.0 | 5.00 | 8.00/-0.03 | 6/0.67/0.55/2.10 | 0.07 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| NDS_schem_M1 | cap8_compare/summary.csv | 1 | schematic_scalp_M1_nd864_brk_pull_a1.0_ndz_sm | 5.00 | 5.00/-0.58 | 5/0.80/0.32/2.32 | 0.06 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| NDS_schem_M5 | cap8_compare/summary.csv | 1 | schematic_scalp_M5_nd88_brk_p3_a1.0_ndz | 5.00 | 2.00/1.77 | 4/0.75/1.07/4.60 | 0.05 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| NDS_sym_M1 | cap8_compare/summary.csv | 1 | course_scalp_M1_sym_brk_pull_a1.0 | 8.00 | 268.00/-0.09 | 200/0.42/-0.14/0.75 | 2.35 | 0.25 | DROP/DROP | no edge IS or OOS |
| NDS_sym_M5 | cap8_compare/summary.csv | 1 | course_scalp_M5_sym_brk_p3_a1.0 | 5.00 | 8.00/-0.01 | 6/0.50/1.51/2.80 | 0.07 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| SessionBox_M1 | cap8_compare/summary.csv | 1 | box_M1_limit_mid_rr2_disp1_d0.8_slatr_buf | 8.00 | 88.00/-0.01 | 35/0.49/0.33/1.49 | 0.41 | 0.75 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| SessionBox_M5 | cap8_compare/summary.csv | 1 | box_M5_limit_mid_rr1.5_disp1_d0.8_slatr_buf | 8.00 | 65.00/0.10 | 25/0.60/0.45/2.10 | 0.29 | 0.75 | KEEP/KEEP | survived (see robust/IS) |
| CRT | crt/summary.csv | 6 | crt_ltf_H1_M15_body_extreme | 8.00 | 7.00/1.68 | 5/0.60/1.15/3.64 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| DailySweepNY | daily_sweep_ny/summary.csv | 3 | dailyny_ema_ny1330_w2_M15_asia_mid_rr2 | 8.00 | 10.00/0.47 | 6/0.33/0.02/1.09 | 0.07 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| ArsalanEMA | ema_arsalan/summary.csv | 6 | arsalan_m1sharp_M5_ema20_n12_ov0.65_t3_rr2.0 | 5.00 | 68.00/-0.19 | 45/0.36/0.09/1.08 | 0.53 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| Box_M15_asia | expand/box_summary.csv | 1 | box_M15_limit_mid_rr1.5_disp1_d0.8_slatr_buf | 8.00 | nan/nan | 10/0.50/0.21/1.22 | 0.12 | 0.33 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Box_M15_both | expand/box_summary.csv | 1 | box_M15_both_limit_mid_rr1.5_disp1_d0.8_slatr | 8.00 | nan/nan | 21/0.43/0.03/0.90 | 0.25 | 0.25 | DROP/DROP | weak (PF/WF/MC gate) |
| Box_M1_asia | expand/box_summary.csv | 1 | box_M1_limit_mid_rr2_disp1_d0.8_slatr_buf | 8.00 | nan/nan | 35/0.49/0.33/1.49 | 0.41 | 0.75 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| Box_M1_both | expand/box_summary.csv | 1 | box_M1_both_limit_mid_rr1.5_disp1_d0.8_slatr_ | 8.00 | nan/nan | 82/0.50/0.13/1.13 | 0.96 | 1.00 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| Box_M1_london | expand/box_summary.csv | 1 | box_M1_london_limit_mid_rr1.5_disp1_d0.8_slat | 8.00 | nan/nan | 57/0.46/0.01/0.91 | 0.67 | 0.75 | DROP/DROP | weak (PF/WF/MC gate) |
| Box_M3_asia | expand/box_summary.csv | 1 | box_M3_limit_mid_rr1.5_disp1_d0.8_slatr_buf | 8.00 | nan/nan | 38/0.55/0.30/1.52 | 0.45 | 0.75 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| Box_M3_both | expand/box_summary.csv | 1 | box_M3_both_limit_mid_rr1.5_disp1_d0.8_slatr_ | 8.00 | nan/nan | 81/0.48/0.13/1.09 | 0.95 | 0.75 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| Box_M3_london | expand/box_summary.csv | 1 | box_M3_london_limit_mid_rr1.5_disp1_d0.8_slat | 8.00 | nan/nan | 69/0.46/0.08/1.00 | 0.81 | 0.75 | DROP/DROP | weak (PF/WF/MC gate) |
| Box_M5_asia | expand/box_summary.csv | 1 | box_M5_limit_mid_rr1.5_disp1_d0.8_slatr_buf | 8.00 | nan/nan | 25/0.60/0.45/2.10 | 0.29 | 0.75 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| Box_M5_both | expand/box_summary.csv | 1 | box_M5_both_limit_mid_rr1.5_disp1_d0.8_slatr_ | 15.00 | nan/nan | 51/0.47/0.02/1.02 | 0.60 | 0.50 | INFO_DROP/DROP | weak (PF/WF/MC gate) |
| Box_M5_london | expand/box_summary.csv | 1 | box_M5_london_limit_mid_rr1.5_disp1_d0.8_slat | 8.00 | nan/nan | 50/0.40/-0.08/0.89 | 0.59 | 0.50 | DROP/DROP | IS edge failed OOS |
| day_M3_sym | expand/fidelity_summary.csv | 5 | course_day_M3_sym_brk_p3_a1.0_pe_r864_htf |  | 66.00/0.77 | 52/0.48/0.44/2.68 | 0.61 | 1.00 | KEEP/KEEP | survived (see robust/IS) |
| day_M5_sym | expand/fidelity_summary.csv | 5 | course_day_M5_sym_brk_p3_a1.0_pe_r864_htf |  | 19.00/4.78 | 23/0.43/0.96/4.02 | 0.27 | 1.00 | KEEP/KEEP | survived (see robust/IS) |
| scalp_M3_sym | expand/fidelity_summary.csv | 5 | course_scalp_M3_sym_brk_p3_a1.0_pe_r864_htf |  | 270.00/1.02 | 167/0.46/0.61/2.55 | 1.96 | 1.00 | KEEP/KEEP | survived (see robust/IS) |
| scalp_M5_sym | expand/fidelity_summary.csv | 5 | course_scalp_M5_sym_brk_p3_a1.0_r864 |  | 118.00/2.58 | 82/0.43/0.84/2.38 | 0.96 | 1.00 | KEEP/KEEP | survived (see robust/IS) |
| ALT_alt_at_f | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_rr1.5_at_f_a1.0 |  | 336.00/-0.25 | 165/0.40/-0.03/1.00 | 1.94 | 0.25 | DROP/DROP | no edge IS or OOS |
| ALT_alt_brk_pull | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_rr1.5_brk_pull_a1.0 |  | 175.00/-0.03 | 101/0.37/-0.13/0.79 | 1.19 | 0.50 | DROP/DROP | no edge IS or OOS |
| ALT_alt_lr2 | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_rr1.5_brk_p3_a1.0_lr2 |  | 170.00/0.07 | 75/0.51/0.20/1.43 | 0.88 | 1.00 | KEEP/KEEP | survived (see robust/IS) |
| ALT_alt_m1_brk_pull | expand/nds_uncap_summary.csv | 1 | course_scalp_M1_rr1.5_brk_pull_a1.0 |  | 588.00/-0.07 | 268/0.41/-0.02/0.91 | 3.15 | 0.25 | DROP/DROP | no edge IS or OOS |
| ALT_alt_nd864 | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_nd864_brk_p3_a1.0 |  | 275.00/-0.06 | 135/0.44/0.05/1.13 | 1.59 | 0.25 | DROP/MAYBE | weak (PF/WF/MC gate) |
| ALT_alt_sl_fixed02 | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_rr1.5_brk_p3_a1.0_slfixed02 |  | 275.00/-0.06 | 136/0.43/-0.02/0.98 | 1.60 | 0.50 | DROP/DROP | no edge IS or OOS |
| NDS_day_M1 | expand/nds_uncap_summary.csv | 1 | course_day_M1_rr1.5_brk_p3_a1.0 |  | 118.00/-0.14 | 61/0.43/-0.00/0.96 | 0.72 | 0.50 | DROP/DROP | no edge IS or OOS |
| NDS_day_M15 | expand/nds_uncap_summary.csv | 1 | course_day_M15_sym_brk_p3_a1.0 |  | 44.00/-0.01 | 34/0.44/-0.17/0.66 | 0.40 | 0.33 | DROP/DROP | no edge IS or OOS |
| NDS_day_M3 | expand/nds_uncap_summary.csv | 1 | course_day_M3_rr1.5_brk_p3_a1.0 |  | 127.00/-0.01 | 62/0.40/-0.00/0.95 | 0.73 | 0.50 | DROP/DROP | no edge IS or OOS |
| NDS_day_M5 | expand/nds_uncap_summary.csv | 1 | course_day_M5_sym_brk_p3_a1.0 |  | 66.00/-0.09 | 36/0.36/-0.18/0.69 | 0.42 | 0.25 | DROP/DROP | no edge IS or OOS |
| NDS_scalp_M1 | expand/nds_uncap_summary.csv | 1 | course_scalp_M1_sym_brk_p3_a1.0 |  | 680.00/-0.02 | 293/0.35/-0.25/0.65 | 3.45 | 0.50 | DROP/DROP | no edge IS or OOS |
| NDS_scalp_M15 | expand/nds_uncap_summary.csv | 1 | course_scalp_M15_sym_brk_p3_a1.0 |  | 104.00/0.02 | 55/0.38/-0.11/0.75 | 0.65 | 0.25 | DROP/DROP | IS edge failed OOS |
| NDS_scalp_M3 | expand/nds_uncap_summary.csv | 1 | course_scalp_M3_sym_brk_p3_a1.0 |  | 194.00/0.11 | 86/0.48/0.20/1.27 | 1.01 | 0.75 | KEEP/KEEP | survived (see robust/IS) |
| NDS_scalp_M5 | expand/nds_uncap_summary.csv | 1 | course_scalp_M5_sym_brk_p3_a1.0 |  | 271.00/-0.05 | 134/0.43/0.10/1.22 | 1.58 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| expand | expand/verify_summary.csv | 8 | course_scalp_M3_sym_brk_p3_a1.0_pe_r864_rtprr |  | 227.00/-0.21 | 146/0.39/0.10/1.27 | 1.72 | 0.25 | DROP/MAYBE | weak (PF/WF/MC gate) |
| Fib78Limit | fib78_limit/summary.csv | 6 | fib78_M15_fr3_ft1 | 8.00 | 208.00/0.02 | 118/0.25/0.01/0.97 | 1.39 | 0.50 | DROP/DROP | weak (PF/WF/MC gate) |
| FibOTEFVG | fib_ote_fvg/summary.csv | 6 | fibote_M15_M5_ob_mid_beyond10_rr2 | 5.00 | 4.00/0.08 | 5/0.40/0.39/1.91 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| BASE | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20 |  | 37.00/-0.17 | 16/0.62/0.44/2.00 | 0.19 | 0.50 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| OV:adr_fill | final/overlays/summary.csv | 7 | liqraid_pdh_pdl_rr1.5_kzany|adr_fill |  | 32.00/-0.24 | 23/0.61/0.41/1.87 | 0.27 | 0.75 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| OV:atr_regime | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20|atr_regime |  | 37.00/-0.17 | 16/0.62/0.44/2.00 | 0.19 | 0.50 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| OV:dxy_align | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20|dxy_align |  | 18.00/-0.14 | 6/0.83/0.97/5.77 | 0.07 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| OV:ex_partial_be | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20|ex_partial_be |  | 37.00/-0.23 | 16/0.69/0.25/1.71 | 0.19 | 0.25 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| OV:ex_trail15 | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20|ex_trail15 |  | 37.00/-0.12 | 16/0.56/0.35/1.79 | 0.19 | 0.50 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| OV:mh30s | final/overlays/summary.csv | 7 | clx2_M5_rr1.5_lb20|mh30s |  | 37.00/-0.17 | 16/0.62/0.44/2.00 | 0.19 | 0.50 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| OV:sess_london_ny | final/overlays/summary.csv | 6 | clx2_M5_rr1.5_lb20|sess_london_ny |  | 18.00/-0.42 | 7/0.57/0.31/1.65 | 0.08 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| OV:sess_overlap | final/overlays/summary.csv | 6 | clx2_M5_rr1.5_lb20|sess_overlap |  | 13.00/-0.34 | 7/0.57/0.31/1.65 | 0.08 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| OV:sess_overlap+atr | final/overlays/summary.csv | 6 | clx2_M5_rr1.5_lb20|sess_overlap+atr |  | 13.00/-0.34 | 7/0.57/0.31/1.65 | 0.08 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| OV:sess_overlap+dxy | final/overlays/summary.csv | 5 | clx2_M5_rr1.5_lb20|sess_overlap+dxy |  | 6.00/-0.28 | 4/1.00/1.40/999.00 | 0.05 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| OV:sess_overlap+ex_partial_be | final/overlays/summary.csv | 6 | liqraid_pdh_pdl_rr1.5_kzany|sess_overlap+ex_p |  | 2.00/0.92 | 5/0.60/0.10/1.19 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| OV:stack_overlap_atr_dxy_partial | final/overlays/summary.csv | 6 | clx2_M5_rr1.5_lb20|stack_overlap_atr_dxy_part |  | 6.00/-0.45 | 4/1.00/0.90/999.00 | 0.05 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| BP | final/research_batch1/summary.csv | 5 | bp_M5_rr1.5_pb3_r50_dxy |  | 196.00/-0.19 | 115/0.40/-0.16/0.76 | 1.35 | 0.25 | DROP/DROP | no edge IS or OOS |
| FinalFlag | final/research_batch1/summary.csv | 5 | ff_M5_rr1.5_signal_dxy |  | 143.00/-0.12 | 63/0.41/-0.13/0.77 | 0.74 | 0.25 | DROP/DROP | no edge IS or OOS |
| H2L2 | final/research_batch1/summary.csv | 5 | h2l2_M5_rr1.5_nq_cap8 |  | 602.00/-0.15 | 302/0.38/-0.20/0.72 | 3.55 | 0.00 | DROP/DROP | no edge IS or OOS |
| Judas | final/research_batch1/summary.csv | 5 | judas_M1_rr1.5_h1_ema |  | 5.00/0.90 | 5/1.00/1.38/999.00 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Wedge | final/research_batch1/summary.csv | 5 | mw_M5_rr2 |  | 319.00/-0.09 | 157/0.38/-0.02/0.95 | 1.85 | 0.50 | DROP/DROP | no edge IS or OOS |
| II | final/research_batch2/summary.csv | 5 | ii_M5_rr1.5_soft_bom |  | 47.00/0.22 | 28/0.36/-0.22/0.68 | 0.33 | 0.50 | DROP/DROP | IS edge failed OOS |
| InsideBar | final/research_batch2/summary.csv | 5 | ib_M5_rr2_hard_mother_ema20 |  | 377.00/-0.20 | 202/0.33/-0.14/0.81 | 2.38 | 0.00 | DROP/DROP | no edge IS or OOS |
| MDBMDT | final/research_batch2/summary.csv | 5 | mdbmdt_M5_rr2_t0.75_w4_signal_q_m15 |  | 401.00/-0.12 | 229/0.35/-0.11/0.82 | 2.69 | 0.00 | DROP/DROP | no edge IS or OOS |
| MDBSL | final/research_batch2/summary.csv | 5 | mdb_sl_M5_rr2_t1 |  | 282.00/-0.09 | 167/0.36/-0.08/0.86 | 1.96 | 0.25 | DROP/DROP | no edge IS or OOS |
| Mitigation | final/research_batch2/summary.csv | 5 | mit_M15_M5_rr1.5_k1 |  | 46.00/-0.15 | 23/0.48/0.04/1.05 | 0.27 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| TRFBO | final/research_batch2/summary.csv | 5 | trfbo_M5_rr2_n24 |  | 301.00/-0.28 | 156/0.35/-0.13/0.81 | 1.84 | 0.00 | DROP/DROP | no edge IS or OOS |
| Breaker | final/research_batch3/summary.csv | 5 | brk_M5_M1_rr1.5_k1 |  | 292.00/-0.07 | 134/0.49/0.06/1.09 | 1.58 | 0.75 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| FailedTrap | final/research_batch3/summary.csv | 5 | trap_M5_rr1.5_q |  | 888.00/-0.05 | 417/0.45/-0.03/0.91 | 4.91 | 0.50 | DROP/DROP | no edge IS or OOS |
| Fakey | final/research_batch3/summary.csv | 5 | fakey_M5_rr2_e0.3_signal |  | 493.00/-0.04 | 242/0.34/-0.12/0.81 | 2.85 | 0.00 | DROP/DROP | no edge IS or OOS |
| ORV | final/research_batch3/summary.csv | 5 | orv_ny_M5_rr2_2nd |  | 2.00/-1.08 | 3/0.67/0.89/3.19 | 0.04 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| PDHL | final/research_batch3/summary.csv | 5 | pdhl_rr1.5_kzany_nohtf |  | 48.00/-0.17 | 37/0.51/0.17/1.25 | 0.44 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| Climax2 | final/research_batch4/summary.csv | 5 | clx2_M5_rr1.5_lb20 |  | 37.00/-0.17 | 16/0.62/0.44/2.00 | 0.19 | 0.50 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| LiqRaid | final/research_batch4/summary.csv | 7 | liqraid_pdh_pdl_rr1.5_kzany |  | 48.00/-0.17 | 37/0.51/0.17/1.25 | 0.44 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| MTR | final/research_batch4/summary.csv | 5 | mtr_lhhl_M15_rr2 |  | 23.00/-0.16 | 11/0.36/0.08/1.11 | 0.13 | 0.50 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| TTRBOM | final/research_batch4/summary.csv | 6 | ttrbom_M5_mm_n16_bom |  | 3.00/0.25 | 5/0.80/0.51/3.20 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| M15DBDT | final/research_batch5/summary.csv | 5 | m15dbdt_mm_t1.5_neck |  | 0.00/0.00 | 0/0.00/0.00/0.00 | 0.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| PWH | final/research_batch5/summary.csv | 5 | liqraid_pwh_pwl_rr2_kzboth |  | 7.00/-0.26 | 6/0.50/0.39/1.69 | 0.07 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| RawOB | final/research_batch5/summary.csv | 5 | rawob_M15_M1_rr1.5_signal_k1 |  | 11.00/-0.20 | 5/0.60/0.36/1.93 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| U | final/stage3/summary.csv | 6 | U3_F3dxy_F7atr |  | 130.00/0.06 | 94/0.35/0.42/1.93 | 1.11 | 0.75 | KEEP/KEEP | survived (see robust/IS) |
| AMD_PO3_iFVG | final_verdicts.csv | 1 | asian_M5_market_range | 7.50 | 15.00/2.28 | 6/0.17/0.88/2.51 | 1.00 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| Idris | final_verdicts.csv | 1 | h4_rsi_ib_rr3.0 | 5.00 | 15.00/0.53 | 3/0.33/-0.22/0.04 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| MicroMAP | final_verdicts.csv | 1 | H1_rr1.5 | 7.50 | 25.00/-0.53 | 8/0.00/-1.18/0.00 | 1.00 | 0.50 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| NDS_Fib | final_verdicts.csv | 2 | 062_078_rr1.5 | 5.00 | 64.00/0.06 | 25/0.28/-0.47/0.39 | 1.09 | 0.25 | DROP/DROP | IS edge failed OOS |
| ProBTB | final_verdicts.csv | 1 | M5_m5_stop_breakout_extreme_rr2.0 | 5.00 | 203.00/0.19 | 133/0.47/0.22/1.32 | 2.33 | 0.75 | KEEP/KEEP | survived (see robust/IS) |
| SP2L | final_verdicts.csv | 1 | M5_A_rr1.5 | 5.00 | 15.00/-0.19 | 12/0.33/-0.19/0.51 | 1.09 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| Gartley | gartley_textbook/summary.csv | 6 | gartley_M5_p3_t0.08_xa786_slbeyond_x_tp0.382 | 5.00 | 4.00/0.21 | 5/0.40/0.67/1.51 | 0.06 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| H4OpenFVG | h4open_fvg/summary.csv | 5 | h4open_M5_side_of_open_rr2.0 | 8.00 | 127.00/0.14 | 90/0.23/-0.08/0.80 | 1.06 | 0.50 | DROP/DROP | IS edge failed OOS |
| Hougaard | hougaard_daily/summary.csv | 5 | hougaard_B_long_M5_mss_rr2 | 5.00 | 1.00/-1.16 | 1/1.00/1.96/999.00 | 0.01 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| LiqSweepMSS | ict3/verdicts.csv | 5 | ls_asian_london_limit_mid_liq_d1.0_slatr_buf | 8.00 | 10.00/0.56 | 8/0.12/2.28/3.03 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| LiqSweepMSS_DXY | ict3/verdicts.csv | 5 | ls_asian_ny_limit_mid_rr2_d1.0_slatr_buf | 8.00 | 11.00/0.54 | 4/0.75/1.21/5.05 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| SessionBoxMSS | ict3/verdicts.csv | 5 | box_limit_mid_rr1.5_disp1_d0.8_slatr_buf | 8.00 | 63.00/-0.04 | 25/0.60/0.45/2.12 | 1.00 | 1.00 | KEEP/KEEP | OOS+ but IS<=0 → not robust |
| SessionBoxMSS_DXY | ict3/verdicts.csv | 5 | box_market_rr2_disp1_d1.0_slatr_buf | 5.00 | 25.00/-0.06 | 6/0.67/1.09/3.29 | 1.00 | 1.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| SilverBullet | ict3/verdicts.csv | 5 | sb_limit_mid_rr2_d1.0_sw2_reclaim_slatr_buf | 8.00 | 13.00/0.09 | 6/0.50/0.58/1.42 | 1.00 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| SilverBullet_DXY | ict3/verdicts.csv | 1 | sb_limit_mid_rr1.5_d1.0_sw2_reclaim_slatr_buf | 8.00 | 5.00/0.92 | 2/1.00/1.47/999.00 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| BOSGrabCHoCH | ict_bos_grab_choch/summary.csv | 6 | bosgrab_M15_all_rr2_mid | 5.00 | 5.00/0.61 | 1/1.00/1.88/999.00 | 0.01 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| IdrisV2 | idris_v2/summary.csv | 7 | idris_h4_hl_stoch_M15_stop_mother_rr3_tokyo_l | 8.00 | 9.00/0.68 | 5/0.40/0.49/2.44 | 0.06 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| LiqSweepIFVG | liq_sweep_ifvg/summary.csv | 6 | ls_ifvg_prev_day_both_swing_d1.0 | 5.00 | 0.00/0.00 | 0/0.00/0.00/0.00 | 0.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| MagnetPDMid | magnet_pdmid/summary.csv | 5 | magnet_M15_pullback_mid_rr1.5 | 8.00 | 4.00/-1.74 | 3/0.67/1.45/7.05 | 0.04 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| MTFSMC | mtf_smc/summary.csv | 6 | mtf_M5_smt_ext_sw2 | 8.00 | 5.00/0.47 | 3/0.67/1.79/5.48 | 0.04 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| ALL | nds_course/schematic/summary.csv | 8 | schematic_scalp_M5_nd88_brk_p3_a1.0_ndz | 5.00 | 8.00/0.05 | 4/0.75/1.12/5.96 | 1.00 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| ALL_DXY | nds_course/schematic/summary.csv | 8 | course_ctx_M5_M5_rr1.5_brk_p3_a1.0 | 5.00 | 27.00/-0.02 | 6/0.67/0.62/3.40 | 1.00 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| NDS_Course | nds_course/summary.csv | 6 | scalp_M5_rr1.5_brk_p3_a1.0 | 5.00 | 65.00/-0.02 | 23/0.52/0.29/1.64 | 1.10 | 0.67 | MAYBE/KEEP | OOS+ but IS<=0 → not robust |
| NDS_Course_DXY | nds_course/summary.csv | 6 | scalp_M5_sym_brk_p3_a1.0 | 5.00 | 28.00/-0.26 | 6/0.50/1.57/4.98 | 1.00 | 0.00 | DROP/KEEP | too few OOS trades (n<20; often SL cap skips) |
| AsianBO | new4/verdicts.csv | 1 | asian_fade_close_break_slmid_rr1.5_london_ny | 5.00 | 2.00/-1.35 | 0/0.00/0.00/0.00 | 0.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| AsianBO_DXY | new4/verdicts.csv | 1 | asian_fade_close_break_slmid_rr1.5_london_ny | 5.00 | 1.00/-0.84 | 0/0.00/0.00/0.00 | 0.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| EMA_PB | new4/verdicts.csv | 1 | 15min_slope50_pb50_slswing_rr2.0 | 5.00 | 20.00/-0.13 | 5/0.40/0.16/1.58 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| EMA_PB_DXY | new4/verdicts.csv | 1 | 15min_slope50_pb20_slatr_rr2.0 | 8.00 | 60.00/-0.17 | 62/0.35/0.10/1.15 | 1.35 | 0.50 | MAYBE/MAYBE | OOS+ but IS<=0 → not robust |
| ORB | new4/verdicts.csv | 1 | london_r30_stop_slopposite_rr2.0_atr | 8.00 | 27.00/0.13 | 15/0.40/0.15/1.30 | 1.00 | 0.50 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| ORB_DXY | new4/verdicts.csv | 1 | london_r30_stop_slmid_rr2.0_atr | 7.50 | 81.00/-0.24 | 51/0.37/-0.01/0.98 | 1.00 | 0.50 | DROP/DROP | no edge IS or OOS |
| VWAP_MR | new4/verdicts.csv | 1 | fade2sd_sd2.5_rr1.5_tf | 8.00 | 137.00/-0.10 | 65/0.17/0.07/0.68 | 1.10 | 0.25 | DROP/DROP | weak (PF/WF/MC gate) |
| VWAP_MR_DXY | new4/verdicts.csv | 1 | fade2sd_sd2.0_rr1.5_tf | 8.00 | 67.00/0.20 | 27/0.07/-0.72/0.23 | 1.08 | 0.00 | DROP/DROP | IS edge failed OOS |
| AsianBO | new4/verdicts_b.csv | 4 | asian_fade_close_break_slatr_buf_rr1.5_london | 8.00 | 103.00/-0.12 | 60/0.37/-0.21/0.56 | 1.00 | 0.00 | DROP/DROP | no edge IS or OOS |
| AsianBO_DXY | new4/verdicts_b.csv | 4 | asian_fade_close_break_slatr_buf_rr1.5_london | 8.00 | 29.00/-0.25 | 19/0.63/0.30/1.60 | 1.00 | 1.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| EMA_PB | new4/verdicts_b.csv | 4 | 15min_ema50_200_pb20_slatr_rr2.0 | 5.00 | 105.00/-0.21 | 2/0.50/0.45/1.79 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| EMA_PB_DXY | new4/verdicts_b.csv | 4 | 15min_ema50_200_pb20_slatr_rr2.0 | 5.00 | 60.00/-0.29 | 1/1.00/1.99/999.00 | 1.00 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| ORB | new4/verdicts_b.csv | 4 | ny_r60_stop_slmid_rr1.5_atr | 7.50 | 12.00/-0.05 | 2/1.00/1.39/999.00 | 1.00 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| ORB_DXY | new4/verdicts_b.csv | 4 | london_r30_close_break_slmid_rr0.0_atr | 5.00 | 32.00/0.07 | 4/0.25/0.32/1.20 | 1.00 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| VWAP_MR | new4/verdicts_b.csv | 4 | fade2sd_sd2.5_rr2.0_tf | 8.00 | 137.00/-0.10 | 65/0.17/0.07/0.68 | 1.10 | 0.25 | DROP/DROP | weak (PF/WF/MC gate) |
| VWAP_MR_DXY | new4/verdicts_b.csv | 4 | fade2sd_sd2.5_rr1.5_tf | 7.50 | 58.00/0.08 | 27/0.19/0.29/0.64 | 1.08 | 0.50 | DROP/DROP | weak (PF/WF/MC gate) |
| NYCloseMagnet | ny_close_magnet/summary.csv | 6 | nymag_h22_ny_open_rr1.5 | 8.00 | 11.00/-0.39 | 13/0.31/0.12/0.99 | 0.15 | 0.50 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| OverlapBO | overlap_breakout/summary.csv | 6 | ovbo_1100_1230_stop_slmid_rr2 | 8.00 | 22.00/-0.30 | 7/0.43/0.04/1.22 | 0.08 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| PreNYH1 | preny_h1_candle/summary.csv | 6 | preny_h1_13-14_mid_rr2 | 8.00 | 1.00/1.98 | 1/1.00/0.59/999.00 | 0.01 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |
| SMAHLChannel | sma_hl_channel/summary.csv | 6 | smahl_M5_break_rr2_slchannel | 5.00 | 5.00/-0.64 | 5/0.60/0.89/4.67 | 0.06 | 0.00 | DROP/MAYBE | too few OOS trades (n<20; often SL cap skips) |
| TEMACross | tema_cross/summary.csv | 6 | tema_M15_both_slswing_a1.5 | 5.00 | 4.00/1.10 | 2/0.50/0.94/3.17 | 0.02 | 0.00 | DROP/DROP | too few OOS trades (n<20; often SL cap skips) |