# دسته ۲ — ستاپ‌های قابل‌کدنویسی XAUUSD (M1–M15)
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | ادامهٔ تحقیق (بدون سقف ساعت ۱۰) | هدف: چالش پراپ SGB ۱۰۰۰ دلاری

قواعد مشترک (مثل دسته ۱):
- فقط قوانین منبع؛ هیچ عدد بک‌تستی اختراع نشده.
- فیلتر پراپ پیشنهادی: `signal_risk_USD <= 8` مگر منبع SL وسیع‌تری بگوید.
- زمان‌ها: UTC و تهران (UTC+3:30). اکتبر ۲۰۲۶: NY هنوز EDT = UTC−4.
- هیچ ستاپی از دسته ۱ تکرار نشده.
- ستاپ‌های ردشدهٔ قبلی (Silver Bullet ساده، LiqSweep+MSS+FVG، fib OTE+FVG، NY ORB، Casper یک‌کندلی، Supertrend، Ichimoku، TEMA، Gartley) تکرار نمی‌شوند مگر نسخهٔ قاعدتاً متفاوت با توضیح تفاوت.

اولویت این دسته: SL حدود ≤۸ دلار طلا + چند سیگنال در روز.

---

## ۱) Micro Double Bottom / Micro Double Top (MDB / MDT) | منبع: Al Brooks

**نام و منبع**
- نام: Micro Double Bottom (`MDB`) / Micro Double Top (`MDT`)
- اختصار رسمی: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `MDB = Micro Double Bottom`؛ `MDT = Micro Double Top`؛ همچنین `DB`/`DT` = دو کندل متوالی با low/high یکسان.
- تعریف عملی Brooks (ویدئو/متن ۵ قدم): https://www.brookstradingcourse.com/trading-strategies/5-steps-to-finding-todays-trades/ — تأیید شد. نقل: MDB طی ۲، ۳ یا ۴ کندل رخ می‌دهد؛ روی تایم‌فریم کوچک‌تر همان Double Bottom معمولی است. ورود: buy stop یک تیک بالای سیگنال‌بار صعودی با close نزدیک high؛ SL درست زیر همان بار؛ هدف حداقل ۲R.
- PDF Patterns on the Open (محل SL نسبت به ریورسال): https://www.brookstradingcourse.com/wp-content/uploads/2018/10/181030-futuresio-Patterns-on-the-Open-Al-Brooks.pdf
- تعریف گردن و ورود محافظه‌کارانه (ثانویه، هم‌راستا): https://www.priceactionindicators.com/indicators/support-and-resistance-double-bottom-top/ — stop entry یک تیک آن‌سوی neckline بین دو کف/سقف.

**تفاوت با ردشده‌ها**
- هیچ اندیکاتور trend-follow (Supertrend/Ichimoku/TEMA) نیست.
- Casper یک‌کندلی نیست؛ حداقل دو extreme محلی روی ۲–۴ کندل لازم است.
- Gartley/هارمونیک نیست.
- به LiqSweep+MSS+FVG وابسته نیست.

**تایم‌فریم**
- اجرا: M1 یا M5 (ارتفاع الگوی میکرو روی این تایم‌ها اغلب ≤۸ دلار است).
- فیلتر زمینه: M15 Always-In یا تشخیص TR.

**سشن**
- منبع محدود نکرده. پیشنهاد فیلتر حجم طلا:
  - UTC 07:00–16:00 / تهران 10:30–19:30
- در TR و انتهای لگ‌های قوی، Brooks صراحتاً منتظر 2nd entry از نوع MDB/MDT می‌ماند (PDF webinar strong legs).

**تعاریف کد**
- **MDB**: دو low محلی روی پنجرهٔ ۲–۴ کندل که اختلافشان ≤ `tol` دلار است (پیشنهاد tol = 0.50 تا 1.00 برای طلا؛ یا «تقریباً یکسان» طبق Brooks). بین دو low حداقل یک کندل با high بالاتر از هر دو low وجود دارد (= گردن/neck).
- **تأیید MDB**: قیمت از low دوم بالای `neck_high` (بالاترین high بین دو low) معامله شود.
- **MDT**: قرینه با دو high و `neck_low`.
- **سیگنال‌بار خرید**: کندل صعودی با close در نیمهٔ بالای دامنه (نزدیک high)، ترجیحاً دومین bull bar متوالی (مثال Brooks).

**ورود قدم‌به‌قدم (خرید MDB)**
1. زمینه: انتهای لگ نزولی داخل روند صعودی، یا کف نیمهٔ پایین TR، یا بعد از لگ نزولی قوی که Brooks می‌گوید «صبر برای 2nd entry / micro DB».
2. دو low با |L1−L2| ≤ tol در ≤۴ کندل شناسایی کن.
3. `neck = max(high بین دو low)`.
4. گزینهٔ A (محافظه‌کارانه): buy stop یک تیک بالای neck.
5. گزینهٔ B (Brooks در مثال ۵قدم): اگر سیگنال‌بار قوی با close روی high داری، buy stop یک تیک بالای high همان سیگنال‌بار (می‌تواند جلوتر از neck باشد).
6. اگر تریگر در کندل بعد از سیگنال نشد → لغو یا صبر برای سیگنال تازه.

**فروش MDT**: قرینه.

**SL**
- زیر پایین‌ترین low الگوی MDB (یا زیر سیگنال‌بار اگر همان extreme است) — یک تیک آن‌سو.
- فیلتر: اگر `entry − stop > 8` → رد.

**TP**
- حداقل ۲R (نقل مستقیم صفحهٔ ۵قدم).
- جایگزین: measured move ارتفاع MDB، یا TBTL.

**فیلترها**
- در وسط لگ خیلی قوی خلاف جهت، صبر برای second MDB/MDT (PDF strong legs: «When a leg down is strong, wait for a 2nd entry buy signal, like a micro double bottom»).
- اجتناب از TTR خیلی فشرده برای stop-entry.

**آمار بک‌تست**
- **source gives no stats** برای winrate/XAUUSD. فقط ساختار و قاعدهٔ ۲R در منبع آمده.

---

## ۲) Inside Bar (ib) با فیلتر ارتفاع Mother ≤ ۸$ | منبع: Brooks + Nial Fuller

**نام و منبع**
- نام: Inside Bar / Mother Bar breakout (`ib` / `mb`)
- تعریف Brooks: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `ib = Inside bar, the high of the bar is at or below the high of the prior bar and the low is at or above the low of the prior bar`
- ورود/SL کلاسیک: https://priceaction.com/price-action-university/strategies/inside-bar/ — تأیید شد. Buy/sell stop روی high/low مادر؛ SL معمولاً آن‌سوی مادر یا در ۵۰٪ ارتفاع مادر اگر مادر بزرگ باشد. منبع می‌گوید روی D1 بهترین است و روی M5/M1 داخل‌بار زیاد و پرنویز است — این هشدار را در فیلترها نگه دار.
- زمینهٔ Brooks روی ۵دقیقه: inside bar اغلب پیش از ریورسال؛ شکست دوطرفهٔ سیگنال (مقاله ۵دقیقه): https://www.brookstradingcourse.com/futures-market/day-trading-5-minute-emini/

**تفاوت با ردشده‌ها**
- NY ORB نیست (به بازهٔ ثابت نیویورک وابسته نیست).
- Casper یک‌کندلی نیست؛ الگوی دو کندلی mother+inside است.
- اندیکاتور trend نیست.

**تایم‌فریم**
- برای چالش SL کوچک: M5 (یا M15 اگر mother ≤۸$). روی M1 نویز زیاد است — فقط با فیلتر روند سخت.
- فیلتر روند: Always-In روی M15 یا جهت EMA20 روی همان TF اجرا.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30 (فیلتر عملیاتی؛ منبع سشن اجباری نگذاشته).

**تعاریف کد**
- Mother bar = کندل i−1؛ Inside = کندل i.
- شرط سخت (Fuller «most traders»): `high[i] < high[i-1]` و `low[i] > low[i-1]` (تساوی مجاز نیست).
- شرط نرم Brooks: `high[i] <= high[i-1]` و `low[i] >= low[i-1]`.
- `mother_range = high[mb] − low[mb]`.
- فیلتر پراپ اجباری این نسخه: `mother_range <= 8` دلار. اگر مادر بزرگ‌تر است یا از قاعدهٔ Fuller استفاده کن: SL در ۵۰٪ مادر، مشروط به اینکه ریسک واقعی ≤۸ شود؛ وگرنه رد.

**ورود قدم‌به‌قدم (با روند)**
1. Always-In Long (برای خرید) یا Short (برای فروش).
2. تشکیل ib داخل mother با `mother_range <= 8`.
3. خرید: buy stop یک تیک بالای `high[mother]`؛ همزمان می‌توان sell stop زیر `low[mother]` گذاشت فقط در Breakout Mode بدون بایاس — برای نسخهٔ با روند فقط هم‌جهت.
4. وقتی یک طرف پر شد، سفارش مخالف را لغو کن.
5. فقط break هم‌جهت روند را بگیر (Fuller: beginners with the trend).

**SL**
- کلاسیک: آن‌سوی mother (زیر low مادر برای لانگ).
- اگر مادر نزدیک ۸ دلار است و می‌خواهی تنگ‌تر: SL در ۵۰٪ mother (مجاز طبق Fuller وقتی مادر بزرگ‌تر از متوسط است) به شرط ریسک ≤۸.

**TP**
- حداقل ۱:۲ نسبت به ریسک (پیشنهاد رایج Fuller؛ عدد بک‌تست ثابت در صفحه نیست).
- یا ساختار بعدی / 2R.

**فیلترها**
- Fuller: از M5 خام بدون فیلتر پرهیز کن؛ فقط با روند یا سطح کلیدی.
- خبرهای سنگین را رد کن.
- چند ib داخل یک mother مجاز است (coiling).

**آمار بک‌تست**
- **source gives no stats** کمی برای XAUUSD در صفحات تأییدشده. Fuller فقط کیفی می‌گوید R:R خوب است.

---

## ۳) ii — دو Inside متوالی (Breakout Mode) | منبع: Al Brooks

**نام و منبع**
- نام: `ii` = consecutive inside bars، Breakout Mode (هر دو جهت سیگنال)
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `ii = Consecutive inside bars, Breakout Mode, so both buy and sell signal`؛ همچنین `iii` سه داخل؛ `ioi` outside بین insideها؛ `OO` دو outside متوالی.
- کاربرد در روتین روزانه: https://www.brookstradingcourse.com/trading-strategies/5-steps-to-finding-todays-trades/ — ii/OO/ioi به‌عنوان special bars و BOM.
- منطق ورود دو طرفه روی سیگنال‌بار: https://www.brookstradingcourse.com/futures-market/day-trading-5-minute-emini/

**تفاوت با Inside Bar ساده (#۲)** و ردشده‌ها
- اینجا **حداقل دو** inside پشت‌سرهم است → فشردگی بیشتر و صریحاً Breakout Mode دو طرفه.
- با NY ORB فرق دارد: بازهٔ ثابت ساعت نیست؛ الگوی نواری است.
- با Casper/اندیکاتورها فرق دارد.

**تایم‌فریم**
- M5 (اصلی Brooks)؛ M1 فقط با فیلتر ارتفاع کل الگوی ii ≤۸$.

**سشن**
- UTC 07:00–16:00 / تهران 10:30–19:30.

**تعاریف کد**
- کندل‌های t−1 و t هر دو inside نسبت به قبلی‌شان (تعریف ib).
- `pattern_high = max(high در پنجرهٔ ii)`؛ `pattern_low = min(low همان پنجره)`.
- فیلتر: `pattern_high − pattern_low <= 8`.

**ورود قدم‌به‌قدم**
1. ii (یا iii) را روی M5 پیدا کن با ارتفاع ≤۸.
2. هم‌زمان:
   - buy stop یک تیک بالای `pattern_high`
   - sell stop یک تیک زیر `pattern_low`
3. اولین تریگر = ورود؛ طرف دیگر را فوراً لغو کن.
4. اگر زمینه Always-In قوی است، می‌توانی فقط هم‌جهت را فعال کنی (نسخهٔ فیلترشده؛ منبع خام BOM دو طرفه است).

**SL**
- آن‌سوی الگوی ii (زیر pattern_low برای لانگ؛ بالای pattern_high برای شورت) → طبق فیلتر ارتفاع، ریسک ≤۸.

**TP**
- 1R اسکالپ یا 2R swing.
- اگر بعد از BO، PB به لبهٔ ii برگشت و نگه داشت → می‌تواند BP جدا باشد (دسته ۱)؛ اینجا فقط شکست اولیه است.

**فیلترها**
- در TTR خیلی بی‌قرار، Brooks می‌گوید stop-entry سخت است؛ اگر بیشتر کندل‌ها دم دارند و همپوشانی زیاد → رد یا صبر.
- بعد از خبر بزرگ، اولین ii را رد کن.

**آمار بک‌تست**
- **source gives no stats**.

---

## ۴) Mitigation Block (بدون sweep) — ری‌تست بعد از failure swing | منبع: ICT / DT Terminal

**نام و منبع**
- نام: Mitigation Block (MB)
- تعریف تفکیک‌شده از Breaker: https://www.thedtterminal.com/academy/ict-breaker-and-mitigation-blocks — تأیید شد.
  - Breaker = اول sweep نقدینگی extreme قدیمی، بعد body close از بلوک.
  - Mitigation = **بدون sweep**؛ failure swing (higher low در حالت صعودی / lower high در حالت نزولی)، سپس body close از بلوک با displacement؛ ری‌تست در جهت شکست.
- منبع صریحاً می‌گوید entry/stop/target را خودت به‌صورت قاعده بنویس؛ و «No peer-reviewed study tests breakers or mitigation blocks».

**تفاوت صریح با «LiqSweep+MSS+FVG» ردشده**
1. **عمداً بدون sweep** — اگر sweep باشد این ستاپ mitigation نیست (آن breaker است و در این دسته جداگانه نیامده).
2. **FVG اجباری نیست**؛ نقطهٔ حساس = آخرین کندل مخالف قبل از failure swing (بلوک).
3. **MSS جدا به‌عنوان شرط نام‌گذاری نشده**؛ شرط کلیدی DT: failure swing + body close beyond distal line بلوک + ری‌تست.
4. fib OTE لازم نیست.

**تایم‌فریم**
- شناسایی بلوک: M15 یا M5
- اجرا/ری‌تست: M5 یا M1 برای سیگنال‌بار کوچک

**سشن**
- پیشنهاد: لندن تا نیویورک
  - UTC 07:00–16:00 / تهران 10:30–19:30
- مثال آموزشی DT روی XAUUSD H1 هم آمده (فقط نمونهٔ ساختاری، نه آمار).

**تعاریف کد**
- **Order block اولیه (برای context)**: آخرین کندل مخالف قبل از یک displacement (مثلاً آخرین down-close قبل از rally برای bearish block بالقوه — طبق قرارداد ICT رایج؛ DT می‌گوید آخرین opposite candle قبل از failure swing).
- **Distal line**: برای بلوک صعودیِ شکسته‌شونده، لبهٔ دور = low بلوک؛ برای بلوک نزولی = high بلوک.
- **Failure swing (bullish mitigation path)**: قیمت higher low می‌سازد (به زیر old low نمی‌رود) سپس body close بالای distal بلوکِ قبلیِ نزولی.
- **Failure swing (bearish mitigation path)**: lower high بدون گرفتن old high، سپس body close زیر distal بلوک صعودی قبلی.
- **Displacement**: حداقل یک کندل با بدنهٔ بزرگ که از بلوک عبور و کلوز کند (پارامتر: body ≥ k×ATR؛ k قابل‌تنظیم چون منبع عدد ثابت نداده).

**ورود قدم‌به‌قدم (خرید — bullish mitigation)**
1. یک بلوک نزولی قدیمی شناسایی کن که با failure swing (بدون sweep زیر old low) از بالا شکسته و body close بالای آن آمده.
2. منتظر برگشت قیمت به داخل محدودهٔ همان کندل بلوک (ری‌تست) بمان.
3. روی M5، سیگنال‌بار صعودی با close نزدیک high داخل/روی بلوک → buy stop یک تیک بالای high آن.
4. اگر body دوباره خلاف جهت از distal دیگر بگذرد قبل از ورود → باطل.

**فروش — bearish mitigation**: قرینه.

**SL**
- آن‌سوی لبهٔ دور بلوک (فراتر از wick کامل کندل بلوک، طبق منطق رایج invalidation؛ DT می‌گوید stop را خودت بنویس).
- فیلتر: فقط وقتی `entry تا distal+buffer <= 8`؛ روی M15 اغلب رد می‌شود → اجرا روی M5/M1 یا فقط بلوک‌های کوچک.

**TP**
- 1R/2R؛ یا نقدینگی سویینگ بعدی در جهت شکست.
- منبع آمار هدف نمی‌دهد.

**فیلترها**
- اگر failing swing extreme قدیمی را گرفت → این ستاپ را نگیر (برو تعریف breaker؛ عمداً اینجا نیست).
- بدون body close از بلوک → هنوز flip نشده.
- هم‌راستا با بایاس HTF ترجیح داده شود (پارامتر عملیاتی).

**آمار بک‌تست**
- DT: «No peer-reviewed study…» → **source gives no stats**. مثال XAUUSD فقط شماتیک آموزشی است.

---

## ۵) Trading Range Extreme — شکست ناموفق + Second Entry | منبع: Al Brooks

**نام و منبع**
- نام: Trading Range reversal / failed breakout at extremes با انتظار برای 2nd signal
- صفحهٔ ۱۰ الگو (بخش Trading range reversals): https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ — تأیید شد.
  - در روزهای TR، بازار به سقف vacuum می‌شود و BO اغلب fail می‌کند؛ در کف همین‌طور.
  - «When the legs up and down in a trading range are often strong… higher probability… wait for a 2nd signal.»
  - Buy low, sell high, scalp.
- PDF strong legs: وقتی لگ قوی است صبر برای 2nd entry مثل micro DB/DT — https://www.brookstradingcourse.com/wp-content/uploads/2016/05/Al-Brooks-Webinar-Distinguishing-Strong-Legs-TR-vs-Trends-May-3-2016.pdf
- BOM احتمال: اختصار `BOM` ≈ ۵۰٪ شانس BO موفق هر طرف — https://www.brookstradingcourse.com/brooks-price-action-abbreviations/

**تفاوت با ردشده‌ها و با دسته ۱**
- NY ORB نیست: بازه = trading range جاری روز/سشن، نه الزاماً ثابت باز نیویورک.
- Final Flag (دسته ۱) روی «پرچم دیر در روند» است؛ اینجا زمینه صریحاً **روز/فاز TR** است و قانون «صبر برای سیگنال دوم» مرکزیت دارد.
- LiqSweep+MSS+FVG نیست؛ ورود PA روی سیگنال‌بار دوم (اغلب MDT در سقف / MDB در کف).

**تایم‌فریم**
- تشخیص TR: M5/M15 (علائم: دم‌های زیاد، همپوشانی، نبود ۲–۳ trend bar متوالی بزرگ، اینرسی از TR دیروز — نقل صفحه).
- اجرا: M5/M1 روی 2nd signal با ریسک ≤۸.

**سشن**
- هر زمان TR فعال است؛ اوج مفید طلا همان UTC 07:00–16:00 / تهران 10:30–19:30.
- نزدیک ۲ ساعت پایانی: صفحه می‌گوید اگر نزدیک HOD/LOD هستی، به سمت open برگرد (magnet open).

**تعاریف کد**
- **TR day/phase**: مثلاً در N کندل اخیر (پیشنهاد N=20–30 روی M5) دامنه محدود است و تعداد برگشت‌ها ≥ R، و میانگین |close−open|/range پایین است (پارامترها چون منبع عددی دقیق برای تشخیص خودکار نداده قابل‌تنظیم‌اند).
- **سقف TR** = highest high بازه؛ **کف TR** = lowest low.
- **Failed BO بالا**: قیمت > TR_high سپس ظرف K کندل دوباره به داخل TR برمی‌گردد و کلوز داخل می‌کند.
- **First sell signal**: اولین سیگنال‌بار نزولی بعد از failed BO بالا.
- **Second sell signal**: سیگنال نزولی بعدی ظرف چند کندل (اغلب MDT یا L2 کوچک) — این تریگر اصلی است.

**ورود قدم‌به‌قدم (فروش سقف TR)**
1. فاز TR را تأیید کن.
2. BO به بالای TR_high و برگشت به داخل را ببین (failed BO).
3. سیگنال اول را علامت بزن ولی وارد نشو (یا فقط اگر خیلی قوی بود با سایز کوچک — منبع ترجیح 2nd دارد).
4. سیگنال دوم: سیگنال‌بار نزولی با close نزدیک low (ترجیحاً MDT) → sell stop یک تیک زیر low آن.
5. SL بالای extreme همان BO شکسته‌شده یا بالای high سیگنال دوم؛ اگر >۸ → فقط وقتی سیگنال دوم خودش ارتفاع ≤۸ دارد و SL پشت همان سیگنال است (ریسک تنگ‌تر، احتمال کمتر طبق Brooks).

**خرید کف TR**: قرینه با MDB / 2nd buy.

**TP**
- اسکالپ به وسط TR یا سمت مخالف؛ حداقل ۱R؛ بهتر ۲R اگر جا باشد.
- صفحه: در TR اغلب به open روز برمی‌گردد.

**فیلترها**
- اگر بعد از failed BO، Always-In قوی خلاف fade شکل گرفت → ستاپ را رها کن (روند از TR خارج شده).
- از اولین سیگنال بعد از لگ خیلی قوی بدون second خودداری کن.

**آمار بک‌تست**
- اختصار BOM: حدود ۵۰٪ شانس BO موفق هر طرف (مفهوم کلی، نه سیستم کامل).
- صفحهٔ ریورسال‌ها عدد winrate مخصوص این سیستم روی طلا نمی‌دهد.
- **source gives no stats** اختصاصی XAUUSD برای این پکیج قواعد.

---

## جمع‌بندی دسته ۲ (مناسب SL کوچک / تکرار)

| # | ستاپ | فرکانس کیفی | مناسب ≤۸$ |
|---|---|---|---|
| 1 | MDB/MDT | زیاد روی M1/M5 | بله |
| 2 | Inside Bar (mother≤۸) | زیاد با فیلتر | بله با فیلتر |
| 3 | ii Breakout Mode | متوسط–زیاد | بله با فیلتر ارتفاع |
| 4 | Mitigation Block (no sweep) | متوسط | فقط بلوک کوچک / M5–M1 |
| 5 | TR extreme + 2nd signal | چند بار در روزهای TR | بله روی سیگنال‌بار دوم |

لینک‌های اصلی با WebFetch در این نوبت تأیید شدند.
