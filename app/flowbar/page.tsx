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

export default function FlowBarPage() {
  const { settings } = useSettings();
  const [state, setState] = useState<"idle" | "recording" | "processing" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [audioLevels, setAudioLevels] = useState<number[]>([4, 10, 16, 10, 4]);
  const [seconds, setSeconds] = useState(0);

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
    setErrorMessage("");

    try {
      let text = "";

      if (browserRecognizerRef.current) {
        text = await browserRecognizerRef.current.stop();
        browserRecognizerRef.current = null;
      }

      if (recorderRef.current) {
        const wavBlob = await recorderRef.current.stop();
        recorderRef.current = null;

        if (!text || !text.trim()) {
          const formData = new FormData();
          formData.append("audio", wavBlob, "speech.wav");

          const res = await fetch("/api/chimege/transcribe", {
            method: "POST",
            body: formData,
          });

          const data = await res.json().catch(() => ({}));
          text = data.text || "";
        }
      }

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
      });

      HistoryStore.add({
        text: processed,
        rawText: text,
        durationSeconds: seconds,
        language: "mn",
        engine: "Voice FlowBar",
        wordCount: processed.split(/\s+/).length,
        charCount: processed.length,
      });

      const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
      if (win?.electron?.insertText) {
        win.electron.insertText(processed);
      } else {
        navigator.clipboard?.writeText(processed);
      }

      setState("success");
      setTimeout(() => setState("idle"), 2200);
    } catch {
      setErrorMessage("Дахин оролдоно уу");
      setState("error");
      setTimeout(() => setState("idle"), 2500);
    }
  }, [settings, seconds]);

  const startRecording = useCallback(async () => {
    setSeconds(0);
    setErrorMessage("");
    try {
      if (isBrowserSpeechSupported() && settings.sttEngine !== "chimege") {
        const recognizer = new BrowserSpeechRecognizer({
          language: settings.language,
          onError: (err) => console.warn("FlowBar browser speech error:", err),
        });
        browserRecognizerRef.current = recognizer;
        recognizer.start();
      }

      const recorder = new AudioRecorder({
        deviceId: settings.selectedAudioDevice,
        autoStop: settings.autoStop,
        onAudioLevel: (lvl) => {
          setAudioLevels((prev) => [...prev.slice(1), Math.max(4, Math.round(lvl * 22))]);
        },
        onSilenceDetected: () => stopAndTranscribe(),
      });
      recorderRef.current = recorder;
      await recorder.start();
      setState("recording");
    } catch {
      setErrorMessage("Микрофон шалгана уу");
      setState("error");
    }
  }, [settings, stopAndTranscribe]);

  const toggleRecording = () => {
    if (state === "idle" || state === "error" || state === "success") {
      startRecording();
    } else if (state === "recording") {
      stopAndTranscribe();
    }
  };

  useEffect(() => {
    const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
    if (win?.electron?.onRecordingStart && win?.electron?.onRecordingStop) {
      win.electron.onRecordingStart(() => startRecording());
      win.electron.onRecordingStop(() => stopAndTranscribe());
    }
  }, [startRecording, stopAndTranscribe]);

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
      <div
        onClick={toggleRecording}
        style={{
          cursor: "pointer",
          borderRadius: state === "idle" ? "14px" : "20px",
          transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          background:
            state === "idle"
              ? "rgba(15, 19, 26, 0.88)"
              : state === "recording"
              ? "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
              : state === "processing"
              ? "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"
              : state === "success"
              ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
              : "linear-gradient(135deg, #b91c1c 0%, #991b1b 100%)",
          color: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          padding: state === "idle" ? "6px 16px" : "8px 20px",
          boxShadow:
            state === "recording"
              ? "0 0 35px rgba(239, 68, 68, 0.6)"
              : state === "processing"
              ? "0 0 30px rgba(99, 102, 241, 0.5)"
              : "0 10px 30px rgba(0, 0, 0, 0.35)",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          minWidth: state === "idle" ? "120px" : "200px",
          height: state === "idle" ? "28px" : "36px",
          userSelect: "none",
        }}
      >
        {state === "idle" && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <MicIcon width={13} height={13} style={{ color: "var(--accent)" }} />
            <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em" }}>
              VOICE FLOW
            </span>
          </div>
        )}

        {state === "recording" && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: "#fff", animation: "pulse 1s infinite" }} />
            <span style={{ fontSize: "12px", fontWeight: 700 }}>{seconds}s</span>
            <div style={{ display: "flex", alignItems: "center", gap: "2px", height: "18px" }}>
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
            Боловсруулж байна...
          </span>
        )}

        {state === "success" && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <CheckIcon width={14} height={14} />
            <span style={{ fontSize: "12px", fontWeight: 700 }}>Бичигдлээ!</span>
          </div>
        )}

        {state === "error" && (
          <span style={{ fontSize: "11px", fontWeight: 500 }}>
            {errorMessage}
          </span>
        )}
      </div>
    </div>
  );
}
