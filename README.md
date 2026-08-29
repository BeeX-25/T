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
| **رسيفر Enigma2** (Vu+/Zgemma/Octagon/Dreambox…) | **لا شيء** | الأفضل: تحكم كامل + قنوات الرسيفر + تشغيل أي رابط عليه |
| **رسيفر عادي بفيرموير مغلق** (ماجيك/نيو ورلد/1506/GX6605S) | لا شيء | تحكم بالأشعة + ماكروات + قنوات بالأرقام (بلا تأكيد) |
| **صندوق أندرويد قديم** موصول أصلاً | لا شيء | تحكم + مكتبة كاملة |
| لا هذا ولا ذاك | جوال أندرويد مستعمل رخيص | أرخص "صندوق بث" ممكن |

> ملاحظة مهمة: بعض الجوالات لا تُخرج صورة عبر USB‑C (تحتاج دعم DisplayPort
> Alt Mode). تحقّق من موديل جوالك قبل شراء المحوّل. وإن كان تلفازك يدعم
> Miracast، يمكنك العرض لاسلكياً من الجوال بدون كبل أصلاً.

كل واحدة من هذه الحالات لها "واجهة" جاهزة في المشروع، والخدمة تختار
تلقائياً أول واجهة متاحة تدعم الأمر المطلوب:

```
جوالك ──HTTP──▶ الخدمة (على جوال قديم أو أي جهاز)
                   ├── enigma2  → رسيفر لينكس عبر OpenWebif (شبكة)
                   ├── ir       → أشعة تحت حمراء من بليستر الجوال (بدون أي كبل)
                   ├── cec      → عبر كبل HDMI نفسه (تشغيل/إطفاء/أزرار)
                   ├── samsung  → واي فاي (Tizen)
                   ├── webos    → واي فاي (LG)
                   └── player   → الرسيفر نفسه، أو VLC على الأندرويد، أو mpv على اللينكس
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

### على رسيفر Enigma2

```bash
ssh root@RECEIVER "sh /tmp/bridge/scripts/install_enigma2.sh"   # التفاصيل أدناه
```

### على راسبيري باي أو حاسوب لينكس

```bash
sudo sh scripts/install.sh     # يثبّت cec-utils و mpv وخدمة systemd
```

### للتجربة بدون أي جهاز

```bash
python3 -m smarttv --demo      # تلفاز وهمي، الواجهة تعمل بالكامل
```

---

## على رسيفر Enigma2 (أفضل حالة على الإطلاق)

أغلب الرسيفرات المنتشرة (Vu+، Zgemma، Octagon، Gigablue، Dreambox، وكل ما
يعمل بصور OpenATV/OpenPLi/OpenViX) هي **أجهزة لينكس** فيها بايثون وواجهة
**OpenWebif**. وهذا يعني أن الرسيفر:

- موصول بالتلفاز أصلاً — لا تحتاج كبلاً ولا محوّلاً ولا جوالاً إضافياً،
- يعرف كل قنواتك (الباقات) ويستطيع تشغيل أي رابط إنترنت على شاشته،
- ويمكن تشغيل هذه الخدمة **بداخله** لأنها بلا أي مكتبة خارجية.

### الطريقة (أ): التحكم به عبر الشبكة

شغّل الخدمة على أي جهاز (جوال/حاسوب) وضع في `config.json`:

```json
"tv": {
  "order": ["enigma2"],
  "enigma2": {
    "enabled": true,
    "host": "192.168.1.30",
    "username": "root",
    "password": "كلمة سر الرسيفر إن وُجدت"
  }
},
"player": { "backend": "enigma2" },
"catalog": {
  "sources": [
    { "name": "قنوات الرسيفر", "type": "enigma2", "host": "192.168.1.30" }
  ]
}
```

### الطريقة (ب): تشغيل الخدمة داخل الرسيفر

```bash
scp -r smarttv config.example.json scripts root@192.168.1.30:/tmp/bridge/
ssh root@192.168.1.30 "sh /tmp/bridge/scripts/install_enigma2.sh"
```

يثبّتها في `/usr/local/smarttv` مع سكربت إقلاع، ويجعل `host` هو `127.0.0.1`.

### ماذا تحصل

| الشيء | كيف يعمل |
| --- | --- |
| ريموت كامل | كل أزرار الرسيفر (بما فيها الملوّنة و EPG والنص) عبر `api/remotecontrol` |
| الاستعداد والتشغيل | `api/powerstate` — و«الاستعداد العميق» اختياري لأن الرجوع منه يحتاج زر الجهاز |
| قراءة الحالة | يعرف فعلاً إن كان الرسيفر يعمل أو في وضع الاستعداد (عكس الأشعة) |
| قنوات الرسيفر في جوالك | تُقرأ الباقات من `api/getallservices`، والضغط على قناة **يبدّل الرسيفر إليها** |
| مشاهدة القناة على الجوال | كل قناة لها أيضاً رابط بث `http://الرسيفر:8001/<sref>` يفتح في VLC |
| تشغيل أي رابط على التلفاز | يُغلَّف الرابط في مرجع خدمة `4097:...` ويُرسل للرسيفر |
| رسالة على الشاشة | `api/message` — مفيدة للتنبيهات والأتمتة |

> إن لم يشتغل تشغيل الروابط، غيّر `service_type` من `4097` (GStreamer) إلى
> `5002` (ExtEplayer3) حسب صورة الرسيفر لديك.

### الرسيفرات ذات الفيرموير المغلق (Magic / New World / 1506 / GX6605S)

الرسيفرات الرخيصة المنتشرة — ماجيك ٥٥٥، نيو ورلد، نيو ستار وأشباهها — تعمل
بمعالجات **Sunplus 1506** أو **GX6605S** بفيرموير مغلق حجمه ميغابايتات
قليلة: **لا لينكس ولا بايثون ولا صلاحية دخول ولا أي واجهة برمجية**، و«السوفت
وير» الخاص بها ملف `.bin` من الشركة يُحمَّل عبر USB. لذلك:

> **لا يمكن تثبيت هذا النظام (ولا أي نظام بديل) على هذه الرسيفرات.** لا يوجد
> بديل مفتوح لهذه المعالجات، والتجربة تعني تعطيل الجهاز بلا مقابل.

ما يمكن عمله معها:

| الهدف | الطريقة |
| --- | --- |
| التحكم بها من الجوال | **الأشعة (IR)** — عبر معالج الضبط أدناه |
| قنوات وأفلام ومسلسلات | خاصية IPTV/Xtream داخل الرسيفر نفسه إن وُجدت، أو جوال على HDMI |
| مكتبة وبحث وأتمتة حقيقية | شغّل الخدمة على جوال أندرويد موصول بـ HDMI، وابقِ الرسيفر للقنوات الفضائية |

### كيف تجعل جهازاً مغلقاً «قابلاً للبرمجة»؟

لا يمكن جعله قابلاً للبرمجة **من الداخل** — لكن يمكن جعله قابلاً للبرمجة
**من الخارج**، وهذا ما تفعله كل أنظمة الأتمتة المنزلية مع الأجهزة المغلقة.
ثلاث درجات، من الأرخص إلى الأقوى:

**الدرجة الأولى: قيادته بأزراره (متاح الآن، بلا أي شراء)**

بعد ضبط أكواد الأشعة، صار كل زر في ريموته دالّة تُستدعى: من سطر الأوامر، أو
من cron، أو من زر في جوالك. وفوق ذلك أضيفت **الماكروات** — تسلسل أزرار
بمهلات، وهو ما يحوّل «افعل هذا يدوياً» إلى أمر واحد:

```json
"macros": [
  { "name": "مشاهدة الفضائيات",
    "steps": ["power_on", "wait:2", "source:1", "wait:1", "digits:103"] }
]
```

خطوات الماكرو: اسم زر (`up`)، أو `key:<زر>`، أو `wait:<ثوانٍ>`، أو
`digits:<رقم القناة>` (يُترجم إلى ضغطات الأرقام)، أو أوامر مثل `power_on`
و`power_off` و`volume:up` و`cast:<رابط>`.

**قائمة قنوات بالأرقام:** أعطِ البرنامج أرقام قنواتك في الرسيفر، فتظهر لك في
جوالك كشبكة قابلة للبحث، وكل ضغطة تُرسل أرقامها عبر الأشعة:

```json
{
  "name": "قنوات رسيفري",
  "type": "channels",
  "confirm": "select",
  "items": [
    { "name": "MBC 1", "number": 103, "group": "عام" },
    { "name": "الجزيرة", "number": 7,  "group": "أخبار" }
  ]
}
```

ويمكن وضعها في ملف `csv` بسيط (`الاسم,الرقم,المجموعة`) أو JSON عبر `path`.

> **حدّ صريح:** هذه قيادة «مفتوحة الحلقة» — لا يوجد أي طريق يخبرنا أن الجهاز
> استجاب فعلاً. لذلك يعرض البرنامج آخر قناة أُرسلت مع كلمة **(بلا تأكيد)**،
> ولا يدّعي معرفة الحالة الحقيقية. من يريد تأكيداً حقيقياً يحتاج جهازاً
> يتكلم في الاتجاهين (Enigma2 أو أندرويد).

**الدرجة الثانية: جسر أشعة عبر الواي فاي (بدولارين)**

إن لم يكن في جوالك بليستر — أو أردت أن تعمل الأتمتة والجوال بعيد عن الجهاز —
فأي ESP8266 مع ليد أشعة يكفي. في `scripts/esp8266_ir_bridge.ino` سكيتش جاهز
(٦٠ سطراً) يستقبل نفس النبضات ويرسلها:

```json
"ir": {
  "enabled": true,
  "brand": "my_remote",
  "transport": "http",
  "url": "http://192.168.1.9/ir?freq={frequency}&pattern={pattern}"
}
```

نفس القالب يصلح لأي جهاز إرسال آخر (Tasmota أو ESPHome أو سكربت خاص بك)،
وكذلك `transport: "command"` لمن عنده LIRC.

**الدرجة الثالثة: استبدال الصندوق (إن أردت برمجة حقيقية)**

رسيفر Enigma2 مستعمل أو صندوق أندرويد رخيص يعطيك ما لا يعطيه أي التفاف على
جهاز مغلق: قراءة الحالة، ومعرفة القناة الحالية، وتشغيل الروابط، وواجهة
برمجية حقيقية. القاعدة البسيطة: **الأشعة تكفي للتحكم، ولا تكفي للأتمتة
الموثوقة.**

---

## اشتراك IPTV بصيغة Xtream Codes

معظم الاشتراكات تُباع بواجهة **Xtream Codes** (رابط + مستخدم + كلمة سر).
أضفه كمصدر واحد فتحصل على القنوات والأفلام والمسلسلات مع تصنيفاتها:

```json
{
  "name": "اشتراكي",
  "type": "xtream",
  "url": "http://provider.example:8080",
  "username": "USER",
  "password": "PASS",
  "kinds": ["live", "movies", "series"]
}
```

حلقات المسلسل لا تُجلب مسبقاً (اشتراك كبير = مئات الطلبات)، بل عند فتح
المسلسل فقط عبر `GET /api/episodes?series_id=…`.

> بيانات اشتراكك تبقى في ملف إعداداتك، لكن روابط التشغيل تحتوي المستخدم
> وكلمة السر بطبيعة البروتوكول — فعّل `server.auth_token` إن كانت شبكتك
> مشتركة مع آخرين.

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

### إن كان جهازك غير معروف (وهذا وضع أغلب الرسيفرات)

أكواد الريموتات الرخيصة ليست في أي جدول جاهز، فأمامك طريقان — كلاهما داخل
البرنامج:

**١) معالج التجربة:** افتح ⚙ ← «ضبط الأشعة»، فتظهر قائمة مجموعات أكواد
مرشّحة (الماركات المعروفة + مسح لعناوين NEC الشائعة). اضغط «جرّب» وراقب
الجهاز، وعند استجابته اضغط «احفظ» — يُحفظ الاختيار ويبقى بعد إعادة التشغيل.
ومن سطر الأوامر:

```bash
python3 -m smarttv --cmd ir-candidates      # اعرض المرشّحين
python3 -m smarttv --cmd ir-test lg power   # جرّب واحداً
python3 -m smarttv --cmd ir-save lg 4       # اعتمد ما نجح
```

**٢) استيراد أكواد ريموتك بالضبط:** إن وجدت ملف `lircd.conf` لريموتك أو ملف
CSV من قاعدة **irdb**، استورده فيصير ريموتك مدعوماً بالكامل:

```bash
python3 -m smarttv --import-ir magic555.conf
```

يفهم البرنامج صيغتَي LIRC (`SPACE_ENC` و`RAW_CODES`) وصيغة irdb، ويعيد بناء
النبضات بتوقيتات ريموتك الأصلي حرفياً بدل تخمين البروتوكول.

**حدّ صريح:** الأشعة اتجاه واحد — لا يمكنها قراءة حالة التلفاز أبداً. لذلك
هذه الواجهة لا تعلن دعم `power_status`، وتبقى قراءة الحالة من نصيب CEC أو
الشبكة عند توفرها. وتحتاج أيضاً أن يكون الجوال موجّهاً نحو الجهاز.

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
| GET | `/api/episodes` | `?series_id=` — حلقات مسلسل من Xtream عند الطلب |
| GET | `/api/ir/candidates` | مجموعات أكواد مرشّحة + الريموت الحالي |
| POST | `/api/ir/test` · `/api/ir/save` | جرّب مجموعة / اعتمدها واحفظها |
| POST | `/api/ir/import` | استيراد `lircd.conf` أو irdb CSV |
| GET | `/api/macros` | الماكروات المعرّفة |
| POST | `/api/macro` | `{"name": …}` أو `{"steps": [...]}` |
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

| القدرة | رسيفر Enigma2 | جوال أندرويد (Termux) | لينكس / راسبيري باي |
| --- | --- | --- | --- |
| تشغيل رابط على الشاشة | ✅ عبر الرسيفر نفسه | ✅ عبر VLC / YouTube | ✅ عبر mpv |
| إيقاف مؤقت وتقديم | ✅ بأزرار الريموت | ⚠️ يحتاج روت أو ADB | ✅ كامل |
| مستوى الصوت | ✅ مطلق (0‑100) | ✅ عبر Termux:API | ✅ |
| متابعة من حيث توقفت | ⚠️ الرسيفر لا يعطي موضع التشغيل | ⚠️ يديرها VLC نفسه | ✅ يخزّنها المشروع |
| قراءة حالة التلفاز/الجهاز | ✅ | حسب الواجهة | حسب الواجهة |
| التحكم | شبكة (OpenWebif) | IR / CEC / شبكة | CEC / شبكة |

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
  backends/       cec · ir · enigma2 · samsung · webos · dummy
  players/        mpv (لينكس) · android (Termux) · enigma2 (الرسيفر)
  openwebif.py    عميل واجهة الرسيفر (يستعمله التحكم والتشغيل معاً)
  sources.py      قراءة M3U و XMLTV و Xtream Codes وباقات الرسيفر
  catalog.py      التخزين المؤقت والبحث وتجميع المسلسلات
  store.py        المفضلة ومواضع المتابعة والسجل (كتابة ذرّية)
  ircodes.py      توليد نبضات NEC / Samsung32 / SIRC / RC5 والمرشّحين
  irimport.py     استيراد أكواد الريموتات من LIRC و irdb
  macros.py       تسلسلات أزرار بمهلات: برمجة الأجهزة التي لا ترد
  automation.py   cron مصغّر + مؤقّت النوم
  keys.py         خريطة أزرار موحّدة بين كل الواجهات
  web/            صفحة الريموت والمكتبة (PWA بالعربية)
```

## الاختبارات

```bash
python3 -m unittest discover
```

٢٧٥ اختباراً تعمل بلا تلفاز وبلا رسيفر وبلا إنترنت وبلا أي مكتبة خارجية:
توليد نبضات الأشعة واستيراد ملفات LIRC/irdb، تحليل مخرجات `cec-client`،
أوامر OpenWebif ومراجع الخدمة، واجهة Xtream، قوائم M3U ودليل XMLTV، منطق
اختيار الواجهات، تعابير cron، بناء نوايا أندرويد، حماية المسارات والرمز
السرّي.

---

## English summary

A dependency-free Python service that turns a TV into a smart one using
hardware you already own. Best case is an **Enigma2 satellite receiver**:
it is already on the HDMI port, runs Linux, and exposes OpenWebif - so the
service can drive it over the network or run *inside* it, list its bouquets
on your phone, zap it, and make it play any stream URL. Otherwise control
goes over **HDMI-CEC**, over **infrared**
from a phone's IR blaster (NEC / Samsung32 / SIRC / RC5 encoders included),
or over Wi-Fi to Samsung Tizen and LG webOS sets. Remotes nobody has a
table for - the cheap Sunplus 1506 / GX6605S receivers, say, which cannot
run anything themselves - are handled by a trial wizard over candidate
code sets, or by importing a `lircd.conf` or irdb CSV. Such a box is made
programmable from the outside: macros (key sequences with pauses) and
numbered channel lists turn "dial 1-0-3 on the remote" into one API call,
and the service says plainly when a command is open-loop. Pulses go out
through the phone's blaster, an `irsend` command, or an ESP8266 Wi-Fi
bridge (sketch included). Playback runs through
**mpv** on Linux or through **VLC/YouTube intents** on an Android phone in
Termux, which - plugged into HDMI - is the cheapest media box there is. A
library layer reads your own **M3U playlists, XMLTV guides, Xtream Codes
subscriptions and receiver bouquets** (the project ships no content) and turns them into a searchable, favouritable,
resumable catalogue on a phone-friendly web remote.

```bash
sh scripts/install_enigma2.sh  # on an Enigma2 receiver
sh scripts/install_termux.sh   # Android phone
sudo sh scripts/install.sh     # Debian / Raspberry Pi OS
python3 -m smarttv --demo      # no hardware at all
```
