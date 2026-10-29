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
  sttEngines,
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
  resetFlowBarPosition: () => Promise<void>;
  quitVoiceApp: () => Promise<void>;
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
  const [flowbarStatus, setFlowbarStatus] = useState({
    status: "idle",
    visible: true,
    last_text: "",
    last_timestamp: 0,
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

  // Poll Native Windows FlowBar status (so Ctrl+Alt dictations in Word/Facebook also sync into Workspace & History)
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/flowbar");
        if (!res.ok) return;
        const data = await res.json();
        if (data && typeof data.status === "string") {
          setFlowbarStatus({
            status: data.status,
            visible: Boolean(data.visible),
            last_text: data.last_text || "",
            last_timestamp: data.last_timestamp || 0,
          });

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
    try {
      const res = await fetch("/api/flowbar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "toggle_visibility" }),
      });
      if (res.ok) {
        const data = await res.json();
        setFlowbarStatus((prev) => ({
          ...prev,
          visible: Boolean(data.visible),
          status: data.status || prev.status,
        }));
      }
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

  const resetFlowBarPosition = useCallback(async () => {
    try {
      const res = await fetch("/api/flowbar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset_position" }),
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
  }, []);

  const quitVoiceApp = useCallback(async () => {
    if (confirm("VOICE системийг бүрэн хаах уу?")) {
      try {
        await fetch("/api/quit", { method: "POST" });
        window.close();
      } catch {}
    }
  }, []);

  // Sync settings with Python server
  useEffect(() => {
    fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hotkey: settings.desktopHotkey || "f8",
        stt_engine: settings.sttEngine === "auto" ? "google" : settings.sttEngine,
        whisper_model: settings.whisperModel || "small",
        chimege_token: settings.chimegeToken || "",
        language: settings.language || "auto",
        sound_cues: Boolean(settings.soundCues),
        number_normalization: Boolean(settings.numberNormalization),
        voice_actions: Boolean(settings.voiceActions),
        filler_word_cleaner: Boolean(settings.fillerWordCleaner),
        noise_gate: Boolean(settings.noiseGate),
        auto_insert_text: Boolean(settings.autoInsertText),
        start_with_windows: Boolean(settings.startWithWindows),
        custom_snippets: Boolean(settings.customSnippets),
        tech_terms_normalization: Boolean(settings.techTermsNormalization),
        snippets: settings.snippets || {},
      }),
    }).catch(() => {});
  }, [
    settings.desktopHotkey,
    settings.sttEngine,
    settings.whisperModel,
    settings.chimegeToken,
    settings.language,
    settings.soundCues,
    settings.numberNormalization,
    settings.voiceActions,
    settings.fillerWordCleaner,
    settings.noiseGate,
    settings.autoInsertText,
    settings.startWithWindows,
    settings.customSnippets,
    settings.techTermsNormalization,
    settings.snippets,
  ]);

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
      resetFlowBarPosition,
      quitVoiceApp,
    }),
    [settings, workspaceText, flowbarStatus, toggleFlowBar, triggerFlowBarRecording, resetFlowBarPosition, quitVoiceApp]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

const navItems = [
  { href: "/dashboard", label: "Шинэ яриа", icon: PlusIcon },
  { href: "/tts", label: "VoiceStudio", icon: VolumeIcon },
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
  const { settings, update, flowbarStatus, toggleFlowBar, resetFlowBarPosition } = useSettings();

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

        <div className="side-note" style={{ flexDirection: "column", alignItems: "flex-start", gap: "6px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="status-dot" />
            <b style={{ color: "var(--text)", fontSize: "12px" }}>VoiceStudio AI Бэлэн</b>
          </div>
          <span style={{ fontSize: "11px", lineHeight: 1.4 }}>
            Word / Facebook дээр <kbd>Ctrl+Alt</kbd> дарж шууд ярьж бичнэ.
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
                ? "🔴 Систем дээр яриа бичиж байна..."
                : "Шууд бичих товчлуур:"}
            </span>
            <kbd>
              {
                settings.desktopHotkey === "f8" ? "F8" :
                settings.desktopHotkey === "ctrl_shift" ? "Ctrl + Shift" :
                settings.desktopHotkey === "alt_shift" ? "Alt + Shift" :
                settings.desktopHotkey === "ctrl_space" ? "Ctrl + Space" :
                settings.desktopHotkey === "f9" ? "F9" :
                settings.desktopHotkey === "f10" ? "F10" :
                settings.desktopHotkey === "f2" ? "F2" :
                settings.desktopHotkey === "f4" ? "F4" :
                "Ctrl + Alt (буюу F8)"
              }
            </kbd>
          </div>

          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button
              type="button"
              onClick={toggleFlowBar}
              className="btn-secondary"
              style={{
                fontSize: "12px",
                padding: "7px 14px",
                borderColor: flowbarStatus.visible ? "rgba(16, 185, 129, 0.4)" : undefined,
                background: flowbarStatus.visible ? "rgba(16, 185, 129, 0.08)" : undefined,
              }}
              title="Дэлгэцийн баруун доод буланд хөвөх жижиг VOICE Капсул цонхыг харуулах / нуух"
            >
              <FlowBarIcon width={16} height={16} />
              <span>{flowbarStatus.visible ? "VOICE Капсул: Идэвхтэй" : "VOICE Капсул: Нуусан"}</span>
            </button>

            <button
              type="button"
              onClick={resetFlowBarPosition}
              className="btn-secondary"
              style={{ fontSize: "12px", padding: "7px 12px" }}
              title="VOICE Капсул байрлалыг дэлгэцийн баруун доод буланд шилжүүлж сэргээх"
            >
              <span>📍 Капсул байрлал</span>
            </button>

            <LanguageSelect
              value={settings.language}
              onChange={(v) => update("language", v)}
            />
          </div>
        </header>

        {children}
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
      if (isBrowserSpeechSupported() && settings.sttEngine !== "chimege") {
        const recognizer = new BrowserSpeechRecognizer({
          language: settings.language,
          onInterim: (previewText) => {
            setLivePreview(previewText);
          },
          onError: (err) => {
            console.warn("Browser Speech warning:", err);
          },
        });
        browserRecognizerRef.current = recognizer;
        recognizer.start();
      }

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

      setState("recording");
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Микрофон ажиллуулахад алдаа гарлаа. Зөвшөөрөл шалгана уу.";
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

    try {
      let preferredVoice = "mn-MN-YesuiNeural";
      try {
        const savedClones = localStorage.getItem("voice_clones");
        if (savedClones) {
          const parsed = JSON.parse(savedClones);
          if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].id) {
            preferredVoice = parsed[0].id;
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
        }),
      });

      if (!res.ok) {
        throw new Error("TTS дуу үүсгэхэд алдаа гарлаа.");
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
          <small>VOICE INTELLIGENCE STUDIO — Ухаалаг Дуу Хоолойн Орчин</small>
          <h1>Ярихыг урлаг болго.</h1>
          <p>
            Монгол болон олон улсын яриа таних, зөв бичих дүрэм, дуу хоолой хувилах (VoiceStudio) болон Word/Facebook/Chrome дээр <kbd>F8</kbd> эсвэл <kbd>Ctrl+Alt</kbd> дарж шууд бичих систем.
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
              : "Дуу хоолойг бодит цагт бичиж байна..."
            : "✨ Word, Facebook, Chrome дээр курсороо байрлуулаад Ctrl+Alt дарж ярихад текст шууд бичигдэнэ"}
        </p>
      </div>

      {state === "error" && errorMessage && (
        <div className="error" role="alert">
          <b>Мэдээлэл:</b> {errorMessage}
        </div>
      )}

      {/* Transcript Section */}
      <section className="transcript">
        <header>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <SparklesIcon width={16} height={16} style={{ color: "var(--accent)" }} />
            <b>Таны текст</b>
          </div>
          <span>
            {stats.wordCount} үг • {stats.charCount} тэмдэгт
          </span>
        </header>

        <div className="transcript-body">
          {state === "processing" ? (
            <div className="empty">
              <b>Хиймэл оюун яриаг боловсруулж байна...</b>
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
              <b>Таны текстийн үр дүн энд бууна.</b>
              <small>
                Микрофон дээр дарж ярих эсвэл Facebook / Word дээр очоод <kbd>Ctrl+Alt</kbd> дарж шууд ярьж бичээрэй.
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
            onClick={() => {
              if (!rawText) return;
              fetch("/api/flowbar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ insertText: rawText }),
              }).catch(() => {});
            }}
            disabled={!rawText}
            title="Сүүлд ажиллаж байсан Word, Facebook, Chrome, Antigravity цонх руу шууд бичих"
          >
            <FlowBarIcon width={15} height={15} />
            <span>Цонх руу шууд бичих</span>
          </button>
          <button
            className="btn-secondary"
            onClick={() => playTextToSpeech(rawText)}
            disabled={!rawText || ttsLoading}
          >
            <VolumeIcon width={15} height={15} />
            <span>{ttsLoading ? "Уншиж байна..." : "Сонсох (VoiceStudio)"}</span>
          </button>
          <button
            className="btn-secondary"
            onClick={handleRunSpellCheck}
            disabled={!rawText || spellChecking}
          >
            <SparklesIcon width={15} height={15} />
            <span>{spellChecking ? "Шалгаж байна..." : "Зөв бичиг шалгах"}</span>
          </button>
          <button className="btn-secondary" onClick={() => setEditing(!editing)} disabled={!rawText}>
            <EditIcon width={15} height={15} />
            <span>{editing ? "Хадгалах" : "Засах"}</span>
          </button>
          <button className="btn-secondary" onClick={copyToClipboard} disabled={!rawText}>
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

      <div className="meta">
        <span>
          Апп доторх товч <kbd>{settings.shortcut}</kbd>
        </span>
        <span>
          Word / Facebook дээр шууд бичих <kbd>Ctrl+Alt</kbd>
        </span>
        <span>
          Горим <b>{settings.recordingMode}</b>
        </span>
        <span>
          Студи <b>VoiceStudio AI</b>
        </span>
      </div>
    </section>
  );
}

export function SettingsPanel() {
  const { settings, update, flowbarStatus, toggleFlowBar, triggerFlowBarRecording, resetFlowBarPosition, quitVoiceApp } = useSettings();
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [newTrigger, setNewTrigger] = useState("");
  const [newReplacement, setNewReplacement] = useState("");
  const [isTestingMic, setIsTestingMic] = useState(false);
  const [micVolume, setMicVolume] = useState(0);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    getAudioInputDevices().then(setAudioDevices);
  }, []);

  const stopMicTest = useCallback(() => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setIsTestingMic(false);
    setMicVolume(0);
  }, []);

  const startMicTest = async () => {
    if (isTestingMic) {
      stopMicTest();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: settings.selectedAudioDevice ? { deviceId: { exact: settings.selectedAudioDevice } } : true,
      });
      micStreamRef.current = stream;
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      setIsTestingMic(true);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const checkVolume = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        const vol = Math.min(100, Math.round((avg / 60) * 100));
        setMicVolume(vol);
        animFrameRef.current = requestAnimationFrame(checkVolume);
      };
      checkVolume();
    } catch {
      alert("Микрофонд холбогдож чадсангүй. Төхөөрөмж зөв сонгогдсон эсэх эсвэл зөвшөөрлийг шалгана уу.");
      stopMicTest();
    }
  };

  useEffect(() => {
    return () => {
      stopMicTest();
    };
  }, [stopMicTest]);

  const handleAddSnippet = () => {
    const trig = newTrigger.trim().toLowerCase();
    const rep = newReplacement.trim();
    if (!trig || !rep) return;
    const current = { ...(settings.snippets || {}) };
    current[trig] = rep;
    update("snippets", current);
    setNewTrigger("");
    setNewReplacement("");
  };

  const handleRemoveSnippet = (trigger: string) => {
    const current = { ...(settings.snippets || {}) };
    delete current[trigger];
    update("snippets", current);
  };

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
      {/* Desktop Mode / VOICE Capsule */}
      <section className="settings">
        <h2>VOICE Капсул & Шууд бичих (Desktop Flow)</h2>
        <p>Word, Chrome, Facebook, Telegram гэх мэт дурын цонхон дээр шууд ярьж бичих тохиргоо.</p>

        <div style={{ background: "var(--subtle)", padding: "14px", borderRadius: "14px", fontSize: "12px", lineHeight: 1.65, marginBottom: "14px", border: "1px solid var(--border)" }}>
          <div><b>1. Курсороо байрлуулах:</b> Бичих гэж буй програмынхаа (Word, Chrome, Telegram) текст бичих нүдэн дээр дарна.</div>
          <div style={{ marginTop: "4px" }}>
            <b>2. Ярьж эхлэх:</b> Гар дээрээ <kbd>F8</kbd> эсвэл <kbd>Ctrl</kbd> + <kbd>Alt</kbd> дарна (эсвэл баруун доод хөвөх <b>VOICE Капсул</b> дээр дарна).
          </div>
          <div style={{ marginTop: "4px" }}>
            <b>3. Шууд бичигдэх:</b> Ярьж дуусмагц таны курсор байрласан цонхонд текст автоматаар шууд бичигдэнэ!
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "14px" }}>
          <button type="button" onClick={toggleFlowBar} className="btn-primary">
            <FlowBarIcon width={16} height={16} />
            <span>
              {flowbarStatus.visible ? "Хөвөгч Капсул нуух" : "Хөвөгч Капсул харуулах"}
            </span>
          </button>

          <button type="button" onClick={triggerFlowBarRecording} className="btn-secondary">
            <MicIcon width={15} height={15} />
            <span>
              {flowbarStatus.status === "recording" ? "Бичлэг зогсоох" : "Шууд ярьж шалгах"}
            </span>
          </button>

          <button
            type="button"
            onClick={resetFlowBarPosition}
            className="btn-secondary"
            style={{ fontSize: "12px", padding: "8px 14px" }}
          >
            <span>📍 Капсул байрлал сэргээх</span>
          </button>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
            Шууд ярих үндсэн товчлуур (Shortcut):
          </label>
          <select
            value={settings.desktopHotkey || "f8"}
            onChange={(e) => update("desktopHotkey", e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "10px",
              background: "var(--card)",
              color: "var(--foreground)",
              border: "1px solid var(--border)",
              fontSize: "13px",
            }}
          >
            <option value="f8">F8 (Санал болгох — Chrome Omnibox, Word, Notepad-д 100% найдвартай)</option>
            <option value="ctrl_alt">Ctrl + Alt (Хосолсон товчлуур)</option>
            <option value="ctrl_shift">Ctrl + Shift</option>
            <option value="alt_shift">Alt + Shift</option>
            <option value="ctrl_space">Ctrl + Space</option>
            <option value="f9">F9</option>
            <option value="f10">F10</option>
            <option value="f2">F2</option>
            <option value="f4">F4</option>
          </select>
          <small style={{ display: "block", color: "var(--muted)", fontSize: "11px", marginTop: "4px" }}>
            Санамж: F8 болон Ctrl+Alt товчлуурууд аль аль нь байнга идэвхтэй ажиллана.
          </small>
        </div>

        <div style={{ marginTop: "14px" }}>
          <Toggle
            k="autoInsertText"
            label="Auto-insert text (Шууд бичих)"
            description="Яриаг таньмагц идэвхтэй цонхонд автоматаар буулгах."
          />
          <Toggle
            k="soundCues"
            label="Дуут дохио (Audio Feedback)"
            description="Бичлэг эхлэх болон дуусахад тааламжтай дуут дохио өгөх."
          />
          <Toggle
            k="startWithWindows"
            label="Windows асахад автоматаар эхлэх"
            description="Компьютер асмагц VOICE Капсул цаанаа бэлэн ажиллаж эхэлнэ."
          />
        </div>
      </section>

      {/* Smart Writing & Voice Actions */}
      <section className="settings">
        <h2>Ухаалаг Текст & Дуут Командууд</h2>
        <p>Яриаг цэгцтэй найруулга бүхий мэргэжлийн бичвэр болгох ухаалаг шүүлтүүрүүд.</p>

        <Toggle
          k="voiceActions"
          label="Дуут тушаалууд (Voice-to-Action)"
          description="'Шинэ мөр', 'Цэг', 'Таслал', 'Хашилт', 'Асуултын тэмдэг' гэж хэлэхэд автоматаар тэмдэгт болгон буулгах."
        />
        <Toggle
          k="fillerWordCleaner"
          label="Сул үг автоматаар цэвэрлэх"
          description="Яриан дахь 'нөгөө', 'аан', 'тиймээ', 'ер нь бол', 'юу л даа' гэх мэт илүүц сул үгсийг арилгах."
        />
        <Toggle
          k="numberNormalization"
          label="Монгол тоог автоматаар цифр болгох"
          description="'хоёр мянга хорин зургаа' -> '2026', 'ерэн таван хувь' -> '95%' гэж шууд хөрвүүлэх."
        />
        <Toggle
          k="autoPunctuation"
          label="Өгүүлбэр, цэг тэмдэг автоматаар янзлах"
          description="Эхний үсгийг томруулж, өгүүлбэрийн төгсгөлд цэг/асуултын тэмдэг тавих."
        />
        <Toggle
          k="noiseGate"
          label="Арын чимээ шүүгч (Noise Gate)"
          description="Амьсгаа болон өрөөний арын сул шуугианыг таслах шүүлтүүр."
        />
        <Toggle
          k="autoCorrection"
          label="Зөв бичгийн дүрэм (Spellcheck)"
          description="Бичвэр бэлэн болмогц зөв бичгийн алдааг шалгаж санал болгох."
        />
        <Toggle
          k="techTermsNormalization"
          label="Технологийн нэрсийг латинаар үлдээх"
          description="'фэйсбүүк' ➔ 'Facebook', 'зуум' ➔ 'Zoom', 'пидиэф' ➔ 'PDF', 'гитхаб' ➔ 'GitHub' гэх мэт түгээмэл нэрсийг зөв латинаар буулгах."
        />
      </section>

      {/* Custom Voice Snippets */}
      <section className="settings">
        <h2>Дуут Товчлолууд & Хурдан Текст (Voice Snippets)</h2>
        <p>
          Түлхүүр үг хэлэхэд автоматаар таны тохируулсан урт бичвэр, имэйл, дансны дугаар болгон хувиргах ухаалаг товчлол.
        </p>

        <Toggle
          k="customSnippets"
          label="Дуут товчлолууд ашиглах"
          description="Яриа дунд тохируулсан үг сонсогдвол шууд бүтэн бичвэрээр нь орлуулна."
        />

        <div style={{ marginTop: "14px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "8px" }}>
            Бүртгэлтэй дуут товчлолууд ({Object.keys(settings.snippets || {}).length}):
          </label>

          {Object.keys(settings.snippets || {}).length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--muted)", padding: "10px", background: "var(--subtle)", borderRadius: "8px", border: "1px dashed var(--border)" }}>
              Одоогоор бүртгэлтэй товчлол алга байна. Доорх талбараар шинээр нэмнэ үү.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {Object.entries(settings.snippets || {}).map(([trigger, replacement]) => (
                <div
                  key={trigger}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "var(--subtle)",
                    padding: "8px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--border)",
                    fontSize: "12px",
                  }}
                >
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginRight: "10px" }}>
                    <span style={{ color: "var(--accent)", fontWeight: 600 }}>&ldquo;{trigger}&rdquo;</span>
                    <span style={{ margin: "0 8px", color: "var(--muted)" }}>➔</span>
                    <span style={{ fontFamily: "monospace", color: "var(--foreground)" }}>{replacement}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveSnippet(trigger)}
                    className="btn-danger"
                    style={{ padding: "4px 8px", fontSize: "11px", flexShrink: 0 }}
                    title="Устгах"
                  >
                    <TrashIcon width={12} height={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "flex", gap: "8px", marginTop: "12px", flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Дуудах үг (жнь: миний данс)"
              value={newTrigger}
              onChange={(e) => setNewTrigger(e.target.value)}
              style={{
                flex: "1 1 140px",
                padding: "8px 10px",
                borderRadius: "8px",
                border: "1px solid var(--border)",
                background: "var(--card)",
                fontSize: "12px",
                color: "var(--foreground)",
              }}
            />
            <input
              type="text"
              placeholder="Орлох бичвэр (жнь: Хаан банк: 5000xxxxxx)"
              value={newReplacement}
              onChange={(e) => setNewReplacement(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddSnippet();
                }
              }}
              style={{
                flex: "2 1 200px",
                padding: "8px 10px",
                borderRadius: "8px",
                border: "1px solid var(--border)",
                background: "var(--card)",
                fontSize: "12px",
                color: "var(--foreground)",
              }}
            />
            <button
              type="button"
              onClick={handleAddSnippet}
              className="btn-primary"
              style={{ fontSize: "12px", padding: "8px 16px" }}
            >
              + Нэмэх
            </button>
          </div>
          <small style={{ display: "block", color: "var(--muted)", fontSize: "11px", marginTop: "6px" }}>
            Жишээ: &ldquo;миний имэйл&rdquo; гэж хэлэхэд автоматаар таны и-мэйл хаяг бичигдэнэ.
          </small>
        </div>
      </section>

      {/* STT Engine & Microphone */}
      <section className="settings">
        <h2>Яриа таних хөдөлгүүр & Микрофон</h2>
        <p>Ашиглах микрофон төхөөрөмж болон яриа таних хиймэл оюуны загвар.</p>

        <div style={{ marginBottom: "14px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
            Микрофон төхөөрөмж:
          </label>
          <select
            value={settings.selectedAudioDevice}
            onChange={(e) => update("selectedAudioDevice", e.target.value)}
            style={{ width: "100%", padding: "8px 10px", borderRadius: "8px", background: "var(--card)", color: "var(--foreground)", border: "1px solid var(--border)", fontSize: "13px" }}
          >
            <option value="">Default Microphone (Анхдагч систем)</option>
            {audioDevices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Microphone (${d.deviceId.slice(0, 6)}...)`}
              </option>
            ))}
          </select>

          {/* Live Mic Volume VU-Meter */}
          <div style={{ marginTop: "10px", padding: "10px 12px", background: "var(--subtle)", borderRadius: "10px", border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <span style={{ fontSize: "12px", fontWeight: 600 }}>Дууны түвшин (Live Mic Meter):</span>
              <button
                type="button"
                onClick={startMicTest}
                className={isTestingMic ? "btn-danger" : "btn-secondary"}
                style={{ fontSize: "11px", padding: "4px 10px" }}
              >
                {isTestingMic ? "⏹️ Шалгалтыг зогсоох" : "🎤 Микрофон шалгах"}
              </button>
            </div>
            <div style={{ width: "100%", height: "10px", background: "var(--card)", borderRadius: "5px", overflow: "hidden", border: "1px solid var(--border)" }}>
              <div
                style={{
                  width: `${micVolume}%`,
                  height: "100%",
                  background: micVolume > 75 ? "#ef4444" : micVolume > 35 ? "#10b981" : "#3b82f6",
                  transition: "width 60ms linear",
                  borderRadius: "5px",
                }}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
              <span>{isTestingMic ? (micVolume > 8 ? "🟢 Дуу мэдрэгдэж байна" : "⚪ Чимээгүй...") : "Шалгах товч дээр дарна уу"}</span>
              <span>{micVolume}%</span>
            </div>
          </div>
        </div>

        <div className="option-list">
          {sttEngines.map((x) => (
            <label className="radio" key={x.value}>
              <input
                type="radio"
                name="stt_engine"
                checked={settings.sttEngine === x.value}
                onChange={() => update("sttEngine", x.value)}
              />
              <span>
                <b>{x.label}</b>
                <small>{x.description}</small>
              </span>
            </label>
          ))}
        </div>

        {settings.sttEngine === "whisper" && (
          <div style={{ marginTop: "14px", padding: "12px", background: "var(--subtle)", borderRadius: "10px", border: "1px solid var(--border)" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
              Faster-Whisper AI загварын хэмжээ:
            </label>
            <select
              value={settings.whisperModel || "small"}
              onChange={(e) => update("whisperModel", e.target.value)}
              style={{ width: "100%", padding: "7px 10px", borderRadius: "8px", background: "var(--card)", color: "var(--foreground)", border: "1px solid var(--border)" }}
            >
              <option value="tiny">Tiny (Хамгийн хурдан, 39M)</option>
              <option value="base">Base (Хөнгөн, 74M)</option>
              <option value="small">Small (Тэнцвэртэй - Санал болгох, 244M)</option>
              <option value="medium">Medium (Өндөр чанар, 769M)</option>
              <option value="large-v3">Large-v3 (Хамгийн нарийн, 1550M)</option>
            </select>
            <small style={{ display: "block", color: "var(--muted)", fontSize: "11px", marginTop: "4px" }}>
              Интернетгүй үед оффлайн ажиллана.
            </small>
          </div>
        )}

        {settings.sttEngine === "chimege" && (
          <div style={{ marginTop: "14px", padding: "12px", background: "var(--subtle)", borderRadius: "10px", border: "1px solid var(--border)" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
              Chimege API Token:
            </label>
            <input
              type="password"
              placeholder="Chimege API токен оруулна уу"
              value={settings.chimegeToken || ""}
              onChange={(e) => update("chimegeToken", e.target.value)}
              style={{ width: "100%", padding: "7px 10px", borderRadius: "8px", background: "var(--card)", color: "var(--foreground)", border: "1px solid var(--border)" }}
            />
          </div>
        )}
      </section>

      {/* VoiceStudio AI & Voice Cloning */}
      <section className="settings">
        <h2>VoiceStudio AI & Дуу Хоолой Хувилах</h2>
        <p>
          Хүний дууны өнгө төрх, формант (F₁–F₄), тембрийг шинжлэн хувилах болон Broadcast DSP эффектүүдээр уншуулах студи.
        </p>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "14px 0 16px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981", display: "inline-block" }} />
          <span style={{ fontSize: "13px", fontWeight: 600 }}>
            Voice Cloning + Broadcast DSP • 100% Үнэгүй, Хязгааргүй
          </span>
        </div>

        <Link href="/tts" className="btn-primary" style={{ fontSize: "13px", textDecoration: "none" }}>
          <VolumeIcon width={15} height={15} />
          <span>VoiceStudio руу орох →</span>
        </Link>
      </section>

      {/* Appearance & System */}
      <section className="settings">
        <h2>Харагдац & Систем</h2>
        <p>Өнгөний горим болон програмын хадгалалт, гарах үйлдлүүд.</p>
        <div className="themes" style={{ marginBottom: "14px" }}>
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

        <Toggle
          k="saveTranscripts"
          label="Save transcripts"
          description="Бүх хөрвүүлсэн текстийг Түүх (History) хэсэгт хадгалах."
        />

        <div style={{ display: "flex", gap: "10px", marginTop: "16px", flexWrap: "wrap" }}>
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

          <button
            type="button"
            onClick={quitVoiceApp}
            className="btn-secondary"
            style={{ fontSize: "12px", padding: "8px 14px", color: "#ef4444", borderColor: "rgba(239, 68, 68, 0.4)" }}
          >
            <span>🛑 VOICE-оос бүрэн гарах</span>
          </button>
        </div>
      </section>
    </div>
  );
}
