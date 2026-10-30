# دسته ۶ — Add-onها (فیلتر / خروج / پراپ / NDS) | بدون ستاپ جدید
تاریخ تهیه: ۱۴۰۴/۰۸/۰۸ (2026-10-30) | مخاطب: رایان | هدف: مکمل ستاپ‌های دسته ۱–۵ برای چالش SGB ۱۰۰۰ دلاری XAUUSD

قواعد:
- فقط Add-on؛ هیچ ستاپ جدیدی پیشنهاد نشده.
- هر مورد: لینک منبع + قوانین قابل‌کد؛ هرجا آمار نبود صریح نوشته شده.
- زمان‌ها: UTC و تهران (UTC+3:30). اکتبر ۲۰۲۶: NY هنوز EDT = UTC−4 مگر خلافش گفته شود.
- هیچ عدد بک‌تستی اختراع نشده.

---

# (۱) فیلترهای اسکالپ اینترادی طلا

## ۱.۱ ساعات / سشن‌های باکیفیت

**منبع A — ForexR Gold Scalping**  
https://forexr.com/learn/gold-scalping (WebFetch 2026-10-30)

قوانین قابل‌کد (از متن منبع):
- **Trade window:** London open + NY overlap **۸–۱۱ صبح وقت نیویورک**.
  - NY summer (EDT): ۸–۱۱ NY = **UTC 12:00–15:00** = تهران **۱۵:۳۰–۱۸:۳۰**.
  - نمونهٔ منبع برای آسیا: ۸–۱۱ p.m. KL/Singapore در تابستان آمریکا.
- **Avoid:** یک ساعت دو طرفهٔ **۵ p.m. NY break** (گسترده‌ترین اسپرد، رنج مرده).
  - ۵ p.m. NY EDT = UTC 21:00 → پنجرهٔ اجتناب تقریبی **UTC 20:00–22:00** / تهران ۲۳:۳۰–۰۱:۳۰.
- **Avoid:** ±۱۵ دقیقه اطراف NFP، CPI، FOMC decision.
- نمونهٔ سه‌ماههٔ ۱H منبع: بزرگ‌ترین متوسط hourly range از ۸ تا ۱۱ a.m. NY؛ ساعات آسیا آرام‌تر؛ ساعت ۵ p.m. NY هیچ‌چیز معامله‌پذیر نبود.
- **آمار:** منبع میانگین hourly range سه‌ماهه را کیفی توصیف می‌کند ولی جدول عددی کامل هر ساعت را در صفحه چاپ نکرده — **source gives no full hourly ADR table / no winrate**.

**منبع B — FXVPS News & Session Filters**  
https://fxvps.biz/knowledge-base/news-events-strategy-filters/ (WebFetch 2026-10-30)

| سشن | تقریبی UTC | ویژگی |
|---|---|---|
| Asian (Tokyo) | 00:00–08:00 | نوسان کم، رنج، نقدینگی نازک |
| London | 07:00–16:00 | بیشترین حجم، روند قوی‌تر، اسپرد تنگ‌تر |
| New York | 12:00–21:00 | حجم بالا، خبرمحور، fade عصر |
| **London–NY overlap** | **12:00–16:00** | بیشترین حجم؛ اگر فقط یک پنجره → این |

قابل‌کد پیشنهادی روی طلا (ترکیب A+B، پارامترهای صریح):
```
ALLOW if hour_utc in [7..15]   # London through early NY
PREFER if hour_utc in [12..15] # overlap
BLOCK if near_ny_5pm_break ±60m
BLOCK if mon before 08:00 UTC OR fri after 14:00 UTC  # FXVPS day filter
```
**آمار بک‌تست طلا:** ندارد (راهنمای عمومی EA/VPS).

## ۱.۲ فیلتر رژیم ADR و ATR

**منبع C — ForexR (همان صفحهٔ اسکالپ طلا)**  
https://forexr.com/learn/gold-scalping

قوانین قابل‌کد:
- واحد کار = ATR(14) روی تایم‌فریم معامله (مثال منبع: M5 ATR ≈ ۱.۸۰$ در overlap؛ M1 ≈ ۰.۶۰$ — **مثال‌اند نه ثابت**).
- Stop ≈ ۱×ATR؛ Target ≈ ۱.۵×ATR.
- **Spread filter:** اگر `spread > 0.25 × ATR` → تایم‌فریم خیلی کوچک است؛ بالا برو یا نگیر.
- در ساعات آرام ATR M5 می‌تواند به ۰.۶۰$ برسد → همان اسپرد ۰.۳۰$ نصف استاپ می‌شود → setup زنده نمی‌ماند.
- Risk rules صفحه: ≤۰.۵٪ per trade؛ daily stop = ۳ ضرر یا ۲٪ پایین، هرکدام زودتر؛ hard stop همیشه.

**آمار:** مثال‌های عددی آموزشی؛ **source gives no backtested winrate / expectancy**.

**منبع D — Forex Vitals ADR Methodology**  
https://forexvitals.com/articles/forex-volatility-adr-methodology (به‌روز Sep 2026)

فرمول:
```
ADR14 = mean(high-low) of last 14 completed daily bars
today_range = today_high - today_low
ADR_fill% = (today_range / ADR14) * 100
```
حالت‌ها (نمایش scanner؛ نه سیگنال جهت):
| ADR fill | State | سؤال عملی |
|---|---|---|
| <40% | Quiet | واچ‌لیست؛ ورود اجباری نکن |
| 40–70% | Developing | نزدیک‌تر نگاه کن |
| 70–100% | Active | اگر ساختار/سشن موافق |
| ≥100% | Breakout | ادامه ممکن؛ chase دیر؟ |
| ≥120% | Stretched | ورود دیر را سخت‌گیر کن / pullback |

نکات صریح منبع:
- ADR سقف نیست؛ خبر می‌تواند >100% ببرد.
- ADR ≠ ATR (ATR شامل gap از close قبلی است).
- **source gives no XAUUSD-specific stats** (ابزار روی ۲۸ جفت FX متمرکز است؛ منطق فرمول قابل‌انتقال است).

**منبع E — FXVPS ATR gate** (همان لینک B)

```
avgATR = mean(ATR(14) over last 50 bars)
too_hot  if currentATR > 2.0 * avgATR  → pause entries
too_cold if currentATR < 0.4 * avgATR  → false breakouts (در کد نمونهٔ خودشان 0.5–2.0)
percentile alt: trade only if ATR in 20th–80th percentile of last 252 bars
```
**آمار طلا:** ندارد.

**Codable stack پیشنهادی برای SGB طلا (پارامتر، نه ادعا):**
```
1) ATR_M5(14) >= 4 * typical_spread   # ForexR 0.25 rule با حاشیه
2) ADR_fill% in [25, 110]             # خیلی مرده یا خیلی کشیده را ببر
3) if ADR_fill% >= 90: reduce size or require pullback entry
```

## ۱.۳ تقویم خبر و فاصله از خبر

**منبع B — FXVPS** (بالا)

Tier 1 (باید فیلتر): NFP، FOMC+statement، US CPI/Core CPI، ECB rate، BoE rate، BoJ rate، US GDP Advance.  
Tier 2: PMI/ISM، Retail Sales، ADP/Jobless، minutes، Trade Balance، RBA/RBNZ/SNB.  
Tier 3: مسکن، اعتماد مصرف‌کننده، … — معمولاً بدون فیلتر یا ±۵د.

Blackout قابل‌کد:
```
Tier1: no NEW trades from T-30m to T+30m
Tier2: T-15m to T+15m
Tier3: none (or T±5m)
Open positions (scalp/intraday): close before Tier1 (option 1 recommended)
```
تقویم: MQL5 Calendar API / ForexFactory / TradingEconomics.

**منبع A — ForexR:** ±۱۵ دقیقه اطراف NFP/CPI/FOMC برای اسکالپ طلا.

**منبع F — FTMO (محدودیت بروکری/پراپ، نه فیلتر استراتژی)**  
https://ftmo.com/en/blog/updated-trading-conditions-for-the-dollar-index-dxy-and-xauusd/  
روی برخی حساب‌ها: از ۲ دقیقه قبل تا ۲ دقیقه بعد خبرهای منتخب، باز/ویرایش/بستن XAUUSD و DXY ممنوع.  
→ این قانون **بروکر/پراپ** است؛ با blackout استراتژی قاطی نشود. SGB طبق Consistry/Wikilix خبر را آزاد می‌داند (پایین).

**آمار:** هیچ‌کدام winrate فیلتر خبر روی طلا نمی‌دهند — **source gives no stats**.

## ۱.۴ فیلتر همبستگی DXY / US10Y

**منبع G — United Kings XAUUSD Correlation Playbook**  
https://unitedkings.net/xauusd-correlation-playbook-dxy-10y-yield-rules/ (WebFetch 2026-10-30)

توجه صداقت: سایت سیگنال تجاری است و «۸۵٪+ winrate» تبلیغ می‌کند — **آن ادعا را قبول نکن**؛ فقط آستانه‌های فیلتر را به‌عنوان قوانین practitioner گزارش می‌کنیم. بک‌تست peer-reviewed نیست.

قوانین قابل‌کد:
```
# رژیم‌ها
A) Clean inverse: DXY↑ → gold↓ (و برعکس) → فیلتر قوی
B) Risk-off both-up: DXY↑ و gold↑ → DXY گمراه‌کننده؛ وزن بیشتر به yields
C) Chop: DXY در رنج تنگ → DXY = neutral

# آستانهٔ DXY از open روز
|dxy_chg%| < 0.10  → neutral
0.10–0.20          → moderate; favor aligned trades
> 0.20             → strong impulse; don't fight unless news reversal setup

# آستانهٔ US10Y از open / prior close (bps)
0–2 bp  → noise
3–5 bp  → meaningful confirmation
6–10 bp → dominant; expect gold to respect yield direction

# Alignment score 0–3
+1 if XAUUSD structure supports trade
+1 if DXY direction supports (inverse most days)
+1 if 10Y direction supports (inverse most days)
TAKE if score >= 2; REDUCE/SKIP if score <= 1

# مثال رد long: DXY +0.20%+ AND 10Y +4–6 bp (منبع: "high friction")
# خبر: CPI/FOMC/NFP می‌تواند همبستگی را 5–30 دقیقه بشکند → صبر برای second move
```
سایزینگ همراه score (پیشنهاد منبع): 3/3 نرمال؛ 2/3 نرمال/کاهش؛ 1/3 نیم‌سایز یا skip؛ 0/3 skip.

**آمار معتبر:** **source gives no independent stats**؛ اعداد آستانه qualitative/practical از یک desk سیگنال‌اند.

---

# (۲) قوانین خروج و مدیریت معامله

## ۲.۱ Break-even و partials — Al Brooks

**منبع H — Day trading the 5-minute Emini**  
https://www.brookstradingcourse.com/futures-market/day-trading-5-minute-emini/

قوانین قابل‌کد (منطق Emini؛ برای طلا واحد را ATR/R جای ticks بگذار):
- Protective stop ابتدا یک تیک آن‌سوی سیگنال‌بار؛ یا ۴–۱۲ تیک بسته به اندازهٔ متوسط بار.
- اگر بخشی را swing می‌کنی: بعد از گرفتن **۴ تیک سود روی بخش scalp**، استاپ باقی‌مانده را به **breakeven** ببر.
- اغلب فقط scalp ۴ تیک سودآورتر است؛ در reversal قوی high/low روز یا روند قوی → swing بخشی یا همه.
- مثال مدیریت: نصف در ۴ تیک؛ ۲۵٪ دیگر نزدیک measured risk؛ باقی با stop روی BE.

**منبع I — Ask Al: Stop management & scaling in**  
https://www.brookstradingcourse.com/ask-al/trade-stop-management-scaling-in/

- طیف معقول: (الف) ناامید → کل پوزیشن روی BE خارج؛ (ب) partial + swing؛ (ج) کل را swing با stop ساختاری.
- Brooks: معمولاً وسط را انتخاب می‌کند؛ اگر ناامید باشد به‌ندرت کل را swing می‌کند.

**منبع J — Forum Reversals trade management**  
https://www.brookstradingcourse.com/support-forum/21-reversals/slide-8-trade-management-of-reversals/  
- TP روی نصف وقتی ≈۲:۱ R:R رسید؛ بقیه تا تکمیل TBTL.

**Codable پیش‌فرض برای ستاپ‌های دسته ۱–۵ روی طلا (نگاشت، نه آمار منبع):**
```
on fill:
  SL = structure invalidation
at +1.0R:  close 50%; move SL to entry (BE) on remainder
at +2.0R:  close another 25% OR trail
remainder: trail / structure exit
if price returns to entry without +1R and structure weakens: exit flat (Brooks "disappointed → BE")
```
**آمار XAUUSD:** **source gives no stats**.

## ۲.۲ Trailing

منابع عمومی در این دسته trailing اختصاصی طلا با عدد ثابت نمی‌دهند. نزدیک‌ترین‌ها:
- Brooks: بعد از scalp، stop روی BE؛ سپس مدیریت بر اساس pullback / EMA / measured move (صفحهٔ Emini).
- ForexR: اسکالپ را به «سویینگ» تبدیل نکن (swap، daily break، headline).
- PSRC Wake (TradingView، XAUUSD M15 — سیستم جدا): partial در R قابل‌تنظیم + BE؛ سپس ATR trail بعد از trail-activation R.  
  https://www.tradingview.com/script/U8rZmN1g-PSRC-Wake-Signal-Engine/  
  → فقط به‌عنوان الگوی معماری؛ **source gives no peer-reviewed edge claim you should trust blindly**.

Codable محافظه‌کار:
```
if unrealized_R >= 1.5:
  trail_stop = max(BE, close - k*ATR_M5)  # long; k≈1
  ratchet only in trade direction
```

## ۲.۳ Time-stop

**منبع B — FXVPS:** برای استراتژی سشن‌محور (مثل Asian breakout): اگر تا **14:00–15:00 UTC** به تارگت نرسید → ببند؛ لبهٔ سشن را به سشن بعدی نکشان.  
Dead zone **16:00–17:30 UTC** را بسیاری از اپراتورها کلاً حذف می‌کنند.  
جمعه: بستن ورودی‌ها تا **14:00 UTC** برای trend-followers.

**منبع A — ForexR:** سقف ۳ معامله در روز سپس بستن پلتفرم؛ اسکالپ را نگه ندار.

Codable:
```
MAX_HOLD_BARS_M5 = 24   # مثال ≈2h؛ پارامتر
if bars_in_trade >= MAX_HOLD_BARS and R < 1.0: exit market
if utc_time >= session_hard_exit: flatten
if daily_trades >= 3: no new entries (ForexR example)
```
**آمار:** ندارد.

---

# (۳) قوانین ریسک پراپ — ترجیحاً SGB

## ۳.۱ منابع عمومی تأییدشده

| منبع | لینک | نقش |
|---|---|---|
| Consistry SGB rules (verified Oct 19, 2026) | https://www.consistry.com/prop-firm-rules/sgb | خلاصهٔ Plan A + یادداشت‌های برنامه |
| Wikilix SGB (updated Sep 21, 2026) | https://wikilix.com/en/prop/sarmaye-gozare-bartar-sgb | Class A/B، tick-scalp، risk per position، payout |
| سایت رسمی | https://sarmayegozarebartar.com | **مرجع نهایی** — قبل از چالش با متن فارسی/رسمی تطبیق بده |

هر دو اگریگیتورند؛ اگر با سایت رسمی اختلاف بود، رسمی برنده است.

## ۳.۲ Plan / Class A (معادل Consistry «Plan A» / Wikilix «Class A»)

| مورد | مقدار | Codable |
|---|---|---|
| هدف فاز ۱ / ۲ | ۸٪ سپس ۴٪ | `target_p1=0.08; target_p2=0.04` |
| Daily loss | ۵٪ از **opening balance/equity روز**؛ ریست **00:00 UTC** | `daily_loss_limit = 0.05 * sod_balance`؛ floating profit سقف را بالا نمی‌برد (Consistry notes) |
| Max loss | ۱۲٪ **static** از بالانس اولیه | `floor = start_balance * 0.88`؛ هرگز حرکت نمی‌کند |
| نوع چک | balance **و** equity؛ حتی با slippage برخورد = fail | `if equity<=floor OR equity<=sod*(1-0.05): fail` |
| حداقل روز معامله | ۵ در هر فاز | |
| محدودیت زمان | فاز۱: ۳۰ روز تقویمی از اولین ترید (+ یک ۱۰روزه رایگان اگر در سود)؛ فاز۲: ۶۰ روز | |
| Consistency روز/درصد سود | **No consistency rule** عمومی (Consistry) | — |
| Tick scalp | سود معاملات سودده بسته‌شده در **<۳۰ ثانیه** حداکثر **۲۰٪** هدف فاز (یا سود قابل‌برداشت در funded)؛ بالاتر → reset حساب | `if sum(profit where hold_sec<30) > 0.20*phase_target: breach` |
| Risk همزمان / تک‌پوزیشن | Wikilix: زیان یک ترید یا مجموع باز همزمان ≤ **۳٪** بالانس زنده برای حساب‌های ۱K–۵۰K؛ **۲٪** برای ۱۰۰K/۲۰۰K؛ فقط-slippage عمدی حساب نمی‌شود | برای ۱۰۰۰$: `max_simultaneous_risk = 0.03 * live_balance` |
| EA / VPS | ممنوع (EA معاملاتی؛ ابزار risk OK؛ VPS ممنوع — Wikilix) | |
| News | مجاز بدون محدودیت؛ احتیاط اسپرد | |
| Weekend hold | مجاز؛ کریپتو وقتی FX بسته = ممنوع | |
| حساب فعال | حداکثر ۲؛ سقف ۲۵۰K per person | |
| عدم‌فعالیت | ۳۰ روز بدون ترید → بسته | |
| پلتفرم | فقط MT5؛ پرداخت USDT | |

## ۳.۳ Class B (Wikilix)

- هدف ۱۰٪ سپس ۵٪؛ daily ۵٪؛ max ۱۲٪ static؛ حداقل **۳** روز معامله.
- Tick scalp و risk% مشابه.
- Split/payout جزئیات در Wikilix (اولین برداشت بعد از ۳ هفته + حداقل روزها).

## ۳.۴ نگاشت عملی برای حساب ۱۰۰۰$ SGB

```
start = 1000
sod = balance_at_00_00_UTC
daily_floor_equity = sod * 0.95          # 5% daily
static_floor = 1000 * 0.88               # 880$  (12% static)
risk_per_setup_USD <= 8                  # از خواست پروژه؛ زیر سقف 3% (=30$) بماند
max_open_risk_sum <= 0.03 * live_balance # Wikilix
tick_scalp_profit_cap = 0.20 * phase_target_USD
  # Class A P1 target = 80$ → tick scalp cap = 16$
prefer hold_time >= 30s on winners       # برای نخوردن به سقف تیک‌اسکالپ
no EA execution; manual or semi with allowed risk tools only
```

**پیشنهاد عملیاتی (نه قانون پراپ):** daily soft-stop شخصی سخت‌تر از ۵٪ — مثلاً ۳ ضرر یا ۲٪ (ForexR) — تا به دیوار ۵٪ نرسی.

**آمار پاس‌نرخ چالش SGB:** در صفحات Consistry/Wikilix **source gives no pass-rate stats**.

---

# (۴) NDS، 123Flag، دکتر فازی الجیک / فازی لاجیک — گزارش صادقانه

## ۴.۱ هویت و نام

- در منابع فارسی عمومی، مدرس به‌صورت **دکتر ایرج جعفریان، ملقب به دکتر فازی لاجیک** (گاهی «فازی لاجیک» نوشته می‌شود؛ در پیام رایان: «Dr. Fazi Aljik» — همان فرد به‌نظر می‌رسد؛ املای لاتین استاندارد عمومی یافت نشد).
- NDS = **Nodal Displacement Sequencing** (توالی جابه‌جایی نودها).
- 123Flag = ستاپ اصلاحی شناخته‌شده داخل چارچوب NDS.

## ۴.۲ منابع عمومی یافت‌شده (همه آموزشی/تبلیغاتی جامعهٔ فارسی)

| # | منبع | لینک | نوع |
|---|---|---|---|
| 1 | پریسا نصر — آموزش NDS + PDF | https://parisanasr.com/nds-strategy/ و PDF https://parisanasr.com/wp-content/uploads/2024/09/NDS-Strategy-V1.2.pdf | بلاگ آموزشی فارسی؛ فایل به نام استاد/شاگردان |
| 2 | زورا اف‌ایکس — آموزش NDS (به‌روز Oct 15, 2026) | https://mag.zorafx.io/nds-strategy-tutorial/ | بلاگ آکادمی/پراپ |
| 3 | FXMaxi — ۵ پایهٔ NDS | https://fxmaxi.com/forexstrategy-nds/ | بلاگ استراتژی |
| 4 | Academia — «NDS Strategy English Version» | https://www.academia.edu/129627974/NDS_Strategy_English_Version | آپلود کاربر؛ peer-review نیست |

**یافت نشد:** مقالهٔ peer-reviewed، بک‌تست مستقل با نمونه/متدولوژی شفاف روی XAUUSD، یا مستند رسمی «دکتر فازی» با آمار out-of-sample.

**نتیجهٔ صادقانه:** مواد عمومی عمدتاً **ترویجی/آموزشی بلاگ**اند (گاهی با جدول مقایسه‌ای اغراق‌آمیز مثل «R:R 1:5 تا 1:10» یا «تأخیر صفر»). این‌ها را به‌عنوان claim آماری قبول نکن. برای کدنویسی فقط تعریف‌های تکراری بین بلاگ‌ها را به‌صورت **فرضیهٔ ساختاری** بنویس و بک‌تست جداگانه بخواه.

## ۴.۳ تعاریف تکراری قابل‌کد (از parisanasr + zorafx — توافق تقریبی)

**پنج پایه (کیفی):** Fractal، Cycles، Symmetry، Sequencing، Zero-Sum Game.

**نودها:**
- سقف‌ها: هر سقف بالاتر از N1 → N2؛ بالاتر از N2 → N3 سپس انتظار توزیع/ریزش.
- کف‌ها: S1 / S2 / S3 مشابه.
- در سطح پیشرفته برچسب‌ها به ۱،۲،۳ ساده می‌شوند.

**هوک (Hook):** consolidation / جمع‌شدگی؛ انتظار بسته شدن حول نود ۳؛ اصلاح تقریبی **۸۶.۴٪** طول حرکت قبلی (نسبت ویژهٔ این سبک؛ منبع آماری مستقل ندارد).

**رالی:** پس از دو هوک پشت‌سرهم، انتظار شروع Rally؛ جهت روند را روشن می‌کند (ادعای کیفی؛ zorafx/parisanasr).

**فلگ / 123Flag (ستاپ ورود اصلی در بلاگ‌ها):**
```
HTF bias: determine trend on M30/H1/H4
LTF: M1/M5 (و در متن‌ها M10) دنبال 123Flag در اصلاح

SELL (با bias نزولی):
  1) leg نزولی قوی
  2) اصلاح ضعیف به‌شکل flag با نودهای 1,2,3
  3) ورود short در انتهای اصلاح نود 3 / شکست flag / ناحیهٔ ≈86.4% اصلاح لگ اول
  4) SL بالای سقف محلی flag (نود 3)
  5) TP پله‌ای: حدود 1/3 در نواحی نود 1 و 2؛ باقی تا تقارن / نود 3 کلان HTF

BUY: قرینه در روند صعودی
```

**مدیریت خروج NDS (از همان بلاگ‌ها):** خروج پله‌ای؛ یک‌سوم در نقاط ۱ و ۲؛ ادامه تا هدف نهایی نود ۳ تایم بالاتر.

## ۴.۴ آنچه **نمی‌توان** ادعا کرد

- Winrate، expectancy، یا «۹۰٪ شروع روند بعد از هوک» (عبارت تبلیغاتی در برخی صفحات) → **بدون متدولوژی قابل‌تکرار = غیرقابل اتکا**.
- تعریف دقیق الگوریتمی «نود معتبر» در برابر «نویز M1» در منابع رایگان مبهم است؛ zorafx خودش اشتباه رایج را «شتاب در شمارش هر نوسان کوچک به‌عنوان نود» می‌داند.
- PDF Academia provenance نامشخص است.

**پیشنهاد برای رایان:** NDS/123Flag را **به‌عنوان ستاپ جدید کاتالوگ نکن** (طبق فرمان: از دسته ۶ فقط add-on). اگر بعداً بخواهند، اول یک spec کد از روی PDF + قوانین ابطال صریح بنویسند و روی XAUUSD M5/M15 بک‌تست کنند؛ تا آن روز فقط فیلتر/خروج/پراپ بالا را روی ستاپ‌های ۱–۵ سوار کنید.

---

# جمع‌بندی عملی برای روی ستاپ‌های دسته ۱–۵

```
ENTRY GATE (all must pass):
  session in London..NY (prefer overlap UTC 12–15)
  not in news blackout Tier1 ±30m / Tier2 ±15m
  not near NY 5pm break ±60m
  spread <= 0.25 * ATR_tf
  ATR not too_cold (<0.4–0.5×avg) and not too_hot (>2×avg)   # tune
  ADR_fill% not extreme for strategy (skip >120% chase unless pullback)
  DXY/10Y alignment score >= 2 for direction

PROP GATE (SGB 1k Class A):
  risk_USD <= 8 and <= 3% live balance (simultaneous sum)
  projected daily loss if stop hit keeps equity > sod*0.95
  equity cushion above static floor 880$
  avoid winner holds <30s accumulating >20% of phase target

EXIT DEFAULT:
  50% at 1R → BE
  trail / structure for rest
  time-stop if session edge or MAX_HOLD
```

## فایل‌ها
- این سند: `/workspace/trading-research/batch-6.md`
- دسته ۵ (سه ستاپ): `/workspace/trading-research/batch-5.md`
- اگر Add-on بیشتری لازم شد → `batch-7.md` (فعلاً موضوعات ۱–۴ در همین فایل جا شده‌اند).
