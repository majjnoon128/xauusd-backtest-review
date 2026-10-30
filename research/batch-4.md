# دسته ۴ — ستاپ‌های قابل‌کدنویسی XAUUSD (M1–M15)
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | ادامهٔ تحقیق | هدف: چالش پراپ SGB ۱۰۰۰ دلاری

قواعد مشترک (مثل دسته ۱–۳):
- فقط قوانین منبع؛ هیچ عدد بک‌تستی اختراع نشده.
- فیلتر پراپ پیشنهادی: `signal_risk_USD <= 8` مگر منبع SL وسیع‌تری بگوید.
- زمان‌ها: UTC و تهران (UTC+3:30). اکتبر ۲۰۲۶: NY هنوز EDT = UTC−4.
- هیچ ستاپی از دسته ۱–۳ تکرار نشده.
- ستاپ‌های ردشدهٔ قبلی تکرار نمی‌شوند مگر نسخهٔ قاعدتاً متفاوت با توضیح تفاوت.

اولویت این دسته (از بالای لیست کاندید باقی‌مانده): MTR، Climax+2nd entry، EQH/EQL raid، Asian-range raid در لندن، TTR Breakout Mode.

**هشدار صداقت (پایین فایل کامل‌تر است):** پس از این دسته، کاندیدهای PA/ICT واقعاً متمایز، قابل‌کدنویسی، و مناسب SL≈۸$ + چند سیگنال/روز به‌طور محسوس کم می‌شوند. این پنج مورد هنوز قابل دفاع‌اند؛ پد کردن با ستاپ مبهم توصیه نمی‌شود.

---

## ۱) Major Trend Reversal (MTR) — ترجیح LH/HL + سیگنال دوم | منبع: Al Brooks

**نام و منبع**
- نام: `MTR` = Major Trend Reversal (HH MTR / LH MTR / LL MTR / HL MTR)
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `MTR = Major Trend Reversal`؛ همچنین `MRV = Minor Trend Reversal`.
- صفحهٔ ۱۰ الگو: https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ — اجزا: Trend → Pullback که کانال را می‌شکند → Resumption → 2nd pullback که به ترند مخالف تبدیل می‌شود. احتمال سوئینگ ورود زودهنگام معمولاً فقط حدود ۴۰٪.
- PDF Coaching Session #3 MTRs: https://www.brookstradingcourse.com/wp-content/uploads/2025/08/250830-Coaching-Session-3-MTRs.pdf — تأیید شد (WebFetch 2026-10-30).
  - MTR Top: ریورسال نزولی که زیر bull trend line می‌شکند ولی فقط PB می‌شود؛ سپس resumption نزدیک old high fail می‌شود؛ **2nd reversal down** معمولاً با strong bear BO → ترند نزولی.
  - MTR Bottom: قرینه؛ تست باید حداقل ~۳۳٪ PB به سمت low باشد.
  - «Entering after strong breakout, has 60% probability of swing»؛ «Selling before strong bear BO has 40% chance of swing profit».
  - «Frequent (usually about one/day)» روی چارچوب آموزشی؛ Reward حداقل ۲× risk؛ ورود: sell ۱ pip زیر low سیگنال‌بار / buy ۱ pip بالای high.
  - LH MTR اغلب بعد از HH MTR می‌آید و setup فروش بهتری است.

**تفاوت با ردشده‌ها و دستهٔ قبلی**
- با Opening Reversal (دسته ۳): ORV محدود به ۹۰ دقیقهٔ اول سشن و مگنت باز است؛ MTR ساختار چندمرحله‌ای ترند+شکست خط‌روند+تست+ریورسال دوم در هر ساعتی است.
- با TR extreme + 2nd signal (دسته ۲): آنجا زمینهٔ روز/فاز TR است؛ اینجا **خروج از ترند به ترند مخالف** (یا حداقل سوئینگ بزرگ) هدف است.
- با Final Flag (دسته ۱): FF پرچم دیر در ترند است؛ MTR صریحاً شکست خط‌روند + تست extreme + ریورسال دوم می‌خواهد.
- LiqSweep+MSS+FVG / Casper / اندیکاتور نیست.

**تایم‌فریم**
- تشخیص ساختار: M15 (یا M5 برای ترند کوتاه‌تر).
- اجرا: M5/M1 روی سیگنال‌بار با ریسک ≤۸$ (نسخهٔ زودهنگام تنگ‌تر؛ نسخهٔ بعد از BO قوی معمولاً SL دورتر → اغلب برای پراپ ۱۰۰۰ دلاری رد می‌شود مگر سایز کوچک).

**سشن**
- منبع محدود نکرده. پیشنهاد حجم طلا: UTC 07:00–16:00 / تهران 10:30–19:30.

**تعاریف کد**
- **Bull trend**: سری HH و HL در پنجرهٔ اخیر (پارامتر N سوینگ).
- **Bear trend**: سری LH و LL.
- **Bull trend line break (برای MTR Top)**: یک لگ نزولی که close زیر خط روند صعودی رسم‌شده روی دو HL اخیر می‌رود (یا زیر آخرین HL مهم — تقریب کدپذیر).
- **HH MTR sell setup**: بعد از شکست خط‌روند، قیمت دوباره نزدیک/بالای old high می‌آید (HH یا تست)، سپس سیگنال‌بار نزولی با close نزدیک low.
- **LH MTR sell setup (ترجیحی)**: بعد از HH MTR یا بعد از leg نزولی قوی، یک LH شکل می‌گیرد + سیگنال نزولی.
- **HL MTR / LL MTR buy**: قرینه.
- نسخهٔ کد این دسته برای پراپ: **فقط LH MTR فروش و HL MTR خرید** (احتمال/ساختار بهتر طبق PDF؛ SL معمولاً نزدیک‌تر از HH/LL کامل).

**ورود قدم‌به‌قدم (فروش LH MTR)**
1. ترند صعودی قبلی + حداقل یک شکست معنادار زیر bull trend line / به زیر MA20 را ثبت کن.
2. resumption صعودی که به LH نسبت به extreme قبلی ختم شود (نه لزوماً HH جدید).
3. سیگنال‌بار نزولی با close نزدیک low (ترجیحاً بعد از MDT کوچک).
4. Sell stop یک تیک/۱ پیپ زیر low سیگنال‌بار.
5. اگر تا K کندل تریگر نشد → لغو.

**خرید HL MTR**: قرینه.

**SL**
- بالای high سیگنال یا بالای LH extreme (برای فروش).
- فیلتر: فقط وقتی `stop − entry <= 8`؛ در غیر این صورت صبر برای سیگنال‌بار کوچک‌تر روی M1/M5 یا رد.
- نسخهٔ «بعد از strong BO» معمولاً stop دورتر است → برای SGB اغلب نامناسب؛ اگر گرفتی فقط با سایز ریسک‌ثابت.

**TP**
- حداقل ۲R (PDF: reward at least 2× risk).
- یا Measured Move از ارتفاع لگ ریورسال؛ یا TBTL.

**فیلترها**
- اگر فشار فروش/خرید در لگ ریورسال ضعیف است (PDF: معمولاً ۵–۱۰ بار برای Major) → به‌عنوان MRV/اسکالپ رفتار کن نه سوئینگ MTR.
- سیگنال داخل TTR خیلی فشرده → PDF می‌گوید احتمال پایین (~۴۰٪) حتی با سیگنال خوب؛ ترجیح صبر برای BO قوی یا رد برای چالش.

**آمار بک‌تست**
- فقط نقل منبع (نه XAUUSD): حدود ۴۰٪ سوئینگ قبل از BO قوی؛ حدود ۶۰٪ بعد از strong BO؛ معمولاً حدود یک بار در روز (چارچوب Brooks).
- **source gives no stats** winrate اختصاصی طلا.

---

## ۲) Buy/Sell Climax + Second Entry (خلاف جهت) | منبع: Al Brooks

**نام و منبع**
- نام: Climactic reversal / Exhaustion bar سپس **2nd entry** خلاف ترند قبلی
- اختصار: `BX` = Buy Climax؛ `SX` = Sell Climax؛ `EG` = Exhaustion Gap — https://www.brookstradingcourse.com/brooks-price-action-abbreviations/
- PDF Advanced Big Bar Techniques (CME 2018): https://www.brookstradingcourse.com/wp-content/uploads/2018/08/2018-July-20-CME-Advanced-Big-Bar-Techniques.pdf — تأیید شد.
  - Exhaustion: «Big BO late in trend — Probable exhaustion».
  - بزرگ‌ترین جفت bull bar دیر در ترند (>۲۰ بار): Exhaustion Gap؛ «60% chance of one more leg up after 1–3 bar pause» سپس «60% chance of test to below bottom of Buy Climax».
  - بزرگ‌ترین bear bar دیر در ترند: «60% chance of one more Sell Climax before reversal up».
  - بعد از Buy Climax: bulls ناامید → Micro Double Top → «2nd entry sell for at least test of bottom of Buy Climax».
  - در TR: huge surprise bar می‌تواند 2nd Leg Trap باشد (failed BO).
- Ask Al 2nd leg traps: https://www.brookstradingcourse.com/ask-al/advice-on-2nd-leg-traps/ — در زمینهٔ TR/کانال، BO بزرگ اغلب trap است نه measuring gap.
- اصل Second Entry (کتاب Trends، نقل عمومی O'Reilly/DOI): second entry تقریباً همیشه محتمل‌تر از first؛ اگر second entry قیمت بهتر از first بدهد مشکوک به تله است.

**تفاوت با ردشده‌ها و دستهٔ قبلی**
- با ORV (دسته ۳): اینجا **الزام پنجرهٔ باز** نیست؛ شرط = climax دیر در لگ/ترند + ورود روی سیگنال **دوم**.
- با Final Flag: FF الگوی پرچم افقی دیر است؛ اینجا شیء اصلی **میله(های) بزرگ climactic** است.
- با TR extreme 2nd signal: هم‌پوشانی مفهومی دارد ولی تریگر اینجا صریحاً تعریف climax (بزرگ‌ترین بار در ≥۲۰ بار / چند BTC متوالی) است نه فقط failed BO سقف TR.
- با Failed signal trap (دسته ۳): آنجا هر سیگنال‌باری که خلاف جهت بشکند؛ اینجا فقط بعد از زمینهٔ climax.

**تایم‌فریم**
- شناسایی climax: M5 (اصلی) یا M15.
- 2nd entry: M5/M1 با دامنهٔ سیگنال ≤۸$.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30.

**تعاریف کد**
- **Buy Climax (BX)**: در لگ صعودی، یک یا چند کندل با body بزرگ و close نزدیک high که `range` یا `body` آن‌ها ≥ percentile بالا نسبت به N کندل اخیر است (پیشنهاد: بزرگ‌ترین body در ۲۰+ کندل، یا ≥ k×ATR؛ k پارامتر چون منبع آستانهٔ دلاری طلا نداده).
- **Sell Climax (SX)**: قرینه.
- **Late in trend**: حداقل L کندل در جهت ترند قبل از climax (پیشنهاد L≥20 مطابق زبان PDF؛ یا Always-In پایدار).
- **First fade signal**: اولین سیگنال‌بار خلاف بعد از climax (اغلب MDT بعد از BX).
- **Second entry sell**: سیگنال نزولی بعدی ظرف M کندل (اغلب تست دوبارهٔ high climax یا MDT دوم) که high آن ≥ high سیگنال اول باشد یا بدتر نباشد (قانون «قیمت بهتر مشکوک است»).

**ورود قدم‌به‌قدم (فروش بعد از BX)**
1. BX دیر در لگ صعودی را علامت بزن؛ `climax_low` / `climax_high` را ذخیره کن.
2. سیگنال اول فروش را فقط علامت بزن (وارد نشو یا سایز خیلی کوچک — منبع ترجیح 2nd برای احتمال بالاتر).
3. سیگنال دوم: سیگنال‌بار نزولی با close نزدیک low → sell stop یک تیک زیر low آن.
4. هدف حداقلی: تست `climax_low` (نقل PDF).
5. اگر قبل از 2nd، قیمت با displacement قوی بالای climax ادامه داد و Always-In Long ماند → ممکن است measuring باشد نه exhaustion؛ ستاپ را باطل کن.

**خرید بعد از SX**: قرینه.

**SL**
- بالای extreme پای climax/سیگنال دوم (فروش).
- فیلتر ≤۸$؛ روی طلا اغلب فقط وقتی 2nd entry روی M1/M5 فشرده شکل بگیرد.

**TP**
- تست کف/سقف climax؛ سپس ۱R/۲R یا TBTL.
- PDF برای برخی surprise barها MM بر اساس body می‌گوید — به‌عنوان هدف اختیاری.

**فیلترها**
- Climax وسط ترند تازه (کمتر از ~۲۰ بار) → بیشتر measuring؛ fade نکن.
- در TR واضح، BO خیلی بزرگ را به‌عنوان 2nd leg trap در نظر بگیر (Ask Al) — همان منطق 2nd entry fade معتبر است.
- خبر سنگین هم‌زمان با big bar → رد.

**آمار بک‌تست**
- نقل PDF: حدود ۶۰٪ شانس یک لگ دیگر بعد از exhaustion قبل از برگشت؛ حدود ۶۰٪ شانس تست زیر کف buy climax — این‌ها احتمال‌های آموزشی Brooks‌اند نه بک‌تست XAUUSD.
- **source gives no stats** سیستم بسته روی طلا.

---

## ۳) EQH / EQL Raid + Reclaim M5 (بدون MSS/FVG اجباری) | منبع: ICT Turtle Soup / LSG + LuxAlgo concept

**نام و منبع**
- نام: `EQH_EQL_M5_Reclaim` — raid روی Equal Highs / Equal Lows
- LSG Turtle Soup: https://lsgclub.trade/blog/ict-turtle-soup-pattern — تأیید شد.
  - سطوح: «Relative equal highs or lows — two or more touches at nearly the same price».
  - Confirmation: raid candle یا بعدی close back inside؛ ورود تهاجمی روی همان close؛ MSS+FVG محافظه‌کارانه (در این نسخه اختیاری).
- SniperCharts checklist (آموزشی): https://snipercharts.com/learn/strategies/turtle-soup — EQH/EQL را در لیست سطوح معنادار می‌آورد؛ body باید داخل بسته شود.
- تعریف مفهومی equal as liquidity: https://www.luxalgo.com/library/concept/equal-highs-lows-as-liquidity/ — EQH = دو یا چند swing high تقریباً هم‌قیمت (BSL)؛ EQL قرینه (SSL)؛ «equal» معمولاً چند تیک/کسری از ATR است نه تیک دقیق.

**تفاوت صریح با PDH/PDL (دسته ۳ #۳)**
1. سطح = **بانک نقدینگی از ≥۲ تماس نسبتاً برابر**، نه الزاماً سقف/کف تقویم روز قبل.
2. PDH/PDL ممکن است فقط یک تماس داشته باشد؛ EQH/EQL بدون دو (یا بیشتر) touch واجد شرایط نیست.
3. همان قانون «بدون MSS/FVG اجباری» برای فاصله از ردشدهٔ LiqSweep+MSS+FVG حفظ می‌شود.

**تفاوت با MDB/MDT (دسته ۲)**
- MDB/MDT الگوی ۲–۴ کندلی میکرو برای ورود با روند/TR است؛ EQH/EQL می‌تواند روی ده‌ها کندل و چند سشن شکل بگیرد و تریگر = **raid فراتر از باند + reclaim** است نه عبور از neckline میکرو.

**تایم‌فریم**
- تشخیص EQH/EQL: M15 یا M5 (سوینگ‌ها).
- Raid/reclaim: M5.

**سشن**
- London 02:00–05:00 NY / UTC 06:00–09:00 / تهران 09:30–12:30
- یا NY AM 07:00–10:00 NY / UTC 11:00–14:00 / تهران 14:30–17:30
(LSG)

**تعاریف کد**
- Swing high محلی: high[i] > high در هر دو سمت w بار (w پیشنهاد ۲–۳).
- **EQH**: حداقل ۲ swing high با `|h1 − h2| <= tol` (tol پیشنهاد 0.5–1.5$ طلا یا 0.1×ATR؛ پارامتر).
- `eqh_level = max(h1, h2, …)` یا میانگین؛ `eqh_band_low = min(...)`.
- **Bearish EQH raid**: `high > eqh_level` سپس M5 با `close < eqh_band_low` (یا `< eqh_level` بسته به سخت‌گیری).
- **EQL**: قرینه برای خرید.
- حداقل lookback بین اولین و آخرین touch: ترجیحاً چند ده کندل؛ اگر هر دو touch در ۵ کندل باشند → به MDB/MDT نزدیک است و این ستاپ را نزن (تفکیک).

**ورود قدم‌به‌قدم (فروش EQH)**
1. Bias/HTF موافق fade سقف (LSG).
2. در Kill Zone: عبور از `eqh_level`.
3. M5 close برگشتی زیر سطح/باند → reclaim.
4. ورود A: فروش روی close؛ ورود B: sell stop زیر low کندل reclaim.
5. SL بالای `raid_extreme`.

**SL / TP / فیلترها**
- مثل منطق Turtle Soup دسته ۳: SL فراتر از extreme + بافر؛ TP تعادل رنج یا سمت مخالف EQ؛ فیلتر ≤۸$؛ ترند روز با کلوزهای متوالی آن‌سوی سطح → رد.

**آمار بک‌تست**
- **source gives no stats** برای XAUUSD.

---

## ۴) Asian Range High/Low Raid در London | منبع: ICT / LSG

**نام و منبع**
- نام: `Asian_H_L_London_Raid`
- LSG: https://lsgclub.trade/blog/ict-turtle-soup-pattern — «Asian range high and low — often raided during the London session.» Kill Zone لندن مثال: 02:00–05:00 NY.
- روایت رایج ICT (icttraders.net killzones — به‌عنوان منبع ثانویه برای ساعت‌ها): Asian consolidation → در لندن یک طرف range raid می‌شود → displacement به سمت مخالف. Asian Killzone مثال ۲۰:۰۰–۲۲:۰۰ NY؛ London 02:00–05:00 NY.
- SniperCharts: Asian H/L را سطح معتبر Turtle Soup می‌داند.

**تفاوت صریح با PDH/PDL و Judas و EQH**
| | این ستاپ | PDH/PDL #۳ | Judas #۱ | EQH/EQL #۳ همین دسته |
|---|---|---|---|---|
| سطح | High/Low **بازهٔ آسیا** همان روز | سقف/کف روز تقویمی قبل | midnight open + quiet 00–02 NY | دو+ تماس برابر |
| زمان raid | **فقط London KZ** | London یا NY AM | تا 05:00 NY با قانون midnight | London یا NY AM |
| تعریف range | پنجرهٔ ساعتی ثابت قبل از لندن | Daily | Quiet range نیمه‌شب | سوینگ‌های برابر |

**تایم‌فریم**
- ساخت Asian range: M5/M15.
- Raid + reclaim: M5.

**سشن (تعریف کدپذیر — منبع‌ها بازهٔ «Asian range» را همیشه دقیقه به دقیقه یکی نمی‌نویسند؛ این پارامتر صریح است)**
| جزء | NY time | UTC (EDT) | تهران |
|---|---|---|---|
| Asian range (پیشنهاد عملیاتی) | 19:00–02:00 | 23:00–06:00 | 02:30–09:30 |
| London raid window | 02:00–05:00 | 06:00–09:00 | 09:30–12:30 |

اگر رایان تعریف دیگری از Asian برای طلا بخواهد (مثلاً فقط Tokyo 00:00–07:00 JST)، فقط مرز ساعت عوض می‌شود؛ منطق raid یکسان است.

**تعاریف کد**
- در پنجرهٔ Asian: `ASH = max high`؛ `ASL = min low`؛ `asian_height = ASH − ASL`.
- فیلتر کیفیت: `asian_height` نه خیلی کوچک (نویز) نه نزدیک ADR کامل (خسته)؛ پیشنهاد نسبی: بین ۰.۱۵× و ۰.۶× ADR روزانه (پارامتر؛ LSG عدد ثابت نداده).
- **Bearish**: در London، `high > ASH` سپس M5 `close < ASH`.
- **Bullish**: `low < ASL` سپس M5 `close > ASL`.

**ورود قدم‌به‌قدم (خرید بعد از raid ASL)**
1. Bias صعودی یا draw روی نقدینگی بالا (LSG/ICT روایت لندن).
2. در 02:00–05:00 NY: low از ASL عبور کند.
3. M5 close بالای ASL → reclaim.
4. ورود روی close یا buy stop بالای high کندل reclaim.
5. SL زیر `raid_extreme`؛ اگر >۸$ → رد یا سایز کوچک.
6. TP1: میانهٔ Asian range؛ TP2: `ASH` یا نقدینگی خارجی بعدی.

**فروش raid ASH**: قرینه با bias نزولی.

**فیلترها**
- اگر Asian range هنوز در حال گسترش داخل London است و ASH/ASL قطعی نیست → صبر تا تثبیت (یا از high/low تا 02:00 به‌عنوان ثابت استفاده کن).
- Body close پایدار آن‌سوی سطح → breakout؛ لغو.
- هم‌زمانی با خبر لندن → رد.

**آمار بک‌تست**
- **source gives no stats**.

---

## ۵) Tight Trading Range (TTR) → Breakout Mode (ورود روی BO، نه اسکالپ داخل) | منبع: Al Brooks

**نام و منبع**
- نام: `TTR_BOM_Breakout` — فشردگی TTR سپس stop-entry روی شکست با هدف Measured Move
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/
  - `TTR = Tight Trading Range, limit order market, bad for scalping with stop orders. Most traders should wait`
  - `BOM = Breakout Mode means trading range. About 50% chance successful breakout up or down, and then about a measured move based on the height of trading range. 50% chance 1st breakout up or down will reverse`
- PDF Strong Legs: https://www.brookstradingcourse.com/wp-content/uploads/2016/05/Al-Brooks-Webinar-Distinguishing-Strong-Legs-TR-vs-Trends-May-3-2016.pdf — TTR = limit order market؛ «Wait for broader range or breakout»؛ برای اسکالپ داخل TTR معمولاً نباید با stop order وارد شد.
- فروم BOM vs TTR: https://www.brookstradingcourse.com/support-forum/general-trading-discussion/bom-vs-ttr/ — هر TTR افقی BOM است؛ اگر بازه خیلی تنگ با ۱۰+ بار بدون momentum باشد، شانس BO موفق روندساز کمتر و احتمال روز TR بیشتر است. ارتفاع مطلوب opening range حدود ۲۰–۳۰٪ ADR ذکر شده (برای open؛ به‌عنوان راهنمای کیفیت range قابل‌پارامتر است).

**تفاوت با ii BOM (دسته ۲ #۳)**
- `ii` = دقیقاً دو (یا بیشتر) **inside bar متوالی**.
- اینجا TTR = **چندباره (≥۶ پیشنهاد) فشردگی افقی**؛ نیازی به الگوی inside متوالی نیست (همپوشانی زیاد، دم، نبود trend barهای بزرگ).

**تفاوت با TR extreme + 2nd signal (دسته ۲ #۵)**
- آن ستاپ **fade** شکست ناموفق در سقف/کف TR است.
- این ستاپ **هم‌جهت BO** از TTR برای Measured Move است (قبول ریسک ۵۰/۵۰ اولین BO طبق BOM).

**تفاوت با BP دسته ۱**
- Breakout Pullback = صبر برای PB بعد از BO؛ اینجا ورود اولیه روی خودِ شکست TTR است (می‌توان BP را فیلتر اختیاری کرد).

**تایم‌فریم**
- تشخیص TTR: M5.
- اجرا: M5 (یا M1 اگر ارتفاع کل TTR ≤۸$).

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30.
- روی open: اگر TTR خیلی تنگ با ۱۰+ بار باشد، فروم می‌گوید شانس ترند کمتر است — فیلتر کیفیت.

**تعاریف کد**
- پنجرهٔ N کندل (پیشنهاد N=8…20).
- `tr_high = max high`؛ `tr_low = min low`؛ `h = tr_high − tr_low`.
- شرط TTR: `h <= max_ttr_height` و میانگین |close−open|/range پایین و تعداد برگشت‌ها زیاد / نبود ۲–۳ trend bar بزرگ متوالی (پارامترها؛ منبع آستانهٔ طلا نداده).
- **فیلتر پراپ کلیدی:** `h <= 8` تا بتوان SL آن‌سوی TTR گذاشت و ریسک ≤۸ باشد.
- اگر `h` خیلی کوچک‌تر از متوسط بار باشد → PDF می‌گوید حتی limit scalp سخت است؛ حداقل `h >= 2 × typical_bar` پیشنهاد عملیاتی.

**ورود قدم‌به‌قدم**
1. TTR با `h <= 8` شناسایی کن → حالت BOM.
2. هم‌زمان: buy stop یک تیک بالای `tr_high`؛ sell stop یک تیک زیر `tr_low`.
3. طرف اول پر شد → طرف دیگر را لغو کن.
4. اختیاری محافظه‌کارانه: فقط BO هم‌جهت Always-In/M15 bias را بگیر؛ یا صبر برای BP (دسته ۱) اگر می‌خواهی احتمال بالاتر و ورود دیرتر.
5. اگر اولین BO فوراً fail شد و برگشت داخل TTR → طبق BOM حدود ۵۰٪ مواقع؛ می‌توانی معکوس کنی فقط اگر قواعد TR extreme (دسته ۲) جداگانه فعال باشد — در این ستاپ پیش‌فرض = یک‌بار تلاش BO.

**SL**
- آن‌سوی لبهٔ مخالف TTR (برای لانگ: زیر `tr_low`).
- با `h <= 8` خودکار با فیلتر پراپ سازگار است.

**TP**
- Measured Move ≈ `h` فراتر از لبهٔ شکست (نقل BOM/صفحهٔ measured moves).
- یا ۱R/۲R؛ چون h کوچک است، ۲R ممکن است از MM بزرگ‌تر/کوچک‌تر باشد — هر دو را لاگ کن.

**فیلترها**
- داخل TTR با stop اسکالپ نکن (صریح TTR abbreviation + PDF).
- TTR با ۱۰+ بار بسیار مرده روی open → انتظار TR day بیشتر؛ سایز کوچک یا رد.
- خبر → رد.

**آمار بک‌تست**
- BOM: حدود ۵۰٪ شانس BO موفق هر طرف؛ حدود ۵۰٪ شانس fail اولین BO؛ سپس حدود MM به اندازهٔ ارتفاع range — نقل اختصار Brooks، نه بک‌تست طلا.
- **source gives no stats** XAUUSD.

---

## جمع‌بندی دسته ۴

| # | ستاپ | فرکانس کیفی | مناسب ≤۸$ |
|---|---|---|---|
| 1 | MTR (ترجیح LH/HL) | معمولاً ≤۱/روز روی TF بالاتر؛ روی M5 بیشتر | بله فقط روی سیگنال‌بار فشرده؛ بعد از strong BO اغلب خیر |
| 2 | Climax + 2nd entry | چند بار در هفته تا روزانه در بازار پرنوسان | بله روی 2nd entry کوچک |
| 3 | EQH/EQL M5 reclaim | متوسط (بستگی به تعداد EQ دارد) | فقط اگر raid نزدیک بماند |
| 4 | Asian H/L London raid | معمولاً ۰–۱ صبح | فقط اگر ارتفاع raid ≤۸ |
| 5 | TTR → BOM breakout | چند بار در روز وقتی فشردگی هست | بله با فیلتر `h<=8` |

---

## صداقت دربارهٔ اشباع کاندیدها

پس از دسته‌های ۱–۴، بخش عمدهٔ ستاپ‌های PA/ICT که هم‌زمان:
1) از منبع عمومی قابل‌استناد تعریف دقیق دارند،
2) از ردشده‌ها و از یکدیگر به‌اندازهٔ کافی متمایزند،
3) برای `signal_risk_USD <= 8` و چند سیگنال در روز روی طلا منطقی‌اند،

پوشش داده شده‌اند.

**باقی‌ماندهٔ لیست قبلی دیگر یا کم‌فرکانس‌اند، یا مبهم برای کد، یا با ردشده/قبلی هم‌پوشانی خطرناک دارند:**

| کاندید | وضعیت |
|---|---|
| Order Block خام + ری‌تست | قابل نوشتن، ولی به Mitigation/Breaker نزدیک است؛ فقط اگر رایان OB غیرشکسته بخواهد |
| Propulsion / Rejection block | منبع عمومی دقیق و یکدست کم؛ خطر پد |
| Session VWAP fade | نیاز به منبع PA/کمی معتبر جدا؛ فعلاً برای قالب این تحقیق ضعیف |
| Liquidity void / imbalance fill بدون MSS | خیلی نزدیک به FVG ردشده مگر تعریف کاملاً متفاوت تأیید شود |
| DB/DT کامل M15 با گردن ≤۸$ | مکمل MDB؛ متمایز اما کم‌فرکانس روی گردن ≤۸ |
| EMA20 gap-pullback continuation | زیرمجموعهٔ ORV fail / Trend From The Open؛ نیمه‌پوشش در دسته ۳–۴ |
| Measured Move PB entry | نزدیک BP دسته ۱ |
| PWH/PWL raid | همان خانوادهٔ Turtle Soup؛ متمایز از Asian/PDH/EQH ولی منطق تکراری |

**توصیه به رایان:** به‌جای دسته ۵ اجباری، بهتر است روی بک‌تست/کدنویسی ۱۵ ستاپ ارسال‌شده تمرکز شود؛ اگر دسته ۵ خواستید، حداکثر ۲–۳ مورد واقعاً متمایز (مثلاً OB خام، DB/DT کامل، PWH/PWL) بدون پد.

---

## لیست کاندید به‌روز (بعد از دسته ۱–۴)

### ارسال‌شده
**دسته ۱:** H2/L2؛ Breakout Pullback؛ Final Flag fail؛ Wedge/MW؛ Judas M15 reclaim  
**دسته ۲:** MDB/MDT؛ Inside Bar (mother≤۸)؛ ii BOM؛ Mitigation (no sweep)؛ TR extreme + 2nd signal  
**دسته ۳:** Failed signal trap؛ Fakey؛ PDH/PDL M5 reclaim؛ Opening Reversal؛ Breaker (+sweep)  
**دسته ۴ (همین فایل):** MTR (LH/HL)؛ Climax+2nd entry؛ EQH/EQL M5 reclaim؛ Asian H/L London raid؛ TTR→BOM breakout

### ردشده
Silver Bullet ساده؛ LiqSweep+MSS+FVG؛ fib OTE+FVG؛ NY ORB؛ Casper یک‌کندلی؛ Supertrend؛ Ichimoku؛ TEMA؛ Gartley

### باقی‌ماندهٔ نازک (فقط در صورت درخواست صریح دسته ۵)
1. Order Block خام + ری‌تست (غیرشکسته) — با تفاوت اجباری از Mitigation/Breaker
2. Double Bottom/Top کامل روی M15 با `neck_to_extreme <= 8`
3. PWH/PWL (prior week) raid + M5 reclaim — همان خانوادهٔ Turtle Soup، سطح هفتگی
4. (اختیاری ضعیف) Trend From The Open continuation بعد از failed ORV — ۲۰٪ روزها طبق Brooks

### خارج از محدودهٔ توصیه (پد نکن)
Propulsion/Rejection بدون منبع یکدست؛ VWAP fade بدون منبع؛ imbalance/FVG-like؛ هارمونیک‌ها؛ اندیکاتور خالص (RSI/KC)

---

لینک‌های اصلی این فایل با WebFetch در نوبت تهیه تأیید شدند (صفحهٔ ۱۰ الگو گاهی Cloudflare challenge می‌دهد؛ محتوای MTR از همان صفحه در نوبت‌های قبل + PDF Coaching MTR 2025 استخراج و استفاده شد).
