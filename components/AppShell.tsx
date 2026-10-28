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
} from "@/lib/constants";
import type {
  Language,
  RecordingState,
  Settings,
  Shortcut,
  SttEngine,
} from "@/lib/types";
import { AudioRecorder, getAudioInputDevices } from "@/lib/audio-recorder";
import { BrowserSpeechRecognizer, isBrowserSpeechSupported } from "@/lib/speech-recognition";
import { processTranscriptText, getTextStats } from "@/lib/text-processor";
import { HistoryStore } from "@/lib/history-store";
import { SpellCheckClient } from "@/lib/spellcheck-client";

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

const nav = [
  ["/dashboard", "＋", "New"],
  ["/history", "◷", "History"],
  ["/settings", "⚙", "Settings"],
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

  const engineName =
    settings.language === "mn"
      ? settings.chimegeToken
        ? "Chimege AI Engine"
        : "Chimege (Token missing)"
      : "Speech Recognition Engine";

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="brand">
          VOICE
        </Link>
        <nav>
          {nav.map(([href, icon, label]) => (
            <Link
              key={href}
              href={href}
              className={path === href ? "nav active" : "nav"}
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>
        <div className="side-note">
          <i />
          {engineName}
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <b className="mobile-brand">VOICE</b>
          <LanguageSelect
            value={settings.language}
            onChange={(v) => update("language", v)}
          />
        </header>
        {children}
      </main>
      <nav className="mobile-nav">
        {nav.map(([href, icon, label]) => (
          <Link
            key={href}
            href={href}
            className={path === href ? "mnav active" : "mnav"}
          >
            <span>{icon}</span>
            {label}
          </Link>
        ))}
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
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioLevels, setAudioLevels] = useState<number[]>([10, 15, 20, 15, 10]);
  const [copied, setCopied] = useState(false);

  // Spellcheck state
  const [spellChecking, setSpellChecking] = useState(false);
  const [spellCheckResults, setSpellCheckResults] = useState<{
    misspelled: string[];
    suggestions: Record<string, string[]>;
  }>({ misspelled: [], suggestions: {} });
  const [showSpellPanel, setShowSpellPanel] = useState(false);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const browserRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const pttActiveRef = useRef(false);

  // Sync workspaceText from context if set
  useEffect(() => {
    if (workspaceText && !rawText) {
      setRawText(workspaceText);
    }
  }, [workspaceText, rawText]);

  // Timer logic for recording
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

  // Handle Stop and Transcribe
  const stopAndTranscribe = useCallback(
    async (currentDuration: number) => {
      setState("processing");
      setErrorMessage("");

      const isMongolian = settings.language === "mn" || settings.language === "auto";
      const preferChimege =
        (settings.sttEngine === "chimege" || (settings.sttEngine === "auto" && isMongolian)) &&
        Boolean(settings.chimegeToken);

      try {
        let transcript = "";
        let usedEngine = "browser";

        if (preferChimege) {
          // Use Chimege API with audio recorder
          if (!audioRecorderRef.current) {
            throw new Error("Аудио бичигч идэвхжээгүй байна.");
          }
          usedEngine = settings.useStandardStt ? "Chimege Standard" : "Chimege Long";
          const wavBlob = await audioRecorderRef.current.stop();

          const formData = new FormData();
          formData.append("audio", wavBlob, "speech.wav");
          formData.append("token", settings.chimegeToken);
          formData.append("useStandardStt", String(settings.useStandardStt));
          formData.append("punctuate", String(settings.autoPunctuation));

          const res = await fetch("/api/chimege/transcribe", {
            method: "POST",
            body: formData,
          });

          const data = await res.json();
          if (!res.ok) {
            throw new Error(data.error || "Chimege API-с алдаа буцаалаа.");
          }
          transcript = data.text || "";
        } else if (browserRecognizerRef.current) {
          // Use Browser Web Speech
          usedEngine = "Browser Web Speech";
          transcript = await browserRecognizerRef.current.stop();
        } else if (audioRecorderRef.current) {
          // Fallback if browser recognizer was not initialized
          await audioRecorderRef.current.stop();
          if (isMongolian && !settings.chimegeToken) {
            throw new Error(
              "Монгол яриа танихад Chimege API Token шаардлагатай. Settings цэснээс token-оо оруулна уу."
            );
          }
        }

        if (!transcript || !transcript.trim()) {
          throw new Error("Яриа илрээгүй эсвэл дуу авиа танигдсангүй. Дахин оролдоно уу.");
        }

        // Post-process text
        const processed = processTranscriptText(transcript, {
          mode: settings.processingMode,
          autoPunctuation: settings.autoPunctuation,
          removeFillers: settings.removeFillers,
          language: settings.language,
        });

        setRawText(processed);
        setWorkspaceText(processed);
        setState("success");

        // Save to History
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

        // Auto Spellcheck if enabled and Mongolian language
        if (settings.autoCorrection && isMongolian) {
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

  // Start Recording
  const startRecording = useCallback(async () => {
    setErrorMessage("");
    setSeconds(0);
    setAudioLevel(0);

    const isMongolian = settings.language === "mn" || settings.language === "auto";
    const preferChimege =
      (settings.sttEngine === "chimege" || (settings.sttEngine === "auto" && isMongolian)) &&
      Boolean(settings.chimegeToken);

    try {
      if (preferChimege || !isBrowserSpeechSupported()) {
        // Record audio via AudioRecorder (for Chimege API)
        const recorder = new AudioRecorder({
          deviceId: settings.selectedAudioDevice,
          autoStop: settings.autoStop,
          onAudioLevel: (lvl) => {
            setAudioLevel(lvl);
            setAudioLevels((prev) => {
              const next = [...prev.slice(1), Math.max(6, Math.round(lvl * 36))];
              return next;
            });
          },
          onSilenceDetected: () => {
            stopAndTranscribe(seconds);
          },
        });
        audioRecorderRef.current = recorder;
        await recorder.start();
      } else {
        // Browser Speech Recognizer
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

  // Toggle Recording
  const toggleRecording = useCallback(() => {
    if (state === "idle" || state === "error" || state === "success") {
      startRecording();
    } else if (state === "recording") {
      stopAndTranscribe(seconds);
    }
  }, [state, seconds, startRecording, stopAndTranscribe]);

  // Keyboard shortcut listener
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

  // Run manual Spellcheck
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

  // Replace a misspelled word with a suggestion
  const applySuggestion = (misspelledWord: string, candidate: string) => {
    const regex = new RegExp(`(?<=[^\\p{L}]|^)${misspelledWord}(?=[^\\p{L}]|$)`, "gu");
    const updated = rawText.replace(regex, candidate);
    setRawText(updated);
    setWorkspaceText(updated);

    // Update misspelled list
    setSpellCheckResults((prev) => ({
      misspelled: prev.misspelled.filter((w) => w !== misspelledWord),
      suggestions: prev.suggestions,
    }));
  };

  // Auto-correct all
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

  // Copy transcript
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

  return (
    <section className="workspace">
      <div className="heading">
        <div>
          <small>VOICE WORKSPACE</small>
          <h1>Ярихыг текст болго.</h1>
          <p>Монгол (Chimege AI & Spellcheck.mn), English, 日本語 хэлээр ярьж эхлээрэй.</p>
        </div>
        <LanguageSelect
          value={settings.language}
          onChange={(v) => update("language", v)}
        />
      </div>

      <div className="stage">
        <div className={state === "recording" ? "halo pulse" : "halo"}>
          <button
            className={state === "recording" ? "mic recording" : "mic"}
            onClick={toggleRecording}
            disabled={state === "processing"}
            aria-label={label}
            aria-pressed={state === "recording"}
          >
            <span>●</span>
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
                    height: `${Math.max(4, lvl + (idx % 2 === 0 ? 4 : -2))}px`,
                    opacity: 0.6 + (lvl / 40) * 0.4,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <p className="engine">
          {settings.language === "mn"
            ? settings.chimegeToken
              ? "⚡ Chimege AI STT + Spellcheck.mn холбогдсон"
              : "⚠️ Chimege Token тохируулаагүй байна. Settings хэсэгт оруулна уу."
            : "🌐 Browser Web Speech Engine бэлэн"}
        </p>
      </div>

      {state === "error" && errorMessage && (
        <div className="error" role="alert">
          <b>Алдаа:</b> {errorMessage}
          {!settings.chimegeToken && settings.language === "mn" && (
            <div style={{ marginTop: "6px" }}>
              <Link href="/settings" style={{ textDecoration: "underline", fontWeight: 600 }}>
                Settings хуудас руу очиж Chimege API Token оруулах →
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Transcript Section */}
      <section className="transcript">
        <header>
          <b>Transcript</b>
          <span>
            {stats.wordCount} үг • {stats.charCount} тэмдэгт
          </span>
        </header>

        <div className="transcript-body">
          {state === "processing" ? (
            <div className="empty">
              <b>Chimege AI яриаг боловсруулж байна...</b>
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
              placeholder="Transcript энд харагдана."
            />
          ) : rawText ? (
            <p className="transcript-text">{rawText}</p>
          ) : (
            <div className="empty">
              <b>Таны текст энд гарна.</b>
              <small>Микрофон дээр дарж эсвэл {settings.shortcut} товчийг дарж ярина уу.</small>
            </div>
          )}
        </div>

        {/* Spellcheck Suggestions Panel */}
        {showSpellPanel && spellCheckResults.misspelled.length > 0 && (
          <div className="spellcheck-panel">
            <div className="spellcheck-header">
              <div className="spellcheck-title">
                <span>Зөв бичгийн алдаа</span>
                <span className="spellcheck-badge">
                  {spellCheckResults.misspelled.length}
                </span>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
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
                <span className="spellcheck-badge clean">✓</span>
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
            onClick={handleRunSpellCheck}
            disabled={!rawText || spellChecking}
            title="spellcheck.mn-ээр шалгах"
          >
            {spellChecking ? "Шалгаж байна..." : "✓ Зөв бичиг шалгах"}
          </button>
          <button onClick={() => setEditing(true)} disabled={!rawText}>
            Edit
          </button>
          <button onClick={copyToClipboard} disabled={!rawText}>
            {copied ? "Хуулагдлаа!" : "Copy"}
          </button>
          {editing && (
            <button onClick={() => setEditing(false)}>
              Done
            </button>
          )}
          <button
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
            Delete
          </button>
        </footer>
      </section>

      <div className="meta">
        Shortcut <kbd>{settings.shortcut}</kbd>
        <span>
          Mode <b>{settings.recordingMode}</b>
        </span>
        <span>
          STT <b>{settings.sttEngine}</b>
        </span>
        <span>
          Processing <b>{settings.processingMode}</b>
        </span>
      </div>
    </section>
  );
}

export function SettingsPanel() {
  const { settings, update } = useSettings();
  const [testingToken, setTestingToken] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<{
    tested: boolean;
    valid?: boolean;
    message?: string;
  }>({ tested: false });
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);

  useEffect(() => {
    getAudioInputDevices().then(setAudioDevices);
  }, []);

  const testChimegeToken = async () => {
    if (!settings.chimegeToken) {
      setTokenStatus({
        tested: true,
        valid: false,
        message: "Эхлээд token-оо оруулна уу.",
      });
      return;
    }

    setTestingToken(true);
    setTokenStatus({ tested: false });

    try {
      const res = await fetch("/api/chimege/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: settings.chimegeToken }),
      });
      const data = await res.json();
      setTokenStatus({
        tested: true,
        valid: data.valid,
        message: data.message,
      });
    } catch {
      setTokenStatus({
        tested: true,
        valid: false,
        message: "Холболтын алдаа гарлаа.",
      });
    } finally {
      setTestingToken(false);
    }
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
        <span>{label}</span>
        {description && (
          <small style={{ display: "block", color: "var(--muted)", fontSize: "11px" }}>
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
      {/* Language */}
      <section className="settings">
        <h2>Language (Хэл)</h2>
        <p>Яриа таних үндсэн хэлээ сонгоно.</p>
        <LanguageSelect
          value={settings.language}
          onChange={(v) => update("language", v)}
        />
      </section>

      {/* Chimege STT API Configuration */}
      <section className="settings">
        <h2>Chimege AI Engine (Монгол яриа)</h2>
        <p>
          Chimege API Token оруулснаар монгол яриаг өндөр нарийвчлалтай танина.
        </p>

        <div className="token-input-group">
          <input
            type="password"
            placeholder="Chimege API Token..."
            value={settings.chimegeToken}
            onChange={(e) => {
              update("chimegeToken", e.target.value);
              setTokenStatus({ tested: false });
            }}
          />
          <button
            className="btn-primary"
            onClick={testChimegeToken}
            disabled={testingToken || !settings.chimegeToken}
          >
            {testingToken ? "Шалгаж байна..." : "Шалгах"}
          </button>
        </div>

        {tokenStatus.tested && (
          <div style={{ marginTop: "10px" }}>
            <span
              className={`status-pill ${
                tokenStatus.valid ? "success" : "error"
              }`}
            >
              {tokenStatus.valid ? "✓" : "✗"} {tokenStatus.message}
            </span>
          </div>
        )}

        <div className="token-help">
          Token байхгүй бол{" "}
          <a
            href="https://console.chimege.com"
            target="_blank"
            rel="noreferrer"
          >
            console.chimege.com
          </a>{" "}
          дээр бүртгүүлж авна уу.
        </div>

        <Toggle
          k="useStandardStt"
          label="Standard STT (Хурдан)"
          description="Богино ярианд илүү хурдан (унтраавал урт ярианы Long STT горим ашиглана)."
        />
      </section>

      {/* STT Engine selection */}
      <section className="settings">
        <h2>Speech Recognition Engine</h2>
        <p>Ашиглах яриа танигч загвар.</p>
        <div className="option-list">
          {sttEngines.map((x) => (
            <label className="radio" key={x.value}>
              <input
                type="radio"
                name="engine"
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
      </section>

      {/* Recording Mode */}
      <section className="settings">
        <h2>Recording (Бичлэг хийх горим)</h2>
        <p>Бичлэгийг хэрхэн эхлүүлэх болон дуусгах тохиргоо.</p>
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
        <h2>Microphone Device (Микрофон сонгох)</h2>
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
        <h2>Text & Spellcheck (Текст боловсруулалт)</h2>
        <p>Зөв бичих дүрэм, цэг таслал болон сул үг цэвэрлэх тохиргоо.</p>
        <Toggle
          k="autoPunctuation"
          label="Auto punctuation"
          description="Цэг таслал, эхний үсгийг автоматаар томруулах."
        />
        <Toggle
          k="autoCorrection"
          label="Auto correction (spellcheck.mn)"
          description="Бичвэр бэлэн болмогц зөв бичгийн алдааг шалгаж санал болгох."
        />
        <Toggle
          k="removeFillers"
          label="Remove fillers (Сул үг арилгах)"
          description="Монгол хэлний сул үгсийг (нөгөө, ер нь, аан, тэгээд...) хасах."
        />
        <div className="option-list">
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
        <h2>Appearance (Харагдац)</h2>
        <p>Theme preference.</p>
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
        <h2>Privacy & Storage (Хадгалалт)</h2>
        <p>Түүх болон хувийн мэдээллийн тохиргоо.</p>
        <Toggle
          k="saveTranscripts"
          label="Save transcripts"
          description="Бүх хөрвүүлсэн текстийг History хэсэгт автоматаар хадгалах."
        />
        <Toggle
          k="saveRecordings"
          label="Save recordings"
          description="Орон нутгийн session-д бичлэгийг хадгалах."
        />
        <div style={{ marginTop: "14px" }}>
          <button
            className="btn-danger"
            onClick={() => {
              if (confirm("Бүх хадгалсан түүхийг устгахдаа итгэлтэй байна уу?")) {
                HistoryStore.clear();
                alert("Түүх амжилттай цэвэрлэгдлээ.");
              }
            }}
          >
            Clear All History (Түүхийг бүрэн цэвэрлэх)
          </button>
        </div>
      </section>
    </div>
  );
}
