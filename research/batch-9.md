# بچ ۹ — منابع بدون کلید برای قیمت زندهٔ XAUUSD (<۱ دقیقه تأخیر)

**محدودیت:** فقط endpointهای **بدون signup و بدون API key**؛ هر منبع با درخواست واقعی بدون احراز از همین باکس تست شد (تعداد کم؛ بدون hammer).  
**خروجی باکس:** Amsterdam / NL (Cloudflare) — **نه ایران**. زمان نمونهٔ اصلی مقایسه: حدود ۱۵:۰۱ UTC در ۳۰ اکتبر ۲۰۲۶ (۱۸:۳۱ Asia/Tehran).  
**معیار تأخیر:** زنده یا تأخیر داده‌ای < ۱ دقیقه (نه صرفاً RTT شبکه).

---

## ۰) خلاصهٔ اجرایی

| وضعیت | منبع |
|---|---|
| **کار کرد و نزدیک به اسپات طلا** | Swissquote public BBO `XAU/USD`؛ `api.gold-api.com/price/XAU` |
| **کار کرد ولی پروکسی توکن طلا (نه اسپات FX)** | Binance PAXGUSDT؛ Kraken PAXGUSD/XAUTUSD؛ OKX PAXG-USDT/XAUT-USDT؛ Coinbase PAXG-USD؛ Bitfinex XAUT:USD؛ Bybit XAUTUSDT |
| **ناموفق از این باکس** | Dukascopy bi5 (timeout)؛ freeserv currentPrices (HTTP 204 خالی)؛ chart/json3 (403)؛ goldprice.org (403)؛ metals.live (TLS fail)؛ Kitco proxyها؛ Investing ajax عمومی |
| **بهترین انتخاب بدون کلید برای اسپات XAU** | **Swissquote public BBO** (bid/ask + `ts` میلی‌ثانیه، RTT≈۰٫۶s، age داده نزدیک صفر) |
| **بهترین M1 شمع بدون کلید روی پروکسی** | Binance `data-api` klines `PAXGUSDT` interval=`1m` (+ WS رسمی) — با شکاف قیمت نسبت به اسپات |

---

## ۱) Swissquote — فید عمومی BBO (اسپات XAU/USD)

- **URL تست‌شده:**  
  `https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD`
- **مستندات رسمی این endpoint عمومی:** صفحهٔ اختصاصی developer برای همین URL در سایت Swissquote **یافت نشد**. API رسمی نهادی Swissquote معمولاً FIX/قراردادی است ([صفحهٔ FIX نهادی](https://www.swissquote.com/en/institutional/solutions/technology/apis/forex)، [PDF مشخصات FIX](https://library.swissquote.com/cdn/2958/ql/sqfx-fix-api-specification-v3-1.pdf)). فهرست‌های شخص‌ثالث این URL را به‌عنوان فید عمومی ذکر کرده‌اند (مثلاً freepublicapis) — این **تأیید رسمی Swissquote نیست**.
- **مشاهده از باکس (نمونه):** HTTP **200**؛ RTT حدود **۰٫۵۹–۰٫۶۲ s**.  
  نمونهٔ کوتاه (پروفایل premium روی یک پلتفرم):
  ```json
  {"topo":{"platform":"SwissquoteCapitalMarkets","server":"Live7"},
   "spreadProfilePrices":[{"spreadProfile":"premium","bid":3921.336,"ask":3921.994,...}],
   "ts":1793372490923}
  ```
- **تأخیر داده:** فیلد `ts` میلی‌ثانیه؛ در یک نمونه skew نسبت به ساعت باکس حدود **+۰٫۲ s** (یعنی timestamp فید تقریباً همزمان با دریافت). معیار <۱ دقیقه: **بله**.
- **Rate limit مستند:** برای همین URL عمومی **مستند نشده** (unverified). نباید hammer کرد.
- **WebSocket:** روی این مسیر REST عمومی مشاهده نشد؛ استریم رسمی Swissquote در مسیر FIX نهادی است (نیاز حساب).
- **ToS:** استفادهٔ بدون قرارداد از فید کارگزار ممکن است خارج از شرایط رسمی باشد؛ redistribution/اتکای معاملاتی بدون لایسنس — **ریسک حقوقی تأییدنشده**. فقط به‌عنوان مشاهدهٔ فنی گزارش شد.
- **ایران:** محدودیت IP عمومی برای این URL در مستندات پیدا نشد (تأییدنشده). افتتاح حساب Swissquote جدا از این endpoint است.

---

## ۲) Gold API (`api.gold-api.com`) — قیمت XAU بدون کلید

- **URL:** `https://api.gold-api.com/price/XAU`  
  **Docs:** [gold-api.com/docs](https://gold-api.com/docs) · **ToS:** [gold-api.com/terms](https://gold-api.com/terms) (مؤثر ۱۰ سپتامبر ۲۰۲۶)
- **مشاهده:** HTTP **200**؛ RTT حدود **۱٫۲–۱٫۴ s**. نمونه:
  ```json
  {"currency":"USD","name":"Gold","price":3922.100098,"symbol":"XAU",
   "updatedAt":"2026-10-30T15:01:13Z","updatedAtReadable":"a few seconds ago"}
  ```
- **تأخیر داده:** در مقایسهٔ نزدیک‌همزمان، `updatedAt` حدود **۱۷ s** قبل از زمان باکس بود؛ دو درخواست با فاصلهٔ ۵ s همان `updatedAt` را برگرداندند → به‌روزرسانی قیمت ظاهراً در مقیاس ده‌ها ثانیه است، نه تیک‌به‌تیک. همچنان معمولاً **<۱ دقیقه**. Docs می‌گوید قیمت‌ها realtime در حافظه؛ عدد «هر ۳۰ ثانیه» در docs اصلی به‌صورت الزام نیامد (در مشاهدات ما cadence کندتر از تیک بود).
- **Rate limit:** Docs/ToS می‌گویند برای realtime «No Rate Limiting»؛ همزمان ToS سوءاستفاده (**چند درخواست در ثانیه**) را ممنوع و باعث ban IP می‌داند. عملاً: polling آرام.
- **WebSocket:** در docs بررسی‌شده اعلام نشده.
- **ToS:** as-is؛ بدون ضمانت دقت؛ استفادهٔ تجاری مجاز اعلام شده؛ spam ممنوع.
- **شکاف vs Swissquote mid (یک نمونه همزمان):** mid SQ ≈ **۳۹۲۱٫۶۶۵**؛ gold-api **۳۹۲۲٫۱۰** → شکاف حدود **+۰٫۴۴ $** (**+۰٫۰۱۱٪**). **یک نمونه ≠ آمار.**

---

## ۳) Dukascopy (freeserv / datafeed bi5)

- **مراجع:** [wiki historical ticks](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/history-ticks/)؛ widget host `freeserv.dukascopy.com`
- **تست‌ها از NL:**
  | درخواست | نتیجه |
  |---|---|
  | `.../2.0/?path=api/currentPrices&instruments=XAU/USD` | HTTP **204** بدنه خالی (دو بار) |
  | `.../chart/json3?...instrument=XAU/USD&period=1&limit=2` | HTTP **403** |
  | `datafeed.dukascopy.com/.../XAUUSD/...h_ticks.bi5` (ساعت جاری UTC) | **timeout** (~۲۰s)، بدون بایت |
- **نتیجه برای watchdog زنده بدون کلید از این باکس:** **قابل اتکا نبود**. bi5 اصولاً آرشیو ساعتی است نه استریم زندهٔ تضمینی؛ و از NL هم timeout شد.
- **Rate limit / WS رسمی keyless:** برای این مسیرهای تست‌شده مستند شفاف مشاهده‌ای موفق نداشتیم.
- **ایران / NL:** شکست مسیر از NL است؛ ربط قطعی به ایران ندارد.

---

## ۴) منابع وب طلا/خبری (بدون کلید)

| منبع | نتیجه مشاهده |
|---|---|
| `https://data-asg.goldprice.org/dbXRates/USD` | HTTP **403** Forbidden |
| `https://api.metals.live/v1/spot/gold` | خطای TLS (`unrecognized name`) |
| Kitco proxy / webapi حدس‌زده | 502 / 404 / fail |
| Investing `instruments_ajax` | HTTP **404** HTML |
| `goldapi.io` بدون کلید | HTTP **403** `No API Key provided` (پس خارج از scope این بچ) |

هیچ‌کدام به‌جز مسیرهای بخش ۱–۲ و صرافی‌های بخش ۵، JSON زندهٔ قابل اتکا بدون کلید ندادند.

---

## ۵) پروکسی‌های PAXG / XAUT روی APIهای عمومی صرافی (بدون کلید)

**هشدار مشترک:** این‌ها قیمت **توکن طلای توکنیزه‌شده** (یا جفت USDT) هستند، نه لزوماً همان XAUUSD اسپات کارگزار. پریمیوم/دیسکانت، نقدشوندگی، معاملهٔ ۲۴/۷ در برابر تعطیلی آخرهفتهٔ بازار طلا، و انحراف USDT↔USD همه باعث شکاف می‌شوند. اعداد شکاف زیر **یک نمونهٔ نزدیک‌همزمان**اند، نه آمار.

مرجع اسپات همان لحظه: **Swissquote mid (premium روی نمونه) ≈ ۳۹۲۱٫۶۶۵**

### ۵.۱ Binance — PAXGUSDT
- **REST بدون کلید (توصیه‌شده market-data):**  
  `https://data-api.binance.vision/api/v3/ticker/bookTicker?symbol=PAXGUSDT`  
  `https://data-api.binance.vision/api/v3/klines?symbol=PAXGUSDT&interval=1m&limit=2`  
  نیز `https://api.binance.com/...` برای همین endpointها کار کرد.  
  **Docs:** [Market data only](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) · [REST](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-api-information) · raw [rest-api.md](https://raw.githubusercontent.com/binance/binance-spot-api-docs/refs/heads/master/rest-api.md)
- **مشاهده:** HTTP **200**؛ RTT ticker حدود **۱٫۳–۱٫۷ s**. نمونه bookTicker:  
  `bidPrice=3931.80 askPrice=3931.81`  
  klines `1m`: آرایه با openTime میلی‌ثانیه (شمع جاری باز).
- **تأخیر:** تیکر زنده؛ serverTime Binance در نمونه ≈ چند ثانیه نسبت به باکس (اختلاف ساعت/مسیر؛ دادهٔ بازار لحظه‌ای). **<۱ دقیقه: بله.**
- **Rate limit (مستند، بر اساس IP نه کلید):** حدود **۶۰۰۰ request weight / دقیقه** و سقف raw requests؛ weight کلاین/price معمولاً ۲؛ تجاوز → ۴۲۹، تکرار → بن ۴۱۸.
- **WebSocket:** بله — `data-stream.binance.vision` / استریمهای اسپات (مثلاً `paxgusdt@bookTicker`). handshake ارتقا از این باکس به وضعیت ۱۰۱ رسید (endpoint زنده).
- **شکاف vs SQ mid (یک نمونه):** mid ≈ **۳۹۳۱٫۸۱** → **+۱۰٫۱۴ $** (**+۰٫۲۶٪**).
- **ToS / ایران:** فهرست ممنوعهٔ Binance (به‌روزرسانی ۵ ژانویه ۲۰۲۶ در PDFهای حقوقی Binance) **ایران** را در کشورهای ممنوع برای ثبت‌نام/استفاده از سرویس‌ها دارد؛ دور زدن با VPN صریحاً ممنوع اعلام شده. اینکه آیا صرفاً خواندن market-data عمومی از IP خارج ایران برای مقیم ایران مجاز است یا نه — **تفسیر حقوقی قطعی اینجا نمی‌دهیم**؛ فقط وجود ممنوعیت سرویس برای ایران را گزارش می‌کنیم.

### ۵.۲ Kraken — PAXGUSD و XAUTUSD
- **URL:**  
  `https://api.kraken.com/0/public/Ticker?pair=PAXGUSD`  
  `https://api.kraken.com/0/public/Ticker?pair=XAUTUSD`  
  OHLC عمومی: `/0/public/OHLC?pair=...&interval=1`  
  **Docs:** [Historical/public data](https://docs.kraken.com/exchange/guides/general/historical-data) · [Rate limits](https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-) · WS: [FAQ](https://support.kraken.com/articles/360022326871-kraken-websocket-api-frequently-asked-questions) `wss://ws.kraken.com/`
- **مشاهده:** HTTP **200**؛ RTT حدود **۰٫۲۰–۰٫۲۹ s**.  
  PAXGUSD نمونه: bid **۳۹۲۴٫۶۳** ask **۳۹۲۵٫۴۵**  
  XAUTUSD نمونه: bid **۳۹۱۴٫۰۰** ask **۳۹۱۴٫۲۰**
- **Rate limit:** endpointهای public بر اساس IP؛ توصیهٔ رسمی تقریباً **≤۱ درخواست/ثانیه** برای ماندن داخل سقف.
- **WebSocket:** بله (عمومی بدون کلید).
- **شکاف vs SQ mid (یک نمونه):** PAXG mid **+۳٫۳۸ $ (+۰٫۰۸۶٪)**؛ XAUT mid **−۷٫۵۷ $ (−۰٫۱۹۳٪)**.
- **ایران:** Terms/پشتیبانی Kraken ایران را حوزهٔ ممنوع/غیرقابل‌خدمت اعلام می‌کند.

### ۵.۳ OKX — XAUT-USDT و PAXG-USDT
- **URL:**  
  `https://www.okx.com/api/v5/market/ticker?instId=XAUT-USDT`  
  `.../ticker?instId=PAXG-USDT`  
  **Docs:** [OKX API v5](https://www.okx.com/docs-v5/en/) — کانال عمومی WS: `wss://ws.okx.com:8443/ws/v5/public` (طبق docs)
- **مشاهده:** HTTP **200**؛ RTT حدود **۰٫۱۴–۰٫۱۶ s**. فیلد `ts` میلی‌ثانیه در پاسخ.  
  XAUT نمونه bid/ask **۳۹۱۹٫۷ / ۳۹۱۹٫۸**؛ PAXG **۳۹۳۱٫۳ / ۳۹۳۱٫۹**
- **Rate limit:** بسیاری از endpointهای public حدود **۲۰ درخواست / ۲ ثانیه / IP** (طبق راهنمای OKX؛ جزئیات per-endpoint در docs).
- **WebSocket:** بله (عمومی).
- **شکاف vs SQ mid (یک نمونه):** XAUT mid **−۱٫۹۲ $ (−۰٫۰۴۹٪)**؛ PAXG mid **+۹٫۹۴ $ (+۰٫۲۵٪)**.
- **ایران:** افشاگری‌های compliance OKX مکان‌های محدود/ممنوع را شامل می‌کند؛ ایران در دستهٔ محدود ذکر شده در مطالب compliance — برای استفادهٔ سرویس حساب، ممنوع/محدود؛ خواندن صرفاً public از خارج: تفسیر قطعی unverified.

### ۵.۴ Coinbase Exchange — PAXG-USD
- **URL:** `https://api.exchange.coinbase.com/products/PAXG-USD/ticker`  
  **Docs rate:** [CDP rate limits](https://docs.cdp.coinbase.com/exchange/introduction/rate-limits-overview) — public REST حدود **۱۰ req/s per IP** (burst تا ۱۵). WS: `wss://ws-feed.exchange.coinbase.com`
- **مشاهده:** HTTP **200**؛ RTT حدود **۰٫۰۸–۰٫۱۰ s**. نمونه: bid **۳۹۲۵٫۰۵** ask **۳۹۲۶٫۶۴**؛ فیلد `time` ISO با دقت بالا.
- **شکاف vs SQ mid (یک نمونه):** mid **+۴٫۱۸ $ (+۰٫۱۰۷٪)**.
- **ایران:** Developer Platform ToS حوزهٔ تحریم جامع (از جمله ایران) را برای استفاده از سرویس‌ها ممنوع می‌کند مگر استثنای قانونی.

### ۵.۵ Bitfinex — tXAUT:USD
- **URL:** `https://api-pub.bitfinex.com/v2/ticker/tXAUT:USD`  
  **Docs:** [REST ticker](https://docs.bitfinex.com/reference/rest-public-ticker) · [WS public](https://docs.bitfinex.com/docs/ws-public) · limits: [Requirements](https://docs.bitfinex.com/docs/requirements-and-limitations) — REST عمومی حدود **۹۰ req/min**؛ WS حدود ۲۰ اتصال/دقیقه و تا ۲۵ کانال/اتصال.
- **مشاهده:** HTTP **200**؛ RTT ≈ **۰٫۲۱–۰٫۲۲ s**. آرایه: `[bid, bidSize, ask, askSize, ...]` نمونه bid **۳۹۲۱٫۴** ask **۳۹۲۳٫۹**.
- **شکاف vs SQ mid (یک نمونه):** mid **+۰٫۹۹ $ (+۰٫۰۲۵٪)**.
- **ایران:** در این دور، متن ToS Bitfinex برای ایران جداگانه باز و نقل نشد — **unverified** در این سند.

### ۵.۶ Bybit
- **PAXGUSDT:** HTTP 200 ولی `retCode=10001` **Not supported symbols**.
- **XAUTUSDT:** HTTP **200**؛ RTT ≈ **۱٫۱۴ s**. نمونه bid **۳۹۲۲٫۱** ask **۳۹۲۲٫۱۱**.  
  Docs عمومی Bybit v5 market tickers — WS عمومی هم دارد (در این دور فقط REST تست شد).
- **شکاف:** در موج مقایسهٔ اصلی همزمان شرکت داده نشد؛ در نمونهٔ جدا mid ≈ ۳۹۲۲٫۱ نزدیک به SQ آن لحظه (فاصلهٔ زمانی جدا → برای جدول شکاف اصلی استفاده نشد).
- **ایران:** جزئیات ToS در این دور به‌طور کامل verify نشد — علامت **unverified**.

---

## ۶) جدول شکاف یک‌نمونه‌ای (نزدیک‌همزمان، NL)

مرجع: Swissquote mid ≈ **۳۹۲۱٫۶۶۵** در همان دسته درخواست‌ها (۱۵:۰۱:۳۰ UTC).

| منبع | mid / price | Δ$ | Δ% |
|---|---:|---:|---:|
| gold-api XAU | 3922.100 | +0.44 | +0.011% |
| Bitfinex XAUT | 3922.650 | +0.99 | +0.025% |
| OKX XAUT | 3919.750 | −1.92 | −0.049% |
| Kraken PAXG | 3925.040 | +3.38 | +0.086% |
| Coinbase PAXG | 3925.845 | +4.18 | +0.107% |
| Kraken XAUT | 3914.100 | −7.57 | −0.193% |
| OKX PAXG | 3931.600 | +9.94 | +0.253% |
| Binance PAXG | 3931.805 | +10.14 | +0.259% |

**این یک نمونه است، نه آمار.** پریمیوم PAXG روی برخی صرافی‌ها در این لحظه واضح‌تر از XAUT بود (و بالعکس روی Kraken). بازار طلا آخرهفته بسته می‌شود؛ توکن‌ها ۲۴/۷ معامله می‌شوند → در گپ‌ها شکاف می‌تواند بزرگ شود.

---

## ۷) بهترین انتخاب بدون کلید و ریسک‌ها

### انتخاب اول (اسپات XAU نزدیک به کارگزار، بدون کلید)
**Swissquote public BBO**  
`https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD`  
- چرا: HTTP 200 پایدار از NL، bid/ask واقعی، `ts` تازه (<۱s)، RTT زیر ۱s، بدون کلید.  
- ریسک‌ها: **بدون مستند رسمی عمومی / بدون rate limit اعلام‌شده**؛ ممکن است هر زمان قطع یا محدود شود؛ وضعیت ToS برای مصرف بات تأیید نشده؛ CORS ندارد (برای مرورگر مستقیم مشکل؛ برای سرور OK).

### انتخاب دوم (ساده، بدون کلید، اسپات تقریبی)
**gold-api.com `/price/XAU`**  
- چرا: docs و ToS واضح، بدون کلید، شکاف نمونه ناچیز vs SQ.  
- ریسک‌ها: به‌روزرسانی کندتر از تیک؛ بدون WS؛ as-is؛ ban در صورت spam؛ منبع قیمت زیرین در docs شفاف نیست.

### اگر M1 شمع + WS بدون کلید لازم است (پروکسی)
**Binance `data-api` PAXGUSDT** (یا Kraken/OKX XAUT|PAXG)  
- چرا: klines 1m و WS مستند، بدون کلید روی market-data.  
- ریسک‌ها: **پروکسی توکن ≠ XAUUSD**؛ شکاف مشاهده‌شده تا حدود ۰٫۲۶٪؛ USDT؛ نقدشوندگی؛ ToS صرافی‌ها ایران را برای سرویس حساب ممنوع می‌کند؛ برای سیگنال اسکالپ SGB روی نماد بروکر ممکن است کافی نباشد.

### غیرقابل اتکا در این تست
Dukascopy freeserv/bi5 از NL، goldprice.org، metals.live، Kitco حدسی، Investing ajax.

### آیا موضوع معتبری برای بچ بعدی باقی است؟
برای **دادهٔ اسپات XAU بدون کلید**، دو مسیر عملی (Swissquote public + gold-api) همین‌جا پوشش داده شد. ادامهٔ مفید فقط اگر رایان بخواهد: (الف) پایداری/رفتار rate-limit Swissquote با مانیتور آرام چندساعته، یا (ب) کالیبراسیون آماری شکاف PAXG/XAUT در ساعات لندن/نیویورک — نه کشف منبع keyless اسپات جدیدِ بدیهی. **منبع keyless اسپات سومِ معتبر در این دور پیدا نشد.**

---

*پایان بچ ۹ — فقط منابع بدون کلید؛ اعداد فقط از مشاهده یا نقل مستند.*
