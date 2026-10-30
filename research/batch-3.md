# دسته ۳ — ستاپ‌های قابل‌کدنویسی XAUUSD (M1–M15)
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | ادامهٔ تحقیق | هدف: چالش پراپ SGB ۱۰۰۰ دلاری

قواعد مشترک (مثل دسته ۱ و ۲):
- فقط قوانین منبع؛ هیچ عدد بک‌تستی اختراع نشده.
- فیلتر پراپ پیشنهادی: `signal_risk_USD <= 8` مگر منبع SL وسیع‌تری بگوید.
- زمان‌ها: UTC و تهران (UTC+3:30). اکتبر ۲۰۲۶: NY هنوز EDT = UTC−4.
- هیچ ستاپی از دسته ۱ یا ۲ تکرار نشده.
- ستاپ‌های ردشدهٔ قبلی (Silver Bullet ساده، LiqSweep+MSS+FVG، fib OTE+FVG، NY ORB، Casper یک‌کندلی، Supertrend، Ichimoku، TEMA، Gartley) تکرار نمی‌شوند مگر نسخهٔ قاعدتاً متفاوت با توضیح تفاوت.

اولویت این دسته: failed signal-bar trap، Fakey، raid سقف/کف روز قبل + reclaim روی M5، Opening Reversal، Breaker Block (با sweep) + پیوست کمی طلای اینترادی.

---

## ۱) Failed Signal-Bar Trap | منبع: Al Brooks

**نام و منبع**
- نام: Failed signal bar / trap (شکست خلاف جهت سیگنال‌بار → تله و ورود معکوس)
- صفحهٔ ۵دقیقه Emini: https://www.brookstradingcourse.com/futures-market/day-trading-5-minute-emini/ — تأیید شد (WebFetch 2026-10-30).
  - نقل نزدیک به متن: سیگنال‌بار ستاپ است نه ورود؛ اگر کندل بعد یک تیک آن‌سوی high/low سیگنال برود، همان entry bar است. «Often, it is wise to enter on a breakout of either side of a signal bar. For example, if there is a bull signal bar and if the next bar takes out the low instead of the high, then it’s usually a good idea to go short because the existing trapped longs will drive the market down as they cover.» مثال Bar 25 در همان صفحه.
  - قاعدهٔ ورود عمومی همان صفحه: stop entry یک تیک بالای/زیر prior bar؛ protective stop یک تیک آن‌سوی prior bar تا اسکالپ؛ یا ریسک ۴ تا ۱۲ تیک بسته به اندازهٔ متوسط بار (عدد برای Emini است، نه طلا).
- زمینهٔ «چه کسی گیر کرده»: همان صفحه — «who is trapped and who will have to get out».

**تفاوت با ردشده‌ها و دستهٔ قبلی**
- Casper یک‌کندلی نیست: اینجا **سیگنال‌بار + شکست خلاف جهت** الزامی است (دو رویداد).
- LiqSweep+MSS+FVG نیست؛ هیچ FVG/MSS اجباری نیست.
- با H2/L2 دسته ۱ فرق دارد: H2 یعنی دومین لگ پولبک موفق؛ اینجا سیگنال اول **trigger نمی‌شود** و طرف مخالف پر می‌شود.

**تایم‌فریم**
- منبع: ۵دقیقه Emini (۱۰–۲۰ ستاپ در روز روی همان بازار — نقل صفحه؛ این عدد برای طلا نیست).
- اجرا روی طلا: M5 (اصلی)؛ M1 فقط با فیلتر ارتفاع سیگنال ≤۸$.

**سشن**
- منبع محدود نکرده. پیشنهاد حجم طلا: UTC 07:00–16:00 / تهران 10:30–19:30.

**تعاریف کد**
- **Bull signal bar**: کندل با بدنهٔ صعودی و close در نیمهٔ بالای دامنه (نزدیک high) در زمینهٔ خرید محتمل (مثلاً بعد از لگ نزولی یا در کف).
- **Bear signal bar**: قرینه.
- **Failed bull signal (تلهٔ لانگ)**: بعد از سیگنال خرید، قبل از اینکه high سیگنال + ۱ تیک تریگر شود، قیمت `low[signal] − 1 tick` را می‌گیرد → سفارش فروش فعال می‌شود.
- **Failed bear signal**: قرینه (high سیگنال قبل از تریگر فروش گرفته می‌شود).
- اختیاری هم‌زمان: دو سفارش stop دو طرف سیگنال؛ طرف اول پر شود، طرف دیگر لغو.

**ورود قدم‌به‌قدم (فروش بعد از failed bull signal)**
1. سیگنال‌بار صعودی شناسایی کن.
2. هم‌زمان: buy stop یک تیک بالای high آن؛ sell stop یک تیک زیر low آن.
3. اگر sell stop اول پر شد → ورود شورت (تلهٔ لانگ‌ها).
4. buy stop را فوراً لغو کن.

**خرید بعد از failed bear signal**: قرینه.

**SL**
- یک تیک آن‌سوی extreme سیگنال‌بار (برای شورت: بالای high سیگنال).
- فیلتر: اگر `abs(entry − stop) > 8` → رد یا فقط سیگنال‌بارهایی با دامنه ≤۸$.

**TP**
- منبع برای اسکالپ Emini «four ticks» می‌گوید — برای طلا قابل‌نقل به‌عنوان عدد ثابت نیست.
- پیشنهاد کد: حداقل ۱R؛ در ریورسال قوی/احتمال HOD/LOD بخشی را به ۲R/TBTL بسپار (منطق صفحه برای swing).

**فیلترها**
- سیگنال خیلی ضعیف (دم بزرگ خلاف جهت، close وسط) را نادیده بگیر یا سایز کوچک.
- در میکروکانال خیلی قوی هم‌جهت سیگنال اول، شکست خلاف ممکن است فقط یک تیک trap باشد و دوباره ادامه دهد — صبر برای تأیید بیشتر (مثلاً close entry bar نزدیک extreme).

**آمار بک‌تست**
- صفحه فقط برای Emini می‌گوید «typically… 10 to 20 set ups per day» روی ۵م — **نه** winrate و **نه** XAUUSD.
- **source gives no stats** برای این سیستم روی طلا.

---

## ۲) Fakey (False Break of Inside Bar) | منبع: Nial Fuller

**نام و منبع**
- نام: Fakey pattern = false-breakout از ساختار Inside Bar
- مقالهٔ اصلی: https://www.learntotradethemarket.com/forex-trading-strategies/what-is-fakey-pattern — تأیید شد (WebFetch 2026-10-30).
  - تعریف: «a fakey is when price initially breaks one way from an inside bar pattern but then price snaps back the other direction, creating a false break of the inside bar structure.»
  - معنا: استاپ‌ران خرده‌فروش یا واکنش به رویداد بزرگ؛ جهت محتمل = مخالف false-break.
  - واریانت‌ها: false-break دو باره؛ یا pin bar به‌عنوان false-break یک‌باره؛ سه باره نادرتر و کمتر ایده‌آل.
  - چند inside پشت‌سرهم قبل از false-break مجاز است.
  - ورود و SL: در مثال‌ها، stop «just below the lowest point of the two-bar false-break» برای خرید؛ ورود پس از شکل‌گیری واضح false-break (منبع می‌گوید بهترین Fakeyها «dead obvious»اند).
  - زمینه: ترند، رنج، یا خلاف ترند روی S/R کلیدی؛ نه در بازار choppy.

**تفاوت با Inside Bar دسته ۲ و ردشده‌ها**
- Inside Bar دسته ۲ = breakout هم‌جهت مادر با فیلتر ارتفاع. Fakey = **شکست اولیهٔ مادر fail می‌شود** و ورود در جهت مخالف.
- با ii Breakout Mode فرق دارد: ii دو طرفهٔ BOM است بدون نیاز به false-break؛ Fakey صریحاً false-break می‌خواهد.
- Casper/اندیکاتور/Gartley نیست.

**تایم‌فریم**
- Fuller در کامنت‌ها/مقاله TF اجباری نگذاشته؛ برای SL≤۸$: M5 یا M15 با `mother_range` و ارتفاع false-break کوچک.
- روی M1 نویز زیاد — فقط با فیلتر سطح کلیدی و ارتفاع ≤۸.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30 (فیلتر عملیاتی).

**تعاریف کد**
- Mother + Inside(ها) طبق تعریف سخت Fuller یا نرم Brooks (مثل دسته ۲).
- **Bullish Fakey**: قیمت ابتدا زیر `low[mother]` (یا low مجموعهٔ insideها) می‌شکند (wick یا close موقت)، سپس به داخل برمی‌گردد و از `high[mother]` عبور/کلوز می‌کند (یا سیگنال‌بار صعودی قوی بعد از snap-back).
- **Bearish Fakey**: قرینه بالای high مادر.
- `false_break_extreme` = پایین‌ترین low (خرید) یا بالاترین high (فروش) در پای false-break.
- فیلتر وضوح: false-break باید حداقل `eps` دلار آن‌سوی مادر باشد (پیشنهاد eps = 0.30–1.00؛ پارامتر چون منبع عدد طلا نداده).

**ورود قدم‌به‌قدم (خرید bullish Fakey)**
1. Mother + حداقل یک inside تشکیل شود.
2. شکست کاذب زیر low مادر (false-break) ثبت شود.
3. قیمت به داخل مادر برگردد.
4. گزینهٔ A (تهاجمی): buy stop یک تیک بالای high مادر پس از snap-back.
5. گزینهٔ B: صبر برای سیگنال‌بار صعودی (مثلاً pin یا engulf) بعد از false-break → buy stop بالای high آن.
6. اگر قبل از ورود، قیمت دوباره زیر `false_break_extreme` برود و بماند → باطل.

**فروش**: قرینه.

**SL**
- «just below the lowest point of the … false-break» (نقل منطق مقاله برای خرید).
- فیلتر: فاصله تا extreme ≤۸$؛ وگرنه رد.

**TP**
- منبع عدد ثابت نمی‌دهد؛ می‌گوید حرکت در جهت مخالف false-break.
- کد: ۱R و ۲R؛ یا لبهٔ مخالف رنج/سطح بعدی.

**فیلترها**
- بازار choppy → رد (صریح Fuller).
- اگر false-break «واضح» نیست (باید حدس بزنی) → رد.
- confluence: ترند + S/R یا کف/سقف رنج ترجیح داده شود.

**آمار بک‌تست**
- **source gives no stats** کمی (winrate/R:R عددی در مقاله نیست).

---

## ۳) PDH/PDL Raid + Reclaim کلوز M5 (بدون MSS/FVG اجباری) | منبع: ICT Turtle Soup / LSG Club

**نام و منبع**
- نام این نسخهٔ کدپذیر: `PDH_PDL_M5_Reclaim` (زیرمجموعهٔ ICT Turtle Soup روی سقف/کف روز قبل)
- راهنمای ساختاری: https://lsgclub.trade/blog/ict-turtle-soup-pattern — تأیید شد (WebFetch 2026-10-30).
  - PDH/PDL «the most common Turtle Soup level for intraday traders».
  - سه جزء: context (bias)، raid، confirmation.
  - Confirmation: «The raid candle, or the next one, closes back inside the range.»
  - ورود تهاجمی: «on the close back inside»؛ محافظه‌کارانه: بعد از MSS + FVG (این بخش عمداً در نسخهٔ ما **اختیاری** است تا از ردشده فاصله بگیرد).
  - SL فراتر از extreme raid؛ هدف سمت مخالف رنج / نقدینگی بعدی.
  - Kill Zones مثال: London 02:00–05:00 یا NY AM 07:00–10:00 به وقت نیویورک.
- مکمل تعریف: https://www.ictkillzone.com/ict-turtle-soup — تأیید شد؛ تأکید روی body close برگشتی داخل رنج؛ هشدار می‌دهد نسخهٔ کامل ICT اغلب MSS+FVG می‌خواهد — ما صریحاً نسخهٔ **aggressive close-back** ال‌اس‌جی را کد می‌کنیم.

**تفاوت صریح با ستاپ ردشدهٔ «LiqSweep+MSS+FVG»**
1. سطح اجباری = **فقط PDH یا PDL** (نه هر سوینگ دلخواه).
2. تأیید اصلی = **کلوز M5 برگشتی به داخل دامنهٔ روز قبل** (close back inside) — نه الزام MSS.
3. **FVG اجباری نیست**؛ ورود روی close reclaim یا stop-entry روی سیگنال‌بار M5 هم‌جهت بلافاصله بعد از reclaim.
4. اگر بعداً MSS+FVG دیدی می‌توانی به‌عنوان فیلتر اختیاری اضافه کنی؛ ولی هستهٔ سیگنال این دسته بدون آن‌ها کامل است.

**تفاوت با Judas دسته ۱**
- Judas مرجع midnight open + quiet range 00:00–02:00 NY است؛ اینجا مرجع **PDH/PDL تقویم روز قبل** است و محدود به پنجرهٔ midnight نیست.

**تایم‌فریم**
- علامت سطح: Daily (PDH/PDL).
- Raid و reclaim: M5 (طبق اولویت درخواست؛ LSG نیز M5–M15 برای تایمینگ می‌گوید).

**سشن**
| پنجره | NY time | UTC (EDT) | تهران |
|---|---|---|---|
| London KZ (مثال LSG) | 02:00–05:00 | 06:00–09:00 | 09:30–12:30 |
| NY AM KZ (مثال LSG) | 07:00–10:00 | 11:00–14:00 | 14:30–17:30 |

خارج از این‌ها فقط اگر پارامتر `allow_any_session=true`؛ پیش‌فرض false.

**تعاریف کد**
- `PDH` = highest high روز تقویمی قبل (جلسهٔ طلای همان روز معاملاتی قبلی).
- `PDL` = lowest low همان روز قبل.
- **Bearish PDH raid**: `high > PDH` سپس یک M5 با `close < PDH` (بازگشت داخل).
- **Bullish PDL raid**: `low < PDL` سپس M5 با `close > PDL`.
- `raid_extreme` = max high در پای عبور از PDH (فروش) یا min low در پای عبور از PDL (خرید).

**ورود قدم‌به‌قدم (فروش بعد از PDH raid)**
1. Bias روزانه/H4 نزولی یا draw روی نقدینگی پایین (پارامتر جدا؛ LSG بدون bias نمی‌خواهد fade کند).
2. در Kill Zone: high از PDH عبور کند.
3. کندل M5 (همان یا بعدی) با `close < PDH` بسته شود → `reclaim_bear = true`.
4. ورود A: فروش market/limit روی همان close.
5. ورود B: sell stop یک تیک زیر low همان کندل reclaim یا سیگنال‌بار نزولی بعدی.
6. اگر قبل از ورود، `close > raid_extreme` → breakout واقعی؛ لغو.

**خرید PDL**: قرینه.

**SL**
- فراتر از `raid_extreme` + بافر اسپرد (LSG).
- اگر فاصله >۸$ → رد برای چالش، یا سایز ریسک‌ثابت کوچک‌تر (LSG صریحاً ATR و سایز کوچک‌تر روی طلای پرنوسان را می‌گوید بدون عدد ثابت دلار).

**TP**
- تعادل رنج روز قبل (≈۵۰٪) به‌عنوان TP1؛ سمت مخالف / نقدینگی خارجی به‌عنوان TP2 (LSG).
- حداقل کد: ۱R و ۲R.

**فیلترها**
- LSG: روزهای ترند با displacement و کلوزهای متوالی آن‌سوی سطح → رد (breakout واقعی).
- خلاف HTF draw → رد.
- خبر سنگین → رد.
- سطحی که در همان سشن دو بار raid شده و «پاک» شده → ضعیف‌تر (LSG).

**آمار بک‌تست**
- هر دو منبع آموزشی‌اند؛ **source gives no stats** winrate/XAUUSD.

---

## ۴) Opening Reversal (ORV) — ریورسال ۹۰ دقیقهٔ اول | منبع: Al Brooks

**نام و منبع**
- نام: Opening Reversal
- صفحهٔ ۱۰ الگو: https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ — تأیید شد.
  - اجزا: «Usually fast move to a magnet (support or resistance)»؛ «Reversal in 1st 60 – 90 minutes that leads to a swing for the next few hours or the entire day».
  - مثال: فروش vacuum تست yesterday’s low سپس رالی بقیهٔ روز؛ یا gap up و برگشت به EMA سپس wedge bull flag.
- PDF Patterns on the Open (futures.io 2018-10-30): https://www.brookstradingcourse.com/wp-content/uploads/2018/10/181030-futuresio-Patterns-on-the-Open-Al-Brooks.pdf — تأیید شد.
  - نقل اسلاید: «80% of days have reversal on open (1st 90 min)»؛ «Trends From The Open: 20% of days».
  - «BO on Open: 50% Reverse, No Matter How Strong».
  - ریورسال اغلب DT/DB/Wedge در تست yesterday H/L یا EMA.
  - ورود: stop بالای bull bar با close نزدیک high / زیر bear bar با close نزدیک low؛ SL آن‌سوی extreme ریورسال یا HL/LH اصلی.
  - مثال صریح اسلاید: «B 2nd failed BO below yesterday’s low»؛ «Failed BO above yesterday’s high» + L2.

**تفاوت با ردشده‌ها و Judas/PDH**
- NY ORB نیست: اینجا بازهٔ ثابت جعبه‌ای برای breakout نیست؛ **ریورسال از تست مگنت** در ۹۰ دقیقهٔ اول است.
- با PDH/PDL #۳: آنجا raid+reclaim سطح روز قبل در هر Kill Zone؛ اینجا تمرکز روی **الگوی باز شدن سشن** (غالباً رنج/گپ نسبت به دیروز و EMA) و ترجیح Brooks برای **دومین شکست ناموفق** yesterday H/L.
- LiqSweep+MSS+FVG نیست.

**تایم‌فریم**
- تشخیص باز: M5 (هم‌راستا با روتین Brooks).
- اجرا: M5/M1 با ریسک ≤۸.

**سشن (نقشه برای طلا — همپوشانی لندن/NY)**
- «۹۰ دقیقهٔ اول» را برای طلا دو پنجرهٔ عملیاتی تعریف کن (منبع بازار فیوچرز آمریکاست؛ برای XAUUSD پارامتر):
  - باز لندن: UTC 07:00–08:30 / تهران 10:30–12:00
  - باز نیویورک: UTC 12:00–13:30 / تهران 15:30–17:00
- فقط یکی را در بک‌تست فعال کن یا هر دو را جدا تگ بزن.

**تعاریف کد**
- `Y_high` / `Y_low` = high/low روز قبل.
- `open_window` = ۹۰ دقیقهٔ اول سشن انتخابی.
- **Sell climax ORV (خرید)**: در پنجره، حرکت سریع به سمت/زیر `Y_low` (یا مگنت دیگر)، سپس سیگنال‌بار صعودی؛ ترجیحاً **دومین** failed BO زیر `Y_low` (طبق اسلایدهای PDF).
- **Buy climax ORV (فروش)**: قرینه بالای `Y_high`.
- مگنت‌های مجاز: Y_high، Y_low، EMA20 همان TF، کف/سقف گپ روزانه.

**ورود قدم‌به‌قدم (خرید — 2nd failed BO زیر Y_low)**
1. در open_window، یک بار `low < Y_low` و برگشت به داخل را ببین (first failed BO).
2. بار دوم نزدیک/زیر `Y_low` با برگشت → سیگنال‌بار صعودی با close نزدیک high.
3. Buy stop یک تیک بالای high سیگنال‌بار.
4. اگر تا پایان open_window + ۳۰ دقیقه (پارامتر) تریگر نشد → لغو.

**فروش 2nd failed BO بالای Y_high**: قرینه.

**SL**
- زیر پایین‌ترین low کل پای ریورسال (نه فقط سیگنال اگر HL قبلی پایین‌تر است) — نقل PDF.
- فیلتر ≤۸$؛ روی طلا اغلب باید سیگنال‌بار دوم/میکرو باشد.

**TP**
- سوئینگ چند ساعته یا بقیهٔ روز (کیفی صفحه)؛ کد: ۲R حداقل برای swing؛ یا تست open روز / میانهٔ رنج.

**فیلترها**
- اگر بعد از ریورسال اول، Always-In قوی خلاف ادامه داد و دومین تست نیامد → ممکن است Trend From The Open (۲۰٪ روزها) باشد؛ fade نکن.
- مبتدیان: ۱–۳ ترید سوئینگ در روز (PDF).

**آمار بک‌تست (فقط آنچه منبع می‌گوید — نه winrate سیستم طلا)**
- PDF: حدود ۸۰٪ روزها ریورسال در ۹۰ دقیقهٔ اول؛ حدود ۲۰٪ Trend From The Open؛ حدود ۵۰٪ حتی BO قوی باز برمی‌گردد.
- این‌ها فراوانی الگو روی چارچوب Brooks/فیوچرزند، **نه** expectancy بک‌تست‌شده روی XAUUSD.
- Winrate اختصاصی این پکیج روی طلا: **source gives no stats**.

---

## ۵) Breaker Block (با Sweep اجباری) | منبع: DT Terminal / ICT

**نام و منبع**
- نام: Breaker Block (failed order block **بعد از** liquidity sweep)
- درس DT Academy: https://www.thedtterminal.com/academy/ict-breaker-and-mitigation-blocks — تأیید شد (WebFetch 2026-10-30).
  - شکست بلوک = body close فراتر از distal (زیر low بلوک صعودی / بالای high بلوک نزولی).
  - **Breaker**: «sweeps the old low, then closes above the block» (حالت صعودی)؛ قرینه برای نزولی.
  - **Mitigation**: «a higher low, no sweep, then closes above the block».
  - یک سؤال: آیا failing swing extreme قدیمی را گرفت؟ بله → breaker؛ خیر → mitigation؛ بدون body close → هیچ‌کدام.
  - استفاده: ری‌تست در جهت شکست؛ «Entry, stop and target are your own written rule».
  - «No peer-reviewed study tests breakers or mitigation blocks.»

**تفاوت صریح با Mitigation (دسته ۲ #۴)**
| | Breaker (اینجا) | Mitigation (دسته ۲) |
|---|---|---|
| قبل از شکست بلوک | **Sweep** extreme قدیمی (SSL/BSL) | Failure swing؛ **بدون** sweep |
| شکست | Body close + displacement از بلوک | همان |
| ری‌تست | در جهت شکست | همان |

**تفاوت صریح با ردشدهٔ «LiqSweep+MSS+FVG»**
1. شیء معاملاتی = **کندل/زون order block شکسته‌شده** پس از sweep؛ نه الزام دنبالهٔ MSS+FVG به‌عنوان تریگر.
2. ورود این نسخه = ری‌تست زون breaker + سیگنال‌بار PA روی M5/M1؛ FVG اگر هم‌پوشانی داشت اختیاری است، اجباری نیست.
3. بدون body close از distal، حتی با sweep، breaker تشکیل نشده (نقل DT: «Sweep, no break → nothing to flip»).

**تایم‌فریم**
- شناسایی بلوک و sweep: M15 یا M5.
- اجرا/ری‌تست: M5 یا M1 برای رسیدن به ریسک ≤۸$.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30 (فیلتر عملیاتی؛ DT سشن اجباری روی این صفحه نگذاشته).

**تعاریف کد**
- **Bearish OB (نامزد breaker صعودی)**: آخرین up-close قبل از سوینگ‌لاوی که بعداً جارو می‌شود (منطق DT: «last up-close candle(s) before that low»).
- **Bullish breaker**:
  1. `sweep`: `low < old_swing_low` (SSL گرفته شد).
  2. سپس displacement و `close > distal` بلوک نزولی قبلی (یا عبور از prior swing high با body — طبق شرح درس).
  3. زون breaker = همان کندل(های) up-close قبل از low جاروشده؛ از این به بعد به‌عنوان support روی ری‌تست.
- **Bearish breaker**: قرینه (HH جارو سپس close زیر بلوک).
- Displacement: حداقل یک کندل با body بزرگ؛ پارامتر `body >= k * ATR` چون منبع عدد ثابت نداده.

**ورود قدم‌به‌قدم (خرید — bullish breaker)**
1. شرایط ۱–۲ بالا → پرچم `breaker_bull = true` و ذخیرهٔ `[proximal, distal]` زون.
2. منتظر برگشت قیمت به داخل زون باش.
3. روی M5: سیگنال‌بار صعودی با close نزدیک high داخل/روی زون → buy stop یک تیک بالای high آن.
4. اگر قبل از ورود body دوباره زیر distal برود → invalidation زون؛ لغو.

**فروش**: قرینه.

**SL**
- آن‌سوی distal زون (+ بافر). DT می‌گوید قانون stop را خودت بنویس.
- فیلتر: فقط وقتی ریسک ≤۸$؛ وگرنه فقط زون‌های کوچک روی M5/M1.

**TP**
- نقدینگی سوینگ بعدی در جهت شکست؛ یا ۱R/۲R.
- منبع هدف عددی نمی‌دهد.

**فیلترها**
- اگر sweep نبود → این ستاپ را نزن (برو Mitigation دسته ۲).
- اگر فقط sweep بود و body از بلوک نگذشت → هنوز breaker نیست.
- هم‌راستایی با HTF bias ترجیحی (پارامتر).

**آمار بک‌تست**
- DT صریحاً: هیچ مطالعهٔ peer-reviewed؛ **source gives no stats**. مثال‌های EURUSD/XAUUSD شماتیک آموزشی‌اند.

---

## پیوست — یافته‌های کمی منتشرشده دربارهٔ طلای اینترادی (فقط نقل تحت‌اللفظی چکیده)

> هیچ‌کدام از این مقالات ستاپ‌های PA/ICT بالا را تست نکرده‌اند. فقط برای زمینهٔ کمی طلا/فلزات گرانبها اینترادی نقل می‌شوند. عدد خارج از چکیدهٔ تأییدشده اضافه نشده.

### A) Batten, Lucey, McGroarty, Peat, Urquhart (2018)
- عنوان: Does intraday technical trading have predictive power in precious metal markets?
- لینک چکیده: https://ideas.repec.org/a/eee/intfin/v52y2018icp102-113.html — تأیید شد.
- DOI: 10.1016/j.intfin.2017.06.005
- نقل چکیده: با پارامترهای استاندارد ادبیات، قوانین MA اینترادی «offer no predictive power whatsoever». پس از جستجوی جهان پارامترها، «a number of parameter combinations offer significant predictability in the gold market, but there remains no significant predictability in the silver market». «the longer parameters of the technical trading rules are more successful than the traditional parameters». نتیجهٔ چکیده: «intraday technical trading rules have some predictive power in the gold market but offer no significant predictability in the silver market.»
- **توجه:** این دربارهٔ قوانین میانگین متحرک است، نه Fakey/Breaker/ORV.

### B) Jin, Xiaoye (2022)
- عنوان: Performance of intraday technical trading in China’s gold market
- لینک: https://ideas.repec.org/a/eee/intfin/v76y2022ics1042443121001876.html — تأیید شد.
- DOI: 10.1016/j.intfin.2021.101481
- دادهٔ ذکرشده در چکیده: ۵دقیقه‌ای، فعال‌ترین قرارداد فیوچرز طلای Shanghai Futures Exchange، ۱۲ مارس ۲۰۱۸ تا ۱۰ مارس ۲۰۲۱.
- نقل چکیده: پس از درنظرگرفتن data snooping، هزینهٔ معامله، شرایط بازار و فرکانس rebalancing، «investors are unlikely to choose technical trading rules that persistently yield attractive out-of-sample performance, indicating that the predictive power of intraday technical trading in China’s gold market is illusory.»

### C) Gil Cohen (2022)
- عنوان: Intraday Trading of Precious Metals Futures Using Algorithmic Systems
- لینک: https://ideas.repec.org/a/eee/chsofr/v154y2022ics0960077921010304.html — تأیید شد.
- DOI: 10.1016/j.chaos.2021.111676
- دادهٔ چکیده: ابتدای ۲۰۲۰ تا پایان سپتامبر ۲۰۲۱؛ بهینه‌سازی PSO روی RSI و Keltner Channels.
- نقل تحت‌اللفظی آمار چکیده برای طلا:
  - سیستم RSI: «delivered 106.2% … excess returns for Gold» (همچنین اعداد جدا برای Silver/Platinum/Palladium در همان جمله).
  - سیستم KC: «Sixty minutes bars with 1.5 Average True rang Multiplier (MATR) have been found to be a fruitful configuration for the KC system trading Gold … providing better trading returns than the B&H strategy, by 64.72% …»
- **توجه برای رایان:** این excess return روی سیستم‌های RSI/KC بهینه‌شده با PSO است — **نه** روی ستاپ‌های PA/ICT این دسته؛ و جزئیات هزینه/OOS کامل در چکیده نیست. فقط به‌عنوان منبع کمی عمومی طلای اینترادی ثبت شد.

### D) Zhang, Wang, Li (2020) — مومنتوم اینترادی کالاهای چین (شامل بستر طلا در بازار کالا)
- عنوان: Intraday momentum in Chinese commodity futures markets
- لینک: https://ideas.repec.org/a/eee/riibaf/v54y2020ics0275531919311328.html — تأیید شد.
- DOI: 10.1016/j.ribaf.2020.101278
- نقل چکیده: ایندکس وزن‌دار open-interest همهٔ فیوچرز کالا؛ «the first half-hour return can readily predict the last half-hour return» در آزمون‌های in-sample و out-of-sample؛ شدت با نوسان/حجم/اندازهٔ معامله و نوع کالا و آغاز night trading تغییر می‌کند؛ «economic significance» و مقاومت به وزن‌دهی جایگزین ادعا شده.
- چکیده عدد winrate/% جدا برای قرارداد طلای تکی نمی‌دهد → عدد طلای جدا نقل نمی‌شود.

### آنچه پیدا نشد / قابل‌نقل نبود
- مقالهٔ نیم‌ساعتهٔ GLD روی PMC (مثلاً PMC7480318): WebFetch با 403 مسدود شد → بدنه نقل نشد.
- هیچ بک‌تست عمومی peer-reviewed با winrate مشخص برای Fakey / Breaker / Turtle Soup / ORV روی XAUUSD M1–M15 در منابع این نوبت یافت و تأیید نشد.

---

## جمع‌بندی دسته ۳

| # | ستاپ | فرکانس کیفی | مناسب ≤۸$ |
|---|---|---|---|
| 1 | Failed signal-bar trap | زیاد روی M5 | بله با فیلتر دامنه سیگنال |
| 2 | Fakey | متوسط–زیاد | بله اگر false-break فشرده باشد |
| 3 | PDH/PDL + M5 reclaim | ۰–چند بار در روز | فقط اگر raid نزدیک سطح بماند |
| 4 | Opening Reversal (2nd fail Y H/L) | معمولاً ۰–۲ در باز سشن | بله روی سیگنال‌بار دوم/میکرو |
| 5 | Breaker Block (+sweep) | متوسط | فقط زون کوچک / M5–M1 |

---

## لیست کاندید به‌روز (بعد از دسته ۱–۳)

### ارسال‌شده به رایان
**دسته ۱:** H2/L2؛ Breakout Pullback؛ Final Flag fail؛ Wedge/MW؛ Judas M15 reclaim  
**دسته ۲:** MDB/MDT؛ Inside Bar (mother≤۸)؛ ii BOM؛ Mitigation (no sweep)؛ TR extreme + 2nd signal  
**دسته ۳ (همین فایل):** Failed signal trap؛ Fakey؛ PDH/PDL M5 reclaim؛ Opening Reversal؛ Breaker (+sweep)

### ردشده (تکرار نکن مگر نسخهٔ قاعدتاً متفاوت)
Silver Bullet ساده؛ LiqSweep+MSS+FVG؛ fib OTE+FVG؛ NY ORB؛ Casper یک‌کندلی؛ Supertrend؛ Ichimoku؛ TEMA؛ Gartley

### کاندیدهای باقی‌مانده برای دسته‌های بعدی (اولویت پیشنهادی)
1. **Major Trend Reversal (MTR) / HH یا LL MTR** — Brooks؛ ورود زودهنگام ~۴۰٪ احتمال سوئینگ (نقل صفحهٔ ۱۰ الگو).
2. **Climax / Exhaustion bar + 2nd entry** — مرتبط با ORV ولی خارج پنجرهٔ باز.
3. **Equal Highs/Lows raid (نه فقط PDH/PDL)** — Turtle Soup روی EQH/EQL.
4. **Asian range high/low raid در لندن** — زیرمجموعهٔ Turtle Soup.
5. **Breakout Mode روی TTR / Tight Trading Range** — Brooks BOM خارج از ii.
6. **Measured Move pullback entry** — Brooks؛ ورود روی برگشت به نقطهٔ BO.
7. **EMA20 gap-pullback Opening continuation** — وقتی ORV fail می‌شود و ترند از باز ادامه می‌دهد (۲۰٪ روزها).
8. **Order Block خام + ری‌تست (قبل از fail)** — متفاوت از Breaker/Mitigation؛ فقط اگر رایان OB غیرشکسته‌شده را نخواسته رد کند.
9. **Propulsion block / rejection block** — فقط با منبع ICT عمومی تأییدشدنی.
10. **Session VWAP deviation fade** — اگر منبع PA/کمی معتبر پیدا شود (فعلاً نیازمند منبع).
11. **Liquidity void / imbalance fill بدون MSS اجباری** — نسخهٔ متمایز از FVG ردشده.
12. **Double Bottom/Top کامل (نه میکرو) روی M15 با گردن ≤۸$** — مکمل MDB.

### ایده‌های کم‌اولویت / احتیاط
- هر سیستم اندیکاتوری خالص (RSI/KC مثل Cohen) — با چالش «Price Action / ICT» هم‌راستا نیست مگر رایان صراحتاً بخواهد.
- الگوی هارمونیک دیگر (Bat/Butterfly) — مشابه Gartley ردشده.
- Supply/Demand کلاسیک بدون تعریف کندلی دقیق — ابهام کدنویسی.

---

لینک‌های اصلی این فایل در نوبت تهیه با WebFetch باز و تأیید شدند (Marketalyx sweep به‌خاطر 504 در این نوبت استفاده نشد؛ به‌جایش LSG + ictkillzone).
