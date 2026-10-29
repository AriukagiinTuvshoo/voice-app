"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { AudioRecorder } from "@/lib/audio-recorder";
import { BrowserSpeechRecognizer, isBrowserSpeechSupported } from "@/lib/speech-recognition";
import { useSettings } from "@/components/AppShell";
import { processTranscriptText } from "@/lib/text-processor";
import { HistoryStore } from "@/lib/history-store";
import { MicIcon, CheckIcon } from "@/components/Icons";

interface IWindowWithElectron extends Window {
  electron?: {
    isDesktop?: boolean;
    insertText?: (text: string) => void;
    onRecordingStart?: (cb: () => void) => void;
    onRecordingStop?: (cb: () => void) => void;
  };
}

const LANGUAGES = [
  { code: "auto", label: "AUTO", icon: "🌐" },
  { code: "mn", label: "MN", icon: "🇲🇳" },
  { code: "en", label: "EN", icon: "🇬🇧" },
  { code: "ja", label: "JA", icon: "🇯🇵" },
];

export default function FlowBarPage() {
  const { settings, update } = useSettings();
  const [state, setState] = useState<"idle" | "recording" | "processing" | "success" | "error">("idle");
  const [isDismissed, setIsDismissed] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [audioLevels, setAudioLevels] = useState<number[]>([4, 10, 16, 10, 4]);
  const [seconds, setSeconds] = useState(0);
  const [langIndex, setLangIndex] = useState(0);

  // Drag position
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0, posX: 0, posY: 0 });

  const recorderRef = useRef<AudioRecorder | null>(null);
  const browserRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Restore saved position
  useEffect(() => {
    try {
      const saved = localStorage.getItem("voice_flowbar_pos");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          setPos(parsed);
        }
      }
    } catch {}
  }, []);

  // Timer while recording
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

  const currentLang = LANGUAGES[langIndex];

  const cycleLanguage = (e: React.MouseEvent) => {
    e.stopPropagation();
    const nextIdx = (langIndex + 1) % LANGUAGES.length;
    setLangIndex(nextIdx);
    const nextCode = LANGUAGES[nextIdx].code;
    update("language", nextCode as any);
    fetch("/api/flowbar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "set_language", language: nextCode }),
    }).catch(() => {});
  };

  const stopAndTranscribe = useCallback(async () => {
    setState("processing");
    setErrorMessage("");

    try {
      let browserText = "";
      let serverText = "";

      if (browserRecognizerRef.current) {
        browserText = await browserRecognizerRef.current.stop();
        browserRecognizerRef.current = null;
      }

      if (recorderRef.current) {
        const wavBlob = await recorderRef.current.stop();
        recorderRef.current = null;

        const formData = new FormData();
        formData.append("audio", wavBlob, "speech.wav");
        formData.append("language", currentLang.code);

        const res = await fetch("/api/chimege/transcribe", {
          method: "POST",
          body: formData,
        });

        const data = await res.json().catch(() => ({}));
        serverText = (data.text || "").trim();
      }

      const text =
        serverText.length >= browserText.length
          ? serverText || browserText
          : browserText || serverText;

      if (!text || !text.trim()) {
        setErrorMessage("Сонсогдсонгүй");
        setState("error");
        setTimeout(() => setState("idle"), 2200);
        return;
      }

      const processed = processTranscriptText(text, {
        mode: settings.processingMode,
        autoPunctuation: settings.autoPunctuation,
        removeFillers: settings.removeFillers,
        language: currentLang.code as any,
        customSnippets: settings.customSnippets,
        snippets: settings.snippets,
      });

      HistoryStore.add({
        text: processed,
        rawText: text,
        durationSeconds: seconds,
        language: currentLang.code as any,
        engine: "Voice FlowBar",
        wordCount: processed.split(/\s+/).length,
        charCount: processed.length,
      });

      // 1. Copy to clipboard
      navigator.clipboard?.writeText(processed).catch(() => {});

      // 2. Direct injection into active cursor (Word, Chrome, Telegram, etc.)
      await fetch("/api/flowbar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ insertText: processed, text: processed }),
      }).catch(() => {});

      // 3. Electron IPC fallback
      const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
      if (win?.electron?.insertText) {
        win.electron.insertText(processed);
      }

      setState("success");
      setTimeout(() => setState("idle"), 2400);
    } catch {
      setErrorMessage("Дахин оролдоно уу");
      setState("error");
      setTimeout(() => setState("idle"), 2500);
    }
  }, [settings, seconds, currentLang.code]);

  const startRecording = useCallback(async () => {
    setSeconds(0);
    setErrorMessage("");
    try {
      if (isBrowserSpeechSupported() && settings.sttEngine !== "chimege") {
        try {
          const recognizer = new BrowserSpeechRecognizer({
            language: currentLang.code === "auto" ? "mn" : (currentLang.code as any),
            onError: (err) => console.warn("FlowBar browser speech error:", err),
          });
          browserRecognizerRef.current = recognizer;
          recognizer.start();
        } catch (recErr) {
          console.warn("FlowBar browser speech init error:", recErr);
          browserRecognizerRef.current = null;
        }
      }

      const recorder = new AudioRecorder({
        deviceId: settings.selectedAudioDevice,
        autoStop: settings.autoStop,
        onAudioLevel: (lvl) => {
          setAudioLevels((prev) => [...prev.slice(1), Math.max(4, Math.round(lvl * 24))]);
        },
        onSilenceDetected: () => stopAndTranscribe(),
      });
      recorderRef.current = recorder;
      await recorder.start();
      setState("recording");
    } catch (err: unknown) {
      if (browserRecognizerRef.current) {
        browserRecognizerRef.current.abort();
        browserRecognizerRef.current = null;
      }
      if (recorderRef.current) {
        recorderRef.current.cancel();
        recorderRef.current = null;
      }
      const msg = err instanceof Error ? err.message : "Микрофон шалгана уу";
      setErrorMessage(msg);
      setState("error");
    }
  }, [settings, currentLang.code, stopAndTranscribe]);

  const toggleRecording = () => {
    if (state === "idle" || state === "error" || state === "success") {
      startRecording();
    } else if (state === "recording") {
      stopAndTranscribe();
    }
  };

  // Keyboard shortcut listener inside window
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey && e.altKey) || e.key === "F8") {
        e.preventDefault();
        if (isDismissed) {
          setIsDismissed(false);
        }
        toggleRecording();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDismissed, toggleRecording]);

  // Global Electron IPC shortcuts
  useEffect(() => {
    const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
    if (win?.electron?.onRecordingStart && win?.electron?.onRecordingStop) {
      win.electron.onRecordingStart(() => startRecording());
      win.electron.onRecordingStop(() => stopAndTranscribe());
    }
  }, [startRecording, stopAndTranscribe]);

  // Drag Handlers
  const onMouseDownGrip = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      posX: pos.x,
      posY: pos.y,
    };

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const dx = ev.clientX - dragStartRef.current.x;
      const dy = ev.clientY - dragStartRef.current.y;
      const newX = dragStartRef.current.posX + dx;
      const newY = dragStartRef.current.posY + dy;
      setPos({ x: newX, y: newY });
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      try {
        localStorage.setItem("voice_flowbar_pos", JSON.stringify(pos));
      } catch {}
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "transparent",
        padding: "6px",
      }}
    >
      {isDismissed ? (
        <button
          type="button"
          onClick={() => {
            setIsDismissed(false);
            fetch("/api/flowbar", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action: "toggle_visibility" }),
            }).catch(() => {});
          }}
          aria-label="VOICE FlowBar-г буцаан нээх"
          title="VOICE FlowBar нээх (Ctrl+Alt эсвэл F8 дарж шууд ярина)"
          style={{
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 16px",
            borderRadius: "999px",
            background: "linear-gradient(135deg, rgba(20, 25, 43, 0.95) 0%, rgba(12, 15, 30, 0.98) 100%)",
            color: "#ffffff",
            border: "1px solid rgba(99, 102, 241, 0.5)",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5), 0 0 16px rgba(99, 102, 241, 0.3)",
            fontSize: "12px",
            fontWeight: 700,
            backdropFilter: "blur(20px)",
            pointerEvents: "auto",
            zIndex: 9999,
            transition: "all 0.2s ease",
            outline: "none",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "scale(1.04)";
            e.currentTarget.style.borderColor = "rgba(165, 180, 252, 0.7)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
            e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.5)";
          }}
        >
          <div
            style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <MicIcon width={12} height={12} style={{ color: "#ffffff" }} />
          </div>
          <span>VOICE FLOW нээх (Ctrl+Alt)</span>
        </button>
      ) : (
        <div
          style={{
            transform: `translate(${pos.x}px, ${pos.y}px)`,
            borderRadius: "999px",
            transition: isDraggingRef.current ? "none" : "background 0.25s, box-shadow 0.25s",
            background:
              state === "idle"
                ? "linear-gradient(135deg, rgba(20, 25, 43, 0.94) 0%, rgba(12, 15, 30, 0.96) 100%)"
                : state === "recording"
                ? "linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)"
                : state === "processing"
                ? "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"
                : state === "success"
                ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                : "linear-gradient(135deg, #b91c1c 0%, #991b1b 100%)",
            color: "#ffffff",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "6px 14px",
            boxShadow:
              state === "recording"
                ? "0 0 35px rgba(239, 68, 68, 0.7)"
                : state === "processing"
                ? "0 0 30px rgba(99, 102, 241, 0.6)"
                : state === "success"
                ? "0 0 25px rgba(16, 185, 129, 0.5)"
                : "0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.2)",
            border:
              state === "recording"
                ? "1px solid rgba(254, 202, 202, 0.6)"
                : "1px solid rgba(165, 180, 252, 0.25)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            height: "44px",
            userSelect: "none",
            cursor: "default",
          }}
        >
          {/* Drag Grip Handle */}
          <div
            onMouseDown={onMouseDownGrip}
            title="Чирч хүссэн байрлалдаа зөөх"
            style={{
              cursor: "grab",
              display: "flex",
              alignItems: "center",
              padding: "4px 2px",
              color: "rgba(255, 255, 255, 0.45)",
              fontSize: "14px",
              letterSpacing: "-1px",
              pointerEvents: "auto",
            }}
          >
            ⋮⋮
          </div>

          {/* Main Mic Button & Status */}
          <button
            type="button"
            onClick={toggleRecording}
            aria-label={state === "recording" ? "Бичлэг зогсоох (Ctrl+Alt)" : "Дарж ярих (Ctrl+Alt)"}
            aria-pressed={state === "recording"}
            title={state === "recording" ? "Бичлэг дуусгах (Ctrl+Alt)" : "Дарж ярих (Ctrl+Alt)"}
            style={{
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              background: "transparent",
              border: "none",
              padding: "4px 6px",
              borderRadius: "999px",
              color: "#ffffff",
              pointerEvents: "auto",
              transition: "all 0.15s ease",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {state === "idle" && (
              <>
                <div
                  style={{
                    width: "28px",
                    height: "28px",
                    borderRadius: "50%",
                    background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 0 12px rgba(99, 102, 241, 0.5)",
                  }}
                >
                  <MicIcon width={14} height={14} style={{ color: "#ffffff" }} />
                </div>
                <span style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.04em", color: "#f8fafc" }}>
                  VOICE FLOW (Ctrl+Alt)
                </span>
              </>
            )}

            {state === "recording" && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: "#ffffff",
                    animation: "pulse 1s infinite",
                  }}
                />
                <span style={{ fontSize: "13px", fontWeight: 700 }}>{seconds}с</span>
                <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "20px" }}>
                  {audioLevels.map((lvl, i) => (
                    <div
                      key={i}
                      style={{
                        width: "3px",
                        height: `${Math.max(4, lvl)}px`,
                        background: "#ffffff",
                        borderRadius: "999px",
                        transition: "height 0.08s ease",
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {state === "processing" && (
              <span style={{ fontSize: "12px", fontWeight: 600 }}>
                Текст болгож байна...
              </span>
            )}

            {state === "success" && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <CheckIcon width={14} height={14} />
                <span style={{ fontSize: "12px", fontWeight: 700 }}>Бичигдлээ!</span>
              </div>
            )}

            {state === "error" && (
              <span style={{ fontSize: "12px", fontWeight: 600 }}>
                {errorMessage}
              </span>
            )}
          </button>

          {/* Language Badge (Click to toggle AUTO / MN / EN / JA) */}
          <button
            type="button"
            onClick={cycleLanguage}
            aria-label={`Хэл солих: одоо ${currentLang.label}`}
            title={`Хэл солих: ${currentLang.label} (Дарж солино уу)`}
            style={{
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "3px 8px",
              borderRadius: "999px",
              background: "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              color: "#ffffff",
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.05em",
              pointerEvents: "auto",
              transition: "all 0.15s ease",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.12)";
            }}
          >
            <span>{currentLang.icon}</span>
            <span>{currentLang.label}</span>
          </button>

          {/* Close Button */}
          <button
            type="button"
            aria-label="VOICE FlowBar хаах / нуух"
            onClick={(e) => {
              e.stopPropagation();
              setIsDismissed(true);
              fetch("/api/flowbar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "toggle_visibility" }),
              }).catch(() => {});
            }}
            title="Хаах / Нуух (F8 эсвэл Ctrl+Alt дарж буцаан нээнэ)"
            style={{
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "26px",
              height: "26px",
              padding: 0,
              fontSize: "14px",
              color: "rgba(255, 255, 255, 0.65)",
              background: "transparent",
              border: "1px solid transparent",
              borderRadius: "50%",
              transition: "all 0.15s ease",
              pointerEvents: "auto",
              zIndex: 10,
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#ffffff";
              e.currentTarget.style.background = "rgba(255, 255, 255, 0.18)";
              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.25)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "rgba(255, 255, 255, 0.65)";
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderColor = "transparent";
            }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
