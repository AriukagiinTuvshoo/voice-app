"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { AudioRecorder } from "@/lib/audio-recorder";
import { useSettings } from "@/components/AppShell";
import { processTranscriptText } from "@/lib/text-processor";
import { HistoryStore } from "@/lib/history-store";

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
  const [audioLevels, setAudioLevels] = useState<number[]>([4, 8, 12, 8, 4]);
  const [seconds, setSeconds] = useState(0);

  const recorderRef = useRef<AudioRecorder | null>(null);
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
    if (!recorderRef.current) return;
    setState("processing");

    try {
      const wavBlob = await recorderRef.current.stop();

      const formData = new FormData();
      formData.append("audio", wavBlob, "speech.wav");
      formData.append("token", settings.chimegeToken);
      formData.append("useStandardStt", String(settings.useStandardStt));

      const res = await fetch("/api/chimege/transcribe", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Transcribe алдаа");
      }

      const data = await res.json();
      const text = data.text || "";

      // Post process
      const processed = processTranscriptText(text, {
        mode: settings.processingMode,
        autoPunctuation: settings.autoPunctuation,
        removeFillers: settings.removeFillers,
      });

      // Save to history
      HistoryStore.add({
        text: processed,
        rawText: text,
        durationSeconds: seconds,
        language: "mn",
        engine: "Chimege STT (FlowBar)",
        wordCount: processed.split(/\s+/).length,
        charCount: processed.length,
      });

      // Insert directly into active app if in Electron desktop mode
      const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
      if (win?.electron?.insertText) {
        win.electron.insertText(processed);
      } else {
        navigator.clipboard?.writeText(processed);
      }

      setState("success");
      setTimeout(() => setState("idle"), 2500);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Хөрвүүлэхэд алдаа гарлаа");
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  }, [settings, seconds]);

  const startRecording = useCallback(async () => {
    setSeconds(0);
    setErrorMessage("");
    try {
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
      setErrorMessage(err instanceof Error ? err.message : "Микрофон алдаа");
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

  // Connect to Electron IPC global hotkey triggers
  useEffect(() => {
    const win = typeof window !== "undefined" ? (window as unknown as IWindowWithElectron) : null;
    if (win?.electron?.onRecordingStart && win?.electron?.onRecordingStop) {
      win.electron.onRecordingStart(() => {
        startRecording();
      });
      win.electron.onRecordingStop(() => {
        stopAndTranscribe();
      });
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
        padding: "4px",
      }}
    >
      <div
        onClick={toggleRecording}
        style={{
          cursor: "pointer",
          borderRadius: state === "idle" ? "12px" : "18px",
          transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
          background:
            state === "idle"
              ? "rgba(20, 22, 28, 0.92)"
              : state === "recording"
              ? "linear-gradient(135deg, #dc2626, #ef4444)"
              : state === "processing"
              ? "linear-gradient(135deg, #2563eb, #3b82f6)"
              : state === "success"
              ? "linear-gradient(135deg, #059669, #10b981)"
              : "linear-gradient(135deg, #b91c1c, #dc2626)",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          padding: state === "idle" ? "6px 14px" : "8px 18px",
          boxShadow: "0 8px 30px rgba(0, 0, 0, 0.4)",
          minWidth: state === "idle" ? "120px" : "190px",
          height: state === "idle" ? "24px" : "34px",
          userSelect: "none",
        }}
      >
        {state === "idle" && (
          <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.05em" }}>
            VOICE FLOW
          </span>
        )}

        {state === "recording" && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#fff", animation: "pulse 1s infinite" }} />
            <span style={{ fontSize: "12px", fontWeight: 700 }}>{seconds}s</span>
            <div style={{ display: "flex", alignItems: "center", gap: "2px", height: "20px" }}>
              {audioLevels.map((lvl, i) => (
                <div
                  key={i}
                  style={{
                    width: "3px",
                    height: `${Math.max(4, lvl)}px`,
                    background: "#fff",
                    borderRadius: "2px",
                    transition: "height 0.08s ease",
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {state === "processing" && (
          <span style={{ fontSize: "12px", fontWeight: 500 }}>
            Боловсруулж байна...
          </span>
        )}

        {state === "success" && (
          <span style={{ fontSize: "12px", fontWeight: 700 }}>
            ✓ Бичигдлээ!
          </span>
        )}

        {state === "error" && (
          <span style={{ fontSize: "11px", fontWeight: 500 }}>
            {errorMessage.slice(0, 20)}...
          </span>
        )}
      </div>
    </div>
  );
}
