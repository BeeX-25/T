# SmartTV Bridge — حوّل تلفازك إلى نظام ذكي بجوال قديم

خدمة **Python بدون أي مكتبة خارجية** تعطيك: ريموت من الجوال، ومكتبة قنوات
وأفلام ومسلسلات قابلة للبحث، وتشغيلاً على شاشة التلفاز، وأتمتة بمواعيد —
وتعمل على **جوال أندرويد** (Termux) أو راسبيري باي أو أي حاسوب قديم.

---

## أولاً: ما الذي تحتاجه فعلاً؟ (بصراحة)

الفيديو لا يصل إلى تلفاز غير ذكي إلا عبر شيء موصول بمنفذ HDMI — هذه حقيقة
فيزيائية لا يلتفّ عليها أي برنامج. لكن هذا "الشيء" غالباً موجود عندك:

| حالتك | ما تحتاجه | ماذا تحصل |
| --- | --- | --- |
| **جوال أندرويد قديم** (ولو مكسور الشاشة) | كبل/محوّل USB‑C → HDMI (بسعر وجبة) | كل شيء: بث + ريموت + مكتبة |
| **جوالك فيه بليستر IR** (شاومي/ريدمي/بوكو وكثير من هواوي) | لا شيء إطلاقاً | تحكم كامل بالتلفاز (تشغيل/صوت/قنوات/أزرار) — بدون بث |
| **تلفازك ذكي أصلاً** (سامسونج/LG) لكن ريموته ضاع أو تريد أتمتته | لا شيء، فقط واي فاي | تحكم كامل عبر الشبكة + تشغيل التطبيقات |
| **مستقبِل/رسيفر أو صندوق أندرويد قديم** موصول أصلاً | لا شيء | تحكم عبر HDMI‑CEC + مكتبة |
| لا هذا ولا ذاك | جوال أندرويد مستعمل رخيص | أرخص "صندوق بث" ممكن |

> ملاحظة مهمة: بعض الجوالات لا تُخرج صورة عبر USB‑C (تحتاج دعم DisplayPort
> Alt Mode). تحقّق من موديل جوالك قبل شراء المحوّل. وإن كان تلفازك يدعم
> Miracast، يمكنك العرض لاسلكياً من الجوال بدون كبل أصلاً.

كل واحدة من هذه الحالات لها "واجهة" جاهزة في المشروع، والخدمة تختار
تلقائياً أول واجهة متاحة تدعم الأمر المطلوب:

```
جوالك ──HTTP──▶ الخدمة (على جوال قديم أو أي جهاز)
                   ├── ir       → أشعة تحت حمراء من بليستر الجوال (بدون أي كبل)
                   ├── cec      → عبر كبل HDMI نفسه (تشغيل/إطفاء/أزرار)
                   ├── samsung  → واي فاي (Tizen)
                   ├── webos    → واي فاي (LG)
                   └── player   → VLC على الأندرويد أو mpv على اللينكس
```

---

## التثبيت على جوال أندرويد (الطريق الموصى به)

1. ثبّت من **F‑Droid** (وليس متجر جوجل): تطبيق **Termux**، ومعه
   **Termux:API** (للأشعة وللصوت)، و**Termux:Boot** (للتشغيل التلقائي).
2. افتح Termux ونفّذ:

```bash
pkg install git
git clone <رابط هذا المستودع> smarttv && cd smarttv
sh scripts/install_termux.sh
```

3. عدّل `~/.smarttv/config.json`: فعّل `tv.ir` واختر ماركة تلفازك، أو فعّل
   `samsung`/`webos` إن كان تلفازك ذكياً.
4. شغّل الخدمة:

```bash
termux-wake-lock && python3 -m smarttv --config ~/.smarttv/config.json
```

5. افتح من أي جوال على نفس الشبكة: `http://IP-الجوال:8099` وأضف الصفحة إلى
   الشاشة الرئيسية لتعمل كتطبيق.

**لعرض الصورة على التلفاز:** وصّل الجوال بالتلفاز عبر USB‑C → HDMI، وحين
تضغط أي عنصر في المكتبة سيفتح في VLC على شاشة التلفاز مباشرة.

### على راسبيري باي أو حاسوب لينكس

```bash
sudo sh scripts/install.sh     # يثبّت cec-utils و mpv وخدمة systemd
```

### للتجربة بدون أي جهاز

```bash
python3 -m smarttv --demo      # تلفاز وهمي، الواجهة تعمل بالكامل
```

---

## المكتبة: القنوات والأفلام والمسلسلات

المشروع **لا يحتوي على أي محتوى ولا يوفّر مصادر**، بل يقرأ الصيغ المفتوحة
التي يستعملها العالم كله: **M3U** للقوائم و**XMLTV** لدليل البرامج. أنت
تختار المصادر في `config.json`، وهي عادة أحد ثلاثة:

1. **قنوات مفتوحة مجاناً (Free‑to‑Air):** مشروع `iptv-org` يفهرس بثوث
   القنوات المتاحة للعموم، مثل:
   `https://iptv-org.github.io/iptv/languages/ara.m3u`
   ودليل برامجها: `https://iptv-org.github.io/epg/guides/ar.xml`
2. **اشتراك تدفعه أنت:** أي مزوّد يعطيك رابط M3U — ضعه كما هو.
3. **مكتبتك الخاصة:** ملفاتك على القرص أو مخدم Jellyfin/Plex، صدّرها كملف
   M3U وأشِر إليه بـ `path`.

```json
"catalog": {
  "sources": [
    { "name": "قنوات عربية", "type": "m3u",   "kind": "live",   "url": "https://iptv-org.github.io/iptv/languages/ara.m3u" },
    { "name": "دليل البرامج", "type": "xmltv",                    "url": "https://iptv-org.github.io/epg/guides/ar.xml" },
    { "name": "أفلامي",      "type": "m3u",   "kind": "movies", "path": "~/media/movies.m3u" },
    { "name": "مسلسلاتي",    "type": "m3u",   "kind": "series", "path": "~/media/series.m3u" }
  ]
}
```

ما تحصل عليه في الواجهة: تبويبات (مباشر / أفلام / مسلسلات / المفضلة / أكمل
المشاهدة)، بحث فوري، تصنيف حسب المجموعات، شعارات القنوات، تجميع حلقات
المسلسل تحت اسم واحد (يفهم `S01E02` و«الحلقة ١٢»)، ومتابعة من حيث توقفت.

> أنت المسؤول عن قانونية المصادر التي تضيفها؛ المشروع لا يوزّع محتوى ولا
> يفكّ حماية ولا يفهرس مصادر مقرصنة.

---

## التحكم بالأشعة تحت الحمراء (بدون أي جهاز)

إن كان جوالك فيه بليستر IR فهو ريموت كامل. فعّل في الإعدادات:

```json
"ir": { "enabled": true, "brand": "samsung" }
```

الماركات المدمجة: `samsung` و`lg` و`sony` و`philips` و`generic_nec`.
البروتوكولات مبنيّة من توقيتاتها المنشورة (NEC، Samsung32، SIRC، RC5)، فإن
لم يستجب زر معيّن في موديلك أضف أكوادك الخاصة:

```json
"ir": {
  "enabled": true,
  "brand": "my_tv",
  "brands": {
    "my_tv": { "protocol": "nec", "address": 4, "keys": { "power": 8, "volume_up": 2 } }
  }
}
```

ومن عنده جهاز LIRC يستطيع استبدال أمر الإرسال كاملاً:
`"command": "irsend SEND_ONCE tv {key}"`.

**حدّ صريح:** الأشعة اتجاه واحد — لا يمكنها قراءة حالة التلفاز أبداً. لذلك
هذه الواجهة لا تعلن دعم `power_status`، وتبقى قراءة الحالة من نصيب CEC أو
الشبكة عند توفرها.

---

## سطر الأوامر

```bash
python3 -m smarttv --cmd power on
python3 -m smarttv --cmd key home
python3 -m smarttv --cmd volume up
python3 -m smarttv --cmd cast "https://youtu.be/..."
python3 -m smarttv --cmd search الجزيرة      # بحث في المكتبة
python3 -m smarttv --cmd refresh             # إعادة تحميل القوائم
python3 -m smarttv --cmd sleep 45            # مؤقّت نوم
python3 -m smarttv --discover                # ابحث عن تلفازات في الشبكة
```

## واجهة HTTP

| الطريقة | المسار | الوظيفة |
| --- | --- | --- |
| GET | `/api/status` | حالة التلفاز والمشغّل والمكتبة والمؤقتات |
| GET | `/api/config` | الاختصارات والواجهات وقدرات المشغّل |
| POST | `/api/power` · `/api/volume` · `/api/key` · `/api/source` | التحكم |
| POST | `/api/app` | تشغيل تطبيق (سامسونج/LG) |
| POST | `/api/cast` | `{"url","name","kind","resume"}` |
| POST | `/api/player` | `toggle` · `seek` · `stop` · `volume` |
| GET | `/api/catalog` | `?kind=live&q=&group=&limit=&offset=` |
| GET | `/api/series` | المسلسلات مجمّعة بحلقاتها |
| POST | `/api/catalog/refresh` | إعادة تحميل المصادر |
| GET | `/api/epg` | `?channel=tvg-id` — الآن والتالي |
| GET/POST | `/api/favorites` | عرض/تبديل المفضلة |
| GET | `/api/resume` | «أكمل المشاهدة» والسجل |
| POST/DELETE | `/api/sleep` | مؤقّت النوم |

الردّ دائماً `{"ok": true, "data": …}` أو `{"ok": false, "error": "…"}`.
لحماية الواجهة ضع `server.auth_token` وأدخِله من زر ⚙ في الصفحة.

## الأتمتة

```json
"rules": [
  { "cron": "0 2 * * *",     "action": "power_off" },
  { "cron": "30 7 * * 1-5",  "action": "cast:https://…" }
]
```

الأوامر: `power_on` · `power_off` · `stop` · `key:<زر>` · `volume:<up|down|mute>`
· `source:<رقم>` · `cast:<رابط>` · `notify:<رسالة>`.

---

## ما الذي يعمل على كل جهاز (بدون مبالغة)

| القدرة | جوال أندرويد (Termux) | لينكس / راسبيري باي |
| --- | --- | --- |
| تشغيل رابط على الشاشة | ✅ عبر VLC / YouTube | ✅ عبر mpv |
| إيقاف مؤقت وتقديم | ⚠️ يحتاج روت أو ADB (`use_input_keyevents`) | ✅ كامل |
| مستوى الصوت | ✅ عبر Termux:API | ✅ |
| إيقاف التشغيل | ⚠️ بالعودة للشاشة الرئيسية | ✅ إغلاق فعلي |
| متابعة من حيث توقفت | ⚠️ يديرها VLC نفسه | ✅ يخزّنها المشروع |
| التحكم بالتلفاز | IR / CEC / شبكة | CEC / شبكة |

أندرويد يمنع تطبيقاً من حقن أزرار في تطبيق آخر بدون صلاحية shell — لذلك
تُعلن الواجهة عن `pause` و`seek` فقط عند تفعيل `use_input_keyevents`، بدل
ادّعاء قدرة لا توجد.

## حلّ المشاكل

- **التلفاز لا يستجيب لـ CEC:** فعّل CEC من إعدادات التلفاز (Anynet+ /
  SimpLink / Bravia Sync)، وجرّب `echo scan | cec-client -s -d 1`.
- **`no CEC adapter found`:** جرّب منفذ HDMI آخر (عادة HDMI 1) أو محوّل USB‑CEC.
- **الأشعة لا تعمل:** تأكد من تطبيق Termux:API ومن أن جوالك فيه بليستر
  (`termux-infrared-frequencies`)، ومن اختيار الماركة الصحيحة.
- **القنوات لا تفتح:** بعض البثوث تحتاج مشغّلاً يدعم HLS — استعمل VLC، أو
  جرّب الرابط في المتصفح للتأكد أنه حيّ.
- **يوتيوب لا يعمل على لينكس:** حدّث `yt-dlp`.

## البنية

```
smarttv/
  __main__.py     سطر الأوامر ونقطة التشغيل
  server.py       خادم HTTP بالمكتبة القياسية (API + صفحة الريموت)
  api.py          طبقة الخدمة: المسارات والتحقق وتتبّع «أكمل المشاهدة»
  registry.py     اختيار الواجهة المناسبة لكل أمر
  backends/       cec · ir · samsung · webos · dummy
  players/        mpv (لينكس) · android (Termux) خلف واجهة واحدة
  catalog.py      قوائم M3U ودليل XMLTV وبحث وتجميع المسلسلات
  store.py        المفضلة ومواضع المتابعة والسجل (كتابة ذرّية)
  ircodes.py      توليد نبضات NEC / Samsung32 / SIRC / RC5
  automation.py   cron مصغّر + مؤقّت النوم
  keys.py         خريطة أزرار موحّدة بين كل الواجهات
  web/            صفحة الريموت والمكتبة (PWA بالعربية)
```

## الاختبارات

```bash
python3 -m unittest discover
```

١٥٨ اختباراً تعمل بلا تلفاز وبلا إنترنت وبلا أي مكتبة خارجية: توليد نبضات
الأشعة، تحليل مخرجات `cec-client`، قوائم M3U ودليل XMLTV، منطق اختيار
الواجهات، تعابير cron، بناء نوايا أندرويد، حماية المسارات والرمز السرّي.

---

## English summary

A dependency-free Python service that turns a TV into a smart one using
hardware you already own. Control goes over **HDMI-CEC**, over **infrared**
from a phone's IR blaster (NEC / Samsung32 / SIRC / RC5 encoders included),
or over Wi-Fi to Samsung Tizen and LG webOS sets. Playback runs through
**mpv** on Linux or through **VLC/YouTube intents** on an Android phone in
Termux, which - plugged into HDMI - is the cheapest media box there is. A
library layer reads your own **M3U playlists and XMLTV guides** (the
project ships no content) and turns them into a searchable, favouritable,
resumable catalogue on a phone-friendly web remote.

```bash
sh scripts/install_termux.sh   # Android phone
sudo sh scripts/install.sh     # Debian / Raspberry Pi OS
python3 -m smarttv --demo      # no hardware at all
```
