# DXY_synth vs EURUSD-inverse proxy

Generated: 2026-10-30 18:31:05.797052+03:30

EURUSD_inv = 1/EURUSD close (Dukascopy history on box). corr_level=0.9832 corr_ret=0.9718.


## Side-by-side (OOS)

- **F7_base** [OK]: synth R=0.273 PF=1.68 tpd=0.96 rob=True | EUR_inv R=0.273 PF=1.68 tpd=0.96 rob=True (ΔR=+0.000)
- **F3_dxy_align** [WEAKENED]: synth R=0.896 PF=2.94 tpd=0.25 rob=True | EUR_inv R=0.682 PF=2.46 tpd=0.25 rob=True (ΔR=-0.213)
- **F7_atr_regime** [OK]: synth R=0.302 PF=1.74 tpd=0.94 rob=True | EUR_inv R=0.302 PF=1.74 tpd=0.94 rob=True (ΔR=+0.000)
- **brk_sess_overlap+dxy** [OK]: synth R=0.240 PF=1.45 tpd=0.34 rob=True | EUR_inv R=0.198 PF=1.36 tpd=0.33 rob=True (ΔR=-0.042)
- **brk_dxy_align** [OK]: synth R=0.206 PF=1.38 tpd=0.86 rob=False | EUR_inv R=0.203 PF=1.36 tpd=0.84 rob=False (ΔR=-0.003)
- **U3_F3dxy_F7atr** [OK]: synth R=0.417 PF=1.93 tpd=1.11 rob=True | EUR_inv R=0.420 PF=1.92 tpd=1.13 rob=True (ΔR=+0.004)
- **U2_F7atr_brkdxy** [OK]: synth R=0.297 PF=1.71 tpd=1.25 rob=True | EUR_inv R=0.286 PF=1.69 tpd=1.24 rob=True (ΔR=-0.010)
- **U4_F3atr_F7atr_brkdxy** [OK]: synth R=0.274 PF=1.66 tpd=1.69 rob=True | EUR_inv R=0.306 PF=1.71 tpd=1.67 rob=True (ΔR=+0.031)


## Verdict for watchdog viability

No hard kill, but **1 weakened**. EURUSD proxy usable with caution; prefer components robust under both.


Robust+positive under **both** sources: ['F7_base', 'F3_dxy_align', 'F7_atr_regime', 'brk_sess_overlap+dxy', 'U3_F3dxy_F7atr', 'U2_F7atr_brkdxy', 'U4_F3atr_F7atr_brkdxy']


## Full table

               family                 variant  n_orders  IS_n      IS_R    IS_PF  OOS_n   OOS_WR    OOS_R   OOS_PF   OOS_DD      tpd  WF+  MC_pass  worst_streak  mdl_pct verdict  robust  promote  OOS_R_no5                 label dxy_source
              F7_base            F7|DXY_synth       311   110  0.000720 0.781365     82 0.304878 0.272654 1.677742 8.594971 0.964706 0.50   0.9796             9 1.538006   MAYBE    True     True   0.053703               F7_base  DXY_synth
         F3_dxy_align  F3|dxy_align|DXY_synth       201    29  0.269499 1.240718     21 0.523810 0.895654 2.941876 2.316129 0.247059 1.00   1.0000             3 0.781835    KEEP    True     True  -0.140547          F3_dxy_align  DXY_synth
        F7_atr_regime        F7|atr|DXY_synth       304   108  0.012733 0.798507     80 0.312500 0.301880 1.739794 7.900294 0.941176 0.50   0.9876             9 1.538006   MAYBE    True     True   0.079039         F7_atr_regime  DXY_synth
 brk_sess_overlap+dxy  brk|sess+dxy|DXY_synth       127    54  0.021678 1.028026     29 0.551724 0.239728 1.454312 2.880146 0.341176 0.75   0.9926             3 0.779130    KEEP    True     True  -0.005335  brk_sess_overlap+dxy  DXY_synth
        brk_dxy_align       brk|dxy|DXY_synth       316   147 -0.069210 0.876717     73 0.534247 0.205715 1.382297 4.695997 0.858824 0.75   0.9828             7 1.550073    KEEP   False    False   0.116473         brk_dxy_align  DXY_synth
       U3_F3dxy_F7atr            U3|DXY_synth       505   130  0.062214 0.879620     94 0.351064 0.416793 1.930994 7.142354 1.105882 0.75   0.9956             9 1.553370    KEEP    True     True   0.184181        U3_F3dxy_F7atr  DXY_synth
      U2_F7atr_brkdxy            U2|DXY_synth       429   155  0.039093 0.871530    106 0.377358 0.296627 1.705066 5.959204 1.247059 0.75   0.9896             5 1.549735    KEEP    True     True   0.130891       U2_F7atr_brkdxy  DXY_synth
U4_F3atr_F7atr_brkdxy            U4|DXY_synth       911   204  0.021973 0.876958    144 0.375000 0.274415 1.660103 8.818373 1.694118 0.75   0.9764             8 1.553370    KEEP    True     True   0.120355 U4_F3atr_F7atr_brkdxy  DXY_synth
              F7_base           F7|EURUSD_inv       321   117  0.030874 0.793353     82 0.304878 0.273140 1.678748 9.304174 0.964706 0.75   0.9816            10 1.535655    KEEP    True     True   0.054220               F7_base EURUSD_inv
         F3_dxy_align F3|dxy_align|EURUSD_inv       195    29  0.071681 0.957050     21 0.476190 0.682154 2.458636 2.536796 0.247059 1.00   0.9996             3 0.781835    KEEP    True     True  -0.279119          F3_dxy_align EURUSD_inv
        F7_atr_regime       F7|atr|EURUSD_inv       315   116  0.033827 0.801581     80 0.312500 0.302378 1.740721 8.614887 0.941176 0.75   0.9890            10 1.532855    KEEP    True     True   0.079570         F7_atr_regime EURUSD_inv
 brk_sess_overlap+dxy brk|sess+dxy|EURUSD_inv       124    50  0.065246 1.107358     28 0.535714 0.197992 1.358022 2.880146 0.329412 0.50   0.9822             3 0.779130   MAYBE    True     True  -0.066799  brk_sess_overlap+dxy EURUSD_inv
        brk_dxy_align      brk|dxy|EURUSD_inv       314   144 -0.068186 0.879497     71 0.535211 0.202868 1.363731 4.695997 0.835294 0.75   0.9850             7 1.550073    KEEP   False    False   0.110706         brk_dxy_align EURUSD_inv
       U3_F3dxy_F7atr           U3|EURUSD_inv       510   137  0.040411 0.837624     96 0.354167 0.420322 1.919927 6.947282 1.129412 0.75   0.9950             9 1.553370    KEEP    True     True   0.193017        U3_F3dxy_F7atr EURUSD_inv
      U2_F7atr_brkdxy           U2|EURUSD_inv       437   156  0.054739 0.871743    105 0.371429 0.286419 1.690056 6.688858 1.235294 0.75   0.9898             6 1.549735    KEEP    True     True   0.118515       U2_F7atr_brkdxy EURUSD_inv
U4_F3atr_F7atr_brkdxy           U4|EURUSD_inv       919   205  0.052968 0.899906    142 0.380282 0.305715 1.707192 7.050211 1.670588 0.75   0.9810             8 1.553370    KEEP    True     True   0.145392 U4_F3atr_F7atr_brkdxy EURUSD_inv