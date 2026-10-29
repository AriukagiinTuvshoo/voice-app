"use client";

import { useState, useRef, useEffect } from "react";
import {
  VolumeIcon,
  PlayIcon,
  SparklesIcon,
  CheckIcon,
  WavesIcon,
  MicIcon,
  TrashIcon,
} from "@/components/Icons";
import { AudioRecorder } from "@/lib/audio-recorder";

interface GeneratedAudio {
  id: string;
  text: string;
  voiceName: string;
  presetLabel: string;
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
  formant_centroid?: number;
  duration?: number;
  refText?: string;
  sampleUrl?: string;
  description: string;
  tag: string;
  createdAt: number;
}

const VOICESTUDIO_PRESETS = [
  { id: "broadcast", label: "Broadcast", icon: "📻", desc: "Радио/Подкаст жигд стандарт" },
  { id: "podcast", label: "Podcast", icon: "🎙️", desc: "Ойрын микрофон, гүн баргил" },
  { id: "warm", label: "Warm", icon: "☀️", desc: "Дулаан, зөөлөн нам давтамж" },
  { id: "bright", label: "Bright", icon: "✨", desc: "Тод цэвэр, өндөр нягтралтай" },
  { id: "cinematic", label: "Cinematic", icon: "🎬", desc: "Студийн орон зайн цуурайтай" },
  { id: "raw", label: "Raw", icon: "🔇", desc: "Нэмэлт эффектгүй" },
];

const DEFAULT_VOICES = [
  {
    id: "mn-MN-YesuiNeural",
    name: "Есүй",
    gender: "female" as const,
    category: "mn",
    icon: "👩",
    defaultPreset: "broadcast",
    description: "Уян зөөлөн, байгалийн тод өнгө аяс (Эмэгтэй)",
    tag: "Үндсэн • Эмэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-YesuiNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-MN-BataaNeural",
    name: "Батаа",
    gender: "male" as const,
    category: "mn",
    icon: "👨",
    defaultPreset: "broadcast",
    description: "Тод цэвэр, өөртөө итгэлтэй, баргил (Эрэгтэй)",
    tag: "Үндсэн • Эрэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-BataaNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-narrator",
    name: "Тэмүүлэн",
    gender: "male" as const,
    category: "mn",
    icon: "🎬",
    defaultPreset: "cinematic",
    description: "Гүн баргил, кино тайлбар болон аудио номд зориулсан өгүүлэгч",
    tag: "Студи • Өгүүлэгч",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-BataaNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-news",
    name: "Ану",
    gender: "female" as const,
    category: "mn",
    icon: "📺",
    defaultPreset: "bright",
    description: "Телевиз, мэдээний студийн тод цэвэр, хурц хэмнэлтэй хөтлөгч",
    tag: "Студи • Мэдээ",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-YesuiNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-podcast",
    name: "Ананд",
    gender: "male" as const,
    category: "mn",
    icon: "🎙️",
    defaultPreset: "podcast",
    description: "Ойрын микрофоны дулаан, энгийн чөлөөт ярианы подкаст хоолой",
    tag: "Студи • Подкаст",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-BataaNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-maral",
    name: "Марал",
    gender: "female" as const,
    category: "mn",
    icon: "🌸",
    defaultPreset: "warm",
    description: "Тайвшруулах, зөөлөн дулаан, уран зохиол ба бясалгалын хоолой",
    tag: "Студи • Уянгалаг",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-YesuiNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-elder",
    name: "Тулга",
    gender: "male" as const,
    category: "mn",
    icon: "🦁",
    defaultPreset: "warm",
    description: "Намбалаг, цээжний гүн резонанстай, жинтэй эрэгтэй хоолой",
    tag: "Студи • Гүн баргил",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-BataaNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "mn-studio-kid",
    name: "Мишээл",
    gender: "female" as const,
    category: "mn",
    icon: "🌟",
    defaultPreset: "bright",
    description: "Үлгэр, хүүхдийн контентод зориулсан цовоо сэргэлэн хоолой",
    tag: "Студи • Хүүхэд",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "mn-MN-YesuiNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "en-US-AvaMultilingualNeural",
    name: "Ava (Multilingual)",
    gender: "female" as const,
    category: "intl",
    icon: "🌐",
    defaultPreset: "broadcast",
    description: "Англи болон олон улсын холимог текстийг унших студийн эмэгтэй хоолой",
    tag: "Олон хэл • Эмэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "en-US-AvaMultilingualNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "en-US-AndrewMultilingualNeural",
    name: "Andrew (Multilingual)",
    gender: "male" as const,
    category: "intl",
    icon: "🌍",
    defaultPreset: "podcast",
    description: "Англи болон олон улсын холимог текстийг унших гүн эрэгтэй хоолой",
    tag: "Олон хэл • Эрэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "en-US-AndrewMultilingualNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "ja-JP-NanamiNeural",
    name: "Nanami • 七海",
    gender: "female" as const,
    category: "intl",
    icon: "🇯🇵",
    defaultPreset: "broadcast",
    description: "Япон хэлний байгалийн, маш тод цэвэр эмэгтэй хоолой (Japanese)",
    tag: "Япон • Эмэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "ja-JP-NanamiNeural",
    sampleUrl: "",
    refText: "",
  },
  {
    id: "ja-JP-KeitaNeural",
    name: "Keita • 圭太",
    gender: "male" as const,
    category: "intl",
    icon: "🗾",
    defaultPreset: "broadcast",
    description: "Япон хэлний тод, итгэлтэй эрэгтэй хоолой (Japanese)",
    tag: "Япон • Эрэгтэй",
    pitch: 1.0,
    speed: 1.0,
    baseVoice: "ja-JP-KeitaNeural",
    sampleUrl: "",
    refText: "",
  },
];

export default function TTSPage() {
  const [activeTab, setActiveTab] = useState<"standard" | "clone">("standard");
  const [voiceFilter, setVoiceFilter] = useState<"all" | "mn" | "intl" | "cloned">("all");

  // Synthesis State
  const [text, setText] = useState(
    "Сайн байна уу? Монгол хэлний хиймэл оюуны дуу хоолойн студид тавтай морилно уу."
  );
  const [selectedVoiceId, setSelectedVoiceId] = useState("mn-MN-YesuiNeural");
  const [selectedPreset, setSelectedPreset] = useState("broadcast");
  const [timbreStrength, setTimbreStrength] = useState(0.95);
  const [speed, setSpeed] = useState(1.0);
  const [pitch, setPitch] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [history, setHistory] = useState<GeneratedAudio[]>([]);
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
  const previewSampleRef = useRef<HTMLAudioElement | null>(null);
  const sampleRecorderRef = useRef<AudioRecorder | null>(null);
  const sampleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load saved cloned voices from server + localStorage
  useEffect(() => {
    const loadClones = async () => {
      let localList: ClonedVoice[] = [];
      try {
        const saved = localStorage.getItem("voice_clones");
        if (saved) localList = JSON.parse(saved);
      } catch {}

      try {
        const res = await fetch("/api/tts/clone");
        if (res.ok) {
          const serverList: ClonedVoice[] = await res.json();
          if (Array.isArray(serverList) && serverList.length > 0) {
            const mergedMap = new Map<string, ClonedVoice>();
            for (const item of serverList) mergedMap.set(item.id, item);
            for (const item of localList) {
              if (!mergedMap.has(item.id)) mergedMap.set(item.id, item);
            }
            const merged = Array.from(mergedMap.values()).sort(
              (a, b) => (b.createdAt || 0) - (a.createdAt || 0)
            );
            setClonedVoices(merged);
            localStorage.setItem("voice_clones", JSON.stringify(merged));
            return;
          }
        }
      } catch {}

      setClonedVoices(localList);
    };
    loadClones();
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

  const allVoices = [
    ...DEFAULT_VOICES,
    ...clonedVoices.map((c) => ({
      id: c.id,
      name: c.name,
      gender: c.gender,
      description: c.description || "Хувилсан хоолой",
      tag: "Хувилсан (Voice Clone)",
      pitch: c.pitch || 1.0,
      speed: c.speed || 1.0,
      baseVoice: c.baseVoice,
      sampleUrl: c.sampleUrl || `/api/tts/clone?id=${c.id}`,
      refText: c.refText || "",
    })),
  ];

  const selectedVoice =
    allVoices.find((v) => v.id === selectedVoiceId) || allVoices[0];

  const isSelectedCloned = selectedVoice.id.startsWith("cloned_");

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    setLoading(true);

    try {
      // IMPORTANT: Send selectedVoice.id (e.g. "cloned_xxxx") so tts_server.py applies Cepstral Vocal Tract Timbre Transfer!
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          voice: selectedVoice.id,
          speed,
          pitch,
          preset: selectedPreset,
          timbreStrength,
        }),
      });

      if (!res.ok) {
        throw new Error("Дуу үүсгэхэд алдаа гарлаа.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      setCurrentAudioUrl(url);

      const presetObj =
        VOICESTUDIO_PRESETS.find((p) => p.id === selectedPreset) ||
        VOICESTUDIO_PRESETS[0];

      const newEntry: GeneratedAudio = {
        id: "tts_" + Date.now(),
        text: text.trim(),
        voiceName: selectedVoice.name,
        presetLabel: `${presetObj.icon} ${presetObj.label}`,
        audioUrl: url,
        timestamp: Date.now(),
      };
      setHistory((prev) => [newEntry, ...prev.slice(0, 15)]);

      setTimeout(() => {
        if (audioRef.current) {
          audioRef.current.play().catch(() => {});
        }
      }, 80);
    } catch (err: unknown) {
      console.warn("TTS error:", err);
    } finally {
      setLoading(false);
    }
  };

  const playReferenceSample = (sampleUrl: string) => {
    if (!sampleUrl) return;
    if (!previewSampleRef.current) {
      previewSampleRef.current = new Audio();
    }
    previewSampleRef.current.src = sampleUrl;
    previewSampleRef.current.play().catch(() => {});
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
      setCloneName("Миний хоолой");
      setSampleBlob(null);
      setSampleAudioUrl(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Хоолой шинжлэхэд алдаа гарлаа.";
      setCloneError(msg);
    } finally {
      setIsCloning(false);
    }
  };

  const handleDeleteClonedVoice = async (id: string) => {
    const updated = clonedVoices.filter((v) => v.id !== id);
    saveClonedVoices(updated);
    if (selectedVoiceId === id) {
      setSelectedVoiceId("mn-MN-YesuiNeural");
    }
    try {
      await fetch(`/api/tts/clone?id=${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch {}
  };

  const samplePhrases = [
    "Сайн байна уу? Монгол хэлний дуу хоолойн системд тавтай морилно уу.",
    "Өнөөдрийн цаг агаар Улаанбаатар хотод тогтуун, тааламжтай байна.",
    "Хиймэл оюуны тусламжтайгаар өөрийн хоолойг хувилан хүссэн бичвэрээ уншуулаарай.",
    "Нэг хоёр гурав дөрөв тав зургаа долоо найм ес арав.",
  ];

  return (
    <section className="page">
      <small>VOICESTUDIO AI • ZERO-SHOT TIMBRE & DSP ENGINE</small>
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
          <h1 style={{ margin: "6px 0 10px" }}>Дуу Хоолойн Студи (VoiceStudio)</h1>
          <p style={{ maxWidth: "660px" }}>
            Монгол дуу хоолойгоор уншуулах, <b>хүний хоолойн тембр ба формантыг (F₁–F₄) хувилах (Voice Clone)</b> болон студийн <b>Broadcast DSP</b> эффектээр баяжуулах систем.
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
              ? "VoiceStudio Сервер Бэлэн (localhost:8000)"
              : "Сервер унтарсан (run-tts.bat)"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          marginTop: "24px",
          borderBottom: "1px solid var(--border)",
          paddingBottom: "14px",
          flexWrap: "wrap",
        }}
      >
        <button
          onClick={() => setActiveTab("standard")}
          className="btn-secondary"
          style={{
            background: activeTab === "standard" ? "var(--text)" : "var(--surface)",
            color: activeTab === "standard" ? "var(--bg)" : "var(--text)",
            padding: "9px 18px",
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
            padding: "9px 18px",
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
              <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                <VolumeIcon width={18} height={18} style={{ color: "var(--accent)" }} />
                <span>1. Дуу хоолойны загвар сонгох ({allVoices.length})</span>
              </h2>
              <button
                onClick={() => setActiveTab("clone")}
                className="btn-primary"
                style={{ fontSize: "12px", padding: "7px 14px" }}
              >
                <SparklesIcon width={14} height={14} />
                <span>+ Шинэ хоолой хувилах</span>
              </button>
            </div>

            {/* Category filter pills */}
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "16px" }}>
              {[
                { id: "all", label: `Бүгд (${allVoices.length})` },
                { id: "mn", label: "🇲🇳 Монгол Студи (8)" },
                { id: "intl", label: "🌐 Англи / Япон (4)" },
                { id: "cloned", label: `✨ Миний хувилсан (${clonedVoices.length})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setVoiceFilter(tab.id as "all" | "mn" | "intl" | "cloned")}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "999px",
                    fontSize: "12px",
                    fontWeight: 600,
                    border: voiceFilter === tab.id ? "1px solid var(--accent)" : "1px solid var(--border)",
                    background: voiceFilter === tab.id ? "rgba(99, 102, 241, 0.16)" : "var(--surface)",
                    color: voiceFilter === tab.id ? "var(--accent)" : "var(--muted)",
                    transition: "all 0.15s ease",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
                gap: "12px",
              }}
            >
              {allVoices
                .filter((v) => {
                  const isCloned = v.id.startsWith("cloned_");
                  const cat = "category" in v ? (v as { category?: string }).category : "cloned";
                  if (voiceFilter === "cloned") return isCloned;
                  if (voiceFilter === "mn") return !isCloned && cat === "mn";
                  if (voiceFilter === "intl") return !isCloned && cat === "intl";
                  return true;
                })
                .map((voice) => {
                const isSelected = selectedVoiceId === voice.id;
                const isFemale = voice.gender === "female";
                const isCloned = voice.id.startsWith("cloned_");
                const customIcon = "icon" in voice ? (voice as { icon?: string }).icon : undefined;
                const defPreset = "defaultPreset" in voice ? (voice as { defaultPreset?: string }).defaultPreset : undefined;
                return (
                  <div
                    key={voice.id}
                    onClick={() => {
                      setSelectedVoiceId(voice.id);
                      if (defPreset) setSelectedPreset(defPreset);
                    }}
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
                            width: "38px",
                            height: "38px",
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
                            fontSize: "16px",
                            fontWeight: 700,
                            boxShadow: isCloned ? "0 0 12px rgba(217, 70, 239, 0.4)" : "none",
                          }}
                        >
                          {isCloned ? "✨" : customIcon || (isFemale ? "👩" : "👨")}
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
                        margin: "10px 0 0",
                        fontSize: "12px",
                        color: "var(--muted)",
                        lineHeight: 1.45,
                      }}
                    >
                      {voice.description}
                    </p>

                    {isCloned && voice.refText && (
                      <div
                        style={{
                          marginTop: "6px",
                          fontSize: "11px",
                          color: "var(--muted)",
                          fontStyle: "italic",
                        }}
                      >
                        Эх дээж: &ldquo;{voice.refText.slice(0, 48)}&rdquo;
                      </div>
                    )}

                    {isCloned && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginTop: "10px",
                          paddingTop: "8px",
                          borderTop: "1px solid var(--border)",
                        }}
                      >
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            playReferenceSample(voice.sampleUrl || `/api/tts/clone?id=${voice.id}`);
                          }}
                          className="btn-secondary"
                          style={{ fontSize: "11px", padding: "4px 10px" }}
                          title="Таны бичсэн эх дуу хоолойн дээжийг сонсох"
                        >
                          <PlayIcon width={12} height={12} />
                          <span>Эх хоолой сонсох</span>
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClonedVoice(voice.id);
                          }}
                          style={{
                            background: "none",
                            color: "var(--muted)",
                            padding: "4px 6px",
                            borderRadius: "6px",
                          }}
                          title="Хоолойг устгах"
                        >
                          <TrashIcon width={14} height={14} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* VoiceStudio Audio DSP Presets */}
            <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid var(--border)" }}>
              <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "10px" }}>
                🎚️ VoiceStudio Аудио Мастеринг & Эффект (DSP Preset):
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {VOICESTUDIO_PRESETS.map((p) => {
                  const active = selectedPreset === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setSelectedPreset(p.id)}
                      className="btn-secondary"
                      style={{
                        padding: "7px 14px",
                        borderRadius: "10px",
                        fontSize: "12px",
                        borderColor: active ? "var(--accent)" : undefined,
                        background: active ? "rgba(99, 102, 241, 0.14)" : undefined,
                        fontWeight: active ? 700 : 500,
                      }}
                      title={p.desc}
                    >
                      <span>{p.icon}</span>
                      <span>{p.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Speed, Pitch & Timbre Strength Controls */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "18px",
                marginTop: "18px",
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
                  min="0.6"
                  max="1.4"
                  step="0.05"
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
                  min="0.75"
                  max="1.25"
                  step="0.05"
                  value={pitch}
                  onChange={(e) => setPitch(parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
              </div>

              {isSelectedCloned && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "13px",
                      marginBottom: "8px",
                    }}
                  >
                    <span>Хоолойн тембр ижилсэлт</span>
                    <b>{Math.round(timbreStrength * 100)}%</b>
                  </div>
                  <input
                    type="range"
                    min="0.3"
                    max="1.0"
                    step="0.05"
                    value={timbreStrength}
                    onChange={(e) => setTimbreStrength(parseFloat(e.target.value))}
                    style={{ width: "100%" }}
                  />
                </div>
              )}
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
                <span>2. Уншуулах бичвэр</span>
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
                  {phrase.slice(0, 32)}...
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
                <VolumeIcon width={20} height={20} />
                <span>
                  {loading
                    ? "Дуу үүсгэж байна..."
                    : `Яриулах (${selectedVoice.name})`}
                </span>
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
                border: "1px solid rgba(99, 102, 241, 0.35)",
                background:
                  "linear-gradient(135deg, rgba(99, 102, 241, 0.07), rgba(168, 85, 247, 0.07))",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "14px",
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
                      background: "var(--accent-gradient)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#fff",
                    }}
                  >
                    <WavesIcon width={22} height={22} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "15px" }}>
                      {selectedVoice.name} • VoiceStudio Гаралт
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--muted)" }}>
                      24kHz Broadcast WAV • Cepstral Timbre Engine
                    </div>
                  </div>
                </div>

                <a
                  href={currentAudioUrl}
                  download={`${selectedVoice.name}-speech.wav`}
                  className="btn-secondary"
                  style={{ textDecoration: "none", fontSize: "12px" }}
                >
                  ⬇️ WAV татах
                </a>
              </div>

              <audio
                ref={audioRef}
                controls
                src={currentAudioUrl}
                style={{ width: "100%", height: "42px", borderRadius: "10px" }}
              />
            </div>
          )}

          {/* History */}
          {history.length > 0 && (
            <div className="settings">
              <h2 style={{ marginBottom: "14px" }}>Саяхан үүсгэсэн дуунууд</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {history.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "12px",
                      padding: "12px 14px",
                      background: "var(--subtle)",
                      borderRadius: "12px",
                      border: "1px solid var(--border)",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: "200px" }}>
                      <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent)" }}>
                        {item.voiceName} • {item.presetLabel}
                      </div>
                      <div style={{ fontSize: "13px", marginTop: "2px" }}>
                        {item.text}
                      </div>
                    </div>
                    <audio controls src={item.audioUrl} style={{ height: "34px" }} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: VOICE CLONING STUDIO */}
      {activeTab === "clone" && (
        <div className="settings" style={{ marginTop: "20px" }}>
          <h2 style={{ fontSize: "18px", marginBottom: "8px" }}>
            ✨ Хүний дуу хоолой хувилах (VoiceStudio Acoustic Cloner)
          </h2>
          <p style={{ marginBottom: "20px" }}>
            Өөрийн эсвэл дурын хүний хоолойг 4–10 секунд бичих (эсвэл аудио файл оруулах) замаар тухайн хүний <b>хоолойн тембр, формант (F₁–F₄), үндсэн давтамж ($f_0$) болон ярианы хэмнэлийг</b> хувилж авна.
          </p>

          <div style={{ display: "grid", gap: "18px", maxWidth: "640px" }}>
            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                1. Шинэ хоолойн нэр:
              </label>
              <input
                type="text"
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
                placeholder="Жишээ нь: Миний хоолой, Аавын хоолой..."
                style={{
                  width: "100%",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  border: "1px solid var(--border)",
                  background: "var(--subtle)",
                  color: "var(--text)",
                }}
              />
            </div>

            <div
              style={{
                padding: "18px",
                borderRadius: "16px",
                border: "1px dashed var(--border-focus)",
                background: "var(--subtle)",
              }}
            >
              <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
                2. Дээж өгүүлбэр уншиж бичих (4–10 секунд):
              </div>
              <p style={{ fontSize: "13px", color: "var(--text)", fontStyle: "italic", marginBottom: "14px" }}>
                &ldquo;Сайн байна уу? Өнөөдөр цаг агаар маш сайхан байна. Би өөрийн дуу хоолойг хиймэл оюунд таниулж, шинэ хоолойн загвар үүсгэж байна.&rdquo;
              </p>

              <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
                {!isRecordingSample ? (
                  <button
                    type="button"
                    onClick={startRecordingSample}
                    className="btn-primary"
                  >
                    <MicIcon width={16} height={16} />
                    <span>Микрофоноор хоолой бичих</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopRecordingSample}
                    className="btn-danger"
                    style={{ background: "#ef4444", color: "#fff" }}
                  >
                    <span>⏹ Зогсоох ({recordSeconds} сек)</span>
                  </button>
                )}

                <label
                  className="btn-secondary"
                  style={{ cursor: "pointer", margin: 0 }}
                >
                  <span>📂 Эсвэл аудио файл (WAV/MP3) оруулах</span>
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={handleFileUpload}
                    style={{ display: "none" }}
                  />
                </label>
              </div>

              {sampleAudioUrl && (
                <div style={{ marginTop: "14px" }}>
                  <div style={{ fontSize: "12px", color: "#10b981", fontWeight: 600, marginBottom: "6px" }}>
                    ✅ Дууны дээж бэлэн боллоо — сонсож шалгана уу:
                  </div>
                  <audio controls src={sampleAudioUrl} style={{ width: "100%", height: "38px" }} />
                </div>
              )}
            </div>

            {cloneError && (
              <div className="error" style={{ marginTop: 0 }}>
                {cloneError}
              </div>
            )}

            <div style={{ display: "flex", gap: "12px" }}>
              <button
                type="button"
                onClick={handleCloneSubmit}
                disabled={isCloning || !sampleBlob}
                className="btn-primary"
                style={{ padding: "12px 24px", fontSize: "14px" }}
              >
                <SparklesIcon width={18} height={18} />
                <span>
                  {isCloning
                    ? "Хоолойн формант & тембр шинжилж байна..."
                    : "Хоолойг хувилж хадгалах"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
