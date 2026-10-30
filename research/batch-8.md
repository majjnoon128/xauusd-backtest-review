# بچ ۸ — پژوهش رایگان برای Watchdog (دادهٔ قیمت، تقویم خبری، پیام‌رسان)

**وضعیت:** جایگزین master-spec قبلی. رایان خودش `WATCHDOG_SPEC_FINAL` را می‌نویسد.  
**محدودیت پژوهش:** فقط صفحات عمومی و مستندات؛ بدون ثبت‌نام، ساخت اکانت، توکن، یا ارسال پیام.  
**زمان مشاهدهٔ شبکه از این باکس:** ۱۴۰۴/۰۸/۰۸ (۳۰ اکتبر ۲۰۲۶) — خروجی باکس از Amsterdam/NL (Cloudflare)، **نه ایران**.

---

## ۰) تست دسترس‌پذیری بدون احراز هویت (از همین باکس)

| هدف | نتیجهٔ مشاهده‌شده |
|---|---|
| `GET https://nfs.faireconomy.media/ff_calendar_thisweek.json` | HTTP **200**؛ آرایهٔ JSON با ۹۷ رویداد در هفتهٔ جاری نمونه؛ فیلدها: `title`, `country`, `date`, `impact`, `forecast`, `previous`؛ مقادیر `impact` در نمونه: High / Medium / Low / Holiday |
| `HEAD/GET https://api.telegram.org/` | HTTP **302** (پاسخ سرور)؛ `GET .../bot123:AA/getMe` → HTTP **401** `Unauthorized` (یعنی endpoint زنده است) |
| `HEAD https://tapi.bale.ai/` | HTTP **404** روی ریشه؛ `GET .../bot123:AA/getMe` → HTTP **403** با بدنهٔ JSON `Token not found` (یعنی host از NL پاسخ می‌دهد) |
| `https://docs.bale.ai/` | HTTP **200** |
| `https://core.telegram.org/bots/api` | HTTP **200** |
| `https://datafeed.dukascopy.com/datafeed/` | **timeout** از این باکس (قطع/بلاک مسیر؛ نتیجه‌گیری کلی برای ایران نیست) |
| Yahoo `GC=F` / `DX-Y.NYB` / `EURUSD=X` chart API | HTTP **200** بدون کلید |

این فقط وضعیت مسیر از NL است؛ فیلترینگ داخل ایران جداست.

---

## ۱) دادهٔ نزدیک‌به‌لحظه‌ای رایگان: XAUUSD (M1) و DXY / جایگزین EURUSD

### نکتهٔ مشترک دربارهٔ ایران
- بیشتر ارائه‌دهندگان غربی در مستندات عمومی‌شان «بلاک IP ایران» را جداگانه اعلام نمی‌کنند؛ آنچه صریح است معمولاً **محدودیت حوزهٔ قضایی / تحریم برای افتتاح حساب** است (مثلاً OANDA).
- هر جا «بلاک ایران» در جدول زیر «تأییدنشده» آمده یعنی در صفحات عمومی بررسی‌شده، سند صریح IP-block پیدا نشد.

### ۱.۱ OANDA v20 Practice
- **لینک:** [Development Guide](https://developer.oanda.com/rest-live-v20/development-guide/) · [Pricing stream](https://developer.oanda.com/rest-live-v20/pricing-ep/) · [Best practices](https://developer.oanda.com/rest-live-v20/best-practices/)
- **Practice REST:** `https://api-fxpractice.oanda.com`  
  **Practice Stream:** `https://stream-fxpractice.oanda.com`
- **تأخیر / نرخ به‌روزرسانی استریم:** حداکثر حدود **۴ قیمت در ثانیه** برای هر ابزار (پنجرهٔ ۲۵۰ms؛ در حرکت سریع همهٔ تیک‌ها ارسال نمی‌شود). heartbeat هر ۵ ثانیه (طبق صفحهٔ pricing stream).
- **Rate limit:** REST تا **۱۲۰ درخواست/ثانیه/IP** (اضافه → HTTP 429)؛ حداکثر **۲۰ استریم فعال/IP**؛ حداکثر **۲ اتصال جدید در ثانیه**.
- **پوشش طلا / DXY روی رایگان:** فلزات از جمله `XAU_USD` در API v20 پشتیبانی می‌شود (نیاز به حساب practice + personal access token). **شاخص DXY به‌عنوان نماد استاندارد OANDA در همین صفحات بررسی‌شده ذکر نشده**؛ برای پروکسی دلار معمولاً جفت‌هایی مثل `EUR_USD` استفاده می‌شود.
- **WebSocket/Stream:** بله (streaming HTTP طولانی‌عمر، نه لزوماً WS خام مرورگر).
- **ToS / حساب:** نیاز به اکانت fxTrade Practice و توکن شخصی. صفحهٔ unsupported/restricted: OANDA به ساکنان برخی کشورها (از جمله گزارش‌های رسمی/حقوقی مرتبط با حوزهٔ تحریم و صفحهٔ «unable to offer accounts») حساب نمی‌دهد — **افتتاح حساب practice برای مقیم ایران عملاً غیرممکن ارزیابی می‌شود** ([unsupported](https://help.oanda.com/none/en/unsupported.htm)، سیاست حوزهٔ قضایی محدود).
- **ایران / IP:** محدودیت اصلی در سطح **اقامت/هویت حساب** است؛ بلاک صرف IP در مستندات rate-limit ذکر نشده.

### ۱.۲ Twelve Data (Basic رایگان)
- **لینک:** [Pricing](https://twelvedata.com/pricing) · [Trial / Basic](https://support.twelvedata.com/en/articles/5335783-trial) · [Credits](https://support.twelvedata.com/en/articles/5615854-credits) · [Commodity / XAU/USD trial](https://twelvedata.com/exchanges/commodity)
- **محدودیت Basic ($0):** **۸ اعتبار API در دقیقه** و سقف روزانهٔ **۸۰۰/روز** (ریست نیمه‌شب UTC طبق صفحهٔ Credits)؛ **۸ اعتبار WebSocket آزمایشی**.
- **تأخیر:** صفحهٔ Pricing برای Basic می‌گوید **real-time forex** (و crypto / US equities). بازار Commodity در صفحهٔ exchange به‌عنوان Real-time فهرست شده؛ نماد آزمایشی **`XAU/USD`** صریحاً به‌عنوان trial symbol آمده. پوشش کامل commodities در جدول مقایسه برای پلن‌های بالاتر (Grow+) پررنگ‌تر است — برای production باید entitlement حساب بعد از ثبت‌نام چک شود (این پژوهش ثبت‌نام نکرد).
- **DXY:** در کاتالوگ forex عمومی، نماد شاخص DXY به‌عنوان جفت استاندارد دیده نشد؛ **جایگزین عملی: `EUR/USD`** (یا جستجوی `symbol_search` پس از داشتن کلید).
- **WebSocket:** اتصال آزمایشی `wss://ws.twelvedata.com/v1/quotes/price?apikey=...` با محدودیت trial (تا ۱ اتصال و تا ۸ نماد trial طبق صفحهٔ Trial). دسترسی کامل WebSocket طبق Intro/Pricing از پلن **Pro** به بالا.
- **ToS:** استفادهٔ internal / non-display روی Basic؛ redistribution و نمایش عمومی تابع شرایط لایسنس.
- **ایران:** سند عمومی IP-block یافت نشد (تأییدنشده).

### ۱.۳ Finnhub (Forex & Commodities — Basic/Standard رایگان شخصی)
- **لینک:** [Pricing Forex](https://api2.finnhub.io/pricing-forex-api) · [Docs](https://finnhub.io/docs/api) · [Websocket](https://finnhub.io/docs/api/websocket) · [Economic calendar](https://finnhub.io/docs/api/economic-calendar) · [Rate limit](https://www.finnhub.io/docs/api/rate-limit)
- **Rate limit (صفحهٔ Forex pricing):** Basic **۱۵۰ فراخوانی API / دقیقه**؛ Standard **۳۰۰ / دقیقه**؛ هر دو **$0/ماه** با لایسنس **Personal Use**.
- **پوشش:** جدول Forex شامل OHLC، Websocket، All Rates و اندیکاتورها (با تیک در جدول قیمت). نمادهای forex/فلزات از طریق API نمادها؛ طلا معمولاً به‌صورت جفت FX مانند مسیرهای `forex` (نیاز به کلید برای تأیید دقیق ticker — ثبت‌نام نشد). **DXY به‌عنوان جفت استاندارد ذکر نشده** → پروکسی `EUR/USD` یا اجزای سبد.
- **تأخیر:** در بسته‌های رایگان Forex به‌عنوان realtime/websocket تبلیغ شده؛ تأخیر دقیق میلی‌ثانیه‌ای در صفحهٔ قیمت‌گذاری عددگذاری نشده.
- **WebSocket:** بله (طبق جدول و docs/websocket).
- **ToS:** Personal Use؛ Terms اعمال می‌شود.
- **ایران:** سند IP-block عمومی یافت نشد (تأییدنشده). کلید API لازم است (مشاهده از باکس بدون کلید: HTTP 401).

### ۱.۴ Polygon / Massive (Currencies)
- **لینک:** [Currencies](https://massive.com/currencies) · [Subscriptions map](https://massive.com/knowledge-base/article/what-are-the-different-massive-subscriptions-i-can-use) · [Request limits](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis) · [Basic previous-day](https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data)
- **لایهٔ رایگان Basic:** برای هر کلاس دارایی (از جمله Currencies) **REST-only، دادهٔ end-of-day**؛ WebSocket و flat files از پلن‌های پولی شروع می‌شوند. طلا به‌صورت جفت forex مثل `C:XAUUSD` در Currencies قرار دارد (نه Stocks).
- **Rate limit رایگان:** طبق KB محدودیت REST، برای کلاس بدون اشتراک پولی حدود **۵ درخواست در دقیقه** برای آن asset class (به مقالهٔ request limit رجوع شود).
- **Realtime / M1 زنده روی رایگان:** خیر — Basic برای watchdog لحظه‌ای کافی نیست.
- **WebSocket رایگان:** خیر.
- **ToS / توافق صرافی:** realtime پولی نیاز به exchange agreements در داشبورد دارد.
- **ایران:** سند عمومی IP-block یافت نشد (تأییدنشده).

### ۱.۵ Alpha Vantage
- **لینک:** [Support / API key & limits](https://www.alphavantage.co/support/#api-key) · [Documentation](https://www.alphavantage.co/documentation/)
- **Rate limit رایگان:** **۲۵ درخواست API در روز** (و بدون سقف روزانه برای پروژه‌های open-source/educational تأییدشده طبق همان صفحه).
- **توابع مرتبط:** `FX_INTRADAY` (بازه ۱min … ۶۰min)، `CURRENCY_EXCHANGE_RATE`. طلا از مسیر physical currency (`from_symbol=XAU` / `to_symbol=USD`) در مستندات FX مطرح است.
- **تأخیر:** مستندات FX را realtime می‌نامند؛ برای حجم و تازگی عملی، سقف ۲۵/روز گلوگاه است — برای M1 پیوسته مناسب نیست.
- **WebSocket:** در لایهٔ رایگان عمومی ارائه‌شده نیست (REST).
- **DXY:** نماد شاخص استاندارد در docs اصلی دیده نشد → پروکسی EURUSD.
- **ایران:** سند IP-block یافت نشد (تأییدنشده).

### ۱.۶ TraderMade
- **لینک:** [Pricing](https://tradermade.com/pricing) · [Free tier PDF](https://marketdata.tradermade.com/docs/restful-api/free-tier.pdf) · آموزش WS trial در سایت
- **رایگان:** راهنمای Free Tier: دسترسی موقت حدود **۱ ماه** به `/live` و `/convert`؛ پس از پایان trial، `/live` و `/convert` قطع می‌شوند. `/minute_historical` و `/tick_historical` روی free در دسترس نیستند.
- **WebSocket:** trial کوتاه‌مدت در مطالب آموزشی؛ پلن‌های پولی شامل WebSocket.
- **پوشش طلا/FX:** Forex در پلن‌های تجاری؛ جزئیات entitlement رایگان بعد از trial در PDF محدود است.
- **برای watchdog دائمی رایگان:** مناسب نیست (trial زمان‌دار).
- **ایران:** تأییدنشده.

### ۱.۷ Tiingo FX
- **لینک:** [Tiingo blog / IEX alternatives (ذکر Starter)](https://www.tiingo.com/blog/iex-cloud-alternatives/) · [Forex API blog](https://www.tiingo.com/blog/forex-api/) · AsyncAPI websocket community mirror
- **Starter رایگان (طبق نوشتهٔ وبلاگ Tiingo):** حدود **۵۰ درخواست/ساعت**، **۱۰۰۰ درخواست/روز**، **۵۰۰ نماد یکتا/ماه** (اعداد از مطلب رسمی وبلاگ؛ داشبورد فعلی ممکن است عوض شود).
- **پوشش:** FX از جمله مسیرهایی مثل `XAUUSD` در مثال‌های جامعه/مستندات OpenAPI mirror؛ endpointهایی مانند `/tiingo/fx/top` و قیمت‌های historical با `resampleFreq` (پیش‌فرض ۵ دقیقه در برخی schemaها — برای M1 باید پارامتر صریح چک شود پس از داشتن توکن).
- **WebSocket:** بله (FX thresholdLevel در AsyncAPI)؛ یک اتصال به ازای توکن در گزارش‌های محدودیت رایج است.
- **ایران:** تأییدنشده.

### ۱.۸ Dukascopy
- **لینک:** [History ticks wiki](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/history-ticks/) · [Overview historical](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/)
- **ماهیت:** بیشتر **تاریخچهٔ تیک فشرده (bi5)** برای بک‌تست/دانلود؛ نه یک API رایگان سادهٔ «M1 زنده با کلید».
- **Realtime رایگان عمومی:** در صفحات بررسی‌شده به‌عنوان REST/WS رایگان keyless برای live M1 تبلیغ نشده؛ معمولاً از طریق پلتفرم/JForex یا دانلود تاریخی.
- **مشاهده از باکس:** `datafeed.dukascopy.com` از NL **timeout** شد.
- **ایران:** تأییدنشده؛ دسترس‌پذیری datafeed ناپایدار حتی از خارج.

### ۱.۹ MetaTrader5 (پکیج رسمی Python) + ترمینال دمو کارگزار
- **لینک:** [MQL5 Python Integration](https://www.mql5.com/en/docs/python_metatrader5) — `pip install MetaTrader5`
- **ماهیت:** پکیج به **ترمینال MT5 در حال اجرا** وصل می‌شود (IPC)، نه مستقیم به سرور ابری عمومی. توابع: `copy_rates_*` (از جمله `TIMEFRAME_M1`)، `copy_ticks_*`، `symbol_info_tick`.
- **تأخیر / realtime:** همان فید کارگزار دمو/لایو که ترمینال به آن وصل است (بدون عدد تأخیر ثابت در docs پکیج).
- **Rate limit API ابری:** ندارد (محدودیت محلی/کارگزار).
- **پوشش XAU / DXY:** وابسته به نمادهای Market Watch کارگزار (مثلاً `XAUUSD` یا `XAUUSD.x`)؛ DXY ممکن است نباشد → `EURUSD` به‌عنوان پروکسی.
- **محدودیت پلتفرم:** مستندات نصب مثال روی **ویندوز** متمرکز است؛ روی لینوکس/macOS رسمی محدود/غیرمستقیم است.
- **ایران:** خود پکیج بلاک جغرافیایی ندارد؛ محدودیت = آیا کارگزار دمو به مشتری ایرانی می‌دهد و آیا سرور watchdog می‌تواند ترمینال را ۲۴/۷ نگه دارد.

### ۱.۱۰ Yahoo Finance از طریق yfinance (غیررسمی)
- **لینک تأخیر رسمی Yahoo:** [Exchanges and data providers / delays](https://help.yahoo.com/kb/finance-for-web/exchanges-data-providers-yahoo-finance-sln2310.html)
- **نمادها (مشاهده بدون کلید از باکس):** `GC=F` (فیوچرز طلا COMEX)، `DX-Y.NYB` (شاخص دلار)، `EURUSD=X` (نرخ ارز).
- **تأخیر طبق جدول Yahoo:**  
  - **COMEX (`.CMX`) → ۳۰ دقیقه** → `GC=F` برای watchdog لحظه‌ای مناسب نیست.  
  - **ICE Futures US (`.NYB`) → ۳۰ دقیقه** → اگر `DX-Y.NYB` از همین منبع باشد، تأخیر ۳۰ دقیقه.  
  - **Currency Rates (`=X`) → Real-time** (طبق همان جدول) → `EURUSD=X` از نظر جدول Yahoo «Real-time» است، اما yfinance غیررسمی است و پایداری/ToS جداست.
- **WebSocket رسمی Yahoo برای این کاربرد:** خیر؛ yfinance از endpointهای chart/download اسکرپ/ناپایدار استفاده می‌کند.
- **ToS Yahoo:** صریحاً «Do not redistribute»؛ yfinance unofficial و بدون SLA.
- **ایران:** تأییدنشده؛ endpoint از NL پاسخ ۲۰۰ داد.

### جدول جمع‌بندی سریع (۱)

| منبع | M1/realtime رایگان؟ | طلا | DXY | WS | گلوگاه اصلی |
|---|---|---|---|---|---|
| OANDA practice | استریم قیمت بله | XAU_USD | نه (پروکسی FX) | استریم بله | افتتاح حساب برای ایران |
| Twelve Data Basic | forex RT با اعتبار محدود | XAU/USD trial | نامشخص → EURUSD | trial محدود؛ کامل از Pro | ۸/min و ۸۰۰/روز |
| Finnhub free FX | OHLC+WS (personal) | جفت FX | نه → پروکسی | بله | لایسنس شخصی + کلید |
| Massive Currencies Basic | خیر (EOD) | C:XAUUSD در پلن Currencies | — | خیر روی Basic | فقط EOD / ۵ rpm |
| Alpha Vantage | FX_INTRADAY ولی | XAU مسیر FX | نه | خیر | ۲۵/روز |
| TraderMade free | trial زمان‌دار | FX | — | trial | پایان trial |
| Tiingo Starter | محدود نرخ | XAUUSD در مثال‌ها | — | بله | ۵۰/ساعت |
| Dukascopy | تاریخی بیشتر | بله در تاریخچه | — | — | live رایگان شفاف نیست |
| MT5 Python+demo | بله از فید بروکر | وابسته به بروکر | وابسته | تیک ترمینال | ویندوز/دمو/پایداری |
| yfinance | طلا ۳۰min؛ FX جدول RT | GC=F تأخیری | DX تأخیری؟ | خیر | ToS + تأخیر |

---

## ۲) تقویم خبری رایگان و خوانا برای کد (Impact / Tier1)

### ۲.۱ Forex Factory — خروجی هفتگی JSON (پیشنهاد اصلی بدون کلید)
- **URL:** `https://nfs.faireconomy.media/ff_calendar_thisweek.json`  
  (هم‌خانواده: `.xml` / `.csv` / `.ics` روی همان host)
- **فرمت (مشاهدهٔ مستقیم از باکس، HTTP 200):** آرایه‌ای از اشیاء با کلیدهای:
  - `title` (رشته)
  - `country` (کد ارز/کشور مثل USD, EUR, …)
  - `date` (ISO 8601 با آفست، مثال نمونه: `2026-10-27T20:30:00-04:00`)
  - `impact` ∈ {`High`, `Medium`, `Low`, `Holiday`}
  - `forecast`, `previous` (رشته؛ می‌تواند خالی باشد)
- **معادل Tier1:** فیلتر عملی `impact == "High"` (در نمونهٔ همین هفته: ۲۳ رویداد High از ۹۷).
- **فرکانس به‌روزرسانی فایل:** طبق پیام خطای رسمی FF هنگام تجاوز از سقف (نقل در فروم برنامه‌نویسان FF، اوت ۲۰۲۴ به‌بعد): فایل export **حداکثر حدود یک‌بار در ساعت** به‌روز می‌شود؛ درخواست بیش از آن غیرضروری است.
- **Rate limit / بلاک:** همان منبع: حداکثر حدود **۲ دانلود export در ۵ دقیقه** (مستقل از نوع فایل). تجاوز → صفحهٔ HTML با متن **Request Denied** («You've exceeded the limit for Calendar Export requests…»). توصیهٔ عملی: کش محلی و refresh هر ۳۰–۶۰ دقیقه، نه polling ثانیه‌ای.
- **API رسمی با کلید:** ندارد؛ Fair Economy/FF مستندات developer جدا برای این JSON منتشر نکرده — استفاده = مصرف خوراک عمومی export.
- **مشاهده از باکس:** یک GET موفق بدون کلید.

### ۲.۲ Finnhub Economic Calendar
- **لینک:** [economic-calendar docs](https://finnhub.io/docs/api/economic-calendar)
- **Endpoint نمونهٔ مستند:** `GET /api/v1/calendar/economic?from=YYYY-MM-DD&to=YYYY-MM-DD&token=...`
- **Impact:** در مدل‌های کلاینت/نمونه‌ها فیلد impact با مقادیر high/medium/low.
- **رایگان؟** نیازمند API key؛ روی پلن رایگان شخصی Finnhub در دسترس بودن calendar تابع entitlements حساب است (بدون ثبت‌نام اینجا تأیید نشد). Rate همان سقف کلی API (۱۵۰ یا ۳۰۰/دقیقه روی بسته‌های forex رایگان لیست‌شده — calendar ممکن است در بستهٔ economic جدا قیمت‌گذاری شود؛ صفحهٔ [Economic Data pricing](https://www.finnhub.io/pricing-economic-data-api) را قبل از اتکا چک کنید).

### ۲.۳ Trading Economics (guest / API)
- **تقویم وب:** `https://tradingeconomics.com/calendar` (از باکس HTTP 200).
- **API:** [calendar/api](https://tradingeconomics.com/calendar/api) و [api](https://tradingeconomics.com/api/) — دسترسی برنامه‌نویسی معمولاً **پولی / نیاز به کلید**؛ «guest رایگان پایدار برای JSON کامل» در صفحات API به‌عنوان محصول رایگان دائم تبلیغ نشده.
- **نتیجه برای watchdog رایگان:** صفحهٔ HTML مهمان ≠ API کدخوان قابل اتکا بدون قرارداد.

### ۲.۴ Investing.com
- **صفحه:** `https://www.investing.com/economic-calendar/`
- **API عمومی رسمی برای تقویم:** یافت نشد.
- **Caveat اسکرپینگ:** شکننده (DOM/anti-bot)، مغایر ToS محتمل، بدون فیلد impact پایدار قراردادشده. برای بات production توصیه نمی‌شود.

### ۲.۵ Financial Modeling Prep (FMP)
- **Endpoint پایدار اعلام‌شده:** `https://financialmodelingprep.com/stable/economic-calendar`
- **مشاهده از باکس بدون کلید:** HTTP **401**.
- **پلن رایگان FMP:** در مطالب قیمت‌گذاری عمومی به سقف روزانهٔ فراخوانی اشاره شده؛ دسترسی دقیق calendar ممکن است پشت پلن/402 باشد — قبل از اتکا entitlement را چک کنید.
- **نتیجه:** بدون کلید اینجا قابل استفاده نبود.

### ۲.۶ JBlanked News Calendar API
- **لینک:** [Calendar API docs](https://www.jblanked.com/news/api/docs/calendar/) (آخرین به‌روزرسانی صفحه طبق خود سند: 02/07/2026)
- **احراز:** هدر `Authorization: Api-Key YOUR_API_KEY` (کلید از پروفایل — این پژوهش کلید نساخت).
- **Rate limit:** **یک درخواست در ثانیه**.
- **قیمت:** «otherwise free» با credit برای استفادهٔ premium.
- **منابع:** مسیرهای جدا برای MQL5 / Forex Factory / FxStreet؛ فیلتر `impact=High|Medium|Low|None` و `currency=...`.
- **نمونه فیلد پاسخ:** `Name`, `Currency`, `Impact`, `Date`, `Actual`, `Forecast`, `Previous`, …
- **نکته:** لایه روی FF و دیگران؛ برای کاهش وابستگی مستقیم به nfs.faireconomy هم مفید است، ولی باز هم نیاز به کلید دارد.

---

## ۳) ارسال پیام: Telegram Bot API و Bale Bot API

### ۳.۱ Telegram Bot API
- **Base:** `https://api.telegram.org/bot<token>/<METHOD>`  
  مستندات: [Bot API](https://core.telegram.org/bots/api) · FAQ محدودیت‌ها: [Bots FAQ](https://core.telegram.org/bots/faq)
- **sendMessage — طول متن:** **۱ تا ۴۰۹۶ کاراکتر** پس از parse موجودیت‌ها (طبق متد sendMessage).
- **Rate limits (FAQ رسمی «Broadcasting to Users»):**
  - در یک چت واحد: از **بیش از ۱ پیام در ثانیه** پرهیز کنید؛ burst کوتاه ممکن است تحمل شود؛ در ادامه HTTP **429**.
  - در **گروه:** حداکثر حدود **۲۰ پیام در دقیقه**.
  - **Bulk/global تقریبی:** حدود **۳۰ پیام در ثانیه** برای broadcast انبوه (مگر paid broadcasts).
- **دسترس‌پذیری از داخل ایران:** تلگرام در ایران به‌طور گسترده **فیلتر/محدود** است (DPI، مسدودسازی IP/SNI و گزارش‌های تحقیقات سانسور ۲۰۲۴–۲۰۲۵). **سرور بات باید بیرون ایران** به `api.telegram.org` وصل شود؛ کاربر داخل ایران معمولاً برای کلاینت تلگرام به ابزار عبور نیاز دارد. از این باکس (NL): API پاسخ می‌دهد (302/401).

### ۳.۲ Bale (بله) Bot API
- **مستندات:** [docs.bale.ai](https://docs.bale.ai/)  
  **Base معمولی:** `https://tapi.bale.ai/bot<TOKEN>/<METHOD_NAME>`  
  (نیز ارجاع تاریخی/آینه‌ای به `tapi.bale.ai` در جامعه)
- **سازگاری:** صریحاً بر پایهٔ Bot API تلگرام با تغییرات جزئی؛ بسیاری از کتابخانه‌های تلگرام قابل تطبیق‌اند.
- **sendMessage — طول متن:** **۱ تا ۴۰۹۶ کاراکتر** (پس از پردازش؛ طبق جدول sendMessage در docs.bale.ai).
- **Rate limit رسمی:** محدودیت به‌صورت **تعاملی** بر اساس میزان تعامل کاربران با بازو در چت شخصی؛ عدد ثابت «N پیام/ثانیه» در متن اصلی docs مثل تلگرام نوشته نشده. در خطا، `ResponseParameters.retry_after` (ثانیه) برمی‌گردد. برای ارسال انبوه، API کسب‌وکاری با مسیر  
  `https://tapi.bale.ai/business/bot<TOKEN>/...` و سهمیهٔ جدا (پس از شارژ پنل کسب‌وکار) معرفی شده.
- **اعداد غیررسمی شخص ثالث** (مثلاً ابزارهای یکپارچه‌سازی): حدود ۱ پیام/ثانیه per chat و حدود ۳۰/ثانیه سراسری — **این اعداد در docs.bale.ai به‌صورت جدول رسمی دیده نشد؛ به‌عنوان گزارش ثانویه علامت بزنید**.
- **دسترس‌پذیری از خارج ایران:** از این باکس (Amsterdam) `tapi.bale.ai` به درخواست جعلی توکن با JSON خطا پاسخ داد (**host از خارج NL قابل دسترس بود**). گزارش توسعه‌دهندهٔ `bale-mcp` نیز می‌گوید در تست از خروجی ترکیه پاسخ گرفته و در صورت شکست می‌توان proxy گذاشت. **جمع‌بندی:** دسترس از خارج **تأیید مشاهده‌ای از این باکس**؛ پایداری از همهٔ ASNها تضمین رسمی عمومی ندارد.
- **کاربر نهایی در ایران:** بله به‌صورت بومی در دسترس است → برای هشدار به کاربر ایرانی معمولاً **مسیر کم‌اصطکاک‌تر از تلگرام فیلترشده**.

---

## ۴) پشتهٔ پیشنهادی رایگان (کوتاه) و ریسک‌ها

### پیشنهاد عملی برای Watchdog رایگان
1. **قیمت XAU M1 + پروکسی دلار:**  
   - ترجیح هم‌تراز با اجرای واقعی پراپ: **MT5 Python + حساب دمو همان اکوسیستم/نماد نزدیک به SGB** (اگر سرور ویندوز دارید).  
   - بدون ترمینال: **Finnhub free forex (REST+WS، personal)** یا **Twelve Data Basic** برای `XAU/USD` + `EUR/USD` با رعایت سقف اعتبار.  
   - **DXY خام realtime رایگان قابل اتکا کمیاب است** → `EURUSD` به‌عنوان پروکسی؛ Yahoo `DX-Y.NYB` فقط با آگاهی از تأخیر جدول Yahoo.
2. **تقویم Tier1:**  
   - **FF JSON** بدون کلید + کش ≥۱ ساعت + رعایت سقف ۲/۵دقیقه؛ فیلتر `impact=High`.  
   - اختیاری: JBlanked یا Finnhub calendar پس از گرفتن کلید توسط رایان (خارج از این پژوهش).
3. **هشدار:**  
   - **Bale Bot** برای دریافت‌کننده در ایران؛ سرور می‌تواند خارج باشد (`tapi.bale.ai` از NL دیده شد).  
   - **Telegram** فقط اگر مخاطب با کلاینت عبور دارد؛ خودِ API را از سرور خارج ایران صدا بزنید.

### ریسک‌ها (صریح)
- **هیچ فید رایگان «بدون قید» تضمین SLA برای اسکالپ زیر چندثانیه نمی‌دهد.**  
- OANDA practice از نظر فنی عالی است ولی **درِ حساب برای مقیم ایران بسته** است.  
- Twelve/Finnhub/Tiingo: سقف نرخ، لایسنس personal، و احتمال تغییر پلن.  
- Massive Basic و Alpha Vantage free برای M1 زندهٔ پیوسته کافی نیستند.  
- Yahoo/yfinance: تأخیر COMEX ۳۰min برای طلا؛ ممنوعیت redistribution؛ شکنندگی غیررسمی.  
- FF JSON: بدون قرارداد رسمی؛ rate-limit و امکان بلاک؛ فقط خوراک هفتهٔ جاری.  
- اسکرپ Investing و مهمان TE: حقوقی/پایداری ضعیف.  
- تلگرام داخل ایران فیلتر است؛ بله rate رسمی «تعاملی» است و اعداد شخص ثالث را با احتیاط بخوانید.  
- این سند عدد اختراع نکرده؛ هر جا entitlement فقط بعد از signup معلوم می‌شود، صریحاً «تأیید نشد» نوشته شده.

---

*پایان بچ ۸ — پژوهش watchdog رایگان.*
