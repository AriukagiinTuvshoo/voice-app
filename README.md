# 🎙️ VOICE — Speak. Clean. Write.

<p align="center">
  <img src="public/voice.ico" width="84" height="84" alt="VOICE Logo" />
</p>

<p align="center">
  <b>Монгол, Англи, Япон хэлний бодит цагийн холимог яриа танигч, зөв бичгийн дүрэм засварлагч (spellcheck.mn), VoiceStudio AI хоолой хувилагч болон Windows-ийн дурын програм (Word, Chrome, Facebook, Excel, Telegram) дээр курсор алдалгүй, фонт эвдэхгүй шууд бичих ухаалаг систем.</b>
</p>

<p align="center">
  <a href="https://github.com/AriukagiinTuvshoo/voice-app/releases/latest"><img src="https://img.shields.io/badge/Release-v1.4.1-6366f1?style=for-the-badge&logo=windows" alt="Version 1.4.1" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(64--bit)-blue?style=for-the-badge&logo=windows" alt="Platform Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-brightgreen?style=for-the-badge&logo=python" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Node.js-Not%20Required-blueviolet?style=for-the-badge" alt="No Node Needed" />
  <img src="https://img.shields.io/badge/API-Free%20%7C%20No%20Key-success?style=for-the-badge" alt="Free No Key" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License MIT" />
</p>

---

## 📥 1. Татах ба Суулгах заавар (Quick Start)

### 🌟 Сонголт 1: Бие даасан Windows Installer (Санал болгож буй)
👉 [**VOICE-Setup-v1.4.1.exe татах (GitHub Releases)**](https://github.com/AriukagiinTuvshoo/voice-app/releases/latest)
- Администраторын UAC эрх шаардахгүй (`%LOCALAPPDATA%\Programs\VOICE`).
- Desktop болон Start Menu товчлолыг автоматаар үүсгэнэ.
- Хэрэглэгчийн тохиргоо, дуу хоолойн профайл нь тусдаа `%APPDATA%\VOICE` хавтсанд найдвартай хадгалагдах бөгөөд шинэчлэлт хийх эсвэл устгах үед хамгаалагдана.
- Шаардлагатай бүх хиймэл оюуны бинар файлууд (FFmpeg libass, whisper.cpp), Next.js статик интерфейс багтсан.

### 📦 Сонголт 2: Portable Zip хувилбар
👉 [**VOICE-Windows-v1.4.1.zip татах (GitHub Releases)**](https://github.com/AriukagiinTuvshoo/voice-app/releases/latest)
1. Zip файлыг татаж аваад **Extract All... (Бүгдийг задлах)** сонгоно.
2. Хавтас доторх **`Install-VOICE.bat`** файл дээр давхар товшиж ажиллуулна.
3. Desktop дээр үүссэн **`VOICE`** товчлолоор эхлүүлнэ.

---

## 🎙️ 2. Хэрхэн ашиглах вэ? (Word, OneNote, Notepad, Chrome дээр шууд бичих)

VOICE-ийн гол давуу тал нь **курсор байгаа газарт яриаг үг алдагдалгүй, фонт эвдэхгүй шууд шивэх** явдал юм.

```text
1. Word, OneNote, Notepad, Excel, Chrome, Telegram эсвэл дурын бичих талбар дээр курсороо тавина.
2. Гар дээрээ Ctrl + Alt эсвэл F8 товч дарна (эсвэл дэлгэц дээрх VOICE FLOW товч дээр дарна).
3. Товч улаан өнгөтэй болж "Ярьж байна..." горимд шилжихэд микрофондоо ярина.
4. Ярьж дуусмагц товч автоматаар текстийг боловсруулаад яг таны курсор байсан цэгт шууд хуулж оруулна!
```

### 🔤 Unicode NFC & Фонт нийцтэй байдал
- **Дөрвөлжин тэмдэг (`□`) гарахгүй:** Бүх текст автоматаар **Unicode NFC** хэлбэрт нормалчлагдан, Windows native **`CF_UNICODETEXT` (13)** форматаар clipboard руу бичигддэг тул `ө`, `ү` үсгүүд ANSI эвдрэлгүй гарна.
- **Хэрэглэгчийн фонтыг хадгална:** Текстийг RTF/HTML форматаар хүчээр хөрвүүлдэггүй цэвэр Unicode байдлаар дамжуулдаг тул MS Word, OneNote дээр таны идэвхтэй ашиглаж буй фонт (Arial, Times New Roman, Calibri гэх мэт) болон үсгийн хэмжээ хэвээр хадгалагдана.

---

## 🌟 3. Системийн Tray & Background Daemon

Дэлгэцийн баруун доод буланд байрлах **System Tray** цэснээс:
- **VOICE нээх:** Хянах самбарыг хөтөч дээр нээх.
- **FlowBar харуулах / нуух:** Хөвөгч товчийг дэлгэц дээр үзүүлэх эсвэл нуух.
- **Байрлал шинэчлэх:** FlowBar байрлалыг дэлгэцийн анхны байрлалд оруулах.
- **Хэл сонгох (Language):** Монгол хэл (MN), Англи хэл (EN), Автомат (Auto) хооронд шууд сэлгэх.
- **Дуугаар бичихийг түр зогсоох (Pause):** Бичилтийг түр түдгэлзүүлж, дуудлага хүсэлтийг алгасах.
- **Шинэ хувилбар шалгах:** GitHub Releases дээр шинэ хувилбар гарсныг шалгах (`auto_updater.py`).
- **Windows-той хамт эхлэх:** Систем асахад автоматаар чимээгүй эхлэх (`--background` далд горим).
- **Гарах (Quit VOICE):** Системийг бүрэн хаах.

---

## ⌨️ Товчлуурын хослолууд (Shortcuts)

| Товчлуур | Үйлдэл | Тайлбар |
|---|---|---|
| **`F8`** | ⚡ Шуурхай яриа эхлүүлэх | **Санал болгох** (AltGr зөрчилгүй, 1 товчоор ярих) |
| **`Ctrl + Alt`** | 🎙️ VOICE FLOW Шууд ярих | Компьютерын дурын цонх руу шууд бичнэ |
| **`Space`** | 🔴 Ажлын талбарт ярих | VOICE апп дотор яриа эхлүүлэх / зогсоох |
| **`Esc`** | ✕ FlowBar нуух | Хөвөгч товчийг дэлгэцээс түр нууна |

---

## 📁 Төслийн бүтэц

```text
voice-app/
├── installer/
│   └── voice-setup.iss        # 📦 Inno Setup standalone installer скрипт (v1.4.1)
├── tools/
│   ├── ffmpeg/ffmpeg.exe      # 🎬 Native FFmpeg build with libass
│   └── whisper.cpp/Release/   # 🤖 Native CPU/CUDA whisper-cli бинар
├── auto_updater.py            # 🔄 GitHub Releases авто шинэчлэгч & SHA256 шалгагч
├── audio_separator.py         # 🎛️ AI Хөгжим, хоолой салгагч хөдөлгүүр
├── karaoke_ass.py             # 🎤 Word-level SSA/ASS караоке экспортлогч
├── mongolian_grammar.py       # 🇲🇳 Монгол хэлний залгавар ба дүрмийн хөдөлгүүр
├── voice_cloning.py           # 🗣️ VoiceStudio дуу хоолой хувилагч & тембр
├── tts_server.py              # 🧠 Python хөдөлгүүр (FastAPI, Tray, Hotkey & Tkinter FlowBar)
├── voice_core.py              # 🧩 Цэвэр логик функцууд (clamping, sanitize, math, status)
├── Install-VOICE.bat          # 🚀 1-Товшилтоор системд суулгах ба Desktop товчлол үүсгэгч
├── Start-VOICE.bat            # ⚡ VOICE системийг серверийн хамт далд эхлүүлэгч
├── Uninstall-VOICE.bat        # 🗑️ VOICE системийг компьютерээс бүрэн устгагч
├── out/                       # 🎨 Бэлэн веб интерфэйсийн статик файлууд (HTML/CSS/JS)
├── public/                    # 🖼️ Нил ягаан дүрс тэмдэг (voice.ico, icon.svg)
├── requirements.txt           # 📦 Үндсэн Python сангууд
├── requirements-tray.txt      # 📦 Системийн Tray дүрс тэмдэг (pystray, Pillow)
├── VERSION                    # 🏷️ Хувилбарын дугаар (1.4.1)
├── README.md                  # 📖 Дэлгэрэнгүй заавар
└── LICENSE                    # 📄 MIT лиценз
```

### 🔒 Хэрэглэгчийн өгөгдлийн тусгаарлалт
- **Програмын код/бинар:** `%LOCALAPPDATA%\Programs\VOICE`
- **Хэрэглэгчийн тохиргоо ба хувилсан хоолой:** `%APPDATA%\VOICE` (`voice_settings.json`, `clones/`, `history/`)
- Програмыг шинэчлэх эсвэл хасах үед таны бүтээсэн дуу хоолой болон тохиргоо устахгүй хэвээр үлдэнэ.

---

## 📄 Лиценз

Энэхүү төсөл нь [MIT License](LICENSE) эрхтэйгээр нээлттэй хөгжүүлэгдэж байна.  
Хөгжүүлэгч: **@AriukagiinTuvshoo**
