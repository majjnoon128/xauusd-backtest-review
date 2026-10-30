# دسته ۱ — ستاپ‌های قابل‌کدنویسی XAUUSD (M1–M15)
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | هدف: چالش پراپ SGB ۱۰۰۰ دلاری، سیگنال دستی

قواعد مشترک این دسته:
- فقط قوانین نوشته‌شده در منبع؛ هیچ عدد بک‌تستی اختراع نشده.
- اولویت SL کوچک: فیلتر پیشنهادی کدنویسی `signal_bar_range_USD <= 8` (یعنی high−low سیگنال‌بار ≤ ۸ دلار طلا). اگر منبع SL وسیع‌تری بگوید، همان منبع مقدم است و فیلتر ۸ دلاری فقط به‌عنوان محدودیت پراپ اضافه می‌شود.
- زمان‌ها: UTC و تهران (UTC+3:30). برای سشن نیویورک: در اکتبر ۲۰۲۶ هنوز EDT (UTC−4)؛ بعد از پایان DST آمریکا (اولین یکشنبه نوامبر) EST = UTC−5.
- هیچ ادعای سود یا تبلیغ نیست.

---

## ۱) High 2 / Low 2 (H2/L2) — Second Entry Flag | منبع: Al Brooks

**نام و منبع**
- نام: High 2 bull flag / Low 2 bear flag (بارشماری H1→H2 و L1→L2)
- منبع اصلی (صفحه عمومی Brooks): https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ (بخش «High 2 bull flags and Low 2 bear flags») — لینک با WebFetch تأیید شد.
- تعریف اختصاری رسمی: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `H1` = one-legged pullback in a bull move؛ `H2` = two-legged pullback in a bull move؛ `L1`/`L2` قرینه در حرکت نزولی.
- جزئیات شمارش از کتاب (نمونه فصل): https://www.oreilly.com/library/view/trading-price-action/9781118172339/OEBPS/9781118172339_epub_c_17.htm — «اولین باری که high کندل حداقل یک تیک بالای high کندل قبلی برود = High 1».
- PDF کوچینگ رسمی Brooks (اسلایدهای شمارش): https://www.brookstradingcourse.com/wp-content/uploads/2025/10/250823-Coaching-Session-2-PAF-Setups.pdf
- ورود با استاپ و محل SL پیش‌فرض: https://www.brookstradingcourse.com/how-to-trade-manual/stop-orders/ و مقاله ۵دقیقه: https://www.brookstradingcourse.com/futures-market/day-trading-5-minute-emini/

**تایم‌فریم**
- شناسایی و اجرا: M5 (مقاله Brooks روی ۵دقیقه نوشته؛ همان منطق روی M1/M15 هم کار می‌کند).
- فیلتر روند اختیاری: M15 یا H1 برای Always-In (AIL/AIS).

**سشن**
- منبع سشن خاصی را اجباری نکرده؛ روی چارت ۵دقیقه «۱۰ تا ۲۰ ستاپ در روز» را ذکر کرده (Emini، نه طلا).
- پیشنهاد عملی برای طلا (فیلتر ما، نه قانون Brooks): لندن تا نیویورک
  - UTC: 07:00–16:00
  - تهران: 10:30–19:30
- اجتناب از رنج خیلی فشرده نیمه‌شب آسیا مگر Always-In واضح باشد.

**تعاریف دقیق برای کد**
- **روند صعودی (Always-In Long)**: سری HH/HL روی تایم‌فریم فیلتر؛ یا قیمت بالای EMA ۲۰ همان تایم اجرای ستاپ (اختصار Brooks: EMA = 20-bar EMA).
- **شروع pullback نزولی در روند صعودی**: حرکت sideways/down پس از یک breakout صعودی.
- **High 1 (H1)**: در حرکت sideways/down داخل روند صعودی یا TR، اولین کندلی که `high[i] > high[i-1]` (حداقل یک تیک طبق کتاب). آن کندل پایان پای اول است؛ کندل قبلی می‌تواند سیگنال‌بار H1 باشد اگر ورود روی شکست high آن باشد.
- **High 2 (H2)**: پس از H1، اگر بازار یک پای دیگر پایین/ساید بسازد و دوباره کندلی با `high > high prior` بیاید، آن رخداد H2 است؛ **سیگنال‌بار خرید H2 = همان کندلی که high آن شکسته می‌شود** (طبق PDF: «The prior bar is the High 2 buy signal bar»).
- **Low 1 / Low 2**: قرینه — در روند نزولی، اولین/دومین بار که `low[i] < low[i-1]`.
- **سیگنال‌بار خوب (فیلتر کیفیت، از مقاله ۵دقیقه)**: برای خرید، ترجیحاً کندل صعودی با close نزدیک high؛ برای فروش، کندل نزولی با close نزدیک low.
- **Entry bar**: کندلی که یک تیک فراتر از high (خرید) یا low (فروش) سیگنال‌بار معامله می‌شود.
- **لغو**: اگر سیگنال در همان کندل بعدی تریگر نشود، ستاپ کهنه است (قانون رایج Brooks برای stop-entry؛ در صفحه stop-orders و منابع ثانویهٔ هم‌راستا).

**ورود قدم‌به‌قدم (خرید H2)**
1. Always-In Long روی فیلتر (مثلاً M15 HH/HL یا close بالای EMA20).
2. پس از یک BO صعودی، pullback sideways/down را بشمار.
3. H1 را با اولین `high > prior high` علامت بزن.
4. منتظر پای دوم پایین بمان؛ سیگنال‌بار H2 را شناسایی کن (کندلی که شکست high آن = ورود).
5. Buy stop یک تیک بالای high سیگنال‌بار H2.
6. اگر تریگر شد → ورود؛ وگرنه لغو.

**فروش L2**: قرینهٔ کامل.

**SL**
- یک تیک آن‌سوی سیگنال‌بار: خرید → یک تیک زیر low سیگنال‌بار؛ فروش → یک تیک بالای high سیگنال‌بار (صفحه stop-orders و مقاله ۵دقیقه).
- فیلتر پراپ: اگر `(high−low)` سیگنال‌بار + بافر تیک > ۸ دلار طلا → رد ستاپ یا سایز خیلی کوچک.

**TP**
- Scalp: حداقل حدود reward ≈ risk (Brooks اغلب از اسکالپ کوچک صحبت می‌کند؛ روی Emini «چهار تیک» مثال زده — این عدد مخصوص Emini است، نه طلا).
- Swing: هدف Brooks برای swing = حداقل ۲R و ترجیحاً «۱۰ بار، ۲ پا» (TBTL) — از صفحه ۱۰ الگو (بخش Final flags / احتمال).
- پیشنهاد کد برای طلا: TP1 = 1R، TP2 = 2R؛ یا measured move پای قبلی.

**فیلترها**
- فقط با روند (H2 در AIL، L2 در AIS).
- اجتناب از Tight Trading Range (TTR) وقتی Brooks می‌گوید stop-entry بد است.
- سیگنال‌بار خیلی کوچک: Brooks هشدار می‌دهد SL یک‌تیک بالای آن احتمال استاپ‌اوت بالا دارد (Ask Al wedge) — برای سیگنال‌بار خیلی کوچک، SL را ۲–۴ تیک فراتر بگذار یا ستاپ را رد کن.
- خبرهای سنگین US (NFP/CPI/FOMC): خارج از منبع؛ فیلتر عملیاتی پیشنهادی.

**آمار بک‌تست**
- منبع می‌گوید روی ۵دقیقه Emini «معمولاً ۱۰ تا ۲۰ ستاپ در روز» — این آمار تعداد فرصت است، نه winrate روی طلا.
- احتمال swing روی ریورسال‌ها در صفحه ۱۰ الگو حدود ۴۰٪ ذکر شده؛ برای H2 continuation صراحتاً «high probability» گفته اما عدد winrate نداده.
- **source gives no stats** برای XAUUSD / winrate / expectancy این ستاپ.

---

## ۲) Breakout Pullback (BP) — اولین پولبک بعد از BO قوی | منبع: Al Brooks

**نام و منبع**
- نام: Breakout Pullback (اختصار Brooks: `BP`)
- تعریف اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `BP = Breakout Pullback`
- صفحه الگوها (بخش Breakouts + منطق ادامه): https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/
- قواعد عملی شمارش/ورود stop: PDF کوچینگ + stop-orders (لینک‌های بالا)
- جمع‌بندی قاعده‌مند هم‌راستا با Brooks (کتابخانه OneTrend؛ ثانویه است، فقط برای جزئیات کمی که در صفحه عمومی خلاصه شده): https://www.onetrend.app/books/en/al-brooks-price-action.html — بخش «First Pullback After Trend Onset» و «Breakout Pullback Entries»: BO با ۲–۵ trend bar؛ PB معمولاً ۱–۳ بار؛ PB بیش از ۵۰٪ BO را برنمی‌گرداند؛ ورود buy stop بالای high پولبک.

**تایم‌فریم**
- اجرا: M1 یا M5 برای سیگنال‌بار کوچک؛ شناسایی BO روی M5/M15.

**سشن**
- بهترین احتمال عملی وقتی حجم بالاست:
  - لندن: NY 02:00–05:00 → UTC 06:00–09:00 (EDT) → تهران 09:30–12:30
  - نیویورک: NY 08:00–11:00 → UTC 12:00–15:00 (EDT) → تهران 15:30–18:30
- منبع Brooks سشن اجباری برای BP نگذاشته.

**تعاریف کد**
- **Trend bar صعودی**: close > open و close در نیمهٔ بالای دامنهٔ کندل (نزدیک high).
- **Bull breakout قوی**: ۲ تا ۵ کندل متوالی trend bar صعودی که حداقل یک سطح واضح را می‌شکنند (high سویینگ قبلی، سقف کانال، یا high یک TR). اندازهٔ BO = `BO_high − BO_start_low` (از low اولین کندل BO تا high انتهای پای BO).
- **Pullback مجاز**: ۱ تا ۳ کندل بعد از BO؛ حداکثر retrace = ۵۰٪ اندازهٔ BO (طبق OneTrend که صریحاً نوشته؛ صفحه عمومی Brooks فقط «pullback بعد از BO» را بدون عدد ۵۰٪ می‌گوید — در کد، ۵۰٪ را به‌عنوان پارامتر قابل‌تنظیم از منبع ثانویه علامت بزن).
- **سیگنال‌بار PB**: آخرین کندل پولبک که برای خرید، high آن نقطهٔ ورود است (یا H1 داخل پولبک).

**ورود قدم‌به‌قدم (خرید)**
1. شناسایی BO صعودی قوی (۲–۵ bull trend bar + شکست سطح).
2. صبر برای PB ۱–۳ کندلی با retrace ≤ ۵۰٪ BO.
3. Buy stop یک تیک بالای high سیگنال‌بار پولبک (یا بالای high کل محدودهٔ PB اگر فشرده است).
4. تریگر فقط اگر بازار دوباره هم‌جهت BO حرکت کند.

**فروش**: قرینه بعد از bear BO.

**SL**
- یک تیک زیر low سیگنال‌بار (Brooks stop-entry پیش‌فرض).
- فیلتر ۸ دلاری روی ارتفاع سیگنال‌بار.

**TP**
- حداقل ۱R اسکالپ؛ ۲R برای swing.
- هدف جایگزین: measured move هم‌اندازهٔ پای BO (مفهوم MM در صفحه ۱۰ الگو).

**فیلترها**
- PB عمیق‌تر از ۵۰٪ → رد (نسخهٔ OneTrend) یا تبدیل به H2 عمیق‌تر.
- اگر PB بلافاصله به زیر نقطهٔ BO برگردد و ببندد → Failed BO، نه BP.
- فقط اولین PB بعد از شروع روند جدید (اولویت Brooks).

**آمار بک‌تست**
- **source gives no stats** (نه winrate، نه نمونهٔ طلا).

**تفاوت با H2**: BP روی «اولین پولبک بلافاصله بعد از BO قوی» تمرکز دارد و اغلب همان H1/H2 اولیه است؛ شرط صریح قدرت BO (۲–۵ trend bar) و محدودیت عمق PB آن را از H2 عمومی جدا می‌کند.

---

## ۳) Final Flag (FF) — شکست ناموفق پرچم پایانی | منبع: Al Brooks

**نام و منبع**
- نام: Final Flag / Failed Final Flag breakout
- صفحه رسمی: https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ (بخش Final flags) — تأیید شد.
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `FF = Final Flag, usually a horizontal pattern after a trend. The breakout often fails and reverses`
- خلاصهٔ شناسایی هم‌راستا: https://www.luxalgo.com/library/concept/final-flag/ (ارجاع مستقیم به Brooks؛ لینک زنده)

**تایم‌فریم**
- M5 یا M15 برای دیدن پرچم افقی؛ ورود می‌تواند M5/M1 روی سیگنال‌بار ریورسال باشد.

**سشن**
- منبع محدود نکرده. برای طلا پیشنهاد فیلتر حجم:
  - UTC 07:00–16:00 / تهران 10:30–19:30

**تعاریف کد**
- **روند ممتد**: حداقل N کندل Always-In یک‌طرفه (پیشنهاد پارامتر N≥20 روی M5) یا وجود climax (چند trend bar بزرگ پشت‌سرهم).
- **پرچم افقی پایانی**: Tight Trading Range یا مثلث کوچک یا `ii` (دو inside bar متوالی) که بیشتر افقی است، نزدیک انتهای روند و نزدیک یک magnet (مقاومت در صعود / حمایت در نزول).
- **Breakout با روند**: کندلی که high (در صعود) را به extreme جدید می‌برد.
- **شکست ناموفق**: ظرف چند کندل بعد از BO، قیمت به داخل پرچم برمی‌گردد (برای فروش بعد از BO صعودی: شکست low یک سیگنال‌بار نزولی داخل/زیر پرچم).

**ورود قدم‌به‌قدم (فروش بعد از FF صعودی)**
1. روند صعودی ممتد + پرچم افقی دیرهنگام.
2. BO به high جدید را ببین؛ دنبال‌رو را کندل‌به‌کندل چک کن.
3. اگر ظرف K کندل (پیشنهاد K=3 طبق LuxAlgo «within a few bars») قیمت به داخل پرچم برگردد و یک سیگنال‌بار نزولی با close نزدیک low بسازد:
4. Sell stop یک تیک زیر low آن سیگنال‌بار.
5. Invalidation = extreme همان BO شکسته‌شده (بالای high شکست).

**خرید بعد از FF نزولی**: قرینه.

**SL**
- آن‌سوی extreme شکست ناموفق (بالای high BO برای شورت؛ زیر low BO برای لانگ) — مطابق Brooks/LuxAlgo.
- هشدار: این SL اغلب از ۸ دلار بزرگ‌تر است روی M15؛ برای پراپ ۱۰۰۰ دلاری یا روی M1/M5 سیگنال بگیر یا سایز را از روی ریسک ۱٪ حساب کن. اگر extreme−entry > ۸ → یا رد، یا فقط با سایز خیلی کوچک.

**TP**
- هدف Brooks: حداقل دو پای اصلاحی (TBTL / دو لگ). احتمال swing حدود ۴۰٪ در متن صفحهٔ ۱۰ الگو برای ریورسال‌ها ذکر شده؛ برای احتمال بالاتر می‌گوید صبر کن تا BO قوی در جهت جدید بیاید (آن‌وقت احتمال swing «اغلب ۶۰٪ یا بیشتر» ولی SL دورتر است) — نقل از همان صفحه.

**فیلترها**
- وارد شو فقط بعد از failure، نه از قبل (Brooks: برچسب FF فقط در هینسایت قطعی است؛ عمل بعد از شکست ناموفق).
- اگر ریورسال خودش فوراً fail شود (failed failure) → ستاپ با روند برمی‌گردد؛ از شورت خارج شو / برعکس کن.

**آمار بک‌تست**
- صفحهٔ Brooks: احتمال swing روی ریورسال معمولاً حدود ۴۰٪؛ ۶۰٪ معاملات wins/losses کوچک که همدیگر را خنثی می‌کنند؛ بعد از BO قوی در جهت جدید احتمال swing اغلب ۶۰٪+ با SL بزرگ‌تر.
- این‌ها آمار کلی مفهوم ریورسال/FF در متن Brooks است، نه بک‌تست اختصاصی XAUUSD.
- **source gives no stats** اختصاصی طلا.

---

## ۴) Wedge (سه پوش) — W / H3 / L3 | منبع: Al Brooks

**نام و منبع**
- نام: Wedge top/bottom یا three pushes؛ در پرچم: wedge bull/bear flag
- صفحه رسمی: https://www.brookstradingcourse.com/price-action/10-best-price-action-trading-patterns/ (بخش Wedges)
- اختصار: https://www.brookstradingcourse.com/brooks-price-action-abbreviations/ — `W = Wedge or anything similar, like any 3 push pattern`؛ `H3`/`L3` = three-legged pullback (wedge flag یا wedge bottom/top)
- Ask Al دربارهٔ SL تنگ روی wedge: https://www.brookstradingcourse.com/ask-al/tight-stops-selling-wedge-top/

**تایم‌فریم**
- M5/M15 شناسایی سه پوش؛ ورود M5/M1 روی سیگنال‌بار.

**سشن**
- محدود نشده در منبع. فیلتر پیشنهادی همان پنجرهٔ نقدینگی طلا (UTC 07:00–16:00 / تهران 10:30–19:30).

**تعاریف کد**
- **Push (پوش)**: یک پای جهت‌دار که به extreme محلی جدید می‌رسد (در wedge top: سه swing high متوالی با ساختار کانال صعودی).
- **Wedge به‌معنای گستردهٔ Brooks**: هر الگوی سه (گاهی ۴–۵) پوش شیب‌دار؛ لازم نیست همگرا یا کاملِ کتاب‌درسی باشد. «اگر کانال نزولی ۳ پا دارد حتی بدون شکل wedge، مثل wedge ببین.»
- **خط کانال**: بعد از دو پوش، خط اتصال extremeها را بکش و امتداد بده؛ پوش سوم نزدیک این خط = هشدار ریورسال.
- **سیگنال فروش wedge top**: سیگنال‌بار نزولی با close نزدیک low، زیر آن ورود.
- **MicroWedge (`MW`)**: wedge فقط با ۳–۴ کندل — مناسب SL کوچک.

**ورود قدم‌به‌قدم (فروش wedge top)**
1. سه پوش صعودی را علامت بزن (P1, P2, P3) طوری که P3 نزدیک خط کانال امتدادیافتۀ P1–P2 باشد (یا صرفاً سومین push در کانال صعودی تنگ).
2. منتظر سیگنال‌بار نزولی با close در نیمهٔ پایین دامنه بمان.
3. Sell stop یک تیک زیر low سیگنال‌بار.
4. انتظار حداقل دو پا پایین (طبق صفحهٔ ۱۰ الگو).

**خرید wedge bottom / wedge bull flag**: قرینه (سه پوش پایین در روند صعودی → خرید بالای سیگنال‌بار صعودی).

**SL**
- پیش‌فرض: یک تیک بالای high سیگنال‌بار.
- هشدار Ask Al: اگر سیگنال‌بار خیلی کوچک است، SL یک‌تیک بالای آن اغلب زده می‌شود؛ SL را چند تیک بالاتر بگذار.
- فیلتر ۸ دلاری: ترجیح MicroWedge یا سیگنال‌بار کوتاه روی M1/M5.

**TP**
- حداقل ۲ پا خلاف جهت wedge؛ یا ۱R/۲R.
- صفحه می‌گوید هر کانال صعودی را می‌توان bear flag دید چون «۷۵٪ شانس شکست زیر خط روند صعودی» — این نقل‌قول احتمال شکست کانال است نه winrate سیستم کامل.

**فیلترها**
- سه پوش کوچک بدون شکست خط روند قبلی یا overshoot کانال → Brooks می‌گوید اغلب with-trend است نه ریورسال بزرگ؛ در روند قوی، wedge flag را با روند معامله کن نه خلاف آن.
- در TR، برای ریورسال قوی‌تر صبر برای second entry (مرتبط با فصل Second Entries).

**آمار بک‌تست**
- نقل صفحه: ~۷۵٪ شانس شکست زیر bull channel (مفهوم کانال، نه بک‌تست استراتژی wedge کامل روی طلا).
- **source gives no stats** برای winrate/XAUUSD این ستاپ به‌صورت سیستم بسته.

---

## ۵) Judas Swing با قانون تست‌پذیر M15 (نسخهٔ دقیق‌تر از sweep ساده) | منبع: ICT / DT Terminal + AlgoKings

**نام و منبع**
- نام: Judas Swing (manipulation leg در Power of Three / AMD) با قانون reclaim نیمه‌شب
- قانون عددی تست‌پذیر: https://www.thedtterminal.com/academy/ict-power-of-three — تأیید شد. نقل نزدیک به متن: روی M15 و زمان نیویورک، قیمت زیر midnight open و زیر low بازهٔ آرام 00:00–02:00 معامله شود، سپس یک کندل M15 قبل از 05:00 **بالای midnight open کلوز کند**؛ هر دو بخش لازم است.
- توضیح مفهوم و سشن: https://www.algokings.net/learn/judas-swing-explained/ — تأیید شد (پنجره midnight تا 05:00 ET؛ نیاز به bias؛ ورود بعد از تأیید برگشت).
- زمینهٔ AMD روی طلا (ثانویه، برای نگاشت سشن): https://www.xauusdglobal.com/strategies/power-of-three-amd-gold/

**تفاوت صریح با ستاپ ردشدهٔ «LiqSweep+MSS+FVG»**
1. نقطهٔ مرجع اجباری = **قیمت 00:00 نیویورک (midnight open)** نه هر سوینگ.
2. شرط liquidity = شکستن **low/high بازهٔ آرام 00:00–02:00 NY** به‌علاوهٔ عبور از midnight open.
3. تأیید Judas = **کلوز M15 برگشتی نسبت به midnight open قبل از 05:00 NY** (قانون DT Terminal) — نه الزام MSS+FVG.
4. ورود پیشنهادی این نسخه: اولین stop-entry روی M5/M1 بعد از reclaim (سیگنال‌بار هم‌جهت توزیع) با SL آن‌سوی extreme manipulation؛ **FVG/OTE اجباری نیست** (اگر FVG دیدی اختیاری است، ولی هستهٔ سیگنال همان reclaim + سیگنال‌بار است).

**تایم‌فریم**
- شناسایی Judas: M15
- اجرا: M5 یا M1

**سشن (نیویورک)**
| جزء | NY time | UTC (EDT=UTC−4) | تهران (UTC+3:30) |
|---|---|---|---|
| Midnight open | 00:00 | 04:00 | 07:30 |
| Quiet range | 00:00–02:00 | 04:00–06:00 | 07:30–09:30 |
| پنجرهٔ Judas / London KZ | تا 05:00 | تا 09:00 | تا 12:30 |
| بعد از 05:00 NY | ستاپ Judas این قانون فایر نمی‌شود | — | — |

**تعاریف کد**
- `midnight_open` = قیمت در 00:00 America/New_York (last traded / open همان دقیقه).
- `quiet_low` = lowest low در [00:00, 02:00) NY؛ `quiet_high` = highest high همان بازه.
- **Bullish Judas (برای روز با bias صعودی)**:
  1. قبل از لندن bias صعودی داشته باش (مثلاً daily/H4 نزدیک discount و draw روی نقدینگی بالا — منبع می‌گوید bias لازم است؛ روش دقیق bias در این صفحه کامل نیست پس bias را پارامتر جدا کن: close روزانه قبلی، یا HH/HL روی H1).
  2. بین 00:00–05:00 NY: `low < midnight_open` و `low < quiet_low`.
  3. قبل از 05:00 NY یک M15 با `close > midnight_open` بسته شود.
- **Bearish Judas**: قرینه (`high > midnight_open` و `high > quiet_high` سپس M15 `close < midnight_open` قبل از 05:00).

**ورود قدم‌به‌قدم (خرید بعد از bullish Judas)**
1. شرایط ۱–۳ بالا برقرار شود → پرچم `judas_bull = true`.
2. روی M5، اولین سیگنال‌بار صعودی با close نزدیک high را بگیر که high آن بالاتر از high کندل قبلی است (H1 ساده بعد از reclaim).
3. Buy stop یک تیک بالای آن سیگنال‌بار.
4. اگر تا پایان 05:00 NY (یا تا ۳۰ دقیقه بعد از reclaim — پارامتر) تریگر نشد → لغو.

**SL**
- زیر extreme manipulation (زیر low جوداس) + بافر کوچک. AlgoKings برای فارکس majors حدود ۱۰–۲۰ پیپ بافر مثال زده؛ برای طلا آن عدد مستقیم قابل‌استفاده نیست — بافر را بر حسب ATR(M15)×0.1 یا مقدار ثابت دلاری قابل‌تنظیم بگذار.
- اگر فاصلهٔ entry تا extreme > ۸ دلار → یا رد برای چالش ۱۰۰۰ دلاری، یا سایز را به ریسک ثابت (مثلاً ۰.۵–۱٪) محدود کن.

**TP**
- هدف‌های رایج در منابع ICT (بدون آمار اجباری): سمت مخالف Asian range؛ سپس high/low روز قبل یا نقدینگی خارجی بعدی.
- حداقل منطقی کد: 1R و 2R؛ یا `quiet_high` به‌عنوان TP1 در خرید.

**فیلترها**
- بدون daily bias وارد نشو (AlgoKings).
- اگر قیمت کلوز کند و زیر/بالای open بماند بدون reclaim → breakout واقعی است نه Judas (DT Terminal / AlgoKings).
- از ورود روی خودِ sweep قبل از reclaim خودداری کن.

**آمار بک‌تست**
- **source gives no stats** قابل‌استناد برای winrate/XAUUSD در صفحات تأییدشده. (یک سایت ثانویه ادعاهای ۳–۴ بار در هفته و R:R کیفی دارد؛ چون پروموشنال/بدون متدولوژی است اینجا عدد نقل نمی‌شود.)

---

## جمع‌بندی دسته ۱ برای کدنویسی

| # | ستاپ | TF اجرا | سیگنال در روز (کیفی) | مناسب SL≤۸$ |
|---|---|---|---|---|
| 1 | H2/L2 | M5/M1 | زیاد (Brooks روی ۵م: ۱۰–۲۰ فرصت روی Emini) | بله با فیلتر ارتفاع سیگنال‌بار |
| 2 | Breakout Pullback | M5/M1 | متوسط | بله اگر PB فشرده باشد |
| 3 | Final Flag fail | M5/M15 | کم‌تر | اغلب نه روی M15؛ روی M1/M5 یا سایز کوچک |
| 4 | Wedge / MW | M5/M1 | متوسط | بله روی MicroWedge |
| 5 | Judas M15 reclaim | M15→M5 | معمولاً ۰–۱ در صبح | فقط اگر extreme نزدیک باشد |

همهٔ لینک‌های اصلی این فایل با WebFetch در همین نوبت باز و تأیید شدند (به‌جز صفحاتی که فقط به‌عنوان ارجاع ثانویه علامت خورده‌اند).
