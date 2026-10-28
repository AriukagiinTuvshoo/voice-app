"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  languages,
  recordingModes,
  shortcuts,
  modes,
  themes,
  defaultSettings,
} from "@/lib/constants";
import type {
  Language,
  RecordingState,
  Settings,
  Shortcut,
} from "@/lib/types";
import { AudioRecorder, getAudioInputDevices } from "@/lib/audio-recorder";
import { BrowserSpeechRecognizer, isBrowserSpeechSupported } from "@/lib/speech-recognition";
import { processTranscriptText, getTextStats } from "@/lib/text-processor";
import { HistoryStore } from "@/lib/history-store";
import { SpellCheckClient } from "@/lib/spellcheck-client";
import {
  MicIcon,
  PlusIcon,
  HistoryIcon,
  SettingsIcon,
  VolumeIcon,
  SparklesIcon,
  CopyIcon,
  CheckIcon,
  EditIcon,
  TrashIcon,
  FlowBarIcon,
  ShareIcon,
} from "@/components/Icons";

interface Ctx {
  settings: Settings;
  update: <K extends keyof Settings>(k: K, v: Settings[K]) => void;
  workspaceText: string;
  setWorkspaceText: (t: string) => void;
  flowbarStatus: {
    status: string;
    visible: boolean;
    last_text: string;
    last_timestamp: number;
  };
  toggleFlowBar: () => Promise<void>;
  triggerFlowBarRecording: () => Promise<void>;
}

const SettingsContext = createContext<Ctx | null>(null);

export function useSettings() {
  const c = useContext(SettingsContext);
  if (!c) throw new Error("useSettings must be used inside AppShell");
  return c;
}

function Provider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [workspaceText, setWorkspaceText] = useState<string>("");
  const [flowbarStatus, setFlowbarStatus] = useState(() => {
    let saved = true;
    if (typeof window !== "undefined") {
      try {
        saved = localStorage.getItem("voice_web_flowbar_visible") !== "false";
      } catch {}
    }
    return {
      status: "idle",
      visible: saved,
      last_text: "",
      last_timestamp: 0,
    };
  });
  const lastSeenTimestampRef = useRef<number>(0);

  useEffect(() => {
    try {
      const x = localStorage.getItem("voice-settings");
      if (x) setSettings({ ...defaultSettings, ...JSON.parse(x) });
    } catch {}
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("voice-settings", JSON.stringify(settings));
    } catch {}
  }, [settings]);

  // Sync language selection with Native Windows FlowBar
  useEffect(() => {
    fetch("/api/flowbar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "set_language", language: settings.language }),
    }).catch(() => {});
  }, [settings.language]);

  // Poll Native Windows FlowBar status (when running desktop helper)
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/flowbar");
        if (!res.ok) return;
        const data = await res.json();
        if (data && typeof data.status === "string" && data.status !== "offline") {
          setFlowbarStatus((prev) => ({
            ...prev,
            status: data.status,
            visible: data.visible !== undefined ? Boolean(data.visible) : prev.visible,
            last_text: data.last_text || "",
            last_timestamp: data.last_timestamp || 0,
          }));

          if (
            data.last_timestamp &&
            data.last_timestamp > lastSeenTimestampRef.current &&
            data.last_text
          ) {
            lastSeenTimestampRef.current = data.last_timestamp;
            setWorkspaceText(data.last_text);
            const stats = getTextStats(data.last_text);
            HistoryStore.add({
              text: data.last_text,
              rawText: data.last_text,
              durationSeconds: data.seconds || 3,
              language: settings.language,
              engine: "Duudlaga Flow (Ctrl+Alt)",
              wordCount: stats.wordCount,
              charCount: stats.charCount,
            });
          }
        }
      } catch {}
    }, 1200);
    return () => clearInterval(timer);
  }, [settings.language]);

  useEffect(() => {
    const root = document.documentElement;
    const apply = () => {
      root.dataset.theme =
        settings.theme === "system"
          ? matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
          : settings.theme;
    };
    apply();
    if (settings.theme !== "system") return;
    const m = matchMedia("(prefers-color-scheme: dark)");
    m.addEventListener("change", apply);
    return () => m.removeEventListener("change", apply);
  }, [settings.theme]);

  const toggleFlowBar = useCallback(async () => {
    setFlowbarStatus((prev) => {
      const nextVisible = !prev.visible;
      try {
        localStorage.setItem("voice_web_flowbar_visible", String(nextVisible));
      } catch {}
      return { ...prev, visible: nextVisible };
    });
    try {
      await fetch("/api/flowbar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "toggle_visibility" }),
      });
    } catch {}
  }, []);

  const triggerFlowBarRecording = useCallback(async () => {
    try {
      const nextAct = flowbarStatus.status === "recording" ? "stop" : "start";
      const res = await fetch("/api/flowbar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: nextAct }),
      });
      if (res.ok) {
        const data = await res.json();
        setFlowbarStatus((prev) => ({
          ...prev,
          visible: true,
          status: data.status || prev.status,
        }));
      }
    } catch {}
  }, [flowbarStatus.status]);

  const value = useMemo(
    () => ({
      settings,
      update: <K extends keyof Settings>(k: K, v: Settings[K]) =>
        setSettings((s) => ({ ...s, [k]: v })),
      workspaceText,
      setWorkspaceText,
      flowbarStatus,
      toggleFlowBar,
      triggerFlowBarRecording,
    }),
    [settings, workspaceText, flowbarStatus, toggleFlowBar, triggerFlowBarRecording]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

const navItems = [
  { href: "/dashboard", label: "Шинэ яриа", icon: PlusIcon },
  { href: "/tts", label: "VoiceStudio", icon: VolumeIcon },
  { href: "/keyboard", label: "Утасны Гар", icon: FlowBarIcon },
  { href: "/history", label: "Түүх", icon: HistoryIcon },
  { href: "/settings", label: "Тохиргоо", icon: SettingsIcon },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Provider>
      <Shell>{children}</Shell>
    </Provider>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { settings, update, flowbarStatus, toggleFlowBar } = useSettings();

  // Standalone floating pill route — render WITHOUT sidebar or topbar
  if (path === "/flowbar") {
    return <>{children}</>;
  }

  const isFlowRecording = flowbarStatus.status === "recording";

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="brand-wrapper">
          <div className="brand-logo">
            <MicIcon width={18} height={18} />
          </div>
          <span className="brand-title">VOICE</span>
        </Link>

        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = path === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={isActive ? "nav active" : "nav"}
              >
                <span className="nav-icon">
                  <Icon width={18} height={18} />
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="side-note" style={{ flexDirection: "column", alignItems: "flex-start", gap: "4px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="status-dot" />
            <b style={{ color: "var(--text)", fontSize: "12px" }}>VOICE AI • Онлайн</b>
          </div>
          <span style={{ fontSize: "11px", lineHeight: 1.4, color: "var(--muted)" }}>
            Монгол • English • 日本語
          </span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <b className="mobile-brand">
            <span className="brand-logo" style={{ width: "24px", height: "24px" }}>
              <MicIcon width={14} height={14} />
            </span>
            VOICE
          </b>

          <div
            className="desktop-only"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "12px",
              color: "var(--muted)",
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: isFlowRecording
                  ? "#ef4444"
                  : flowbarStatus.visible
                  ? "#10b981"
                  : "#64748b",
                boxShadow: isFlowRecording
                  ? "0 0 10px #ef4444"
                  : flowbarStatus.visible
                  ? "0 0 8px #10b981"
                  : "none",
              }}
            />
            <span>
              {isFlowRecording
                ? "🔴 Яриа бичиж байна..."
                : "Шууд бичих:"}
            </span>
            <kbd>Ctrl + Alt</kbd>
          </div>

          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              type="button"
              onClick={toggleFlowBar}
              className="btn-secondary"
              style={{
                fontSize: "12px",
                padding: "7px 12px",
                borderColor: flowbarStatus.visible ? "rgba(16, 185, 129, 0.4)" : undefined,
                background: flowbarStatus.visible ? "rgba(16, 185, 129, 0.08)" : undefined,
              }}
              title="Хөвөгч FlowBar товчийг харуулах / нуух"
            >
              <FlowBarIcon width={15} height={15} />
              <span>{flowbarStatus.visible ? "FlowBar" : "FlowBar: Нуусан"}</span>
            </button>

            <LanguageSelect
              value={settings.language}
              onChange={(v) => update("language", v)}
            />
          </div>
        </header>

        {children}

        {flowbarStatus.visible && path !== "/flowbar" && (
          <FloatingWebFlowBar />
        )}
      </main>

      <nav className="mobile-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = path === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={isActive ? "mnav active" : "mnav"}
            >
              <Icon width={18} height={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function LanguageSelect({
  value,
  onChange,
}: {
  value: Language;
  onChange: (v: Language) => void;
}) {
  return (
    <label className="language">
      <span className="sr">Language</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as Language)}
      >
        {languages.map((x) => (
          <option key={x.value} value={x.value}>
            {x.icon} {x.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Workspace() {
  const { settings, workspaceText, setWorkspaceText } = useSettings();
  const [state, setState] = useState<RecordingState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [rawText, setRawText] = useState("");
  const [livePreview, setLivePreview] = useState("");
  const [editing, setEditing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [audioLevels, setAudioLevels] = useState<number[]>([12, 18, 26, 18, 12]);
  const [copied, setCopied] = useState(false);

  // Spellcheck state
  const [spellChecking, setSpellChecking] = useState(false);
  const [spellCheckResults, setSpellCheckResults] = useState<{
    misspelled: string[];
    suggestions: Record<string, string[]>;
  }>({ misspelled: [], suggestions: {} });
  const [showSpellPanel, setShowSpellPanel] = useState(false);

  // TTS audio state
  const [ttsLoading, setTtsLoading] = useState(false);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const browserRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const pttActiveRef = useRef(false);

  useEffect(() => {
    if (workspaceText && workspaceText !== rawText && state !== "recording") {
      setRawText(workspaceText);
    }
  }, [workspaceText, rawText, state]);

  useEffect(() => {
    if (state === "recording") {
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [state]);

  const stopAndTranscribe = useCallback(
    async (currentDuration: number) => {
      setState("processing");
      setErrorMessage("");
      setLivePreview("");

      try {
        let browserTranscript = "";
        let serverTranscript = "";
        let usedEngine = "Google Neural STT (mn-MN)";

        if (browserRecognizerRef.current) {
          browserTranscript = await browserRecognizerRef.current.stop();
          browserRecognizerRef.current = null;
        }

        if (audioRecorderRef.current) {
          const wavBlob = await audioRecorderRef.current.stop();
          audioRecorderRef.current = null;

          // Always send WAV to enhanced Python STT server for high-accuracy recognition
          try {
            const formData = new FormData();
            formData.append("audio", wavBlob, "speech.wav");
            formData.append("language", settings.language);
            formData.append("punctuate", String(settings.autoPunctuation));

            const res = await fetch("/api/chimege/transcribe", {
              method: "POST",
              body: formData,
            });

            if (res.ok) {
              const data = await res.json();
              if (data.text && data.text.trim()) {
                serverTranscript = data.text.trim();
                if (data.engine) usedEngine = data.engine;
              }
            }
          } catch (e) {
            console.warn("Server STT fallback to browser STT:", e);
          }
        }

        // Always prefer serverTranscript (Multilingual Code-Switching mn-MN + en-US + ja-JP engine)
        const transcript = serverTranscript || browserTranscript;

        if (!transcript || !transcript.trim()) {
          setState("idle");
          setErrorMessage("Яриа сонсогдсонгүй. Микрофондоо ойрхон, тод ярина уу.");
          return;
        }

        const processed = processTranscriptText(transcript, {
          mode: settings.processingMode,
          autoPunctuation: settings.autoPunctuation,
          removeFillers: settings.removeFillers,
          language: settings.language,
        });

        setRawText(processed);
        setWorkspaceText(processed);
        setState("success");
        navigator.clipboard?.writeText(processed).catch(() => {});

        if (settings.saveTranscripts) {
          const stats = getTextStats(processed);
          HistoryStore.add({
            text: processed,
            rawText: transcript,
            durationSeconds: currentDuration,
            language: settings.language,
            engine: usedEngine,
            wordCount: stats.wordCount,
            charCount: stats.charCount,
          });
        }

        if (settings.autoCorrection) {
          setSpellChecking(true);
          SpellCheckClient.check(processed).then((res) => {
            setSpellCheckResults({
              misspelled: res.misspelled,
              suggestions: res.suggestions,
            });
            if (res.misspelled.length > 0) {
              setShowSpellPanel(true);
            }
            setSpellChecking(false);
          });
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Яриа танихад алдаа гарлаа.";
        setErrorMessage(msg);
        setState("error");
      }
    },
    [settings, setWorkspaceText]
  );

  const startRecording = useCallback(async () => {
    setErrorMessage("");
    setSeconds(0);
    setLivePreview("");

    try {
      if (typeof navigator !== "undefined" && navigator.vibrate) {
        navigator.vibrate(40);
      }

      // 1. Always start AudioRecorder FIRST to cleanly prompt & acquire Microphone Permission
      const recorder = new AudioRecorder({
        deviceId: settings.selectedAudioDevice,
        autoStop: settings.autoStop,
        onAudioLevel: (lvl) => {
          setAudioLevels((prev) => [
            ...prev.slice(1),
            Math.max(6, Math.round(lvl * 36)),
          ]);
        },
        onSilenceDetected: () => {
          stopAndTranscribe(seconds);
        },
      });
      audioRecorderRef.current = recorder;
      await recorder.start();

      // 2. On Desktop browsers, start BrowserSpeechRecognizer AFTER mic permission is granted
      // (On mobile Android/iOS, running SpeechRecognition + getUserMedia simultaneously causes OS mic conflict)
      const isMobile =
        typeof navigator !== "undefined" &&
        /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");

      if (!isMobile && isBrowserSpeechSupported() && settings.sttEngine !== "chimege") {
        try {
          const recognizer = new BrowserSpeechRecognizer({
            language: settings.language,
            onInterim: (previewText) => {
              setLivePreview(previewText);
            },
            onError: () => {},
          });
          browserRecognizerRef.current = recognizer;
          recognizer.start();
        } catch {}
      }

      setState("recording");
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Микрофон ажиллуулахад алдаа гарлаа. Хөтчийнхөө микрофоны зөвшөөрлийг (Allow) шалгана уу.";
      setErrorMessage(msg);
      setState("error");
    }
  }, [settings, seconds, stopAndTranscribe]);

  const toggleRecording = useCallback(() => {
    if (state === "idle" || state === "error" || state === "success") {
      startRecording();
    } else if (state === "recording") {
      stopAndTranscribe(seconds);
    }
  }, [state, seconds, startRecording, stopAndTranscribe]);

  // Keyboard shortcut inside web app
  useEffect(() => {
    const isPushToTalk = settings.recordingMode === "push_to_talk";

    const onKeyDown = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el?.matches("input,textarea,[contenteditable=true]") || e.repeat) return;

      const s = settings.shortcut;
      const ok =
        s === "Space"
          ? e.code === "Space"
          : s.startsWith("Ctrl+")
          ? e.ctrlKey && e.code === s.slice(5)
          : s.startsWith("Alt+")
          ? e.altKey && e.code === s.slice(4)
          : e.key === s;

      if (!ok) return;
      e.preventDefault();

      if (isPushToTalk) {
        if (!pttActiveRef.current && state !== "recording" && state !== "processing") {
          pttActiveRef.current = true;
          startRecording();
        }
      } else {
        toggleRecording();
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (!isPushToTalk || !pttActiveRef.current) return;
      const s = settings.shortcut;
      const ok =
        s === "Space"
          ? e.code === "Space"
          : s.startsWith("Ctrl+")
          ? e.ctrlKey || e.code === s.slice(5)
          : s.startsWith("Alt+")
          ? e.altKey || e.code === s.slice(4)
          : e.key === s;

      if (ok) {
        pttActiveRef.current = false;
        if (state === "recording") {
          stopAndTranscribe(seconds);
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [settings.shortcut, settings.recordingMode, state, seconds, startRecording, stopAndTranscribe, toggleRecording]);

  const handleRunSpellCheck = async () => {
    if (!rawText.trim()) return;
    setSpellChecking(true);
    try {
      const res = await SpellCheckClient.check(rawText);
      setSpellCheckResults({
        misspelled: res.misspelled,
        suggestions: res.suggestions,
      });
      setShowSpellPanel(true);
    } catch {
      setErrorMessage("Зөв бичгийн дүрэм шалгахад алдаа гарлаа.");
    } finally {
      setSpellChecking(false);
    }
  };

  const applySuggestion = (misspelledWord: string, candidate: string) => {
    const regex = new RegExp(`(?<=[^\\p{L}]|^)${misspelledWord}(?=[^\\p{L}]|$)`, "gu");
    const updated = rawText.replace(regex, candidate);
    setRawText(updated);
    setWorkspaceText(updated);

    setSpellCheckResults((prev) => ({
      misspelled: prev.misspelled.filter((w) => w !== misspelledWord),
      suggestions: prev.suggestions,
    }));
  };

  const applyAllCorrections = () => {
    let updated = rawText;
    for (const word of spellCheckResults.misspelled) {
      const candidate = spellCheckResults.suggestions[word]?.[0];
      if (candidate) {
        const regex = new RegExp(`(?<=[^\\p{L}]|^)${word}(?=[^\\p{L}]|$)`, "gu");
        updated = updated.replace(regex, candidate);
      }
    }
    setRawText(updated);
    setWorkspaceText(updated);
    setSpellCheckResults({ misspelled: [], suggestions: {} });
  };

  const playTextToSpeech = async (textToSpeak: string) => {
    if (!textToSpeak.trim()) return;
    setTtsLoading(true);
    setErrorMessage("");

    try {
      let preferredVoice = "mn-MN-YesuiNeural";
      let cloneProfile: Record<string, unknown> | null = null;
      try {
        const savedClones = localStorage.getItem("voice_clones");
        if (savedClones) {
          const parsed = JSON.parse(savedClones);
          if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].id) {
            preferredVoice = parsed[0].id;
            cloneProfile = parsed[0];
          }
        }
      } catch {}

      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textToSpeak.trim(),
          voice: preferredVoice,
          preset: "broadcast",
          cloneProfile,
        }),
      });

      if (!res.ok) {
        throw new Error("Дуу үүсгэхэд алдаа гарлаа.");
      }

      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);

      if (!ttsAudioRef.current) {
        ttsAudioRef.current = new Audio();
      }
      ttsAudioRef.current.src = audioUrl;
      await ttsAudioRef.current.play();
    } catch (err: unknown) {
      console.warn("TTS Play error:", err);
      setErrorMessage("Аудио уншуулахад алдаа гарлаа. Дахин оролдоно уу.");
    } finally {
      setTtsLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (!rawText) return;
    navigator.clipboard?.writeText(rawText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const label =
    state === "idle"
      ? "ЯРЬЖ ЭХЛЭХ"
      : state === "recording"
      ? "ЯРЬЖ БАЙНА..."
      : state === "processing"
      ? "БОЛОВСРУУЛЖ БАЙНА..."
      : state === "error"
      ? "ДАХИН ОРОЛДОХ"
      : "БИЧЛЭГ БЭЛЭН";

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  const displayedText = state === "recording" && livePreview ? livePreview : rawText;
  const stats = getTextStats(displayedText);

  return (
    <section className="workspace">
      <div className="heading">
        <div>
          <h1>Яриаг бичвэр болгох</h1>
          <p>
            Монгол, Англи, Япон хэлээр ярьж, бичвэрээ шууд хуулж эсвэл хуваалцаарай.
          </p>
        </div>
      </div>

      <div className={`stage ${state === "recording" ? "active-stage" : ""}`}>
        <div className={state === "recording" ? "halo pulse" : "halo"}>
          <button
            className={state === "recording" ? "mic recording" : "mic"}
            onClick={toggleRecording}
            disabled={state === "processing"}
            aria-label={label}
            aria-pressed={state === "recording"}
          >
            <MicIcon width={36} height={36} />
          </button>
        </div>

        <strong>{label}</strong>

        {state === "recording" && (
          <div style={{ textAlign: "center" }}>
            <time>{mm}:{ss}</time>
            <div className="waveform-bars">
              {audioLevels.map((lvl, idx) => (
                <div
                  key={idx}
                  className="waveform-bar"
                  style={{
                    height: `${Math.max(6, lvl + (idx % 2 === 0 ? 6 : -4))}px`,
                    opacity: 0.7 + (lvl / 40) * 0.3,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0, textAlign: "center" }}>
          {state === "recording"
            ? livePreview
              ? `Сонсож байна: "${livePreview}"`
              : "Сонсож байна... Тод ярина уу"
            : "Микрофон дээр дарж ярих эсвэл доорх VOICE FLOW товчийг ашиглаарай"}
        </p>
      </div>

      {state === "error" && errorMessage && (
        <div className="error" role="alert">
          <b>Анхаар:</b> {errorMessage}
        </div>
      )}

      {/* Transcript Section */}
      <section className="transcript">
        <header>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <SparklesIcon width={16} height={16} style={{ color: "var(--accent)" }} />
            <b>Таны бичвэр</b>
          </div>
          <span>
            {stats.wordCount} үг • {stats.charCount} тэмдэгт
          </span>
        </header>

        <div className="transcript-body">
          {state === "processing" ? (
            <div className="empty">
              <b>Яриаг бичвэрт хөрвүүлж байна...</b>
              <small>Түр хүлээнэ үү</small>
            </div>
          ) : editing ? (
            <textarea
              autoFocus
              value={rawText}
              onChange={(e) => {
                setRawText(e.target.value);
                setWorkspaceText(e.target.value);
              }}
              placeholder="Бичвэр энд харагдана..."
            />
          ) : displayedText ? (
            <p className="transcript-text">{displayedText}</p>
          ) : (
            <div className="empty">
              <b>Ярианы бичвэр энд гарна</b>
              <small>
                Дээрх микрофон товч дээр дарж ярьж эхэлнэ үү.
              </small>
            </div>
          )}
        </div>

        {/* Spellcheck Suggestions Panel */}
        {showSpellPanel && spellCheckResults.misspelled.length > 0 && (
          <div className="spellcheck-panel">
            <div className="spellcheck-header">
              <div className="spellcheck-title">
                <SparklesIcon width={16} height={16} style={{ color: "#ef4444" }} />
                <span>Зөв бичгийн алдаа</span>
                <span className="spellcheck-badge">
                  {spellCheckResults.misspelled.length}
                </span>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button className="btn-secondary" onClick={applyAllCorrections}>
                  Бүгдийг засах
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => setShowSpellPanel(false)}
                >
                  Хаах
                </button>
              </div>
            </div>

            <div className="spellcheck-words">
              {spellCheckResults.misspelled.map((word) => {
                const candidates = spellCheckResults.suggestions[word] || [];
                return (
                  <div key={word} className="spellcheck-item">
                    <span className="misspelled-tag">{word}</span>
                    <span>→</span>
                    {candidates.length > 0 ? (
                      candidates.slice(0, 5).map((cand) => (
                        <button
                          key={cand}
                          className="suggestion-pill"
                          onClick={() => applySuggestion(word, cand)}
                          title="Дарж энэ хувилбараар солих"
                        >
                          {cand}
                        </button>
                      ))
                    ) : (
                      <small style={{ color: "var(--muted)" }}>Санал олдсонгүй</small>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {showSpellPanel && spellCheckResults.misspelled.length === 0 && !spellChecking && (
          <div className="spellcheck-panel">
            <div className="spellcheck-header">
              <div className="spellcheck-title">
                <span className="spellcheck-badge clean">
                  <CheckIcon width={12} height={12} />
                </span>
                <span>Зөв бичгийн алдаа илэрсэнгүй! (Зөв)</span>
              </div>
              <button
                className="btn-secondary"
                onClick={() => setShowSpellPanel(false)}
              >
                Хаах
              </button>
            </div>
          </div>
        )}

        <footer>
          <button
            className="btn-primary"
            onClick={copyToClipboard}
            disabled={!rawText}
          >
            {copied ? <CheckIcon width={15} height={15} /> : <CopyIcon width={15} height={15} />}
            <span>{copied ? "Хуулагдлаа!" : "Хуулах"}</span>
          </button>
          {typeof navigator !== "undefined" && typeof navigator.share === "function" && (
            <button
              className="btn-secondary"
              onClick={() => {
                if (!rawText) return;
                navigator.share({
                  title: "VOICE Текст",
                  text: rawText,
                }).catch(() => {});
              }}
              disabled={!rawText}
              title="Утсаараа Facebook, Messenger, Telegram руу шууд хуваалцах"
            >
              <ShareIcon width={15} height={15} />
              <span>Хуваалцах</span>
            </button>
          )}
          <button
            className="btn-secondary"
            onClick={() => playTextToSpeech(rawText)}
            disabled={!rawText || ttsLoading}
          >
            <VolumeIcon width={15} height={15} />
            <span>{ttsLoading ? "Уншиж байна..." : "Сонсох"}</span>
          </button>
          <button
            className="btn-secondary"
            onClick={handleRunSpellCheck}
            disabled={!rawText || spellChecking}
          >
            <SparklesIcon width={15} height={15} />
            <span>{spellChecking ? "Шалгаж байна..." : "Дүрэм шалгах"}</span>
          </button>
          <button className="btn-secondary" onClick={() => setEditing(!editing)} disabled={!rawText}>
            <EditIcon width={15} height={15} />
            <span>{editing ? "Хадгалах" : "Засах"}</span>
          </button>
          <button
            className="btn-secondary desktop-only"
            onClick={() => {
              if (!rawText) return;
              fetch("/api/flowbar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ insertText: rawText }),
              }).catch(() => {});
            }}
            disabled={!rawText}
            title="Компьютерын идэвхтэй цонх руу шууд бичих"
          >
            <FlowBarIcon width={15} height={15} />
            <span>Цонх руу бичих</span>
          </button>
          <button
            className="btn-danger"
            onClick={() => {
              setRawText("");
              setLivePreview("");
              setWorkspaceText("");
              setEditing(false);
              setState("idle");
              setSeconds(0);
              setSpellCheckResults({ misspelled: [], suggestions: {} });
              setShowSpellPanel(false);
            }}
            disabled={!rawText}
          >
            <TrashIcon width={15} height={15} />
            <span>Арилгах</span>
          </button>
        </footer>
      </section>
    </section>
  );
}

export function SettingsPanel() {
  const { settings, update, flowbarStatus, toggleFlowBar, triggerFlowBarRecording } = useSettings();
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);

  useEffect(() => {
    getAudioInputDevices().then(setAudioDevices);
  }, []);

  const Toggle = ({
    k,
    label,
    description,
  }: {
    k: keyof Settings;
    label: string;
    description?: string;
  }) => (
    <label className="toggle">
      <div>
        <span style={{ fontWeight: 500 }}>{label}</span>
        {description && (
          <small style={{ display: "block", color: "var(--muted)", fontSize: "11px", marginTop: "2px" }}>
            {description}
          </small>
        )}
      </div>
      <input
        type="checkbox"
        checked={Boolean(settings[k])}
        onChange={(e) => update(k, e.target.checked as never)}
      />
    </label>
  );

  return (
    <div className="settings-grid">
      {/* VoiceStudio AI & Voice Cloning */}
      <section className="settings">
        <h2>VoiceStudio & Дуу Хоолой Хувилах</h2>
        <p>
          Монгол, Англи, Япон хоолойгоор текст уншуулах болон өөрийн дуу хоолойг хувилан ашиглах студи.
        </p>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "14px 0 16px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981", display: "inline-block" }} />
          <span style={{ fontSize: "13px", fontWeight: 600 }}>
            12 Студи Хоолой + Voice Clone
          </span>
        </div>

        <Link href="/tts" className="btn-primary" style={{ fontSize: "13px", textDecoration: "none" }}>
          <VolumeIcon width={15} height={15} />
          <span>VoiceStudio руу орох →</span>
        </Link>
      </section>

      {/* FlowBar */}
      <section className="settings">
        <h2>VOICE FLOW (Хурдан ярьж бичих)</h2>
        <p>Дэлгэцийн доод хэсэгт байрлах хөвөгч VOICE FLOW товчоор хаанаас ч хурдан ярьж текст үүсгэнэ.</p>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "12px" }}>
          <button type="button" onClick={toggleFlowBar} className="btn-primary">
            <FlowBarIcon width={16} height={16} />
            <span>
              {flowbarStatus.visible ? "FlowBar нуух" : "FlowBar харуулах"}
            </span>
          </button>

          <button type="button" onClick={triggerFlowBarRecording} className="btn-secondary desktop-only">
            <MicIcon width={15} height={15} />
            <span>
              {flowbarStatus.status === "recording" ? "Бичлэг зогсоох" : "Шалгах"}
            </span>
          </button>
        </div>

        <div className="desktop-only" style={{ marginTop: "14px" }}>
          <Toggle
            k="autoInsertText"
            label="Шууд бичих (Auto-insert)"
            description="Компьютер дээр яриаг таньмагц идэвхтэй цонхонд шууд бичих."
          />
        </div>
      </section>

      {/* Desktop Helper for system-wide Ctrl+Alt */}
      <section className="settings desktop-only">
        <h2>💻 Chrome, Word, Excel дээр Ctrl+Alt-аар шууд бичих</h2>
        <p>
          Вэб хуудас өөр программ руу дур мэдэн бичих эрхгүй тул компьютер дээрээ 1 жижиг <b>VOICE Windows Helper</b> ажиллуулна.
          Ямар ч Python, нэмэлт програм суулгах шаардлагагүй.
        </p>
        <div style={{ background: "var(--subtle)", padding: "16px", borderRadius: "14px", fontSize: "13px", lineHeight: 1.7, border: "1px solid var(--border)" }}>
          <div style={{ marginBottom: "12px" }}>
            <a
              href="/api/download/helper"
              download="VOICE-Windows-Helper.bat"
              className="btn-primary"
              style={{ textDecoration: "none", display: "inline-flex", padding: "10px 20px" }}
            >
              ⬇️ 1 Товшилтоор Windows Helper татах (.bat)
            </a>
          </div>
          <div><b>1.</b> Дээрх товчоор татаж авсан <code>VOICE-Windows-Helper.bat</code> файлаа 1 удаа давхар товшиж ажиллуулна.</div>
          <div><b>2.</b> Chrome, Word, Excel, Facebook дээр курсороо байрлуулна.</div>
          <div><b>3.</b> <kbd>Ctrl</kbd> + <kbd>Alt</kbd> (эсвэл <kbd>F8</kbd>) дараад ярихад текст курсор дээр шууд бичигдэнэ!</div>
        </div>
      </section>

      {/* Recording Mode */}
      <section className="settings">
        <h2>Бичлэг хийх тохиргоо</h2>
        <p>Бичлэгийг хэрхэн эхлүүлэх болон дуусгах горим.</p>
        {recordingModes.map((x) => (
          <label className="radio" key={x.value}>
            <input
              type="radio"
              name="mode"
              checked={settings.recordingMode === x.value}
              onChange={() => update("recordingMode", x.value)}
            />
            <span>
              <b>{x.label}</b>
              <small>{x.description}</small>
            </span>
          </label>
        ))}
        <Toggle
          k="autoStop"
          label="Auto stop (Дуугүй болоход зогсох)"
          description="2.5 секунд чимээгүй болмогц бичлэгийг автоматаар зогсоож хөрвүүлнэ."
        />
      </section>

      {/* Microphone Selection */}
      <section className="settings">
        <h2>Microphone Device (Микрофон)</h2>
        <p>Ашиглах оролтын төхөөрөмжөө сонгоно.</p>
        <select
          value={settings.selectedAudioDevice}
          onChange={(e) => update("selectedAudioDevice", e.target.value)}
          style={{ width: "100%" }}
        >
          <option value="">Default Microphone (Анхдагч)</option>
          {audioDevices.map((d) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `Microphone (${d.deviceId.slice(0, 6)}...)`}
            </option>
          ))}
        </select>
      </section>

      {/* Keyboard Shortcut */}
      <section className="settings">
        <h2>Keyboard Shortcut (Апп доторх товч)</h2>
        <p>Апп дотор бичлэг эхлүүлэх, зогсоох товч.</p>
        <select
          value={settings.shortcut}
          onChange={(e) => update("shortcut", e.target.value as Shortcut)}
          style={{ width: "100%" }}
        >
          {shortcuts.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      </section>

      {/* Text Processing & Spellcheck */}
      <section className="settings">
        <h2>Зөв бичих дүрэм ба Сул үг</h2>
        <p>Текст цэгцлэх болон зөв бичгийн дүрэм шалгах тохиргоо.</p>
        <Toggle
          k="autoPunctuation"
          label="Auto punctuation"
          description="Цэг таслал, эхний үсгийг автоматаар томруулах."
        />
        <Toggle
          k="autoCorrection"
          label="Auto spellcheck"
          description="Бичвэр бэлэн болмогц зөв бичгийн алдааг шалгаж санал болгох."
        />
        <Toggle
          k="removeFillers"
          label="Remove fillers (Сул үг арилгах)"
          description="Монгол хэлний сул үгсийг (нөгөө, ер нь, аан, тэгээд...) хасах."
        />
        <div className="option-list" style={{ marginTop: "10px" }}>
          {modes.map((x) => (
            <label className="radio" key={x.value}>
              <input
                type="radio"
                name="processing"
                checked={settings.processingMode === x.value}
                onChange={() => update("processingMode", x.value)}
              />
              <span>
                <b>{x.label}</b>
                <small>{x.description}</small>
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* Appearance */}
      <section className="settings">
        <h2>Харагдац (Appearance)</h2>
        <p>Өнгөний горим сонгох.</p>
        <div className="themes">
          {themes.map((x) => (
            <button
              key={x.value}
              className={settings.theme === x.value ? "selected" : ""}
              onClick={() => update("theme", x.value)}
            >
              {x.label}
            </button>
          ))}
        </div>
      </section>

      {/* Privacy & Storage */}
      <section className="settings">
        <h2>Хадгалалт ба Цэвэрлэгээ</h2>
        <p>Түүх хадгалах болон цэвэрлэх үйлдлүүд.</p>
        <Toggle
          k="saveTranscripts"
          label="Save transcripts"
          description="Бүх хөрвүүлсэн текстийг History хэсэгт хадгалах."
        />
        <div style={{ marginTop: "16px" }}>
          <button
            className="btn-danger"
            onClick={() => {
              if (confirm("Бүх хадгалсан түүхийг устгахдаа итгэлтэй байна уу?")) {
                HistoryStore.clear();
                alert("Түүх амжилттай цэвэрлэгдлээ.");
              }
            }}
          >
            <TrashIcon width={15} height={15} />
            <span>Түүхийг бүрэн цэвэрлэх</span>
          </button>
        </div>
      </section>
    </div>
  );
}

export function FloatingWebFlowBar() {
  const { settings, setWorkspaceText, toggleFlowBar } = useSettings();
  const [state, setState] = useState<"idle" | "recording" | "processing" | "success" | "error">("idle");
  const [seconds, setSeconds] = useState(0);
  const [audioLevels, setAudioLevels] = useState<number[]>([4, 10, 16, 10, 4]);
  const [lastDictated, setLastDictated] = useState("");
  const [copiedBadge, setCopiedBadge] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const recorderRef = useRef<AudioRecorder | null>(null);
  const browserRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (state === "recording") {
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [state]);

  const stopAndTranscribe = useCallback(async () => {
    setState("processing");
    setErrMsg("");
    try {
      if (typeof navigator !== "undefined" && navigator.vibrate) {
        navigator.vibrate(50);
      }

      let browserTranscript = "";
      if (browserRecognizerRef.current) {
        browserTranscript = await browserRecognizerRef.current.stop();
        browserRecognizerRef.current = null;
      }

      let wavBlob: Blob | null = null;
      if (recorderRef.current) {
        wavBlob = await recorderRef.current.stop();
        recorderRef.current = null;
      }

      let serverTranscript = "";
      if (wavBlob) {
        try {
          const formData = new FormData();
          formData.append("audio", wavBlob, "flow_speech.wav");
          formData.append("language", settings.language);

          const res = await fetch("/api/chimege/transcribe", {
            method: "POST",
            body: formData,
          });

          const data = await res.json().catch(() => ({}));
          if (data.text && data.text.trim()) {
            serverTranscript = data.text.trim();
          }
        } catch {}
      }

      const rawText = (serverTranscript || browserTranscript || "").trim();

      if (!rawText) {
        setErrMsg("Яриа сонсогдсонгүй");
        setState("error");
        setTimeout(() => setState("idle"), 2400);
        return;
      }

      const processed = processTranscriptText(rawText, {
        mode: settings.processingMode,
        autoPunctuation: settings.autoPunctuation,
        removeFillers: settings.removeFillers,
        language: settings.language,
      });

      setLastDictated(processed);
      setWorkspaceText(processed);
      setState("success");
      setCopiedBadge(true);

      navigator.clipboard?.writeText(processed).catch(() => {});
      HistoryStore.add({
        text: processed,
        rawText,
        durationSeconds: Math.max(1, seconds),
        language: settings.language,
        engine: "VOICE FLOW",
        wordCount: processed.split(/\s+/).length,
        charCount: processed.length,
      });

      if (typeof navigator !== "undefined" && navigator.vibrate) {
        navigator.vibrate([40, 60, 40]);
      }

      setTimeout(() => {
        setState("idle");
        setCopiedBadge(false);
      }, 3500);
    } catch (e) {
      console.warn("Web FlowBar error:", e);
      setErrMsg("Дахин оролдоно уу");
      setState("error");
      setTimeout(() => setState("idle"), 2400);
    }
  }, [settings, seconds, setWorkspaceText]);

  const startRecording = useCallback(async () => {
    setSeconds(0);
    setErrMsg("");
    try {
      if (typeof navigator !== "undefined" && navigator.vibrate) {
        navigator.vibrate(40);
      }

      const recorder = new AudioRecorder({
        deviceId: settings.selectedAudioDevice,
        autoStop: settings.autoStop,
        onAudioLevel: (lvl) => {
          setAudioLevels((prev) => [...prev.slice(1), Math.max(4, Math.round(lvl * 24))]);
        },
        onSilenceDetected: () => {
          stopAndTranscribe();
        },
      });
      recorderRef.current = recorder;
      await recorder.start();

      const isMobile =
        typeof navigator !== "undefined" &&
        /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");

      if (!isMobile && isBrowserSpeechSupported()) {
        try {
          const recognizer = new BrowserSpeechRecognizer({
            language: settings.language,
            onError: () => {},
          });
          browserRecognizerRef.current = recognizer;
          recognizer.start();
        } catch {}
      }

      setState("recording");
    } catch (err: unknown) {
      console.warn("Web FlowBar start error:", err);
      const isPerm =
        err instanceof Error &&
        (err.message.includes("зөвшөөрөл") || err.name === "NotAllowedError");
      setErrMsg(isPerm ? "Микрофон зөвшөөрнө үү (Allow)" : "Микрофон алдаа");
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  }, [settings, stopAndTranscribe]);

  const toggle = () => {
    if (state === "idle" || state === "success" || state === "error") {
      startRecording();
    } else if (state === "recording") {
      stopAndTranscribe();
    }
  };

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  const isRecording = state === "recording";

  return (
    <div
      className={`floating-web-flowbar ${isRecording ? "recording" : ""}`}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest(".flowbar-dismiss, .flowbar-share")) return;
        toggle();
      }}
      title={isRecording ? "Дарж бичлэгийг зогсоох" : "Дарж шууд ярьж бичих (VOICE FLOW)"}
    >
      <button
        type="button"
        className="flowbar-btn"
        aria-label="FlowBar Dictate"
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          border: "none",
          background: isRecording ? "#ef4444" : "linear-gradient(135deg, #6366f1, #8b5cf6)",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          boxShadow: isRecording ? "0 0 14px #ef4444" : "0 2px 8px rgba(99, 102, 241, 0.4)",
          transition: "all 0.2s ease",
          flexShrink: 0,
        }}
      >
        <MicIcon width={16} height={16} />
      </button>

      {state === "recording" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#ef4444", fontSize: "12px", fontWeight: 700, fontFamily: "monospace" }}>
            {mm}:{ss}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "2px", height: "16px" }}>
            {audioLevels.map((lvl, i) => (
              <span
                key={i}
                style={{
                  width: "3px",
                  height: `${Math.max(4, lvl)}px`,
                  background: "#ef4444",
                  borderRadius: "2px",
                  transition: "height 0.1s ease",
                }}
              />
            ))}
          </div>
          <span style={{ fontSize: "12px", color: "var(--text)", fontWeight: 500 }}>
            Сонсож байна...
          </span>
        </div>
      ) : state === "processing" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f59e0b" }} />
          <span style={{ fontSize: "12px", color: "var(--text)", fontWeight: 500 }}>
            Хөрвүүлж байна...
          </span>
        </div>
      ) : state === "success" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <CheckIcon width={14} height={14} style={{ color: "#10b981" }} />
          <span style={{ fontSize: "12px", color: "#10b981", fontWeight: 600 }}>
            {copiedBadge ? "Хуулагдлаа!" : "Амжилттай!"}
          </span>
          <span style={{ fontSize: "11px", color: "var(--muted)", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {lastDictated}
          </span>
        </div>
      ) : state === "error" ? (
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ color: "#ef4444", fontSize: "12px" }}>{errMsg || "Дахин оролдоно уу"}</span>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <b style={{ fontSize: "12px", color: "var(--text)", letterSpacing: "0.5px" }}>VOICE FLOW</b>
          <span
            style={{
              fontSize: "10px",
              padding: "2px 6px",
              background: "rgba(99, 102, 241, 0.18)",
              color: "#a5b4fc",
              borderRadius: "6px",
              fontWeight: 700,
            }}
          >
            {settings.language.toUpperCase()}
          </span>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
            Дарж ярих
          </span>
        </div>
      )}

      {/* Share button on mobile when text is ready */}
      {lastDictated && state !== "recording" && typeof navigator !== "undefined" && typeof navigator.share === "function" && (
        <button
          type="button"
          className="flowbar-share"
          onClick={(e) => {
            e.stopPropagation();
            navigator.share({ title: "VOICE Текст", text: lastDictated }).catch(() => {});
          }}
          style={{
            background: "none",
            border: "none",
            color: "var(--muted)",
            cursor: "pointer",
            padding: "4px",
            display: "flex",
            alignItems: "center",
          }}
          title="Facebook / Messenger / Утас руу хуваалцах"
        >
          <ShareIcon width={13} height={13} />
        </button>
      )}

      {/* Dismiss / Hide button */}
      <button
        type="button"
        className="flowbar-dismiss"
        onClick={(e) => {
          e.stopPropagation();
          toggleFlowBar();
        }}
        style={{
          background: "none",
          border: "none",
          color: "var(--muted)",
          cursor: "pointer",
          padding: "2px 6px",
          fontSize: "12px",
          lineHeight: 1,
        }}
        title="FlowBar-ийг нуух (Дээд цэснээс буцааж гаргаж болно)"
      >
        ✕
      </button>
    </div>
  );
}
