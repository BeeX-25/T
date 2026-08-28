# SmartTV Bridge — حوّل أي تلفاز إلى تلفاز ذكي برمجياً

خدمة صغيرة بلغة **Python** بدون أي مكتبة خارجية، تحوّل أي تلفاز فيه منفذ HDMI
إلى نظام ذكي: ريموت من الجوال، تشغيل يوتيوب والروابط على الشاشة، مؤقّت نوم،
وأتمتة بمواعيد — **بدون شراء أجهزة بث غالية**.

## الفكرة باختصار

كل تلفاز فيه HDMI يدعم بروتوكول **HDMI-CEC** (الشركات تسمّيه بأسماء تجارية:
Anynet+ عند سامسونج، SimpLink عند LG، Bravia Sync عند سوني، Viera Link عند
باناسونيك). هذا البروتوكول يمشي داخل **كبل HDMI نفسه**، ويسمح لأي جهاز موصول
بأن يشغّل التلفاز ويطفئه ويتحكّم بالصوت ويرسل أزرار الريموت.

فالمطلوب ليس جهازاً جديداً، بل جهاز حاسوب قديم موصول بالـ HDMI + هذه الخدمة:

```
جوالك ──HTTP──▶ SmartTV Bridge ──HDMI-CEC──▶ التلفاز (تشغيل/إطفاء/أزرار/صوت)
   (ريموت)      (على جهاز رخيص)  ──mpv────▶ يوتيوب وروابط الفيديو على الشاشة
                                 ──WiFi───▶ سامسونج/LG الشبكية (اختياري)
```

## ماذا تحتاج

| الخيار | التكلفة | ملاحظات |
| --- | --- | --- |
| لابتوب قديم / حاسوب مكتبي قديم | صفر غالباً | الأسهل، وكل شيء يشتغل عليه فوراً |
| Raspberry Pi (أي إصدار فيه HDMI) | رخيص | الـ CEC مدمج فيه بدون أي إضافة |
| صندوق أندرويد قديم / Mini PC | صفر إن كان موجوداً | شغّل عليه لينكس أو Termux |

إضافة لذلك: كبل HDMI (موجود أصلاً)، وشبكة واي فاي واحدة تجمع الجوال بالجهاز.
إن كان جهازك لا يدعم CEC (بعض كروت الشاشة في اللابتوبات لا تدعمه)، فمحوّل
USB‑CEC رخيص يحلّها، أو استخدم واجهة الشبكة إن كان تلفازك سامسونج/LG حديث.

المتطلبات البرمجية: `python3` فقط للخدمة، و`cec-utils` للتحكم بالتلفاز،
و`mpv` + `yt-dlp` لتشغيل يوتيوب والروابط.

## التثبيت السريع

```bash
git clone <هذا المستودع> smarttv && cd smarttv

# على راسبيري باي أو أي نظام ديبيان/أوبنتو:
sudo sh scripts/install.sh          # يثبّت الحزم + خدمة systemd تعمل عند الإقلاع

# أو يدوياً بدون تثبيت:
sudo apt install cec-utils mpv yt-dlp
cp config.example.json config.json
python3 -m smarttv --config config.json
```

ثم افتح من جوالك: `http://IP-الجهاز:8099` وأضف الصفحة إلى الشاشة الرئيسية
لتصير كتطبيق ريموت كامل.

للتجربة على أي جهاز بدون تلفاز موصول:

```bash
python3 -m smarttv --demo          # تلفاز وهمي في الذاكرة، الواجهة تعمل كاملة
```

## الاستعمال من سطر الأوامر

```bash
python3 -m smarttv --cmd power on           # تشغيل التلفاز
python3 -m smarttv --cmd power off
python3 -m smarttv --cmd key home           # أزرار: up/down/left/right/select/back/home/info…
python3 -m smarttv --cmd volume up
python3 -m smarttv --cmd source 2           # التحويل إلى HDMI 2
python3 -m smarttv --cmd cast "https://youtu.be/..."
python3 -m smarttv --cmd sleep 45           # مؤقت نوم بالدقائق
python3 -m smarttv --cmd status
python3 -m smarttv --discover               # ابحث عن التلفازات في الشبكة
python3 -m smarttv --cmd raw "tx 40:44:41"  # إطار CEC خام لمن يريد التوسّع
```

هذا يجعل التلفاز قابلاً للبرمجة من أي سكربت أو cron أو Home Assistant.

## واجهة HTTP

كل شيء متاح كـ JSON على نفس المنفذ، فتستطيع ربطه بأي شيء:

| الطريقة | المسار | الجسم |
| --- | --- | --- |
| GET | `/api/status` | حالة التلفاز والمشغّل والمؤقتات |
| GET | `/api/config` | الاختصارات والواجهات المتاحة |
| GET | `/api/discover` | مسح SSDP للشبكة |
| POST | `/api/power` | `{"state": "on" \| "off" \| "toggle"}` |
| POST | `/api/volume` | `{"action": "up" \| "down" \| "mute", "repeat": 3}` |
| POST | `/api/key` | `{"key": "up", "repeat": 1}` |
| POST | `/api/source` | `{"index": 2}` |
| POST | `/api/app` | `{"app": "youtube"}` (سامسونج/LG فقط) |
| POST | `/api/cast` | `{"url": "https://…"}` |
| POST | `/api/player` | `{"action": "toggle" \| "seek" \| "stop", "value": 30}` |
| POST | `/api/sleep` | `{"minutes": 45}` — و`DELETE` للإلغاء |

مثال:

```bash
curl -X POST localhost:8099/api/cast -d '{"url":"https://youtu.be/jNQXAC9IVRw"}'
```

الردّ دائماً `{"ok": true, "data": …}` أو `{"ok": false, "error": "…"}`.
لحماية الواجهة ضع `auth_token` في الإعدادات، وأدخِله من زر ⚙ في صفحة الريموت.

## الأتمتة

في `config.json`، كل قاعدة عبارة عن تعبير cron وأمر:

```json
"automation": {
  "sleep_timer_minutes": 45,
  "rules": [
    { "name": "إطفاء بعد منتصف الليل", "cron": "0 2 * * *", "action": "power_off" },
    { "name": "أخبار الصباح", "cron": "30 7 * * 1-5", "action": "cast:https://youtu.be/…" }
  ]
}
```

الأوامر المتاحة: `power_on` و`power_off` و`stop` و`key:<اسم الزر>` و
`volume:<up|down|mute>` و`source:<رقم>` و`cast:<رابط>` و`notify:<رسالة>`.

## تلفازات سامسونج و LG الشبكية (اختياري)

إن كان تلفازك ذكياً أصلاً لكن ريموته ضاع أو تريد التحكم به برمجياً، فعّل
الواجهة المناسبة في `config.json`:

```bash
pip3 install samsungtvws     # سامسونج Tizen (2016 فما فوق)
pip3 install pywebostv       # LG webOS
```

المكتبتان تُحمّلان عند الحاجة فقط، والخدمة تعمل بدونهما. عند تفعيل أكثر من
واجهة، يجرّب النظام كل واحدة بالترتيب المذكور في `tv.order` ويختار أول واجهة
تدعم الأمر المطلوب — أي أن زر الصوت قد يذهب عبر CEC وزر تشغيل التطبيقات عبر
الشبكة، دون أن تنتبه أنت لذلك.

## حلّ المشاكل

- **لا يستجيب التلفاز:** فعّل CEC من إعدادات التلفاز (ابحث عن الاسم التجاري:
  Anynet+ / SimpLink / Bravia Sync)، ثم جرّب `echo scan | cec-client -s -d 1`.
- **`no CEC adapter found`:** الكبل غير موصول، أو منفذ HDMI الذي استعملته لا
  يدعم CEC (جرّب منفذاً آخر — عادة HDMI 1)، أو جهازك يحتاج محوّل USB-CEC.
- **الصوت لا يتغيّر:** كثير من التلفازات تمرّر أوامر الصوت إلى مكبّر خارجي
  فقط. استعمل `key:volume_up` بدل `volume`، أو تحكّم بصوت المشغّل نفسه عبر
  `/api/player` `{"action":"volume"}`.
- **يوتيوب لا يعمل:** حدّث `yt-dlp` (`pip3 install -U yt-dlp`)، فمواقع البث
  تغيّر واجهاتها باستمرار.
- **الصفحة لا تفتح من الجوال:** تأكد أن الجهازين على نفس الشبكة، وأن جدار
  الحماية يسمح بالمنفذ 8099.

## بنية المشروع

```
smarttv/
  __main__.py     واجهة سطر الأوامر ونقطة التشغيل
  server.py       خادم HTTP بالمكتبة القياسية (API + صفحة الريموت)
  api.py          طبقة الخدمة: جدول المسارات وقواعد التحقق
  registry.py     اختيار الواجهة المناسبة لكل أمر مع التبديل التلقائي
  backends/       cec (الأساس) · samsung · webos · dummy (للتجربة)
  media.py        تشغيل الوسائط عبر mpv وواجهة IPC الخاصة به
  automation.py   cron مصغّر + مؤقّت النوم
  discovery.py    البحث عن الأجهزة عبر SSDP
  keys.py         خريطة الأزرار الموحّدة بين كل الواجهات
  web/            صفحة الريموت (تعمل كتطبيق PWA على الجوال)
```

## الاختبارات

```bash
python3 -m unittest discover -s tests
```

٨٨ اختباراً تعمل بلا تلفاز وبلا إنترنت وبلا أي مكتبة خارجية: تحليل مخرجات
`cec-client`، بناء إطارات CEC، منطق التبديل بين الواجهات، تعابير cron،
حماية المسارات في الخادم، والتحقق من الرمز السرّي.

---

## English summary

A dependency-free Python service that turns any HDMI TV into a smart TV
without buying streaming hardware. It drives the TV over **HDMI-CEC** (the
control channel already inside your HDMI cable) from any old laptop or
Raspberry Pi, streams YouTube and video URLs to it through **mpv**, serves a
phone-friendly web remote, and exposes the whole thing as a JSON API plus a
CLI so it can be scripted or wired into Home Assistant. Optional
network backends for Samsung Tizen and LG webOS are loaded lazily.

```bash
sudo sh scripts/install.sh     # Debian/Raspberry Pi OS
python3 -m smarttv --demo      # try it with no TV attached
python3 -m smarttv --cmd power on
```
