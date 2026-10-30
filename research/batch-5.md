# دسته ۵ — سه ستاپ نهایی (بدون پد) | XAUUSD M1–M15
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | هدف: چالش پراپ SGB ۱۰۰۰ دلاری

قواعد مشترک (مثل دسته ۱–۴):
- فقط قوانین منبع؛ هیچ عدد بک‌تستی اختراع نشده.
- فیلتر پراپ پیشنهادی: `signal_risk_USD <= 8` مگر منبع SL وسیع‌تری بگوید.
- زمان‌ها: UTC و تهران (UTC+3:30). اکتبر ۲۰۲۶: NY هنوز EDT = UTC−4.
- فقط سه ستاپ درخواست‌شده؛ هیچ ستاپ چهارمی اضافه نشده.
- از دسته ۶ به بعد فقط Add-on (فیلتر/خروج/پراپ/NDS) — نه ستاپ جدید.

---

## ۱) Order Block خام + ری‌تست اول (Untouched Raw OB) | منبع: DT Terminal / ICT

**نام و منبع**
- نام: `Raw_OB_First_Retest` — بلوک سفارش **شکسته‌نشده**، اولین برگشت
- درس Order Blocks: https://www.thedtterminal.com/academy/ict-order-blocks — تأیید شد (WebFetch 2026-10-30).
  - Bullish OB: آخرین کندل down-close قبل از displacement صعودی که structure را می‌شکند (body close از swing high قبلی).
  - Bearish OB: آخرین up-close قبل از displacement نزولی با body close از swing low قبلی.
  - علامت‌گذاری رایج ICT: از open تا far wick (bullish: open→low؛ bearish: open→high).
  - Mean threshold = ۵۰٪ بدنه (open–close)؛ برخی روی full range نصف می‌کنند — یکی را انتخاب و ثابت نگه دار.
  - «Already mitigated. Price has been back once. The first touch is usually ranked highest.»
  - «Closed through. A body close beyond the distal line ends the block. It may then be watched the other way round, as a breaker or a mitigation block.»
  - «No peer-reviewed study tests order blocks as ICT defines them.»
- درس Breaker vs Mitigation (برای تضاد): https://www.thedtterminal.com/academy/ict-breaker-and-mitigation-blocks

**تفاوت صریح با Mitigation (دسته ۲) و Breaker (دسته ۳)**

| | Raw OB (اینجا) | Mitigation | Breaker |
|---|---|---|---|
| وضعیت بلوک | هنوز **شکسته نشده**؛ distal حفظ شده | قبلاً با body از distal گذشته | قبلاً با body از distal گذشته |
| قبل از شکست | — (شکستی نیست) | Failure swing؛ **بدون** sweep extreme قدیمی | **با** sweep extreme قدیمی |
| جهت معامله روی ری‌تست | هم‌جهت displacement اولیه (حمایت روی bullish OB / مقاومت روی bearish OB) | هم‌جهت شکست (قطبیت برعکس) | هم‌جهت شکست (قطبیت برعکس) |
| شرط «untouched» | قیمت هنوز یک‌بار کامل به زون برنگشته (یا حداکثر اولین لمس) | پس از fail | پس از fail+sweep |

اگر body از distal بگذرد → این ستاپ **باطل** است؛ برو تعریف Breaker یا Mitigation.

**تایم‌فریم**
- شناسایی OB + displacement: M15 (یا M5).
- ری‌تست/ورود: M5 یا M1 برای رسیدن به ریسک ≤۸$.
- اختیاری refine: آخرین opposite candle روی M5 داخل زون M15 (DT: refined = tighter stop).

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30 (فیلتر عملیاتی).
- مثال DT: London KZ روی نمونهٔ آموزشی.

**تعاریف کد**
- **Displacement + BOS**: حداقل یک کندل با body بزرگ؛ سپس `close > prior_swing_high` (صعودی) یا `close < prior_swing_low` (نزولی). پارامتر: `body >= k×ATR`.
- **Bullish OB candle**: آخرین down-close در پنجرهٔ lookback (پیشنهاد ≤۵ کندل قبل از displacement؛ هم‌راستا با منطق «last opposite»).
- زون: `proximal = open`؛ `distal = low` (علامت open-to-wick)؛ `mean = (open+close)/2`.
- **Untouched**: از زمان تشکیل تا اکنون، هیچ کندلی `low <= proximal` (برای bullish) نداشته — یا فقط اولین لمس مجاز است و هنوز body از `mean` نگذشته (پارامتر سخت/نرم).
- **Invalidation**: `close < distal` (bullish) → OB مرده.

**ورود قدم‌به‌قدم (خرید — bullish raw OB)**
1. بعد از BOS صعودی، OB را علامت بزن.
2. منتظر اولین برگشت قیمت به زون (`low` یا `close` وارد `[distal, proximal]`).
3. روی M5: سیگنال‌بار صعودی با close نزدیک high داخل/روی زون (ترجیحاً بالای mean) → buy stop یک تیک بالای high آن.
   - یا limit روی proximal / mean (قانون خودت؛ DT می‌گوید entry را بنویس).
4. اگر قبل از ورود `close < distal` → لغو (دیگر raw نیست).
5. اگر قبلاً یک‌بار لمس کامل شده و برگشته → طبق DT رتبه پایین‌تر؛ در نسخهٔ سخت این دسته = رد.

**فروش bearish OB**: قرینه.

**SL**
- آن‌سوی distal (+ بافر اسپرد).
- فیلتر: `entry − distal <= 8`؛ وگرنه فقط OBهای کوچک / refined M5–M1.

**TP**
- نقدینگی سوینگ بعدی در جهت displacement؛ یا ۱R/۲R.
- منبع هدف عددی ثابت نمی‌دهد.

**فیلترها**
- بدون displacement/BOS → کندل معمولی است؛ نگیر (صریح DT).
- خلاف HTF draw → ضعیف‌تر (گزارش کیفی practitioners؛ نرخ اندازه‌گیری‌شده نیست).
- FVG بعد از OB و موقعیت discount/premium = grade اختیاری نه الزام (DT).

**آمار بک‌تست**
- **source gives no stats** (صریح: no peer-reviewed study).

---

## ۲) Double Bottom / Double Top کامل روی M15 با `neck_to_extreme <= 8` | منبع: Al Brooks

**نام و منبع**
- نام: `M15_Full_DB_DT` — DB/DT ساختاری (نه میکرو ۲–۴ کندلی)
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/
  - `DB = Double Bottom, or two consecutive bars with identical lows` (تعریف باریک کندلی)
  - `DT = Double Top, or two consecutive bars with identical highs`
  - `NL = NeckLine`
  - `MDB`/`MDT` = میکرو (قبلاً دسته ۲) — **اینجا عمداً کامل/بزرگ‌تر است**
- فروم Measured Move / neckline: https://www.brookstradingcourse.com/support-forum/20-measured-moves/neck-line-for-double-top/ — شکل سنتی «M»؛ neckline = نقطهٔ میانی؛ حداقل هدف موفق = measured move از سقف‌ها تا neckline (و قرینه برای DB).
- ورود stop کلاسیک Brooks: یک تیک آن‌سوی سیگنال‌بار؛ SL یک تیک آن‌سوی سیگنال — https://www.brookstradingcourse.com/how-to-trade-manual/stop-orders/ و صفحهٔ ۵دقیقه Emini.
- مکمل عملی neckline break: https://www.priceactionindicators.com/indicators/support-and-resistance-double-bottom-top/ (ثانویه؛ stop entry آن‌سوی neckline).

**تفاوت با MDB/MDT (دسته ۲)**
| | Full DB/DT (اینجا) | MDB/MDT |
|---|---|---|
| تایم‌فریم اجباری | **M15** | M1/M5 |
| فاصله دو extreme | می‌تواند ده‌ها کندل باشد | ۲–۴ کندل |
| فیلتر ارتفاع | `neck_to_extreme <= 8` دلار | دامنهٔ کل میکرو اغلب خودبه‌خود کوچک |
| ورود | ترجیحاً شکست neckline یا سیگنال روی/بعد از آن | اغلب بالای سیگنال‌بار میکرو |

**تایم‌فریم**
- الگو: M15.
- تریگر ریز: می‌توان روی M5 سیگنال‌بار هم‌جهت بعد از شکست neck گرفت اگر ریسک ≤۸ بماند.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30.

**تعاریف کد**
- دو swing low محلی روی M15 با `|L1 − L2| <= tol` (tol پیشنهاد 0.5–1.5$ یا «تقریباً برابر» Brooks).
- بین دو low حداقل یک swing high مشخص = `neck = max(high بین دو low)`.
- `neck_to_extreme = neck − min(L1, L2)` برای DB؛ برای DT = `max(H1,H2) − neck`.
- **فیلتر اجباری این نسخه:** `neck_to_extreme <= 8`.
- حداقل فاصله زمانی بین دو extreme: مثلاً ≥۶ کندل M15 تا از MDB جدا شود (پارامتر تفکیک).

**ورود قدم‌به‌قدم (خرید DB)**
1. دو low ≈ برابر + neck با ارتفاع ≤۸ را پیدا کن.
2. گزینهٔ A (محافظه‌کارانه): buy stop یک تیک بالای `neck`.
3. گزینهٔ B: پس از نزدیک‌شدن به neck، سیگنال‌بار صعودی با close نزدیک high → buy stop بالای high آن (اگر هنوز زیر/روی neck است و ریسک تا زیر lowها ≤۸).
4. SL زیر `min(L1,L2)` یک تیک آن‌سو.
5. اگر قبل از تریگر، قیمت با displacement قوی زیر هر دو low برود و بماند → الگوی DB باطل (LL جدید).

**فروش DT**: قرینه؛ sell stop زیر neck؛ SL بالای max highs.

**TP**
- Measured move ≈ `neck_to_extreme` فراتر از neck (منطق فروم MM).
- حداقل ۱R/۲R.

**فیلترها**
- در لگ خیلی قوی خلاف، صبر برای second entry / تأیید بیشتر (منطق Brooks strong legs).
- اگر `neck_to_extreme > 8` → رد برای SGB؛ به MDB روی TF پایین‌تر سوئیچ نکن مگر ستاپ جداگانهٔ دسته ۲.

**آمار بک‌تست**
- **source gives no stats** winrate/XAUUSD برای این پکیج فیلترشده.

---

## ۳) PWH / PWL Raid + Reclaim M5 (بدون MSS/FVG اجباری) | منبع: ICT Turtle Soup / LSG + session levels

**نام و منبع**
- نام: `PWH_PWL_M5_Reclaim`
- LSG Turtle Soup: https://lsgclub.trade/blog/ict-turtle-soup-pattern — «Previous week high and low — larger raids that can define the weekly high or low.» Confirmation: close back inside؛ ورود تهاجمی روی close؛ MSS+FVG اختیاری.
- تعریف سطوح: https://www.theinnercircletraders.com/ict-pdh-pdl-pwh-pwl/ — تأیید شد.
  - PWH = highest high هفتهٔ معاملاتی قبل؛ PWL = lowest low همان هفته.
  - نقدینگی بزرگ‌تر از PDH/PDL (تجمع حدود پنج سشن).
  - علامت‌گذاری یک‌بار در شروع هفته؛ اغلب mid-week (سه‌شنبه–پنج‌شنبه) لمس می‌شوند (کیفی منبع).
- ictkillzone Turtle Soup: prior week high/low را سطح معتبر multi-session می‌داند.

**تفاوت با PDH/PDL (دسته ۳) و Asian (دسته ۴)**
| | PWH/PWL | PDH/PDL | Asian H/L |
|---|---|---|---|
| افق زمان | **هفتهٔ قبل** | روز قبل | پنجرهٔ آسیای همان روز |
| فرکانس | معمولاً کم (۰–چند بار در هفته) | روزانه ممکن | تقریباً روزانه در لندن |
| اندازهٔ حرکت بعد از raid | غالباً بزرگ‌تر (کیفی منابع) | متوسط | متوسط |

همان قانون فاصله از ردشدهٔ LiqSweep+MSS+FVG: هسته = raid + **کلوز M5 برگشتی**؛ FVG/MSS اجباری نیست.

**تایم‌فریم**
- سطح: Weekly / Daily برای خواندن high/low هفته قبل.
- Raid + reclaim: M5.

**سشن**
- London 02:00–05:00 NY / UTC 06:00–09:00 / تهران 09:30–12:30
- و/یا NY AM 07:00–10:00 NY / UTC 11:00–14:00 / تهران 14:30–17:30
(LSG Kill Zones)

**تعاریف کد**
- هفته = از open یکشنبه/دوشنبه تا close جمعه مطابق بروکر (برای طلا مرز را ثابت بنویس؛ ICT فارکس اغلب 17:00 NY را مرز روز می‌گیرد — برای هفته: جمعه close تا یکشنبه/دوشنبه open).
- `PWH = max(high هفته قبل)`؛ `PWL = min(low هفته قبل)`.
- **Bearish PWH raid**: `high > PWH` سپس M5 با `close < PWH`.
- **Bullish PWL raid**: `low < PWL` سپس M5 با `close > PWL`.
- `raid_extreme` = max high پای عبور از PWH / min low پای عبور از PWL.

**ورود قدم‌به‌قدم (فروش بعد از PWH raid)**
1. Bias هفتگی/روزانه موافق fade سقف (مثلاً هفته bearish؛ draw روی PWL) — LSG/ICT.
2. در Kill Zone: عبور از PWH.
3. M5 close زیر PWH → reclaim.
4. ورود A: فروش روی close؛ ورود B: sell stop زیر low کندل reclaim.
5. SL بالای `raid_extreme` + بافر.
6. اگر فاصله >۸$ → رد برای چالش ۱۰۰۰ دلاری یا سایز ریسک‌ثابت خیلی کوچک (raidهای هفتگی اغلب وسیع‌اند — صادقانه: بسیاری از سیگنال‌ها فیلتر ≤۸ را رد می‌کنند).

**خرید PWL**: قرینه.

**TP**
- تعادل رنج هفته قبل؛ سپس سمت مخالف (PWL برای فروش از PWH) یا نقدینگی خارجی بعدی (LSG منطق Turtle Soup).

**فیلترها**
- ترند هفته با کلوزهای متوالی آن‌سوی PWH/PWL → breakout واقعی؛ رد.
- خبر سنگین → رد.
- اگر PWH≈PDH در یک قیمت → confluence بالاتر (کیفی theinnercircletraders)؛ الزام کد نیست.

**آمار بک‌تست**
- **source gives no stats** winrate/XAUUSD.

---

## جمع‌بندی دسته ۵

| # | ستاپ | فرکانس کیفی | مناسب ≤۸$ |
|---|---|---|---|
| 1 | Raw OB first retest | متوسط | فقط OB کوچک / refined |
| 2 | M15 full DB/DT (`neck≤8`) | کم–متوسط | بله با فیلتر ارتفاع |
| 3 | PWH/PWL M5 reclaim | کم (هفتگی) | اغلب سخت؛ فقط raid نزدیک |

## وضعیت کاتالوگ ستاپ‌ها
با دسته ۵، سه کاندید نازک باقی‌ماندهٔ دسته ۴ هم پوشش داده شدند. **ستاپ جدید دیگری پیشنهاد نمی‌شود.** ادامه = فقط Add-on در `batch-6.md` و بعد.
