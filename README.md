# 🎙️ VOICE — Speak. Clean. Write.

<p align="center">
  <img src="public/voice.ico" width="80" height="80" alt="VOICE Logo" />
</p>

<p align="center">
  <b>Монгол, Англи, Япон хэлний бодит цагийн холимог яриа танигч, зөв бичгийн дүрэм шалгагч (spellcheck.mn), VoiceStudio AI хоолой хувилагч болон Windows-ийн дурын програм (Word, Facebook, Chrome, Excel, Telegram) дээр курсор алдалгүй шууд ярьж бичих ухаалаг систем.</b>
</p>

<p align="center">
  <a href="https://github.com/AriukagiinTuvshoo/voice-app/releases/latest"><img src="https://img.shields.io/badge/Release-v1.2.0-indigo?style=for-the-badge&logo=windows" alt="Version 1.2.0" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011%20(64--bit)-blue?style=for-the-badge&logo=windows" alt="Platform Windows" />
  <img src="https://img.shields.io/badge/Startup_Speed-1.0s%20Instant-brightgreen?style=for-the-badge&logo=speedtest" alt="Speed 1s" />
  <img src="https://img.shields.io/badge/Multilingual-MN%20%7C%20EN%20%7C%20JA-purple?style=for-the-badge" alt="Trilingual" />
  <img src="https://img.shields.io/badge/License-MIT-orange?style=for-the-badge" alt="License MIT" />
</p>

---

## 🚀 1. Компьютерт суулгах (1 Товшилтоор)

### 📥 [Албан ёсны суулгагч татах — VOICE-Setup.exe (v1.2.0)](https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.2.0/VOICE-Setup.exe)
*(GitHub Release хуудас: [VOICE Desktop Release v1.2.0](https://github.com/AriukagiinTuvshoo/voice-app/releases/tag/v1.2.0))*

1. Дээрх холбоос дээр дарж **`VOICE-Setup.exe`** (ердөө 414 KB) файлыг татаж авна.
2. **`VOICE-Setup.exe`** дээр давхар товшоод **"🚀 Суулгах ба Нээх"** товчийг дарна.
3. Таны компьютерын дэлгэц (**Desktop**) дээр нил ягаан дүрс бүхий **`VOICE`** апп үүсэж, дэлгэцийн доор **`VOICE FLOW`** хөвөгч капсул бэлэн болно!

> 💡 **Онцлог:** Ямар ч Node.js, Python, сан суулгах эсвэл хар цонх (terminal) нээх шаардлагагүй. 1 секундийн дотор бүрэн сууж шууд ажиллана.

---

## 🌟 2. Гол боломжууд ба Шинэчлэлтүүд

### 1. 🖥️ Chrome, Word, Facebook дээр курсор алдахгүй шууд бичих (Non-Activating FlowBar)
- **Фокус алдахгүй технологи (`WS_EX_NOACTIVATE`):** Хөвөгч товч дээр хулганаар дарах эсвэл дэлгэцээр чирч хөдөлгөхөд Chrome, Word эсвэл Facebook-ийн бичих талбарын курсор **хэзээ ч арилахгүй, фокусаа алдахгүй**.
- **Шууд буулгах:** Та курсороо хүссэн газраа тавиад:
  - Гар дээрээ **`Ctrl + Alt`** (эсвэл **`F8`**) дарах
  - Эсвэл дэлгэц дээрх хөвөгч **`VOICE FLOW`** товч дээр дараад ярихад яриа дуусмагц яг курсор байгаа газарт автоматаар хуулагдан бичигдэнэ!

### 2. 🌐 3-Хэлний холимог яриа танигч (Trilingual Multilingual Code-Switching)
- **Монгол + Англи + Япон зэрэг танина:** Та 3 хэлийг нэг өгүүлбэрт хольж ярихад систем автоматаар ялган хөрвүүлнэ:
  - Жишээ: *"Сайн уу, hi my name is ..., 私の名前は..."* гэж ярихад монгол үг нь криллээр, англи үг нь латинаар, япон үг нь ханз/кана үсгээр зэрэг зөв бичигдэнэ.
- **Хэл солих сонголт:** Товч дээрх хэлний тэмдэг дээр дараад **`🌐 AUTO`**, **`🇲🇳 MN`**, **`🇬🇧 EN`**, **`🇯🇵 JA`** горимуудын хооронд шилжүүлж болно.

### 3. 🎨 Орчин үеийн нео-индиго загвар ба Хөдөлгөөнт төлөвүүд
Хэт харанхуй биш, нүдэнд ээлтэй гүн индиго (`#121626`) дэвсгэр, гэрэлтсэн нил ягаан хүрээ бүхий капсул дизайн:
- 🟣 **Энгийн (Idle):** Нил ягаан хүрээ `VOICE FLOW (Ctrl+Alt)`
- 🔴 **Ярьж байх үед (Recording):** Улаан гэрэлтэх хүрээ ба лугших цэгүүд `🔴 Ярьж байна...`
- 🔵 **Боловсруулах үед (Processing):** Цэнхэр хүрээ `⏳ Текст болгож байна...`
- 🟢 **Амжилттай бичигдсэн (Success):** Ногоон хүрээ `✅ [Таны ярьсан текст]` -> 2 секундийн дараа анхны байдалдаа шилжинэ.
- **Хүссэн газраа байрлуулах:** Зүүн талын бариул (`⠿`) дээр дарж дэлгэцийн аль ч хэсэг рүү чирж тавьж болно (байрлалыг автоматаар цээжилнэ).

### 4. 🟢 VoiceStudio AI — Ногоон бэлэн төлөв & Дуу хоолой хувилах
- Өмнөх хувилбаруудын "Сервер унтарсан" шар анхааруулга арилж, шууд **🟢 VoiceStudio Сервер Бэлэн (localhost:8000)** төлөвтэй ажиллана.
- **Voice Clone:** 5–10 секундийн бичлэгээр хүний дуу хоолойн тембр, өнгийг хувилж хүссэн бичвэрээ уншуулна.
- **Студи хоолойнууд:** Есүй, Батаа, Тэмүүлэн, Ану, Ананд, Марал зэрэг 12 төрлийн студийн хоолойнууд.

### 5. ✨ Монгол хэлний зөв бичгийн дүрэм (`spellcheck.mn`)
- Бичсэн текст дундах зөв бичих дүрмийн алдааг бодит цагт илрүүлж 1 товшилтоор засна.

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
├── VOICE-Setup.exe        # 📦 1-Товшилтоор Windows-д суулгагч файл (414 KB)
├── VOICE.exe              # 🚀 Desktop асаагч ба Non-Activating FlowBar хөвөгч товч (C#)
├── server.cjs             # ⚡ Локал FLAC/Multilingual STT, TTS API & статик хөдөлгүүр
├── out/                   # 🎨 Бэлэн компайл хийгдсэн интерфейсийн файлууд (HTML/CSS/JS)
├── app/                   # 💻 Next.js хуудаснууд (Dashboard, VoiceStudio, History, Settings)
├── components/            # 🧩 UI элементүүд (AppShell, Icons, Waveform)
├── lib/                   # 🛠️ Аудио бичигч, яриа боловсруулагч, spellcheck клиент
├── public/                # 🖼️ Аппликейшний нил ягаан дүрс тэмдэг (voice.ico, icon.svg)
└── tts_server.py          # 🧠 Python VoiceStudio AI модуль
```

---

## 🛠️ Хөгжүүлэгчдэд зориулсан заавар (Developer Guide)

Хэрэв та эх кодоос өөрчлөлт оруулах эсвэл өөрөө компайл хийхийг хүсвэл:

### 1. Интерфейсийг статикаар компайл хийх:
```bash
npm run build
```
Энэ нь Next.js кодыг `out/` хавтас руу статик бүтцээр экспорт хийнэ.

### 2. Локал серверийг турших:
```bash
node server.cjs 8000
```
`http://127.0.0.1:8000` хаяг дээр ажиллаж буйг шалгана.

### 3. C# Асаагч болон Суулгагчийг бүтээх:
```powershell
# VOICE.exe бүтээх (WS_EX_NOACTIVATE фокусгүй горимтой)
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /target:winexe /optimize+ /out:"VOICE.exe" "scratch\VoiceLauncher.cs" /win32icon:public\voice.ico

# VOICE-Setup.exe бүтээх
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /target:winexe /optimize+ /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /out:"VOICE-Setup.exe" "scratch\VoiceSetup.cs" /resource:"scratch\payload.zip",payload.zip /win32icon:public\voice.ico
```

---

## 🔒 Нууцлал ба Аюулгүй байдал (Privacy & Security)

- **100% Локал ажиллагаа:** Таны компьютерт суусан VOICE аппликейшн нь бүх интерфэйс болон хөдөлгүүрээ таны локал систем (`127.0.0.1`) дээр ажиллуулна.
- **Хувийн нууц:** Микрофоны бичлэг ямар ч дундын серверт хадгалагдахгүй.

---

## 📄 Лиценз

Энэхүү төсөл нь [MIT License](LICENSE) эрхтэйгээр нээлттэй хөгжүүлэгдэж байна.
Зохиогч: **@AriukagiinTuvshoo**.
