"use client";

import { useState, useRef, useEffect } from "react";
import {
  VolumeIcon,
  PlayIcon,
  SparklesIcon,
  CheckIcon,
  WavesIcon,
  ZapIcon,
} from "@/components/Icons";

interface GeneratedAudio {
  id: string;
  text: string;
  audioUrl: string;
  timestamp: number;
}

export default function TTSPage() {
  const [text, setText] = useState(
    "Сайн байна уу? Энэхүү бичвэрийг таны компьютер дээр офлайн ажиллаж буй монгол хэлний хиймэл оюуны дуу хоолойгоор уншиж байна."
  );
  const [loading, setLoading] = useState(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [history, setHistory] = useState<GeneratedAudio[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [checkingServer, setCheckingServer] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Check local MMS-TTS server status
  const checkServerStatus = async () => {
    setCheckingServer(true);
    try {
      const res = await fetch("/api/tts");
      if (res.ok) {
        const data = await res.json();
        setServerOnline(!!data.online);
      } else {
        setServerOnline(false);
      }
    } catch {
      setServerOnline(false);
    } finally {
      setCheckingServer(false);
    }
  };

  useEffect(() => {
    checkServerStatus();
    const interval = setInterval(checkServerStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    setLoading(true);

    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });

      if (!res.ok) {
        throw new Error("TTS дуу үүсгэхэд алдаа гарлаа.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      setCurrentAudioUrl(url);

      const newEntry: GeneratedAudio = {
        id: "tts_" + Date.now(),
        text: text.trim(),
        audioUrl: url,
        timestamp: Date.now(),
      };
      setHistory((prev) => [newEntry, ...prev.slice(0, 15)]);

      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current.play().catch(() => {});
        }
      }, 100);
    } catch (err: unknown) {
      console.warn("TTS error:", err);
    } finally {
      setLoading(false);
    }
  };

  const samplePhrases = [
    "Сайн байна уу? Монгол хэлний офлайн дуу хоолойн системд тавтай морилно уу.",
    "Өнөөдрийн цаг агаар тогтуун сайхан байна.",
    "Мэдээлэл технологи, хиймэл оюуны салбар манай улсад эрчимтэй хөгжиж байна.",
    "Нэг хоёр гурав дөрөв тав зургаа долоо найм ес арав.",
  ];

  return (
    <section className="page">
      <small>OFFLINE NEURAL TTS</small>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <h1 style={{ margin: "4px 0 8px" }}>Дуу Хоолойн Студи (MMS-TTS)</h1>
          <p style={{ maxWidth: "600px" }}>
            Meta-ийн <b>facebook/mms-tts-khk</b> (Халх Монгол) VITS модел ашиглан бичвэрийг өөрийн компьютер дээрээ үнэгүй, хязгааргүй дуу хоолой болгон хөрвүүлээрэй.
          </p>
        </div>

        {/* Server status pill */}
        <div
          onClick={checkServerStatus}
          title="Дарж серверийн төлөвийг дахин шалгах"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "10px",
            padding: "8px 16px",
            borderRadius: "999px",
            background: serverOnline ? "rgba(16, 185, 129, 0.12)" : "rgba(245, 158, 11, 0.12)",
            border: `1px solid ${serverOnline ? "rgba(16, 185, 129, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: serverOnline ? "#10b981" : "#f59e0b",
              boxShadow: serverOnline ? "0 0 10px #10b981" : "0 0 10px #f59e0b",
              display: "inline-block",
            }}
          />
          <span style={{ fontSize: "13px", fontWeight: 600, color: serverOnline ? "#10b981" : "#d97706" }}>
            {checkingServer
              ? "Шалгаж байна..."
              : serverOnline
              ? "MMS-TTS Сервер Бэлэн (localhost:8000)"
              : "Сервер холбогдоогүй (run-tts.bat)"}
          </span>
        </div>
      </div>

      {serverOnline === false && (
        <div
          style={{
            marginTop: "16px",
            padding: "16px 20px",
            borderRadius: "16px",
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.25)",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, color: "#d97706" }}>
            <ZapIcon width={18} height={18} />
            <span>Офлайн MMS-TTS Серверийг эхлүүлэх заавар:</span>
          </div>
          <div style={{ fontSize: "13px", color: "var(--muted)", lineHeight: 1.6 }}>
            1. Төслийн үндсэн хавтсанд байрлах <b>run-tts.bat</b> файлыг давхар дарж ажиллуулна уу.<br />
            2. Эсвэл terminal дээр: <code style={{ padding: "2px 6px", background: "var(--subtle)", borderRadius: "6px" }}>uvicorn tts_server:app --port 8000</code><br />
            3. Анх удаа ажиллахад модел (~150MB) автоматаар татагдаж, цаашид интернэтгүй ажиллана.
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "24px", marginTop: "24px" }}>
        {/* Text Input Card */}
        <div className="settings">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <SparklesIcon width={18} height={18} style={{ color: "var(--accent)" }} />
              <span>Уншуулах кирилл бичвэр</span>
            </h2>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>
              {text.length} тэмдэгт • ~{Math.ceil(text.length / 15)} сек
            </span>
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Уншуулах монгол бичвэрээ энд бичнэ үү (цифрийг үсгээр бичвэл сайн: нэг, хоёр, гурав)..."
            style={{
              width: "100%",
              minHeight: "140px",
              padding: "16px",
              background: "var(--subtle)",
              border: "1px solid var(--border)",
              borderRadius: "16px",
              color: "var(--text)",
              fontSize: "15px",
              lineHeight: 1.6,
              resize: "vertical",
              outline: "none",
            }}
          />

          {/* Quick sample chips */}
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "14px" }}>
            <span style={{ fontSize: "12px", color: "var(--muted)", alignSelf: "center" }}>Жишээ өгүүлбэрүүд:</span>
            {samplePhrases.map((phrase, idx) => (
              <button
                key={idx}
                className="suggestion-pill"
                onClick={() => setText(phrase)}
              >
                {phrase.slice(0, 32)}...
              </button>
            ))}
          </div>

          {/* Model info banner */}
          <div
            style={{
              marginTop: "16px",
              padding: "12px 16px",
              borderRadius: "12px",
              background: "var(--subtle)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "13px",
              color: "var(--muted)",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <WavesIcon width={16} height={16} style={{ color: "var(--accent)" }} />
              <span>Модел: <b>facebook/mms-tts-khk</b> (Khalkha Mongolian VITS)</span>
            </div>
            <span style={{ color: "var(--accent)", fontWeight: 600 }}>100% Үнэгүй • Лимитгүй Офлайн</span>
          </div>

          {/* Action buttons */}
          <div style={{ marginTop: "20px", display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <button
              className="btn-primary"
              onClick={handleSynthesize}
              disabled={loading || !text.trim()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "10px",
                padding: "12px 24px",
                fontSize: "15px",
                borderRadius: "14px",
              }}
            >
              {loading ? (
                <>
                  <span className="spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                  <span>Дуу хоолой үүсгэж байна...</span>
                </>
              ) : (
                <>
                  <VolumeIcon width={20} height={20} />
                  <span>Дуу хоолойгоор унших</span>
                </>
              )}
            </button>

            {currentAudioUrl && (
              <button
                className="btn-secondary"
                onClick={() => {
                  if (audioRef.current) {
                    audioRef.current.currentTime = 0;
                    audioRef.current.play().catch(() => {});
                  }
                }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "12px 18px",
                  borderRadius: "14px",
                }}
              >
                <PlayIcon width={16} height={16} />
                <span>Дахин сонсох</span>
              </button>
            )}
          </div>
        </div>

        {/* Current Active Player Card */}
        {currentAudioUrl && (
          <div
            className="settings"
            style={{
              border: "1px solid rgba(99, 102, 241, 0.3)",
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(168, 85, 247, 0.05))",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div
                  style={{
                    width: "44px",
                    height: "44px",
                    borderRadius: "14px",
                    background: "linear-gradient(135deg, var(--accent), var(--accent-gradient-to))",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    boxShadow: "0 8px 16px rgba(99, 102, 241, 0.3)",
                  }}
                >
                  <WavesIcon width={22} height={22} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "16px" }}>Халх Монгол Дуу Хоолой (MMS-TTS)</h3>
                  <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--muted)" }}>
                    Амжилттай үүсгэгдлээ • 16-bit WAV
                  </p>
                </div>
              </div>

              <a
                href={currentAudioUrl}
                download={`mms-voice-${Date.now()}.wav`}
                className="btn-secondary"
                style={{
                  padding: "8px 16px",
                  fontSize: "13px",
                  borderRadius: "10px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                Татаж авах (.wav)
              </a>
            </div>

            <audio
              ref={audioRef}
              src={currentAudioUrl}
              controls
              style={{
                width: "100%",
                height: "48px",
                borderRadius: "12px",
                outline: "none",
              }}
            />
          </div>
        )}

        {/* History of generated speech */}
        {history.length > 0 && (
          <div className="settings">
            <h2 style={{ margin: "0 0 16px", display: "flex", alignItems: "center", gap: "8px" }}>
              <VolumeIcon width={18} height={18} style={{ color: "var(--accent)" }} />
              <span>Үүсгэсэн ярианы түүх ({history.length})</span>
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {history.map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: "14px 16px",
                    borderRadius: "14px",
                    background: "var(--subtle)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "14px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "220px" }}>
                    <p style={{ margin: 0, fontSize: "14px", fontWeight: 500, lineHeight: 1.5 }}>
                      &ldquo;{item.text}&rdquo;
                    </p>
                    <span style={{ fontSize: "12px", color: "var(--muted)", marginTop: "4px", display: "inline-block" }}>
                      {new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} • MMS-TTS
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <button
                      className="icon-btn"
                      onClick={() => {
                        const a = new Audio(item.audioUrl);
                        a.play().catch(() => {});
                      }}
                      title="Тоглуулах"
                      style={{ padding: "8px", borderRadius: "10px" }}
                    >
                      <PlayIcon width={16} height={16} />
                    </button>

                    <button
                      className="icon-btn"
                      onClick={() => {
                        navigator.clipboard.writeText(item.text);
                        setCopiedId(item.id);
                        setTimeout(() => setCopiedId(null), 2000);
                      }}
                      title="Текст хуулах"
                      style={{ padding: "8px", borderRadius: "10px" }}
                    >
                      {copiedId === item.id ? (
                        <CheckIcon width={16} height={16} style={{ color: "#10b981" }} />
                      ) : (
                        <span style={{ fontSize: "12px" }}>Хуулах</span>
                      )}
                    </button>

                    <a
                      href={item.audioUrl}
                      download={`speech-${item.id}.wav`}
                      className="icon-btn"
                      title="WAV татах"
                      style={{ padding: "8px 12px", borderRadius: "10px", fontSize: "12px" }}
                    >
                      WAV
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
