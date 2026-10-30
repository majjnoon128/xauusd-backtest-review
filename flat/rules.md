| __init__.py |  |
| addons_batch6.py | Batch-6 add-ons: pre-registered filters/exits as overlays on surviving components. Faithful to /workspace/trading-research/batch-6.md. US10Y skipped (no free intraday source). News: FF thisweek JSON when cached at data/calendar/ff_thisweek.json (live). Histori |
| amd_po3_ifvg.py | AMD / PO3 + inverted FVG (iFVG) — ICT-style, closed-bar only. Accumulation: Asian 00:00–07:00 UTC range, OR prior N M5 bars with low ATR. Manipulation: wick/close sweep beyond one side during London (07–10) or NY (12–15) open. Distribution: FVG formed in sweep |
| asian_bo.py | Asian range breakout 00:00–07:00 UTC → London/NY. SL: opposite/mid/atr_buf. |
| batch2_helpers.py | Shared helpers for Batch 2 strategies. |
| batch3_setups.py | Batch3 reel setups — closed-bar mechanical translations. |
| batch4_setups.py | Batch4 setups — Sess17, Iran1630Box, HourCandle, FakeBO, Trend50PB. |
| common.py | Shared filters for audited strategies. |
| crt.py | Candle Range Theory (CRT). HTF (H4/D1/H1): candle2 wicks beyond candle1 high/low and closes back inside candle1 range (stronger: inside candle1 body). Short after high sweep / long after low sweep. Entry at candle2 close, SL beyond candle2 wick, TP = candle1 o |
| daily_sweep_ny.py | daily_sweep_ny (hosein_.bashar): daily bias → NY-open counter-trend sweep → M5 FVG pullback. Daily bias from closed daily swing structure (HH/HL long, LH/LL short); fallbacks: prior-day close vs open, or vs EMA. At NY open (13:30 / 14:30 UTC windows), wait for |
| ema_arsalan.py | Arsalan EMA setups on XAUUSD. Mode 1 — sharp trend continuation: M1+EMA60 or M5+EMA20. Sharp = last N bars mostly one side of EMA, low body-overlap, EMA slope/ATR high, price displaced >k*ATR from EMA before pullback. Entry: limit at EMA on 1st touch (also 2nd |
| ema_pullback.py | EMA trend pullback — H1 and M15. |
| fib78_limit.py | fib78_limit (beny.trade): trend (HH/HL or LH/LL) → impulse swing → limit @ 0.78, SL beyond 1.0, TP @ 0.0. Log-scale Fib irrelevant intraday on gold (linear only). First-touch only; invalidate if price exceeds 1.0 before fill. Fractal sizes / TFs: M5 M15 H1 H2. |
| fib_ote_fvg.py | fib_ote_fvg (mehraninvest): BOS impulse → Fib 1.0→0.0 → FVG/OB in 0.62–0.78 → limit entry. Reuses zone math from nds_fib._zone_bounds. Differences vs prior losing NDS Fib 0.62–0.78: - requires BOS (close beyond prior swing) to define the impulse leg - requires |
| gartley_textbook.py | gartley_textbook: classic Gartley via zigzag pivots. AB=0.618 XA, BC 0.382–0.886 AB, D=0.786 XA (also 1.27–1.618 BC alt); limit at D, SL beyond X / buf beyond D; TP 0.382/0.618 AD. M5/M15/H1. |
| h4open_fvg.py | H4-open FVG: bias from previous CLOSED H4 direction (no lookahead on forming H4). Bull: price sweeps below H4 open (of current forming H4), M15/M5 swing low swept, bullish BOS/MSS, limit at FVG of impulse, SL at sweep, TP 1:2. Mirror bear. |
| hougaard_daily.py | Tom Hougaard (fundex24) daily continuation rules. Broker day = UTC calendar day (same as rest of engine / Dukascopy M1). Rule A bear: Fri high < Thu high → Mon target = Fri low. Bull mirror: Fri low > Thu low → Mon target Fri high. Rule B bear: Wed high < Mon  |
| ict_bos_grab_choch.py | ict_bos_grab_choch (fx_amirabbas, claims 80% WR): Prior BOS → wick-only liquidity grab (wick beyond swing, close back inside) → CHoCH of opposite swing with FVG on CHoCH leg → limit at FVG; SL beyond swept extreme; TP RR2 or swing. NY/all. |
| ict_helpers.py | Shared ICT building blocks — closed-bar only (M5). |
| idris.py | Idris: H4 high/low (closed) + M1 RSI hidden div + Inside Bar → market after IB close. |
| idris_v2.py | Idris v2 (author reel): H4 level → reaction → hidden div on exec TF → IB entry. Closed bars only. Use generate_idris_v2_grid() for multi entry/sl/tp in one scan. |
| liq_sweep_mss.py | London/NY liquidity sweep of Asian or previous-day HL → displacement → MSS → FVG entry. |
| magnet_pdmid.py | Previous-day midpoint magnet: long above mid→PDH, short below→PDL. London/NY on M15 context. |
| micromap.py | MicroMAP M5 — single entry H1/IB/H2, no re-entries. |
| mtf_smc.py | MTF SMC (reel): Daily strong bias after FVG fill → H1 FVG tap → M5 SMT? → BOS → limit at M5 FVG. Closed bars only. DXY used for SMT (inverse) as close series (15m→M5 ffill). Separate apply_dxy_gate is the confirmation filter (±DXY in compare), not SMT. |
| nds_course.py | NDS Course — mechanical 123Flag from Nodal Displacement Sequencing PDF. Faithful to course Day-Trading checklist (pp.98–111): HTF M30: 3 rising peaks → short bias; 3 falling troughs → long bias LTF: P1<P2<P3 then F>P3 (short) / L1>L2>L3 then F<L3 (long) Entry  |
| nds_fib.py | NDS Fib — closed M15 impulse, zone, M1 engulfing confirm; market after bar end + delay. Primary zone: 0.62–0.78 retracement. Comparison zone: 0.786–0.86 (legacy). |
| news_calendar.py | Forex Factory weekly JSON calendar — Tier-1 (High impact) ± window filter. Source: https://nfs.faireconomy.media/ff_calendar_thisweek.json Cache ≥30–60 min; ≤2 downloads / 5 min. No invented stats. |
| ny_close_magnet.py | ny_close_magnet (fxshortcast, claim ~75%): stats on prior NY close (21:00/22:00 UTC) touches in London open / London close / NY open vs random baseline; if real, trade toward it. |
| orb.py | Opening Range Breakout — London 07:00 UTC, NY 13:30 UTC. |
| overlap_breakout.py | overlap_breakout (abolfazl.ghariblou): London–NY overlap range break. Pre-overlap window variants 11:00–12:30 / 12:00–13:30 UTC; M5 closed break or stop; SL opposite/mid; TP RR4/2/3; skip SL>cap (engine). |
| preny_h1_candle.py | preny_h1_candle (hosein_.bashar): last closed H1 before NY open → M5 sweep → MSS → FVG limit. Reference = last closed H1 in window before NY (test 12:00–13:00 and 13:00–14:00 UTC = DST-aware NY 8–9 / 9–10 ET). After that H1 closes: wait for M5 sweep of its hig |
| pro_btb.py | Pro BTB M5 — 6 entry modes, closed-bar, orders armed after return/breakout bar end. |
| research_batch1.py | Research batch-1 setups (Al Brooks H2/L2, BP, Final Flag, Wedge/MW, ICT Judas). Faithful to /workspace/trading-research/batch-1.md. Rules enforced: - Stop entry 1 tick beyond signal bar; expire ≈ 1 bar (cancel if next bar misses) - SL beyond signal bar (± tick |
| research_batch2.py | Research batch-2 setups (Brooks MDB/MDT, Inside Bar, ii BOM, ICT Mitigation no-sweep, TR failed BO + 2nd). Faithful to /workspace/trading-research/batch-2.md. Rules: - Stop entry 1 tick beyond signal/pattern; expire ≈ 1 bar - SL beyond extreme (± tick); prop f |
| research_batch3.py | Research batch-3 setups (Brooks Failed Signal-Bar Trap, Fuller Fakey, PDH/PDL M5 reclaim Turtle Soup, Brooks Opening Reversal, ICT Breaker +sweep). Faithful to /workspace/trading-research/batch-3.md. - Stop entry 1 tick; expire ≈ 1 bar; SL beyond extreme; risk |
| research_batch4.py | Research batch-4: MTR (LH/HL), Climax+2nd, unified LiqRaid+M5 reclaim (PDH/PDL/EQH/EQL/Asia), TTR Breakout Mode. Faithful to /workspace/trading-research/batch-4.md. Parent rule: Asia + EQH/EQL share a family with PDH/PDL — level_type is a pre-registered parame |
| research_batch5.py | Research batch-5 (final setups): Raw OB first retest, M15 full DB/DT, PWH via LiqRaid. Faithful to /workspace/trading-research/batch-5.md. Setup catalog CLOSED after this. |
| session_box_mss.py | Session Box → MSS (close outside + break swing) → FVG retrace entry. Boxes: asia = UTC 00:00–07:00 (classic Asian range) london = UTC 07:00–08:00 (London open hour) both = asia + london same day (multiple boxes / day) |
| silver_bullet.py | ICT Silver Bullet — NY 10–11 AM America/New_York on M5. Sweep → Displacement (+ soft MSS reclaim) → FVG retrace entry. Closed bars only. |
| sma_hl_channel.py | sma_hl_channel (trade_ela): SMA20 high / SMA20 low channel. Bias long only above channel; entries: fractal break or pullback-touch+close. SL swing/channel; TP RR1.5/2/3. M5/M15. |
| sp2l.py | SP2L on M5: spike+FVG, pullback; entry A market / B stop after closed bars. |
| tema_cross.py | tema_cross (trade_ela / AdventTrading): TEMA 13/21/55 + EMA8. Long when 55 crosses from above to below all three others; exit when 55 crosses back above all. Mirror short as variant. SL: atr / swing / none(signal-exit via max_hold). TFs M5/M15/H1. |
| vwap_mr.py | Session VWAP mean-reversion and VWAP-trend pullback. Daily reset 00:00 UTC. |
