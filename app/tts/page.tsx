"use client";

import { useState, useRef } from "react";
import { chimegeVoices } from "@/lib/constants";
import { useSettings } from "@/components/AppShell";
import {
  VolumeIcon,
  PlayIcon,
  SparklesIcon,
  CheckIcon,
} from "@/components/Icons";

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
    "Сайн байна уу? Монгол хэлний дуу хоолой болон ярианы хиймэл оюуны студид тавтай морилно уу."
  );
  const [selectedVoiceId, setSelectedVoiceId] = useState(settings.defaultVoiceId || "FEMALE3v2");
  const [genderFilter, setGenderFilter] = useState<"all" | "female" | "male">("all");
  const [speed, setSpeed] = useState(settings.ttsSpeed || 1.0);
  const [pitch, setPitch] = useState(settings.ttsPitch || 1.0);
  const [loading, setLoading] = useState(false);
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

    try {
      const res = await fetch("/api/chimege/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          voiceId: selectedVoiceId,
          speed,
          pitch,
        }),
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
        voiceName: selectedVoice.name,
        voiceId: selectedVoice.id,
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
    "Сайн байна уу? Тавтай морилно уу.",
    "Монгол улсын мэдээлэл технологийн салбар эрчимтэй хөгжиж байна.",
    "Маргаашийн ажлын хэлэлцүүлэг өглөө 10:00 цагт эхэлнэ.",
    "Энэхүү бичвэрийг хиймэл оюуны байгалийн дуу хоолойгоор уншиж байна.",
  ];

  return (
    <section className="page">
      <small>VOICE AI STUDIO</small>
      <h1>Дуу Хоолойн Студи (TTS)</h1>
      <p>
        Бичвэрийг 11 төрлийн байгалийн өнгө аястай эмэгтэй ба эрэгтэй хоолойгоор шууд уншуулж,
        аудиог нь татан аваарай.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "24px", marginTop: "28px" }}>
        {/* Text Input Card */}
        <div className="settings">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <SparklesIcon width={18} height={18} style={{ color: "var(--accent)" }} />
              <span>Уншуулах текст</span>
            </h2>
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
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "12px" }}>
            <span style={{ fontSize: "12px", color: "var(--muted)", alignSelf: "center" }}>Жишээ:</span>
            {samplePhrases.map((phrase, idx) => (
              <button
                key={idx}
                className="suggestion-pill"
                onClick={() => setText(phrase)}
              >
                {phrase.slice(0, 26)}...
              </button>
            ))}
          </div>
        </div>

        {/* Voice Selector Grid */}
        <div className="settings">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <VolumeIcon width={18} height={18} style={{ color: "var(--accent)" }} />
                <span>Дуу хоолой сонгох (11 төрөл)</span>
              </h2>
              <p style={{ margin: "4px 0 0", fontSize: "13px" }}>
                Сонгогдсон: <b>{selectedVoice.name}</b> • {selectedVoice.description}
              </p>
            </div>

            {/* Filter buttons */}
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                className="btn-secondary"
                style={{
                  padding: "6px 12px",
                  fontSize: "12px",
                  background: genderFilter === "all" ? "var(--text)" : "var(--surface)",
                  color: genderFilter === "all" ? "var(--bg)" : "var(--text)",
                }}
                onClick={() => setGenderFilter("all")}
              >
                Бүгд (11)
              </button>
              <button
                className="btn-secondary"
                style={{
                  padding: "6px 12px",
                  fontSize: "12px",
                  background: genderFilter === "female" ? "var(--text)" : "var(--surface)",
                  color: genderFilter === "female" ? "var(--bg)" : "var(--text)",
                }}
                onClick={() => setGenderFilter("female")}
              >
                👩 Эмэгтэй (6)
              </button>
              <button
                className="btn-secondary"
                style={{
                  padding: "6px 12px",
                  fontSize: "12px",
                  background: genderFilter === "male" ? "var(--text)" : "var(--surface)",
                  color: genderFilter === "male" ? "var(--bg)" : "var(--text)",
                }}
                onClick={() => setGenderFilter("male")}
              >
                👨 Эрэгтэй (5)
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(185px, 1fr))",
              gap: "12px",
            }}
          >
            {filteredVoices.map((voice) => {
              const isSelected = selectedVoiceId === voice.id;
              const isFemale = voice.gender === "female";
              return (
                <div
                  key={voice.id}
                  onClick={() => setSelectedVoiceId(voice.id)}
                  style={{
                    padding: "14px 16px",
                    borderRadius: "16px",
                    border: isSelected
                      ? "2px solid var(--accent)"
                      : "1px solid var(--border)",
                    background: isSelected ? "var(--subtle)" : "var(--surface)",
                    boxShadow: isSelected ? "0 0 20px rgba(99, 102, 241, 0.2)" : "var(--shadow-sm)",
                    cursor: "pointer",
                    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                    transform: isSelected ? "scale(1.02)" : "scale(1)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div
                        style={{
                          width: "28px",
                          height: "28px",
                          borderRadius: "50%",
                          background: isFemale
                            ? "linear-gradient(135deg, #f43f5e, #ec4899)"
                            : "linear-gradient(135deg, #3b82f6, #6366f1)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#fff",
                          fontSize: "12px",
                          fontWeight: 700,
                        }}
                      >
                        {isFemale ? "F" : "M"}
                      </div>
                      <b style={{ fontSize: "14px" }}>{voice.name}</b>
                    </div>
                    {isSelected && (
                      <span style={{ color: "var(--accent)" }}>
                        <CheckIcon width={16} height={16} />
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "8px" }}>
                    {voice.description}
                  </div>
                  <span
                    style={{
                      display: "inline-block",
                      marginTop: "8px",
                      fontSize: "10px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "6px",
                      background: "var(--subtle)",
                      border: "1px solid var(--border)",
                      color: "var(--muted)",
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "24px", marginTop: "16px" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "13px" }}>
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
                style={{ width: "100%", accentColor: "var(--accent)" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                <span>0.5x Удаан</span>
                <span>1.0x Энгийн</span>
                <span>2.0x Хурдан</span>
              </div>
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "13px" }}>
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
                style={{ width: "100%", accentColor: "var(--accent)" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                <span>0.5x Баргил</span>
                <span>1.0x Энгийн</span>
                <span>2.0x Нарийн</span>
              </div>
            </div>
          </div>
        </div>

        {/* Action Button & Player */}
        <div className="settings" style={{ textAlign: "center", padding: "32px 24px" }}>
          <button
            className="btn-primary"
            onClick={handleSynthesize}
            disabled={loading || !text.trim()}
            style={{ fontSize: "16px", padding: "14px 32px", borderRadius: "16px" }}
          >
            {loading ? (
              <span>🔊 Дуу хоолой үүсгэж байна...</span>
            ) : (
              <>
                <PlayIcon width={18} height={18} />
                <span>{selectedVoice.name} хоолойгоор яриулах</span>
              </>
            )}
          </button>

          {currentAudioUrl && (
            <div style={{ marginTop: "24px", display: "flex", flexDirection: "column", alignItems: "center", gap: "14px" }}>
              <audio ref={audioRef} controls src={currentAudioUrl} style={{ width: "100%", maxWidth: "480px" }} />
              <a
                href={currentAudioUrl}
                download={`voice-${selectedVoice.name.toLowerCase()}-${Date.now()}.wav`}
                className="btn-secondary"
              >
                <span>⬇ WAV аудио татаж авах</span>
              </a>
            </div>
          )}
        </div>

        {/* History */}
        {history.length > 0 && (
          <div className="settings">
            <h2>Саяхан үүсгэсэн бичлэгүүд</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "14px" }}>
              {history.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 16px",
                    background: "var(--subtle)",
                    border: "1px solid var(--border)",
                    borderRadius: "14px",
                    flexWrap: "wrap",
                    gap: "10px",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "220px" }}>
                    <div style={{ fontSize: "14px", fontWeight: 500 }}>
                      <span className="stats-badge" style={{ marginRight: "8px" }}>{item.voiceName}</span>
                      {item.text.slice(0, 60)}...
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                    <audio controls src={item.audioUrl} style={{ height: "34px", width: "240px" }} />
                    <a
                      href={item.audioUrl}
                      download={`voice-${item.voiceName}-${item.timestamp}.wav`}
                      className="btn-secondary"
                      style={{ padding: "6px 12px", fontSize: "12px" }}
                    >
                      Татах
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
