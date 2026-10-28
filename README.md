# 🎙️ VOICE — Ухаалаг Яриа Таних (STT), Дуу Хоолой Хувилах (VoiceStudio) ба Системийн Гар (Keyboard)

**VOICE** нь Монгол (`mn-MN`), Англи (`en-US`), Япон (`ja-JP`) 3 хэлний яриаг бодит цагт бичвэрт хөрвүүлэх, зөв бичгийн дүрмийн алдааг автоматаар засах (`spellcheck.mn`), өөрийн дуу хоолойг хувилах (Voice Cloning), болон **Компьютер (Windows), Гар утас (Android / iPhone)** дээр ямар ч програм руу шууд ярьж бичих цогц систем юм.

---

## 🌟 Гол боломжууд

1. **3 Хэлний холимог яриа танигч (MN + EN + JA Code-Switching):**
   - Монголоор ярьж байгаад дундуур нь Англи эсвэл Япон үг хэлэхэд автоматаар зөв ялгаж танина.
   - Шуугиан дарах, үг наалдахаас сэргийлэх 4 үе шаттай яриа боловсруулах шүүлтүүртэй.
2. **Монгол хэлний зөв бичгийн дүрэм шалгагч (`spellcheck.mn`):**
   - Бичвэр дундах үсгийн алдааг илрүүлж, зөв хувилбаруудыг санал болгон 1 даралтаар засварлана.
3. **VoiceStudio AI — Дуу хоолой хувилах (Zero-Shot Voice Cloning):**
   - Өөрийн эсвэл дурын хүний хоолойн 5–10 секундийн бичлэгээр хоолойн өнгө, тембр, формантыг хувилж шинэ хоолой үүсгэнэ.
   - Студийн Broadcast, Podcast, Warm, Bright, Cinematic мастер эффектүүдтэй.
4. **Компьютер дээр шууд бичих (Windows System-wide Dictation):**
   - Chrome, Word, Facebook, Excel, Telegram дээр курсороо байрлуулаад `Ctrl + Alt` эсвэл `F8` дарж ярихад текст шууд бичигдэнэ.
5. **Гар утасны системийн гар (Android & iOS Keyboard):**
   - Утсан дээрээ Chrome-ийн хайлт, Messenger, Instagram дээр ямар ч хуулж буулгах үйлдэлгүйгээр **🎤 товчоо дараад л шууд ярьж бичнэ**.

---

## 📱 1. Гар утсан дээрээ ашиглах (Android & iPhone)

### 🤖 Android Утасны Гар (`VOICE-Keyboard.apk`)

Утасны үндсэн гар болгон суулгаснаар Chrome, Google хайлт, Facebook зэрэг бүх апп дээр монгол кирилл үсэг болон **🎤 Дарж ярих** товч гарч ирнэ.

1. **Татах:** [VOICE-Keyboard.apk татах (GitHub Releases)](https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.0.0/VOICE-Keyboard.apk)
2. **Суулгах & Асаах:**
   - Татсан `.apk` файлыг утсандаа суулгана.
   - **VOICE Keyboard** аппыг нээгээд дараах 3 алхмыг хийнэ:
     - **1-р алхам:** "Микрофон зөвшөөрөх" дарна.
     - **2-р алхам:** "Гарын тохиргоо нээх" дарж *VOICE Keyboard*-ийг асаана.
     - **3-р алхам:** "Гар солих цэс нээх" дарж үндсэн гараараа *VOICE Keyboard*-ийг сонгоно.
3. **Хэрэглэх:** Chrome эсвэл дурын чатын бичих нүдэн дээр дарахад гар гарч ирнэ. Дээд талын **🎤** товчийг дараад ярихад текст шууд бичигдэнэ!

---

### 🍎 iPhone / iOS дээр ашиглах

iPhone дээр 2 янзаар ашиглаж болно:

#### Арга 1: 30 секундэд тохируулах (App Store / Компьютер шаардлагагүй — Шилдэг арга)
iPhone-ийн **Shortcuts (Богино холбоос)** болон **Back Tap (Утасны ард 2 товших)** эсвэл **Action Button** ашиглан хүссэн апп дээрээ ярьж бичих:
1. iPhone дээрээ **Shortcuts** апп нээгээд **`+`** дарж шинэ Shortcut үүсгэнэ.
2. Дараах 3 үйлдлийг дарааллаар нь нэмнэ:
   - **Record Audio** *(Stop Recording: On Tap)*
   - **Get Contents of URL** *(Method: POST, URL: `https://voice-app.onrender.com/api/ios-dictate`, Request Body: Form -> `audio` = Recorded Audio)*
   - **Copy to Clipboard**
3. iPhone-ийн **Settings → Accessibility → Touch → Back Tap → Double Tap** дээр энэ Shortcut-аа сонгоно.
4. Одоо Chrome, Google, Safari дээр байхдаа утасныхаа ар талд **2 удаа товшоод** ярихад л таны яриаг шууд текст болгож бэлдэнэ!

#### Арга 2: Системийн гар суулгах (AltStore / Xcode)
- iOS Custom Keyboard Extension-ийн бүрэн Swift эх код нь `mobile/ios/` хавтсанд бэлэн байгаа.
- Татах: [VOICE-Keyboard-iOS.ipa](https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.0.0/VOICE-Keyboard-iOS.ipa)

---

## 💻 2. Компьютер дээр шууд ярьж бичих (`Ctrl + Alt` эсвэл `F8`)

Компьютерынхаа Word, Excel, Chrome хайлтын талбар, Facebook чат дээр курсороо тавиад шууд ярьж бичих:

1. `voice-main` хавтас доторх **`Install-VOICE-Helper.bat`** файл дээр **давхар товшоод** ажиллуулна.
2. Энэ нь Windows асах бүрт далд ажиллах туслах програмыг автоматаар суулгана.
3. Одоо Chrome эсвэл Word дээр курсороо байрлуулаад:
   - **`Ctrl + Alt`** (эсвэл **`F8`**) дараад ярина.
   - Ярьж дуусаад чимээгүй болоход (эсвэл товчоо дахин дарахад) ярьсан үг тань курсор байгаа газарт автоматаар бичигдэнэ!
4. *(Хэрэв туслах програмыг устгах бол `Uninstall-VOICE-Helper.bat` файлыг ажиллуулна).*

---

## 🎙️ 3. VoiceStudio AI — Дуу хоолойгоор яриулах ба Хоолой хувилах

Вэб интерфэйсийн **VoiceStudio** цэс рүү орж:
- **12 Студи Дуу Хоолой:** Монгол (Есүй, Батаа, Тэмүүлэн өгүүлэгч, Ану мэдээ, Ананд подкаст, Марал, Тулга, Мишээл), Англи (Ava, Andrew), Япон (Nanami, Keita).
- **Дуу хоолой хувилах (Voice Clone):**
  1. "Хүний дуу хоолой хувилах" таб руу орно.
  2. Микрофоноор 5–10 секунд ярьж бичнэ (эсвэл бэлэн аудио файл оруулна).
  3. "Хоолойг хувилж хадгалах" дармагц тухайн хүний өнгө төрхтэй шинэ хоолой үүснэ.
- **DSP Эффектүүд:** Broadcast (радио стандарт), Podcast (баргил ойрын микрофон), Warm (зөөлөн), Bright (хурц тод), Cinematic (цуурайтай).

---

## 🌐 4. Вэб ба Серверийг хөгжүүлэлтийн горимд ажиллуулах

### Шаардлага:
- Node.js 18+
- Python 3.10+ (ffmpeg суулгасан байх)

### 1-р алхам: Вэб фронтэнд эхлүүлэх
```bash
cd voice-main
npm install
npm run dev
```
Хөтөч дээрээ **`http://localhost:3000`** хаягаар нээнэ.

### 2-р алхам: Python AI серверийг эхлүүлэх
```bash
# Windows дээр:
run-tts.bat

# эсвэл терминалаас:
pip install -r requirements.txt
python -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
```

---

## ☁️ 5. Cloud Deployment (Render.com Docker)

Энэхүү төсөл нь Render.com зэрэг үүлэн серверт Docker ашиглан 1 товшилтоор байршихад бүрэн бэлэн:
- **`Dockerfile`**: Node.js 20, Python 3, ffmpeg, libsndfile1 зэрэг шаардлагатай бүх санг автоматаар суулгана.
- **`start-cloud.sh`**: Python backend (`port 8000`) болон Next.js production серверийг зэрэг асаана.
- **`render.yaml`**: Серверийн тохиргоог автоматаар уншина.

---

## 📂 Төслийн бүтэц

```text
├── app/
│   ├── api/
│   │   ├── chimege/transcribe/ # Яриаг таних (MN + EN + JA) API
│   │   ├── tts/                # Дуу үүсгэх & VoiceStudio API
│   │   ├── tts/clone/          # Дуу хоолой хувилах API
│   │   ├── flowbar/            # Компьютерын шууд бичих удирдлагын API
│   │   └── ios-dictate/        # iPhone-д зориулсан хялбар текст диктовк API
│   ├── dashboard/              # Үндсэн яриа таних ажлын талбар
│   ├── tts/                    # VoiceStudio & Хоолой хувилах студи
│   ├── keyboard/               # Android APK ба iPhone гар татах/тохируулах хуудас
│   ├── history/                # Түүх ба архив
│   └── settings/               # Хэл, бичлэг, тохиргооны хуудас
├── mobile/
│   ├── android/                # Android Системийн Гар (VoiceKeyboardService - Kotlin)
│   └── ios/                    # iOS Custom Keyboard Extension (Swift)
├── lib/
│   ├── text-processor.ts       # Сул үг арилгах, 3 хэлний шүүлтүүр
│   ├── spellcheck-client.ts    # spellcheck.mn крипто алгоритм ба шалгагч
│   ├── audio-recorder.ts       # Утас болон вэбийн микрофон бичигч
│   └── ensure-py-server.ts     # Сервер унтарсан үед автоматаар асаах хамгаалалт
├── tts_server.py               # FastAPI: STT + Voice Clone DSP + Windows Hotkey Engine
├── Install-VOICE-Helper.bat    # Компьютерт Ctrl+Alt-ийг автоматаар суулгагч
├── Dockerfile                  # Үүлэн серверийн Docker тохиргоо
└── .github/workflows/          # Android APK ба iOS IPA-г автоматаар угсрагч
```

---

## 📄 Лиценз
MIT License — Хувийн болон байгууллагын хэрэгцээнд чөлөөтэй ашиглах боломжтой.
