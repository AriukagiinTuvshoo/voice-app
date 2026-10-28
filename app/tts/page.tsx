"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { chimegeVoices } from "@/lib/constants";
import { useSettings } from "@/components/AppShell";

interface GeneratedAudio {
  id: string;
  text: string;
  voiceName: string;
  voiceId: string;
  audioUrl: string;
  timestamp: number;
}

export default function TTSPage() {
  const { settings } = useSettings();
  const [text, setText] = useState(
    "Сайн байна уу? Монгол хэлний яриа болон хиймэл оюун ухааны технологийн системд тавтай морилно уу."
  );
  const [selectedVoiceId, setSelectedVoiceId] = useState(settings.defaultVoiceId || "FEMALE3v2");
  const [genderFilter, setGenderFilter] = useState<"all" | "female" | "male">("all");
  const [speed, setSpeed] = useState(settings.ttsSpeed || 1.0);
  const [pitch, setPitch] = useState(settings.ttsPitch || 1.0);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [history, setHistory] = useState<GeneratedAudio[]>([]);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const filteredVoices = chimegeVoices.filter((v) => {
    if (genderFilter === "all") return true;
    return v.gender === genderFilter;
  });

  const selectedVoice = chimegeVoices.find((v) => v.id === selectedVoiceId) || chimegeVoices[0];

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setErrorMessage("");

    try {
      const res = await fetch("/api/chimege/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          voiceId: selectedVoiceId,
          speed,
          pitch,
          token: settings.chimegeToken,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Серверийн алдаа (${res.status})`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      setCurrentAudioUrl(url);

      // Add to session history
      const newEntry: GeneratedAudio = {
        id: "tts_" + Date.now(),
        text: text.trim(),
        voiceName: selectedVoice.name,
        voiceId: selectedVoice.id,
        audioUrl: url,
        timestamp: Date.now(),
      };
      setHistory((prev) => [newEntry, ...prev.slice(0, 15)]);

      // Auto play
      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current.play().catch(() => {});
        }
      }, 100);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Яриа үүсгэхэд алдаа гарлаа.";
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  };

  const samplePhrases = [
    "Сайн байна уу? Тавтай морилно уу.",
    "Монгол улсын мэдээлэл технологийн салбар эрчимтэй хөгжиж байна.",
    "Маргаашийн ажлын хэлэлцүүлэг өглөө 10:00 цагт эхэлнэ.",
    "Энэхүү бичвэрийг Chimege хиймэл оюуны хоолойгоор уншиж байна.",
  ];

  return (
    <section className="page">
      <small>VOICE TTS STUDIO</small>
      <h1>Яриа үүсгэгч (Text-to-Speech)</h1>
      <p>
        Бичвэрийг Chimege AI-ийн 11 өөр эмэгтэй, эрэгтэй байгалийн хоолойгоор уншуулж,
        аудиог нь татаж авах боломжтой.
      </p>

      {!settings.chimegeToken && (
        <div className="error" style={{ marginBottom: "20px" }}>
          ⚠️ Chimege API Token тохируулаагүй байна.{" "}
          <Link href="/settings" style={{ textDecoration: "underline", fontWeight: 600 }}>
            Settings цэснээс token-оо оруулна уу →
          </Link>
        </div>
      )}

      {errorMessage && (
        <div className="error" style={{ marginBottom: "20px" }}>
          <b>Алдаа:</b> {errorMessage}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "24px" }}>
        {/* Text Input Card */}
        <div className="settings">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            <h2 style={{ margin: 0 }}>Уншуулах текст</h2>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>
              {text.length} тэмдэгт • ~{Math.ceil(text.length / 15)} сек
            </span>
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Уншуулах монгол бичвэрээ энд бичнэ үү..."
            style={{
              width: "100%",
              minHeight: "120px",
              padding: "12px",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "12px",
              color: "var(--text)",
              fontSize: "14px",
              lineHeight: 1.6,
              resize: "vertical",
            }}
          />

          {/* Quick sample chips */}
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "10px" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", alignSelf: "center" }}>Жишээ:</span>
            {samplePhrases.map((phrase, idx) => (
              <button
                key={idx}
                className="suggestion-pill"
                onClick={() => setText(phrase)}
                style={{ fontSize: "11px" }}
              >
                {phrase.slice(0, 24)}...
              </button>
            ))}
          </div>
        </div>

        {/* Voice Selector Grid */}
        <div className="settings">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "8px" }}>
            <div>
              <h2 style={{ margin: 0 }}>Дуу хоолой сонгох (11 төрөл)</h2>
              <p style={{ margin: "2px 0 0", fontSize: "12px" }}>
                Сонгогдсон: <b>{selectedVoice.name}</b> ({selectedVoice.description})
              </p>
            </div>
            {/* Filter buttons */}
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                className={`btn-secondary ${genderFilter === "all" ? "selected" : ""}`}
                style={{ padding: "4px 10px", fontSize: "12px", background: genderFilter === "all" ? "var(--text)" : "transparent", color: genderFilter === "all" ? "var(--bg)" : "var(--text)" }}
                onClick={() => setGenderFilter("all")}
              >
                Бүгд (11)
              </button>
              <button
                className={`btn-secondary ${genderFilter === "female" ? "selected" : ""}`}
                style={{ padding: "4px 10px", fontSize: "12px", background: genderFilter === "female" ? "var(--text)" : "transparent", color: genderFilter === "female" ? "var(--bg)" : "var(--text)" }}
                onClick={() => setGenderFilter("female")}
              >
                👩 Эмэгтэй (6)
              </button>
              <button
                className={`btn-secondary ${genderFilter === "male" ? "selected" : ""}`}
                style={{ padding: "4px 10px", fontSize: "12px", background: genderFilter === "male" ? "var(--text)" : "transparent", color: genderFilter === "male" ? "var(--bg)" : "var(--text)" }}
                onClick={() => setGenderFilter("male")}
              >
                👨 Эрэгтэй (5)
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "10px",
            }}
          >
            {filteredVoices.map((voice) => {
              const isSelected = selectedVoiceId === voice.id;
              return (
                <div
                  key={voice.id}
                  onClick={() => setSelectedVoiceId(voice.id)}
                  style={{
                    padding: "12px 14px",
                    borderRadius: "14px",
                    border: `2px solid ${isSelected ? "var(--focus)" : "var(--border)"}`,
                    background: isSelected ? "var(--subtle)" : "var(--surface)",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <b style={{ fontSize: "14px" }}>
                      {voice.gender === "female" ? "👩" : "👨"} {voice.name}
                    </b>
                    {isSelected && (
                      <span style={{ color: "var(--focus)", fontSize: "14px" }}>✓</span>
                    )}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                    {voice.description}
                  </div>
                  <span
                    style={{
                      display: "inline-block",
                      marginTop: "6px",
                      fontSize: "10px",
                      padding: "2px 6px",
                      borderRadius: "6px",
                      background: "var(--border)",
                      color: "var(--text)",
                    }}
                  >
                    {voice.tag}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Speed & Pitch Controls */}
        <div className="settings">
          <h2>Хурд ба Өнгөний тохиргоо</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "20px", marginTop: "12px" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "13px" }}>
                <span>Унших хурд (Speed):</span>
                <b>{speed.toFixed(1)}x</b>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--muted)" }}>
                <span>0.5x Удаан</span>
                <span>1.0x Энгийн</span>
                <span>2.0x Хурдан</span>
              </div>
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "13px" }}>
                <span>Өнгөний өндөр (Pitch):</span>
                <b>{pitch.toFixed(1)}x</b>
              </div>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={pitch}
                onChange={(e) => setPitch(parseFloat(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--muted)" }}>
                <span>0.5x Баргил</span>
                <span>1.0x Энгийн</span>
                <span>2.0x Нарийн</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: "12px" }}>
            <button
              className="btn-secondary"
              onClick={() => {
                setSpeed(1.0);
                setPitch(1.0);
              }}
              style={{ fontSize: "11px", padding: "4px 8px" }}
            >
              Тохиргоог дахин эхлүүлэх (Reset)
            </button>
          </div>
        </div>

        {/* Generate Button & Player */}
        <div className="settings" style={{ textAlign: "center", padding: "28px 20px" }}>
          <button
            className="btn-primary"
            onClick={handleSynthesize}
            disabled={loading || !text.trim()}
            style={{ fontSize: "16px", padding: "14px 28px", borderRadius: "14px" }}
          >
            {loading ? "🔊 Дуу үүсгэж байна..." : `▶ ${selectedVoice.name} хоолойгоор яриулах`}
          </button>

          {currentAudioUrl && (
            <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
              <audio ref={audioRef} controls src={currentAudioUrl} style={{ width: "100%", maxWidth: "460px" }} />
              <a
                href={currentAudioUrl}
                download={`chimege-${selectedVoice.name.toLowerCase()}-${Date.now()}.wav`}
                className="btn-secondary"
              >
                ⬇ WAV аудио татаж авах
              </a>
            </div>
          )}
        </div>

        {/* Generated Speeches History */}
        {history.length > 0 && (
          <div className="settings">
            <h2>Саяхан үүсгэсэн бичлэгүүд</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
              {history.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 14px",
                    background: "var(--subtle)",
                    borderRadius: "12px",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "200px" }}>
                    <div style={{ fontSize: "13px", fontWeight: 500 }}>
                      <span className="stats-badge" style={{ marginRight: "6px" }}>{item.voiceName}</span>
                      {item.text.slice(0, 60)}...
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <audio controls src={item.audioUrl} style={{ height: "32px", width: "220px" }} />
                    <a
                      href={item.audioUrl}
                      download={`chimege-${item.voiceName}-${item.timestamp}.wav`}
                      className="btn-secondary"
                      style={{ padding: "6px 10px", fontSize: "11px" }}
                    >
                      ⬇
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
