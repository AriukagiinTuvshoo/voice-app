"use client";

import { useState, useRef, useEffect } from "react";
import {
  VolumeIcon,
  PlayIcon,
  SparklesIcon,
  CheckIcon,
  WavesIcon,
  ZapIcon,
  MicIcon,
  TrashIcon,
} from "@/components/Icons";
import { AudioRecorder } from "@/lib/audio-recorder";

interface GeneratedAudio {
  id: string;
  text: string;
  voiceName: string;
  audioUrl: string;
  timestamp: number;
}

export interface ClonedVoice {
  id: string;
  name: string;
  gender: "female" | "male";
  baseVoice: string;
  pitch: number;
  speed: number;
  f0?: number;
  description: string;
  tag: string;
  createdAt: number;
}

const DEFAULT_VOICES = [
  {
    id: "mn-MN-YesuiNeural",
    name: "Есүй",
    gender: "female" as const,
    description: "Уян зөөлөн, байгалийн өнгө аяс (Эмэгтэй)",
    tag: "Үндсэн • Эмэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-YesuiNeural",
  },
  {
    id: "mn-MN-BataaNeural",
    name: "Батаа",
    gender: "male" as const,
    description: "Тод цэвэр, өөртөө итгэлтэй, баргил (Эрэгтэй)",
    tag: "Эрэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-BataaNeural",
  },
];

export default function TTSPage() {
  const [activeTab, setActiveTab] = useState<"standard" | "clone">("standard");

  // Standard TTS State
  const [text, setText] = useState(
    "Сайн байна уу? Монгол хэлний хиймэл оюуны дуу хоолойн студид тавтай морилно уу."
  );
  const [selectedVoiceId, setSelectedVoiceId] = useState("mn-MN-YesuiNeural");
  const [speed, setSpeed] = useState(1.0);
  const [pitch, setPitch] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [history, setHistory] = useState<GeneratedAudio[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);
  const [checkingServer, setCheckingServer] = useState(false);

  // Voice Cloning State (VoiceStudio)
  const [clonedVoices, setClonedVoices] = useState<ClonedVoice[]>([]);
  const [cloneName, setCloneName] = useState("Миний хоолой");
  const [isRecordingSample, setIsRecordingSample] = useState(false);
  const [sampleBlob, setSampleBlob] = useState<Blob | null>(null);
  const [sampleAudioUrl, setSampleAudioUrl] = useState<string | null>(null);
  const [isCloning, setIsCloning] = useState(false);
  const [cloneError, setCloneError] = useState("");
  const [recordSeconds, setRecordSeconds] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sampleAudioRef = useRef<HTMLAudioElement | null>(null);
  const sampleRecorderRef = useRef<AudioRecorder | null>(null);
  const sampleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load saved cloned voices from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("voice_clones");
      if (saved) {
        setClonedVoices(JSON.parse(saved));
      }
    } catch {}
  }, []);

  const saveClonedVoices = (voices: ClonedVoice[]) => {
    setClonedVoices(voices);
    try {
      localStorage.setItem("voice_clones", JSON.stringify(voices));
    } catch {}
  };

  // Check local TTS server status
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
    const interval = setInterval(checkServerStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  // All voices = default + cloned
  const allVoices = [
    ...DEFAULT_VOICES,
    ...clonedVoices.map((c) => ({
      id: c.id,
      name: c.name,
      gender: c.gender,
      description: `${c.description} • Хувилсан хоолой`,
      tag: "Хувилсан",
      pitch: c.pitch,
      speed: c.speed,
      baseVoice: c.baseVoice,
    })),
  ];

  const selectedVoice =
    allVoices.find((v) => v.id === selectedVoiceId) || allVoices[0];

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    setLoading(true);

    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          voice: selectedVoice.baseVoice || selectedVoice.id,
          speed: speed * (selectedVoice.speed || 1.0),
          pitch: pitch * (selectedVoice.pitch || 1.0),
        }),
      });

      if (!res.ok) {
        throw new Error("Дуу үүсгэхэд алдаа гарлаа.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      setCurrentAudioUrl(url);

      const newEntry: GeneratedAudio = {
        id: "tts_" + Date.now(),
        text: text.trim(),
        voiceName: selectedVoice.name,
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

  // Recording Sample for Voice Cloning
  const startRecordingSample = async () => {
    setCloneError("");
    setSampleBlob(null);
    setSampleAudioUrl(null);
    setRecordSeconds(0);

    try {
      const recorder = new AudioRecorder({
        autoStop: false,
      });
      sampleRecorderRef.current = recorder;
      await recorder.start();
      setIsRecordingSample(true);

      sampleTimerRef.current = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } catch {
      setCloneError("Микрофон ажиллуулахад алдаа гарлаа. Зөвшөөрөл шалгана уу.");
    }
  };

  const stopRecordingSample = async () => {
    if (!sampleRecorderRef.current) return;
    setIsRecordingSample(false);
    if (sampleTimerRef.current) clearInterval(sampleTimerRef.current);

    try {
      const blob = await sampleRecorderRef.current.stop();
      sampleRecorderRef.current = null;
      setSampleBlob(blob);
      setSampleAudioUrl(URL.createObjectURL(blob));
    } catch {
      setCloneError("Бичлэг хадгалахад алдаа гарлаа.");
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSampleBlob(file);
    setSampleAudioUrl(URL.createObjectURL(file));
  };

  // Perform Voice Cloning via /api/tts/clone
  const handleCloneSubmit = async () => {
    if (!sampleBlob) {
      setCloneError("Эхлээд дууны бичлэг хийх эсвэл аудио файл оруулна уу.");
      return;
    }
    if (!cloneName.trim()) {
      setCloneError("Хоолойн нэрээ оруулна уу.");
      return;
    }

    setIsCloning(true);
    setCloneError("");

    try {
      const formData = new FormData();
      formData.append("audio", sampleBlob, "sample.wav");
      formData.append("name", cloneName.trim());

      const res = await fetch("/api/tts/clone", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Хоолой хувилах хүсэлт амжилтгүй боллоо.");
      }

      const clonedProfile: ClonedVoice = await res.json();
      const updated = [clonedProfile, ...clonedVoices];
      saveClonedVoices(updated);

      setSelectedVoiceId(clonedProfile.id);
      setActiveTab("standard");
      setCloneName("");
      setSampleBlob(null);
      setSampleAudioUrl(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Хоолой шинжлэхэд алдаа гарлаа.";
      setCloneError(msg);
    } finally {
      setIsCloning(false);
    }
  };

  const handleDeleteClonedVoice = (id: string) => {
    const updated = clonedVoices.filter((v) => v.id !== id);
    saveClonedVoices(updated);
    if (selectedVoiceId === id) {
      setSelectedVoiceId("mn-MN-YesuiNeural");
    }
  };

  const samplePhrases = [
    "Сайн байна уу? Монгол хэлний дуу хоолойн системд тавтай морилно уу.",
    "Өнөөдрийн цаг агаар Улаанбаатар хотод тогтуун, тааламжтай байна.",
    "Хиймэл оюуны тусламжтайгаар өөрийн хоолойг хувилан хүссэн бичвэрээ уншуулаарай.",
    "Нэг хоёр гурав дөрөв тав зургаа долоо найм ес арав.",
  ];

  return (
    <section className="page">
      <small>AI VOICE & CLONING STUDIO</small>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <h1 style={{ margin: "4px 0 8px" }}>Дуу Хоолойн Студи (VoiceStudio)</h1>
          <p style={{ maxWidth: "620px" }}>
            Монгол дуу хоолойгоор уншуулах, эсвэл <b>өөрийн болон дурын хүний хоолойг хувилж (Voice Clone)</b> хүссэн бичвэрээ уншуулаарай.
          </p>
        </div>

        {/* Server status badge */}
        <div
          onClick={checkServerStatus}
          title="Дарж дахин шалгах"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "10px",
            padding: "8px 16px",
            borderRadius: "999px",
            background: serverOnline
              ? "rgba(16, 185, 129, 0.12)"
              : "rgba(245, 158, 11, 0.12)",
            border: `1px solid ${
              serverOnline ? "rgba(16, 185, 129, 0.3)" : "rgba(245, 158, 11, 0.3)"
            }`,
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
          <span
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: serverOnline ? "#10b981" : "#d97706",
            }}
          >
            {checkingServer
              ? "Шалгаж байна..."
              : serverOnline
              ? "Voice Сервер Бэлэн (localhost:8000)"
              : "Сервер унтарсан (run-tts.bat)"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          marginTop: "20px",
          borderBottom: "1px solid var(--border)",
          paddingBottom: "12px",
        }}
      >
        <button
          onClick={() => setActiveTab("standard")}
          className="btn-secondary"
          style={{
            background: activeTab === "standard" ? "var(--text)" : "var(--surface)",
            color: activeTab === "standard" ? "var(--bg)" : "var(--text)",
            padding: "8px 18px",
            borderRadius: "12px",
            fontWeight: 600,
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <VolumeIcon width={16} height={16} />
          <span>Дуу хоолойгоор яриулах ({allVoices.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("clone")}
          className="btn-secondary"
          style={{
            background: activeTab === "clone" ? "var(--accent)" : "var(--surface)",
            color: activeTab === "clone" ? "#fff" : "var(--text)",
            padding: "8px 18px",
            borderRadius: "12px",
            fontWeight: 600,
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            boxShadow: activeTab === "clone" ? "0 0 16px rgba(99, 102, 241, 0.4)" : "none",
          }}
        >
          <SparklesIcon width={16} height={16} />
          <span>✨ Хүний дуу хоолой хувилах (Voice Clone)</span>
        </button>
      </div>

      {/* TAB 1: STANDARD & CLONED VOICE SYNTHESIS */}
      {activeTab === "standard" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "24px", marginTop: "20px" }}>
          {/* Voice Selector Cards */}
          <div className="settings">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
              <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <VolumeIcon width={18} height={18} style={{ color: "var(--accent)" }} />
                <span>Дуу хоолой сонгох</span>
              </h2>
              <button
                onClick={() => setActiveTab("clone")}
                className="btn-secondary"
                style={{ fontSize: "12px", padding: "6px 12px", display: "inline-flex", alignItems: "center", gap: "6px" }}
              >
                <SparklesIcon width={14} height={14} style={{ color: "var(--accent)" }} />
                <span>+ Шинэ хоолой хувилах</span>
              </button>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: "14px",
              }}
            >
              {allVoices.map((voice) => {
                const isSelected = selectedVoiceId === voice.id;
                const isFemale = voice.gender === "female";
                const isCloned = voice.tag === "Хувилсан";
                return (
                  <div
                    key={voice.id}
                    onClick={() => setSelectedVoiceId(voice.id)}
                    style={{
                      padding: "16px 18px",
                      borderRadius: "16px",
                      border: isSelected
                        ? "2px solid var(--accent)"
                        : "1px solid var(--border)",
                      background: isSelected ? "var(--subtle)" : "var(--surface)",
                      boxShadow: isSelected
                        ? "0 0 20px rgba(99, 102, 241, 0.2)"
                        : "var(--shadow-sm)",
                      cursor: "pointer",
                      transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                      transform: isSelected ? "scale(1.02)" : "scale(1)",
                      position: "relative",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <div
                          style={{
                            width: "36px",
                            height: "36px",
                            borderRadius: "50%",
                            background: isCloned
                              ? "linear-gradient(135deg, #8b5cf6, #d946ef)"
                              : isFemale
                              ? "linear-gradient(135deg, #f43f5e, #ec4899)"
                              : "linear-gradient(135deg, #3b82f6, #6366f1)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#fff",
                            fontSize: "15px",
                            fontWeight: 700,
                            boxShadow: isCloned ? "0 0 12px rgba(217, 70, 239, 0.4)" : "none",
                          }}
                        >
                          {isCloned ? "✨" : isFemale ? "👩" : "👨"}
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: "15px" }}>
                            {voice.name}
                          </div>
                          <span
                            style={{
                              fontSize: "11px",
                              padding: "2px 8px",
                              borderRadius: "6px",
                              background: isSelected
                                ? "rgba(99, 102, 241, 0.15)"
                                : "var(--subtle)",
                              color: isSelected ? "var(--accent)" : "var(--muted)",
                              fontWeight: 600,
                            }}
                          >
                            {voice.tag}
                          </span>
                        </div>
                      </div>
                      {isSelected && (
                        <CheckIcon
                          width={20}
                          height={20}
                          style={{ color: "var(--accent)" }}
                        />
                      )}
                    </div>
                    <p
                      style={{
                        margin: "12px 0 0",
                        fontSize: "13px",
                        color: "var(--muted)",
                        lineHeight: 1.4,
                      }}
                    >
                      {voice.description}
                    </p>

                    {isCloned && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteClonedVoice(voice.id);
                        }}
                        style={{
                          position: "absolute",
                          bottom: "10px",
                          right: "12px",
                          background: "none",
                          color: "var(--muted)",
                          padding: "4px",
                          borderRadius: "6px",
                        }}
                        title="Хоолойг устгах"
                      >
                        <TrashIcon width={14} height={14} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Speed & Pitch Controls */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px",
                marginTop: "20px",
                paddingTop: "16px",
                borderTop: "1px solid var(--border)",
              }}
            >
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "13px",
                    marginBottom: "8px",
                  }}
                >
                  <span>Ярианы хурд</span>
                  <b>{speed}x</b>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.5"
                  step="0.1"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
              </div>
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "13px",
                    marginBottom: "8px",
                  }}
                >
                  <span>Өнгө аяс (Pitch)</span>
                  <b>{pitch}x</b>
                </div>
                <input
                  type="range"
                  min="0.7"
                  max="1.3"
                  step="0.05"
                  value={pitch}
                  onChange={(e) => setPitch(parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
              </div>
            </div>
          </div>

          {/* Text Input Card */}
          <div className="settings">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "12px",
              }}
            >
              <h2
                style={{
                  margin: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <SparklesIcon
                  width={18}
                  height={18}
                  style={{ color: "var(--accent)" }}
                />
                <span>Уншуулах бичвэр</span>
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
                minHeight: "130px",
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

            {/* Sample Phrases */}
            <div
              style={{
                display: "flex",
                gap: "8px",
                flexWrap: "wrap",
                marginTop: "14px",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  color: "var(--muted)",
                  alignSelf: "center",
                }}
              >
                Жишээ:
              </span>
              {samplePhrases.map((phrase, idx) => (
                <button
                  key={idx}
                  className="suggestion-pill"
                  onClick={() => setText(phrase)}
                >
                  {phrase.slice(0, 30)}...
                </button>
              ))}
            </div>

            {/* Action buttons */}
            <div
              style={{
                marginTop: "20px",
                display: "flex",
                gap: "12px",
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >
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
                    <span
                      className="spinner"
                      style={{
                        width: "16px",
                        height: "16px",
                        borderWidth: "2px",
                      }}
                    />
                    <span>Дуу үүсгэж байна...</span>
                  </>
                ) : (
                  <>
                    <VolumeIcon width={20} height={20} />
                    <span>Яриулах ({selectedVoice.name})</span>
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
                background:
                  "linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(168, 85, 247, 0.05))",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "16px",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "14px",
                      background:
                        "linear-gradient(135deg, var(--accent), var(--accent-gradient-to))",
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
                    <h3 style={{ margin: 0, fontSize: "16px" }}>
                      {selectedVoice.name} хоолойгоор үүссэн аудио
                    </h3>
                    <p
                      style={{
                        margin: "2px 0 0",
                        fontSize: "12px",
                        color: "var(--muted)",
                      }}
                    >
                      Амжилттай бэлэн боллоо
                    </p>
                  </div>
                </div>

                <a
                  href={currentAudioUrl}
                  download={`voice-${selectedVoice.name}-${Date.now()}.mp3`}
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
                  Татаж авах (.mp3)
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

          {/* History */}
          {history.length > 0 && (
            <div className="settings">
              <h2
                style={{
                  margin: "0 0 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
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
                      <p
                        style={{
                          margin: 0,
                          fontSize: "14px",
                          fontWeight: 500,
                          lineHeight: 1.5,
                        }}
                      >
                        &ldquo;{item.text}&rdquo;
                      </p>
                      <span
                        style={{
                          fontSize: "12px",
                          color: "var(--muted)",
                          marginTop: "4px",
                          display: "inline-block",
                        }}
                      >
                        {new Date(item.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}{" "}
                        • Хоолой: {item.voiceName}
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
                          <CheckIcon
                            width={16}
                            height={16}
                            style={{ color: "#10b981" }}
                          />
                        ) : (
                          <span style={{ fontSize: "12px" }}>Хуулах</span>
                        )}
                      </button>

                      <a
                        href={item.audioUrl}
                        download={`speech-${item.id}.mp3`}
                        className="icon-btn"
                        title="Аудио татах"
                        style={{
                          padding: "8px 12px",
                          borderRadius: "10px",
                          fontSize: "12px",
                        }}
                      >
                        MP3
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: VOICE CLONING STUDIO (VoiceStudio Style) */}
      {activeTab === "clone" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "24px", marginTop: "20px" }}>
          <div className="settings">
            <h2 style={{ margin: "0 0 8px", display: "flex", alignItems: "center", gap: "8px" }}>
              <SparklesIcon width={20} height={20} style={{ color: "var(--accent)" }} />
              <span>Шинэ дуу хоолой хувилах (Zero-Shot Voice Cloning)</span>
            </h2>
            <p style={{ margin: "0 0 20px", fontSize: "14px", color: "var(--muted)" }}>
              Өөрийн эсвэл дурын хүний <b>3-10 секундийн дууны бичлэгийг</b> микрофоноор бичих эсвэл файлаар оруулж, хиймэл оюунаар өнгө аясыг нь шинжлэн хувийн хоолой болгон хадгалаарай.
            </p>

            {cloneError && (
              <div className="error" style={{ marginBottom: "16px" }}>
                <b>Алдаа:</b> {cloneError}
              </div>
            )}

            {/* Step 1: Voice Name */}
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
                1. Хоолойн нэр (Voice Name):
              </label>
              <input
                type="text"
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
                placeholder="Жишээ: Миний хоолой, Багшийн хоолой, Зоригоо..."
                style={{
                  width: "100%",
                  maxWidth: "400px",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  border: "1px solid var(--border)",
                  background: "var(--subtle)",
                  color: "var(--text)",
                  outline: "none",
                }}
              />
            </div>

            {/* Step 2: Record or Upload Audio Sample */}
            <div style={{ marginBottom: "24px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>
                2. Дууны бичлэг хийх (3-10 секунд тайван ярина уу):
              </label>

              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                {!isRecordingSample ? (
                  <button
                    className="btn-primary"
                    onClick={startRecordingSample}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "12px 20px",
                      borderRadius: "12px",
                      background: "linear-gradient(135deg, #ef4444, #f43f5e)",
                    }}
                  >
                    <MicIcon width={18} height={18} />
                    <span>Микрофоноор бичих</span>
                  </button>
                ) : (
                  <button
                    className="btn-primary"
                    onClick={stopRecordingSample}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "12px 20px",
                      borderRadius: "12px",
                      background: "#ef4444",
                    }}
                  >
                    <span className="spinner" style={{ width: "14px", height: "14px" }} />
                    <span>Бичиж байна ({recordSeconds}с) — Зогсоох</span>
                  </button>
                )}

                <span style={{ fontSize: "13px", color: "var(--muted)" }}>эсвэл</span>

                <label
                  className="btn-secondary"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "12px 18px",
                    borderRadius: "12px",
                    cursor: "pointer",
                  }}
                >
                  <span>📁 Аудио файл оруулах (.wav, .mp3)</span>
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={handleFileUpload}
                    style={{ display: "none" }}
                  />
                </label>
              </div>

              {sampleAudioUrl && (
                <div style={{ marginTop: "16px", padding: "14px", borderRadius: "14px", background: "var(--subtle)", border: "1px solid var(--border)", maxWidth: "460px" }}>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent)", marginBottom: "8px" }}>
                    ✓ Бэлтгэгдсэн аудио бичлэг:
                  </div>
                  <audio ref={sampleAudioRef} src={sampleAudioUrl} controls style={{ width: "100%", height: "40px" }} />
                </div>
              )}
            </div>

            {/* Step 3: Action Button */}
            <div style={{ paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
              <button
                className="btn-primary"
                onClick={handleCloneSubmit}
                disabled={isCloning || !sampleBlob || !cloneName.trim()}
                style={{
                  padding: "12px 28px",
                  fontSize: "15px",
                  borderRadius: "14px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "10px",
                  background: "linear-gradient(135deg, #6366f1, #d946ef)",
                  boxShadow: "0 4px 20px rgba(99, 102, 241, 0.4)",
                }}
              >
                {isCloning ? (
                  <>
                    <span className="spinner" style={{ width: "16px", height: "16px" }} />
                    <span>Хоолойг шинжлэн хувилж байна...</span>
                  </>
                ) : (
                  <>
                    <SparklesIcon width={18} height={18} />
                    <span>Хоолойг шинжлэх & Хувилах</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* List of Cloned Voices */}
          <div className="settings">
            <h2 style={{ margin: "0 0 16px", display: "flex", alignItems: "center", gap: "8px" }}>
              <VolumeIcon width={18} height={18} style={{ color: "var(--accent)" }} />
              <span>Миний хувилсан хоолойнууд ({clonedVoices.length})</span>
            </h2>

            {clonedVoices.length === 0 ? (
              <p style={{ color: "var(--muted)", fontSize: "14px" }}>
                Одоогоор хувилсан хоолой үүсгээгүй байна. Дээрх зааврын дагуу микрофоноороо ярьж эсвэл дууны файл оруулан шинэ хоолой үүсгээрэй.
              </p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "14px" }}>
                {clonedVoices.map((v) => (
                  <div
                    key={v.id}
                    style={{
                      padding: "16px 18px",
                      borderRadius: "16px",
                      background: "var(--subtle)",
                      border: "1px solid var(--border)",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "18px" }}>✨</span>
                          <b style={{ fontSize: "16px" }}>{v.name}</b>
                        </div>
                        <span
                          style={{
                            fontSize: "11px",
                            padding: "2px 8px",
                            borderRadius: "6px",
                            background: "rgba(139, 92, 246, 0.15)",
                            color: "#8b5cf6",
                            fontWeight: 700,
                          }}
                        >
                          {v.gender === "female" ? "Эмэгтэй" : "Эрэгтэй"}
                        </span>
                      </div>
                      <p style={{ margin: "6px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                        {v.description}
                      </p>
                    </div>

                    <div style={{ display: "flex", gap: "8px", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: "10px" }}>
                      <button
                        className="btn-secondary"
                        onClick={() => {
                          setSelectedVoiceId(v.id);
                          setActiveTab("standard");
                        }}
                        style={{ flex: 1, fontSize: "12px", padding: "8px 12px", justifyContent: "center" }}
                      >
                        Энэ хоолойгоор яриулах →
                      </button>

                      <button
                        className="icon-btn"
                        onClick={() => handleDeleteClonedVoice(v.id)}
                        title="Устгах"
                        style={{ padding: "8px", borderRadius: "10px" }}
                      >
                        <TrashIcon width={16} height={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
