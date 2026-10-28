"use client";

import { useState, useEffect } from "react";
import { MicIcon, CheckIcon, SparklesIcon, FlowBarIcon } from "@/components/Icons";

export default function ComputerVoicePage() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [localStatus, setLocalStatus] = useState<{
    nextServer: boolean;
    pyEngine: boolean;
    checking: boolean;
  }>({
    nextServer: true,
    pyEngine: false,
    checking: true,
  });

  useEffect(() => {
    // Check local servers
    async function checkHealth() {
      let py = false;
      try {
        const res = await fetch("http://127.0.0.1:8000/docs", { method: "HEAD", mode: "no-cors" });
        py = true;
      } catch {
        py = false;
      }
      setLocalStatus({
        nextServer: true,
        pyEngine: py,
        checking: false,
      });
    }
    checkHealth();
  }, []);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <section className="page" style={{ maxWidth: "900px", margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
          }}
        >
          <FlowBarIcon width={24} height={24} />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px" }}>💻 Компьютерын Local VOICE</h1>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: "14px" }}>
            Facebook, Google хайлт, Word, Excel зэрэг бүх цонхонд <b>F8</b> дараад шууд ярьж бичих
          </p>
        </div>
      </div>

      {/* Local Server Status Banner */}
      <div
        style={{
          marginTop: "16px",
          marginBottom: "24px",
          padding: "12px 18px",
          borderRadius: "14px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: "#10b981",
              boxShadow: "0 0 10px #10b981",
            }}
          />
          <span style={{ fontSize: "13px", fontWeight: 600 }}>
            Локал горим (100% Local PC): Вэб сервер <span style={{ color: "#10b981" }}>Бэлэн</span>
          </span>
        </div>

        <div style={{ fontSize: "12px", color: "var(--muted)" }}>
          Шууд ажиллуулах: <code>Start-VOICE-App.bat</code>
        </div>
      </div>

      {/* 2 Main Solutions for PC */}
      <div style={{ display: "grid", gap: "20px" }}>
        
        {/* Solution 1: Chrome & Edge Extension */}
        <div
          className="settings"
          style={{
            background: "linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(15, 23, 42, 0.95))",
            border: "1px solid rgba(16, 185, 129, 0.4)",
            padding: "24px",
            borderRadius: "18px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px", marginBottom: "12px" }}>
            <h2 style={{ display: "flex", alignItems: "center", gap: "10px", margin: 0, fontSize: "18px" }}>
              <SparklesIcon width={20} height={20} style={{ color: "#10b981" }} />
              <span>1. Google Chrome Өргөтгөл (Хамгийн хялбар - Вэб сайтуудад)</span>
            </h2>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "#10b981",
                padding: "4px 10px",
                background: "rgba(16, 185, 129, 0.2)",
                borderRadius: "20px",
              }}
            >
              100% Аюулгүй / Блокгүй
            </span>
          </div>

          <p style={{ color: "var(--muted)", fontSize: "14px", lineHeight: 1.6, marginBottom: "16px" }}>
            Chrome болон Edge хөтөч дээрээ суулгаснаар <b>Facebook, Google хайлт, YouTube, Messenger, Gmail</b> зэрэг бүх сайт дээр курсороо тавиад л гар дээрх <b>F8</b> товчоор эсвэл дэлгэцийн баруун доод буланд гарах <b>🎤 VOICE</b> товч дээр товшиж шууд ярьж бичнэ.
          </p>

          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center", marginBottom: "20px" }}>
            <a
              href="/api/download/extension"
              download="VOICE-Chrome-Extension.zip"
              className="btn-primary"
              style={{
                textDecoration: "none",
                padding: "12px 24px",
                fontSize: "14px",
                borderRadius: "14px",
                background: "linear-gradient(135deg, #10b981, #059669)",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                fontWeight: 700,
              }}
            >
              ⬇️ Chrome Өргөтгөл татах (.zip)
            </a>
          </div>

          <div style={{ display: "grid", gap: "10px", fontSize: "13px", lineHeight: 1.6 }}>
            <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "12px", display: "flex", gap: "10px" }}>
              <span style={{ fontWeight: 700, color: "#10b981" }}>1.</span>
              <div>
                <b>Задлах:</b> Татсан <code>VOICE-Chrome-Extension.zip</code> файлыг компьютерынхоо дурын хавтсанд задлана (Extract).
              </div>
            </div>

            <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "12px", display: "flex", gap: "10px" }}>
              <span style={{ fontWeight: 700, color: "#10b981" }}>2.</span>
              <div>
                <b>Chrome-д оруулах:</b> Chrome-ын хаягийн мөрөнд <code>chrome://extensions</code> гэж бичиж ороод баруун дээд буланд байх <b>Developer mode</b>-ийг асаана. Тэгээд <b>Load unpacked</b> товч дарж задалсан хавтсаа сонгоно.
              </div>
            </div>

            <div style={{ padding: "10px 14px", background: "var(--subtle)", borderRadius: "12px", display: "flex", gap: "10px" }}>
              <span style={{ fontWeight: 700, color: "#10b981" }}>3.</span>
              <div>
                <b>Шууд ярьж бичих:</b> Facebook коммент, Google хайлт дээр курсороо тавиад л <b>F8</b> товчоо дараад ярина!
              </div>
            </div>
          </div>
        </div>

        {/* Solution 2: Offline Windows Desktop Helper */}
        <div
          className="settings"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            padding: "24px",
            borderRadius: "18px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px", marginBottom: "12px" }}>
            <h2 style={{ display: "flex", alignItems: "center", gap: "10px", margin: 0, fontSize: "18px" }}>
              <MicIcon width={20} height={20} style={{ color: "var(--accent)" }} />
              <span>2. Windows Бүх Програмд Бичих (Microsoft Word, Excel, Notepad)</span>
            </h2>
          </div>

          <p style={{ color: "var(--muted)", fontSize: "14px", lineHeight: 1.6, marginBottom: "16px" }}>
            Хэрэв та Microsoft Word, Excel, Notepad, Telegram зэрэг компьютерынхаа ямар ч цонхонд шууд ярьж бичихийг хүсвэл төслийн үндсэн хавтас дахь файлыг ашиглана:
          </p>

          <div style={{ display: "grid", gap: "12px", fontSize: "13px" }}>
            <div style={{ padding: "12px 16px", background: "var(--subtle)", borderRadius: "12px" }}>
              <b>📌 Ажиллуулах арга:</b>
              <br />
              Төслийн хавтас доторх <code>Install-VOICE-Helper.bat</code> файл дээр 1 удаа давхар товшиж ажиллуулна.
              <br />
              Одоо Word эсвэл дурын програм дээр курсороо тавиад <b>F8</b> (эсвэл <kbd>Ctrl + Alt</kbd>) дарж шууд ярина.
            </div>

            <div style={{ padding: "12px 16px", background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.3)", borderRadius: "12px" }}>
              <b style={{ color: "#a5b4fc" }}>🚀 Аппликейшнийг 1 даралтаар эхлүүлэх:</b>
              <br />
              <code>Start-VOICE-App.bat</code> файл дээр товшвол яриа таних хиймэл оюун болон дэлгэцийн цонх автоматаар нээгдэнэ.
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
