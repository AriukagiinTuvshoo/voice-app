"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MusicIcon, SparklesIcon, CopyIcon, CheckIcon, TrashIcon } from "@/components/Icons";

interface Segment {
  start: number;
  end: number;
  text: string;
}

export default function LyricsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [language, setLanguage] = useState("auto");
  const [whisperModel, setWhisperModel] = useState("small");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);
  const [copiedType, setCopiedType] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Clean up object URL when component unmounts or file changes
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  // Synchronize active segment with audio playback
  const handleTimeUpdate = useCallback(() => {
    if (!audioRef.current) return;
    const cur = audioRef.current.currentTime;
    setCurrentTime(cur);

    const idx = segments.findIndex(
      (s) => cur >= s.start && cur <= s.end
    );
    if (idx !== -1) {
      setActiveSegmentIndex(idx);
    } else {
      // Find closest preceding segment
      const lastPast = segments.reduce((acc, s, i) => (s.start <= cur ? i : acc), -1);
      setActiveSegmentIndex(lastPast !== -1 ? lastPast : null);
    }
  }, [segments]);

  // Auto-scroll active segment into view if playing
  useEffect(() => {
    if (activeSegmentIndex !== null && listRef.current) {
      const activeEl = listRef.current.querySelector(`[data-index="${activeSegmentIndex}"]`);
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [activeSegmentIndex]);

  const handleFileSelect = (selectedFile: File) => {
    setError(null);
    const validExtensions = [".mp3", ".wav", ".m4a", ".ogg", ".mp4"];
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf(".")).toLowerCase();

    if (!validExtensions.includes(ext)) {
      setError(`Дэмжигдээгүй файл формат байна (${ext}). MP3, WAV, M4A, OGG, эсвэл MP4 файл сонгоно уу.`);
      return;
    }

    if (selectedFile.size > 25 * 1024 * 1024) {
      setError("Файлын хэмжээ хэт том байна! Дээд хязгаар: 25MB.");
      return;
    }

    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    setFile(selectedFile);
    const url = URL.createObjectURL(selectedFile);
    setAudioUrl(url);

    // Auto-fill song title from file name without extension
    const baseName = selectedFile.name.replace(/\.[^/.]+$/, "");
    if (!title) {
      if (baseName.includes("-")) {
        const parts = baseName.split("-").map((p) => p.trim());
        if (parts.length >= 2) {
          if (!artist) setArtist(parts[0]);
          setTitle(parts.slice(1).join("-").trim());
        } else {
          setTitle(baseName);
        }
      } else {
        setTitle(baseName);
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleProcessLyrics = async () => {
    if (!file) {
      setError("Аудио эсвэл видео файл оруулна уу.");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("audio", file);
    formData.append("language", language);
    formData.append("model_name", whisperModel);
    formData.append("title", title);
    formData.append("artist", artist);

    try {
      const res = await fetch("/api/auto-lyrics", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Серверийн алдаа (${res.status})`);
      }

      const data = await res.json();
      if (!data.segments || data.segments.length === 0) {
        setError("Дуу/яриа илэрсэнгүй. Өөр аудио файл сонгож туршина уу.");
      } else {
        setSegments(data.segments);
      }
    } catch (err: any) {
      setError(err.message || "Auto Lyrics боловсруулахад алдаа гарлаа.");
    } finally {
      setLoading(false);
    }
  };

  const updateSegmentText = (index: number, newText: string) => {
    setSegments((prev) =>
      prev.map((seg, i) => (i === index ? { ...seg, text: newText } : seg))
    );
  };

  const seekTo = (seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds;
      audioRef.current.play().catch(() => {});
    }
  };

  const formatDisplayTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 100);
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
  };

  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const exportLRC = () => {
    if (segments.length === 0) return;
    let lrc = "";
    if (title) lrc += `[ti:${title}]\r\n`;
    if (artist) lrc += `[ar:${artist}]\r\n`;
    lrc += `[by:VOICE AI]\r\n\r\n`;

    segments.forEach((s) => {
      const centis = Math.round(s.start * 100);
      const mins = Math.floor(centis / 6000);
      const secs = Math.floor((centis % 6000) / 100);
      const remCentis = centis % 100;
      const timeTag = `[${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${remCentis.toString().padStart(2, "0")}]`;
      lrc += `${timeTag}${s.text.trim()}\r\n`;
    });

    const safeTitle = (title || "lyrics").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
    downloadFile(lrc, `${safeTitle}.lrc`, "text/plain;charset=utf-8");
  };

  const exportSRT = () => {
    if (segments.length === 0) return;
    const formatSRTTime = (seconds: number) => {
      const totalMs = Math.round(seconds * 1000);
      const hrs = Math.floor(totalMs / 3600000);
      const mins = Math.floor((totalMs % 3600000) / 60000);
      const secs = Math.floor((totalMs % 60000) / 1000);
      const ms = totalMs % 1000;
      return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")},${ms.toString().padStart(3, "0")}`;
    };

    let srt = "";
    segments.forEach((s, idx) => {
      srt += `${idx + 1}\r\n`;
      srt += `${formatSRTTime(s.start)} --> ${formatSRTTime(s.end)}\r\n`;
      srt += `${s.text.trim()}\r\n\r\n`;
    });

    const safeTitle = (title || "subtitles").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
    downloadFile(srt, `${safeTitle}.srt`, "text/plain;charset=utf-8");
  };

  const exportVTT = () => {
    if (segments.length === 0) return;
    const formatVTTTime = (seconds: number) => {
      const totalMs = Math.round(seconds * 1000);
      const hrs = Math.floor(totalMs / 3600000);
      const mins = Math.floor((totalMs % 3600000) / 60000);
      const secs = Math.floor((totalMs % 60000) / 1000);
      const ms = totalMs % 1000;
      return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms.toString().padStart(3, "0")}`;
    };

    let vtt = "WEBVTT\r\n\r\n";
    segments.forEach((s, idx) => {
      vtt += `${idx + 1}\r\n`;
      vtt += `${formatVTTTime(s.start)} --> ${formatVTTTime(s.end)}\r\n`;
      vtt += `${s.text.trim()}\r\n\r\n`;
    });

    const safeTitle = (title || "subtitles").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
    downloadFile(vtt, `${safeTitle}.vtt`, "text/vtt;charset=utf-8");
  };

  const exportTXT = () => {
    if (segments.length === 0) return;
    const txt = segments.map((s) => s.text.trim()).join("\r\n");
    const safeTitle = (title || "lyrics").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
    downloadFile(txt, `${safeTitle}.txt`, "text/plain;charset=utf-8");
  };

  const copyLyricsText = () => {
    const text = segments.map((s) => s.text.trim()).join("\n");
    navigator.clipboard?.writeText(text);
    setCopiedType("txt");
    setTimeout(() => setCopiedType(null), 2000);
  };

  const handleClear = () => {
    setFile(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setSegments([]);
    setError(null);
    setTitle("");
    setArtist("");
  };

  return (
    <div className="content-container" style={{ maxWidth: "1080px", margin: "0 auto", padding: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ padding: "8px", background: "rgba(99, 102, 241, 0.15)", borderRadius: "10px", color: "var(--primary, #6366f1)" }}>
              <MusicIcon width={24} height={24} />
            </div>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0 }}>Auto Lyrics & Subtitle Studio</h1>
          </div>
          <p style={{ color: "var(--text-muted, #888)", marginTop: "6px", fontSize: "0.95rem" }}>
            Дуу хөгжим болон видеоноос миллисекундын синхрон дууны үг (.LRC) болон хадмал (.SRT / .VTT) автоматаар үүсгэх.
          </p>
        </div>

        {segments.length > 0 && (
          <button className="btn-secondary" onClick={handleClear} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <TrashIcon width={16} height={16} />
            <span>Шинээр эхлэх</span>
          </button>
        )}
      </div>

      {/* Upload & Setup Section */}
      <div
        className="card"
        style={{
          background: "var(--bg-card, #1e1e24)",
          borderRadius: "14px",
          padding: "20px",
          border: "1px solid var(--border-color, rgba(255,255,255,0.08))",
          marginBottom: "24px",
        }}
      >
        {!file ? (
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: "2px dashed var(--border-color, rgba(255,255,255,0.15))",
              borderRadius: "12px",
              padding: "48px 24px",
              textAlign: "center",
              cursor: "pointer",
              transition: "border-color 0.2s",
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              accept=".mp3,.wav,.m4a,.ogg,.mp4,audio/*,video/mp4"
              style={{ display: "none" }}
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileSelect(e.target.files[0]);
                }
              }}
            />
            <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px" }}>
              <div style={{ padding: "16px", background: "rgba(99, 102, 241, 0.1)", borderRadius: "50%", color: "var(--primary, #6366f1)" }}>
                <MusicIcon width={36} height={36} />
              </div>
            </div>
            <h3 style={{ margin: "0 0 8px 0", fontSize: "1.15rem" }}>Аудио эсвэл видео файл энд чирж тавина уу</h3>
            <p style={{ color: "var(--text-muted, #888)", fontSize: "0.88rem", margin: 0 }}>
              Дэмжигдэх формат: <strong>MP3, WAV, M4A, OGG, MP4</strong> (Дээд хэмжээ: 25MB)
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div style={{ padding: "10px", background: "rgba(99, 102, 241, 0.15)", borderRadius: "8px", color: "var(--primary, #6366f1)" }}>
                  <MusicIcon width={22} height={22} />
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "1rem" }}>{file.name}</div>
                  <div style={{ color: "var(--text-muted, #888)", fontSize: "0.82rem" }}>
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </div>
                </div>
              </div>

              <button
                className="btn-secondary"
                onClick={() => {
                  setFile(null);
                  if (audioUrl) URL.revokeObjectURL(audioUrl);
                  setAudioUrl(null);
                  setSegments([]);
                }}
                style={{ fontSize: "0.82rem", padding: "6px 12px" }}
              >
                Өөр файл сонгох
              </button>
            </div>

            {/* Audio Player */}
            {audioUrl && (
              <div style={{ marginTop: "4px" }}>
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  controls
                  onTimeUpdate={handleTimeUpdate}
                  style={{ width: "100%", borderRadius: "8px" }}
                />
              </div>
            )}

            {/* Metadata and Processing Controls */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted, #888)", marginBottom: "4px" }}>
                  Дууны нэр (Title)
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="Жишээ: Амин хайр"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "6px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted, #888)", marginBottom: "4px" }}>
                  Дуучин / Уран бүтээлч (Artist)
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="Жишээ: The Hu"
                  value={artist}
                  onChange={(e) => setArtist(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "6px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted, #888)", marginBottom: "4px" }}>
                  Хэл сонголт
                </label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="input-field"
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "6px" }}
                >
                  <option value="auto">Автоматаар таних (Auto)</option>
                  <option value="mn">Монгол (Mongolian)</option>
                  <option value="en">English (Англи)</option>
                  <option value="ru">Русский (Орос)</option>
                  <option value="ja">日本語 (Япон)</option>
                  <option value="ko">한국어 (Солонгос)</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted, #888)", marginBottom: "4px" }}>
                  Whisper загвар
                </label>
                <select
                  value={whisperModel}
                  onChange={(e) => setWhisperModel(e.target.value)}
                  className="input-field"
                  style={{ width: "100%", padding: "8px 12px", borderRadius: "6px" }}
                >
                  <option value="tiny">Tiny (Хамгийн хурдан)</option>
                  <option value="base">Base (Ердийн)</option>
                  <option value="small">Small (Тэнцвэртэй - Зөвлөмж)</option>
                  <option value="medium">Medium (Өндөр нарийвчлал)</option>
                </select>
              </div>
            </div>

            {/* Action button */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "6px" }}>
              <button
                className="btn-primary"
                onClick={handleProcessLyrics}
                disabled={loading}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 24px",
                  fontWeight: 600,
                  fontSize: "0.95rem",
                }}
              >
                <SparklesIcon width={18} height={18} />
                <span>{loading ? "Дууны үг гаргаж байна..." : "Синхрон үг үүсгэх"}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div
          style={{
            padding: "14px 18px",
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#f87171",
            borderRadius: "10px",
            marginBottom: "24px",
            fontSize: "0.9rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Results View */}
      {segments.length > 0 && (
        <div
          className="card"
          style={{
            background: "var(--bg-card, #1e1e24)",
            borderRadius: "14px",
            padding: "20px",
            border: "1px solid var(--border-color, rgba(255,255,255,0.08))",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
              paddingBottom: "16px",
              borderBottom: "1px solid var(--border-color, rgba(255,255,255,0.08))",
              marginBottom: "16px",
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 600, margin: 0 }}>
                {title ? `${title} ${artist ? `- ${artist}` : ""}` : "Синхрон дууны үг"}
              </h2>
              <div style={{ color: "var(--text-muted, #888)", fontSize: "0.82rem", marginTop: "2px" }}>
                Нийт {segments.length} мөр тайлагдсан. Мөр дээр дарж тухайн секундыг тоглуулах буюу үгийг засах боломжтой.
              </div>
            </div>

            {/* Export Toolbar */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <button className="btn-secondary" onClick={exportLRC} title="Караоке / Дууны синхрон үг">
                Татах (.LRC)
              </button>
              <button className="btn-secondary" onClick={exportSRT} title="Видео хадмал">
                Татах (.SRT)
              </button>
              <button className="btn-secondary" onClick={exportVTT} title="Вэб видео хадмал">
                Татах (.VTT)
              </button>
              <button className="btn-secondary" onClick={exportTXT} title="Цэвэр текст">
                Татах (.TXT)
              </button>
              <button className="btn-secondary" onClick={copyLyricsText} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                {copiedType === "txt" ? <CheckIcon width={14} height={14} /> : <CopyIcon width={14} height={14} />}
                <span>{copiedType === "txt" ? "Хуулагдлаа" : "Хуулах"}</span>
              </button>
            </div>
          </div>

          {/* Synchronized Lyrics Container */}
          <div
            ref={listRef}
            style={{
              maxHeight: "460px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              paddingRight: "6px",
            }}
          >
            {segments.map((seg, idx) => {
              const isActive = activeSegmentIndex === idx;
              return (
                <div
                  key={idx}
                  data-index={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    padding: "10px 14px",
                    borderRadius: "8px",
                    background: isActive ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.02)",
                    border: isActive ? "1px solid rgba(99, 102, 241, 0.5)" : "1px solid transparent",
                    transition: "all 0.2s ease",
                  }}
                >
                  {/* Timestamp seek button */}
                  <button
                    onClick={() => seekTo(seg.start)}
                    style={{
                      fontFamily: "monospace",
                      fontSize: "0.82rem",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      background: isActive ? "var(--primary, #6366f1)" : "rgba(255,255,255,0.06)",
                      color: isActive ? "#fff" : "var(--text-muted, #aaa)",
                      border: "none",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                    title="Энэ мөчөөс эхлүүлэн тоглуулах"
                  >
                    ▶ {formatDisplayTime(seg.start)}
                  </button>

                  {/* Inline editable lyric line */}
                  <input
                    type="text"
                    value={seg.text}
                    onChange={(e) => updateSegmentText(idx, e.target.value)}
                    style={{
                      flex: 1,
                      background: "transparent",
                      border: "none",
                      outline: "none",
                      color: isActive ? "#ffffff" : "var(--text-color, #e0e0e0)",
                      fontSize: isActive ? "1.05rem" : "0.95rem",
                      fontWeight: isActive ? 600 : 400,
                      transition: "font-size 0.2s, font-weight 0.2s",
                    }}
                  />

                  <div style={{ fontFamily: "monospace", fontSize: "0.78rem", color: "var(--text-muted, #777)", whiteSpace: "nowrap" }}>
                    {formatDisplayTime(seg.end)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
