# 🎙️ VOICE — Speak. Clean. Write.

<p align="center">
  <img src="public/voice.ico" width="80" height="80" alt="VOICE Logo" />
</p>

<p align="center">
  <b>Монгол, Англи, Япон хэлний бодит цагийн яриа танигч, зөв бичгийн дүрэм шалгагч (spellcheck.mn), VoiceStudio AI хоолой хувилагч болон Windows-ийн дурын програм дээр шууд ярьж бичих систем.</b>
</p>

<p align="center">
  <a href="https://github.com/AriukagiinTuvshoo/voice-app/releases/latest"><img src="https://img.shields.io/badge/Release-v1.2.0-indigo?style=for-the-badge&logo=windows" alt="Version 1.2.0" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(64--bit)-blue?style=for-the-badge&logo=windows" alt="Platform Windows" />
  <img src="https://img.shields.io/badge/Startup_Speed-1.0s%20Instant-brightgreen?style=for-the-badge&logo=speedtest" alt="Speed 1s" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License MIT" />
</p>

---

## 🚀 1. Компьютерт суулгах (1 Товшилтоор)

### 📥 [Албан ёсны суулгагч татах — VOICE-Setup.exe (v1.2.0)](https://github.com/AriukagiinTuvshoo/voice-app/releases/latest)

1. Дээрх холбоос дээр дарж **`VOICE-Setup.exe`** (ердөө 405 KB) файлыг татаж авна.
2. **`VOICE-Setup.exe`** дээр давхар товшоод **"🚀 Суулгах ба Нээх"** товчийг дарна.
3. Таны компьютерын дэлгэц (**Desktop**) дээр нил ягаан дүрс бүхий **`VOICE`** апп үүсэж, дэлгэцийн доор **`VOICE FLOW`** хөвөгч товч бэлэн болно!

> 💡 **Онцлог:** Ямар ч Node.js, Python, сан суулгах эсвэл хар цонх (terminal) нээх шаардлагагүй. 1-2 секундийн дотор бүрэн сууж шууд ажиллана.

---

## 🌟 2. Гол боломжууд

### 1. 🖥️ Дэлгэц дээр хөвөх `VOICE FLOW` ба Шууд бичих (`Ctrl + Alt` / `F8`)
- Компьютерын баруун доод хэсэгт үргэлж бэлэн хөвж байрлана.
- **Word, Excel, PowerPoint, Google Docs, Chrome, Facebook, Messenger, Telegram, Notepad** зэрэг дурын програм дээр курсороо байрлуулаад:
  - Гар дээрээ **`Ctrl + Alt`** (эсвэл **`F8`**) дараад ярина.
  - Мөн дэлгэц дээрх хөвөгч капсул дээр хулганаар дарж болно.
- Ярьж дуусаад дахин товчлуураа дарахад таны ярьсан үг яг курсор байгаа талбарт автоматаар хуулагдан бичигдэнэ!

### 2. ✨ Монгол хэлний зөв бичгийн дүрэм (`spellcheck.mn`)
- Ярьж бичсэн текст дундах зөв бичих дүрмийн алдаа, эгшиг гээгдэх болон залгавар үгийн алдааг бодит цагт илрүүлнэ.
- **1-Товшилтоор автоматаар засах** горимтой.

### 3. 🔊 VoiceStudio AI — Дуу хоолой хувилах (Zero-Shot Voice Cloning)
- Өөрийн эсвэл дурын хүний 5–10 секундийн дууны бичлэгээр хоолойн өнгө, тембр, хэлбэрийг яг таг хуулбарлан хувилна.
- Мэргэжлийн 12 студи хоолой (Болор, Зориг, Сарнай, Тулга, Баатар г.м).
- Радио/Подкаст/Кино студийн мастер эффектүүд (**Broadcast, Podcast, Warm, Cinematic**).

### 4. 🇲🇳 3-Хэлний холимог яриа танигч (Code-Switching)
- Монгол, Англи, Япон хэлийг нэг өгүүлбэр дотор хольж ярихад (жишээ нь: *"Өнөөдөр meeting-тэй тул presentation-ээ бэлдье"*) үг бүрийг автоматаар зөв ялгаж хөрвүүлнэ.

### 5. ⚡ 1 Секундын хурдан ажиллагаа (Instant Desktop Architecture)
- Өмнөх хувилбаруудад байсан олон минут хүлээлгэдэг эсвэл `ERR_CONNECTION_TIMED_OUT` алдаа заадаг асуудлыг шинэ статик архитектураар бүрэн шийдсэн.

---

## ⌨️ Товчлуурын хослолууд (Shortcuts)

| Товчлуур | Үйлдэл | Тайлбар |
|---|---|---|
| **`Ctrl + Alt`** | 🎙️ VOICE FLOW Шууд ярих | Компьютерын дурын цонхонд шууд бичнэ |
| **`F8`** | ⚡ Шуурхай яриа эхлүүлэх | 1 товчлуураар ярьж эхлэх / дуусгах |
| **`Space`** | 🔴 Ажлын талбарт ярих | VOICE апп дотор яриа эхлүүлэх / зогсоох |
| **`Esc`** | ✕ FlowBar нуух | Хөвөгч товчийг дэлгэцээс нууна |

---

## 📁 Төслийн бүтэц

```text
voice-app/
├── VOICE-Setup.exe        # 📦 1-Товшилтоор Windows-д суулгагч файл (405 KB)
├── VOICE.exe              # 🚀 Desktop асаагч ба Native VOICE FLOW хөвөгч товч (C#)
├── server.cjs             # ⚡ Хэт хурдан локал API & статик серверийн хөдөлгүүр
├── out/                   # 🎨 Бэлэн компайл хийгдсэн интерфейсийн файлууд (HTML/CSS/JS)
├── app/                   # 💻 Next.js React хуудаснууд (Dashboard, VoiceStudio, History, Settings)
├── components/            # 🧩 UI элементүүд (AppShell, Icons, Waveform)
├── lib/                   # 🛠️ Аудио бичигч, яриа боловсруулагч, spellcheck клиент
├── public/                # 🖼️ Аппликейшний нил ягаан дүрс тэмдэг (voice.ico, icon.svg)
└── tts_server.py          # 🧠 Python VoiceStudio AI модуль (хөгжүүлэгчдэд)
```

---

## 🛠️ Хөгжүүлэгчдэд зориулсан заавар (Developer Guide)

Хэрэв та эх кодоос өөрчлөлт оруулах эсвэл өөрөө компайл хийхийг хүсвэл:

### 1. Интерфейсийг статикаар компайл хийх:
```bash
npm run build
```
Энэ нь Next.js кодыг `out/` хавтас руу статик үйлдвэрлэлийн бүтцээр хөрвүүлнэ.

### 2. Локал серверийг турших:
```bash
node server.cjs 8000
```
`http://127.0.0.1:8000` хаяг дээр ажиллаж буйг шалгана.

### 3. C# Асаагч болон Суулгагчийг бүтээх:
Windows-ийн суурь `csc.exe` ашиглан:
```powershell
# VOICE.exe бүтээх
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /out:"VOICE.exe" /win32icon:public\voice.ico /r:System.Drawing.dll /r:System.Windows.Forms.dll "VoiceLauncher.cs"
```

---

## 🔒 Нууцлал ба Аюулгүй байдал (Privacy & Security)

- **100% Локал ажиллагаа:** Таны компьютерт суусан VOICE аппликейшн нь бүх интерфэйс болон хөдөлгүүрээ таны локал систем (`127.0.0.1`) дээр ажиллуулна.
- **Хувийн нууц:** Микрофоны бичлэг гадны сервер рүү дур мэдэн хуулагдахгүй. Зөвхөн хэрэглэгчийн тохируулсан үйлчилгээнд (Chimege эсвэл Google Web Speech) яриа танихаар ашиглагдана.

---

## 📄 Лиценз

Энэхүү төсөл нь [MIT License](LICENSE) эрхтэйгээр нээлттэй хөгжүүлэгдэж байна.
Зохиогч: **Ариукагийн Түвшинжаргал** (@AriukagiinTuvshoo).
