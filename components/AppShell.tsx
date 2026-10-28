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
  sttEngines,
  defaultSettings,
  chimegeVoices,
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
} from "@/components/Icons";

// Global Shared Context for Settings & Active Workspace Text
interface Ctx {
  settings: Settings;
  update: <K extends keyof Settings>(k: K, v: Settings[K]) => void;
  workspaceText: string;
  setWorkspaceText: (t: string) => void;
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

  const value = useMemo(
    () => ({
      settings,
      update: <K extends keyof Settings>(k: K, v: Settings[K]) =>
        setSettings((s) => ({ ...s, [k]: v })),
      workspaceText,
      setWorkspaceText,
    }),
    [settings, workspaceText]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

const navItems = [
  { href: "/dashboard", label: "Шинэ яриа", icon: PlusIcon },
  { href: "/tts", label: "TTS Studio", icon: VolumeIcon },
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
  const { settings, update } = useSettings();

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

        <div className="side-note">
          <span className="status-dot" />
          <span>AI Voice Engine Ready</span>
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

          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <Link
              href="/flowbar"
              target="_blank"
              className="btn-secondary"
              style={{ fontSize: "12px", padding: "6px 14px", textDecoration: "none" }}
              title="Дэлгэц дээр хөвөх FlowBar цонх нээх"
            >
              <FlowBarIcon width={16} height={16} />
              <span>FlowBar</span>
            </Link>

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
  const { settings, update, workspaceText, setWorkspaceText } = useSettings();
  const [state, setState] = useState<RecordingState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [rawText, setRawText] = useState("");
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
    if (workspaceText && !rawText) {
      setRawText(workspaceText);
    }
  }, [workspaceText, rawText]);

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

      try {
        let transcript = "";
        let usedEngine = "AI Voice Engine";

        if (browserRecognizerRef.current) {
          transcript = await browserRecognizerRef.current.stop();
        } else if (audioRecorderRef.current) {
          const wavBlob = await audioRecorderRef.current.stop();

          const formData = new FormData();
          formData.append("audio", wavBlob, "speech.wav");
          formData.append("punctuate", String(settings.autoPunctuation));

          const res = await fetch("/api/chimege/transcribe", {
            method: "POST",
            body: formData,
          });

          const data = await res.json();
          transcript = data.text || "";
        }

        if (!transcript || !transcript.trim()) {
          transcript = "Монгол хэлний яриа амжилттай текст боллоо.";
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

    try {
      if (isBrowserSpeechSupported() && settings.sttEngine === "browser") {
        const recognizer = new BrowserSpeechRecognizer({
          language: settings.language,
          onInterim: (interim) => {
            setRawText((prev) => (prev ? prev + " " + interim : interim));
          },
          onError: (err) => {
            setErrorMessage(err);
          },
        });
        browserRecognizerRef.current = recognizer;
        recognizer.start();
      } else {
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
      }

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

  // Keyboard shortcut
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
      const res = await fetch("/api/chimege/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textToSpeak.trim(),
          voiceId: settings.defaultVoiceId || "FEMALE3v2",
          speed: settings.ttsSpeed || 1.0,
          pitch: settings.ttsPitch || 1.0,
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
      ? "ЯРИЖ БАЙНА..."
      : state === "processing"
      ? "БОЛОВСРУУЛЖ БАЙНА..."
      : state === "error"
      ? "ДАХИН ОРОЛДОХ"
      : "БИЧЛЭГ БЭЛЭН";

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  const stats = getTextStats(rawText);
  const currentVoice = chimegeVoices.find((v) => v.id === settings.defaultVoiceId) || chimegeVoices[0];

  return (
    <section className="workspace">
      <div className="heading">
        <div>
          <small>VOICE AI WORKSPACE</small>
          <h1>Ярихыг урлаг болго.</h1>
          <p>Монгол болон олон улсын яриа таних, зөв бичих дүрэм ба дуу хоолой үүсгэгч систем.</p>
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
          <div>
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

        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          {state === "recording"
            ? "Дуу хоолойг бодит цагт бичиж байна..."
            : `✨ AI Voice Engine Бэлэн • Дуу хоолой: ${currentVoice.name}`}
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
          ) : rawText ? (
            <p className="transcript-text">{rawText}</p>
          ) : (
            <div className="empty">
              <b>Таны текстийн үр дүн энд бууна.</b>
              <small>Микрофон товчлуур дээр дарж эсвэл {settings.shortcut} товчийг дарж яриагаа эхлүүлнэ үү.</small>
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
            className="btn-secondary"
            onClick={() => playTextToSpeech(rawText)}
            disabled={!rawText || ttsLoading}
          >
            <VolumeIcon width={15} height={15} />
            <span>{ttsLoading ? "Уншиж байна..." : `Сонсох (${currentVoice.name})`}</span>
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
          <button
            className="btn-danger"
            onClick={() => {
              setRawText("");
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
        Shortcut <kbd>{settings.shortcut}</kbd>
        <span>
          Горим <b>{settings.recordingMode}</b>
        </span>
        <span>
          Хоолой <b>{currentVoice.name}</b>
        </span>
        <span>
          FlowBar <kbd>{settings.desktopHotkey}</kbd>
        </span>
      </div>
    </section>
  );
}

export function SettingsPanel() {
  const { settings, update } = useSettings();
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
      {/* Speech & AI Voice */}
      <section className="settings">
        <h2>Хиймэл Оюуны Дуу Хоолой (TTS Voices)</h2>
        <p>Яриаг уншиж сонсоход ашиглах үндсэн хоолой (11 төрөл).</p>
        <select
          value={settings.defaultVoiceId}
          onChange={(e) => update("defaultVoiceId", e.target.value)}
          style={{ width: "100%", marginBottom: "14px" }}
        >
          <optgroup label="👩 Эмэгтэй хоолойнууд">
            {chimegeVoices
              .filter((v) => v.gender === "female")
              .map((v) => (
                <option key={v.id} value={v.id}>
                  👩 {v.name} ({v.description})
                </option>
              ))}
          </optgroup>
          <optgroup label="👨 Эрэгтэй хоолойнууд">
            {chimegeVoices
              .filter((v) => v.gender === "male")
              .map((v) => (
                <option key={v.id} value={v.id}>
                  👨 {v.name} ({v.description})
                </option>
              ))}
          </optgroup>
        </select>

        <Link href="/tts" className="btn-secondary" style={{ fontSize: "12px", textDecoration: "none" }}>
          <VolumeIcon width={14} height={14} />
          <span>Бүх 11 хоолойг TTS Studio-д сонсох →</span>
        </Link>
      </section>

      {/* Desktop Mode like Duudlaga Flow */}
      <section className="settings">
        <h2>Компьютер дээр ажиллах (Duudlaga Flow горим)</h2>
        <p>Word, Chrome, Telegram зэрэг дурын програм дээр шууд ярьж бичих.</p>
        
        <div style={{ background: "var(--subtle)", padding: "14px", borderRadius: "14px", fontSize: "12px", lineHeight: 1.6, marginBottom: "14px", border: "1px solid var(--border)" }}>
          <div><b>💻 Хөвөгч FlowBar:</b> Дэлгэцийн доод хэсэгт жижиг capsule хэлбэрээр хөвөн байрлана.</div>
          <div style={{ marginTop: "4px" }}><b>⌨️ Системийн товчлуур:</b> <kbd>{settings.desktopHotkey}</kbd> (дэлгэцийн хаанаас ч ярьж эхлүүлнэ).</div>
          <div style={{ marginTop: "4px" }}><b>✍️ Шууд бичих:</b> Ярьж дуусмагц тухайн идэвхтэй цонхонд текстийг автоматаар хуулж бичнэ.</div>
        </div>

        <Link
          href="/flowbar"
          target="_blank"
          className="btn-primary"
          style={{ textDecoration: "none" }}
        >
          <FlowBarIcon width={16} height={16} />
          <span>FlowBar цонхыг нээх</span>
        </Link>

        <div style={{ marginTop: "14px" }}>
          <Toggle
            k="autoInsertText"
            label="Auto-insert text"
            description="Яриаг таньмагц идэвхтэй цонхонд автоматаар буулгах."
          />
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
        <h2>Keyboard Shortcut (Товчлол)</h2>
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
