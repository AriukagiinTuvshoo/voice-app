"use client";

import { useState, useEffect } from "react";
import { MicIcon, CheckIcon, CopyIcon, SparklesIcon } from "@/components/Icons";

export default function KeyboardPage() {
  const [activeOs, setActiveOs] = useState<"android" | "ios" | "windows">("android");
  const [originUrl, setOriginUrl] = useState("https://voice-app.onrender.com");
  const [copiedUrl, setCopiedUrl] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setOriginUrl(window.location.origin);
      if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        setActiveOs("ios");
      } else if (!/Android/i.test(navigator.userAgent)) {
        setActiveOs("windows");
      }
    }
  }, []);

  const dictateEndpoint = `${originUrl}/api/ios-dictate`;
  const apkDownloadUrl =
    "https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.0.0/VOICE-Keyboard.apk";
  const ipaDownloadUrl =
    "https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.0.0/VOICE-Keyboard-iOS.ipa";

  const copyEndpoint = () => {
    navigator.clipboard?.writeText(dictateEndpoint);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  return (
    <section className="page">
      <h1>⌨️ Утасны VOICE Гар (Android & iPhone)</h1>
      <p>
        Утсаараа Chrome, Google хайлт, Facebook, Messenger, Instagram доторх бичих нүдэн дээр{" "}
        <b>хуулж буулгахгүйгээр шууд ярьж бичих</b> системийн гар.
      </p>

      {/* OS Selector Tabs */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          marginTop: "20px",
          borderBottom: "1px solid var(--border)",
          paddingBottom: "14px",
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={() => setActiveOs("windows")}
          className="btn-secondary"
          style={{
            background: activeOs === "windows" ? "var(--accent)" : "var(--surface)",
            color: activeOs === "windows" ? "#fff" : "var(--text)",
            padding: "10px 20px",
            borderRadius: "12px",
            fontWeight: 700,
          }}
        >
          💻 Windows Компьютер (Ctrl+Alt)
        </button>

        <button
          type="button"
          onClick={() => setActiveOs("android")}
          className="btn-secondary"
          style={{
            background: activeOs === "android" ? "var(--accent)" : "var(--surface)",
            color: activeOs === "android" ? "#fff" : "var(--text)",
            padding: "10px 20px",
            borderRadius: "12px",
            fontWeight: 700,
          }}
        >
          🤖 Android Гар (APK)
        </button>

        <button
          type="button"
          onClick={() => setActiveOs("ios")}
          className="btn-secondary"
          style={{
            background: activeOs === "ios" ? "var(--accent)" : "var(--surface)",
            color: activeOs === "ios" ? "#fff" : "var(--text)",
            padding: "10px 20px",
            borderRadius: "12px",
            fontWeight: 700,
          }}
        >
          🍎 iPhone / iOS
        </button>
      </div>

      {/* WINDOWS TAB */}
      {activeOs === "windows" && (
        <div style={{ display: "grid", gap: "18px", marginTop: "20px" }}>
          {/* Method 1: Chrome Extension - Recommended & Block-free */}
          <div
            className="settings"
            style={{
              background: "linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(15, 23, 42, 0.95))",
              border: "1px solid rgba(16, 185, 129, 0.4)",
            }}
          >
            <h2 style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <SparklesIcon width={18} height={18} style={{ color: "#10b981" }} />
              <span>Шилдэг арга: Google Chrome Өргөтгөл (100% Аюулгүй, Windows хэзээ ч блоклохгүй)</span>
            </h2>
            <p style={{ marginBottom: "16px" }}>
              Chrome, Edge хөтөч дээрээ суулгаснаар <b>Google хайлт, Facebook, YouTube, Messenger, Gmail, Word Online</b> зэрэг бүх вэбсайт дээр курсороо тавиад л гар дээрээ <kbd>Alt + Shift + V</kbd> дарж шууд ярьж бичнэ.
            </p>

            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center", marginBottom: "16px" }}>
              <a
                href="/api/download/extension"
                download="VOICE-Chrome-Extension.zip"
                className="btn-primary"
                style={{
                  textDecoration: "none",
                  padding: "12px 24px",
                  fontSize: "15px",
                  borderRadius: "14px",
                  background: "linear-gradient(135deg, #10b981, #059669)",
                }}
              >
                ⬇️ Chrome Өргөтгөл татах (.zip)
              </a>
            </div>

            <div style={{ display: "grid", gap: "8px", fontSize: "13px", lineHeight: 1.6 }}>
              <div style={{ padding: "8px 12px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>1. Татаж задлах:</b> Дээрх ногоон товчоор zip файлаа татаад хавтсанд нь задална.
              </div>
              <div style={{ padding: "8px 12px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>2. Chrome-д оруулах:</b> Chrome хөтчийн хаягийн мөрөнд <code>chrome://extensions</code> гэж бичиж ороод баруун дээд талын <b>Developer mode</b> асаана. Тэгээд <b>Load unpacked</b> товч дарж задалсан хавтсаа сонгоно.
              </div>
              <div style={{ padding: "8px 12px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>3. Шууд ярьж бичих:</b> Google хайлтын нүд, Facebook коммент дээр курсороо тавиад <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd> дараад ярина!
              </div>
            </div>
          </div>

          {/* Method 2: Windows System-wide Helper (.bat) */}
          <div className="settings">
            <h2>Арга 2: Word, Excel офлайн програмд бичих (Windows Helper)</h2>
            <p style={{ marginBottom: "14px" }}>
              Хэрэв та зөвхөн хөтөч биш, офлайн <b>Microsoft Word, Excel, Notepad</b> зэрэг бүх цонхонд шууд ярьж бичихийг хүсвэл Windows Helper-ийг ашиглана:
            </p>

            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center", marginBottom: "14px" }}>
              <a
                href="/api/download/helper"
                download="VOICE-Windows-Helper.bat"
                className="btn-secondary"
                style={{ textDecoration: "none" }}
              >
                ⬇️ Windows Helper татах (.bat)
              </a>
            </div>

            <div style={{ padding: "12px 14px", background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "12px", fontSize: "13px", lineHeight: 1.6 }}>
              <b style={{ color: "#f59e0b" }}>⚠️ Windows Smart App Control блоколбол:</b>
              <br />Windows 11 нь интернетээс татсан үл мэдэгдэх .bat файлыг анхааруулдаг.
              <br />1. Татсан <code>VOICE-Windows-Helper.bat</code> файл дээрээ <b>Хулганы баруун товч (Right-click) → Properties (Шинж чанар)</b> дарна.
              <br />2. Доод хэсэгт байх <b>"Unblock" (Блок гаргах)</b> нүдийг чагтлаад <b>OK</b> дарна.
              <br />3. Одоо файл дээрээ давхар товшиж ажиллуулаад <kbd>Ctrl + Alt</kbd> дарж чөлөөтэй бичнэ!
            </div>
          </div>
        </div>
      )}

      {/* ANDROID TAB */}
      {activeOs === "android" && (
        <div style={{ display: "grid", gap: "18px", marginTop: "20px" }}>
          {/* Visual Mockup of the Android Keyboard */}
          <div
            className="settings"
            style={{
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(15, 23, 42, 0.95))",
              border: "1px solid rgba(99, 102, 241, 0.4)",
            }}
          >
            <h2 style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <MicIcon width={18} height={18} style={{ color: "var(--accent)" }} />
              <span>VOICE Keyboard (Android Системийн Гар)</span>
            </h2>
            <p style={{ marginBottom: "16px" }}>
              Суулгасны дараа таны утасны гар дээр <b>🇲🇳 Монгол Кирилл үсэгнүүд</b> болон дээд хэсэгт нь{" "}
              <b>🎤 Дарж ярих (VOICE AI)</b> товч гарч ирнэ. Chrome эсвэл Google-ийн хайлтын хэсэг дээр дараад{" "}
              <b>🎤</b> товчоо дарж ярихад текст шууд бичигдэнэ!
            </p>

            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
              <a
                href={apkDownloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
                style={{
                  textDecoration: "none",
                  padding: "12px 24px",
                  fontSize: "15px",
                  borderRadius: "14px",
                }}
              >
                ⬇️ VOICE-Keyboard.apk Татах (Android)
              </a>

              <a
                href="https://github.com/AriukagiinTuvshoo/voice-app/actions"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
                style={{ textDecoration: "none", fontSize: "13px" }}
              >
                ⚙️ GitHub Build Төлөв харах
              </a>
            </div>
          </div>

          <div className="settings">
            <h2>Android утсанд суулгах 3 алхам:</h2>
            <div style={{ display: "grid", gap: "12px", marginTop: "12px", fontSize: "14px", lineHeight: 1.6 }}>
              <div style={{ padding: "12px 16px", background: "var(--subtle)", borderRadius: "12px" }}>
                <b>1. APK татаж суулгах:</b> Дээрх <b>VOICE-Keyboard.apk Татах</b> товч дээр дарж татаад утсандаа{" "}
                <i>Install</i> хийнэ.
              </div>
              <div style={{ padding: "12px 16px", background: "var(--subtle)", borderRadius: "12px" }}>
                <b>2. Зөвшөөрөл ба Идэвхжүүлэх:</b> Суусан <b>VOICE Keyboard</b> аппыг нээгээд:
                <br />• <b>1-р алхам:</b> Микрофон зөвшөөрөх
                <br />• <b>2-р алхам:</b> Гарын тохиргоо руу орж <i>VOICE Keyboard</i>-ийг асаах
                <br />• <b>3-р алхам:</b> Үндсэн гараар <i>VOICE Keyboard</i> сонгох
              </div>
              <div style={{ padding: "12px 16px", background: "var(--subtle)", borderRadius: "12px" }}>
                <b>3. Серверийн хаяг тохируулах:</b> Апп доторх серверийн хаяг дээр таны онлайн хаяг (
                <code>{originUrl}</code>) байгаа эсэхийг шалгаад <b>Хадгалах</b> дарна. Одоо Chrome, Google, Messenger дээр шууд ярьж бичээрэй!
              </div>
            </div>
          </div>
        </div>
      )}

      {/* iOS / iPHONE TAB */}
      {activeOs === "ios" && (
        <div style={{ display: "grid", gap: "18px", marginTop: "20px" }}>
          {/* Method 1: Instant iPhone Shortcut + Back Tap / Action Button */}
          <div
            className="settings"
            style={{
              background: "linear-gradient(135deg, rgba(16, 185, 129, 0.10), rgba(15, 23, 42, 0.95))",
              border: "1px solid rgba(16, 185, 129, 0.4)",
            }}
          >
            <h2 style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <SparklesIcon width={18} height={18} style={{ color: "#10b981" }} />
              <span>Арга 1: iPhone дээр 30 секундэд шууд ажиллуулах (App Store шаардлагагүй)</span>
            </h2>
            <p style={{ marginBottom: "14px" }}>
              iPhone-ийн өөрийн <b>Shortcuts (Богино холбоос)</b> болон <b>Back Tap (Утасны ар талд 2 товших)</b> эсвэл{" "}
              <b>Action Button</b> ашиглан Chrome, Safari, Google, Messenger-ийн аль ч бичих нүдэн дээр ярьж бичих боломжтой:
            </p>

            <div
              style={{
                padding: "12px 14px",
                background: "var(--subtle)",
                borderRadius: "12px",
                border: "1px solid var(--border)",
                marginBottom: "14px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "10px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ fontSize: "13px" }}>
                <div style={{ color: "var(--muted)", fontSize: "11px" }}>iPhone Dictation API хаяг:</div>
                <code style={{ color: "var(--accent)", fontWeight: 700, wordBreak: "break-all" }}>
                  {dictateEndpoint}
                </code>
              </div>
              <button type="button" onClick={copyEndpoint} className="btn-secondary" style={{ fontSize: "12px" }}>
                {copiedUrl ? <CheckIcon width={14} height={14} /> : <CopyIcon width={14} height={14} />}
                <span>{copiedUrl ? "Хуулагдлаа!" : "Хаяг хуулах"}</span>
              </button>
            </div>

            <div style={{ display: "grid", gap: "10px", fontSize: "13px", lineHeight: 1.6 }}>
              <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>Алхам 1:</b> iPhone дээрх <b>Shortcuts</b> апп руу ороод <b>+</b> дарж шинэ Shortcut үүсгэнэ.
              </div>
              <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>Алхам 2:</b> <b>Record Audio</b> үйлдэл нэмнэ (<i>Stop Recording: On Tap</i>).
              </div>
              <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>Алхам 3:</b> <b>Get Contents of URL</b> нэмээд URL дээр дээрх хуулсан хаягаа тавина:{" "}
                <br />• <i>Method:</i> <b>POST</b>
                <br />• <i>Request Body:</i> <b>Form</b> → <code>audio</code> (Type: <b>File</b> = Recorded Audio)
              </div>
              <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "10px" }}>
                <b>Алхам 4:</b> <b>Copy to Clipboard</b> үйлдэл нэмээд хадгална. Дараа нь iPhone-ийн{" "}
                <b>Settings → Accessibility → Touch → Back Tap → Double Tap</b> дээр энэ Shortcut-аа сонгоход та Chrome/Google дээр байхдаа утасныхаа ар талд 2 товшоод л шууд ярьж бичнэ!
              </div>
            </div>
          </div>

          {/* Method 2: Native iOS Keyboard Extension (.ipa) */}
          <div className="settings">
            <h2>Арга 2: iPhone Системийн Гар (VOICE-Keyboard-iOS.ipa)</h2>
            <p style={{ marginBottom: "14px" }}>
              Бид iPhone-д зориулсан бүрэн <b>iOS Keyboard Extension (Swift)</b> эх код болон <code>.ipa</code> файлыг мөн бэлдсэн. Хэрэв танд <b>AltStore / Sideloadly</b> эсвэл <b>Xcode</b> байгаа бол утсандаа системийн гар болгон суулгаж болно:
            </p>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <a
                href={ipaDownloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
                style={{ textDecoration: "none" }}
              >
                ⬇️ VOICE-Keyboard-iOS.ipa Татах
              </a>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
