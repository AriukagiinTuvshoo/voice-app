"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MusicIcon, SparklesIcon, CopyIcon, CheckIcon, TrashIcon } from "@/components/Icons";
import type { LyricsSegment, LyricsWordTiming } from "@/lib/types";

export default function LyricsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [language, setLanguage] = useState("auto");
  const [whisperModel, setWhisperModel] = useState("small-q5_0");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [segments, setSegments] = useState<LyricsSegment[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number | null>(null);
  const [copiedType, setCopiedType] = useState<string | null>(null);
  const [fallbackNotice, setFallbackNotice] = useState<string | null>(null);
  const [timingSource, setTimingSource] = useState<string | null>(null);

  // Dynamic Audio Waveform & Timeline states
  const [waveformPeaks, setWaveformPeaks] = useState<number[]>([]);
  const [waveformLoading, setWaveformLoading] = useState(false);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverPos, setHoverPos] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const waveformCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const waveformContainerRef = useRef<HTMLDivElement | null>(null);

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

  // Compute waveform amplitude peaks using Web Audio API
  const computeWaveform = async (selectedFile: File) => {
    try {
      setWaveformLoading(true);
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) {
        // Fallback procedural waveform
        generateFallbackPeaks();
        return;
      }

      const audioCtx = new AudioContextClass();
      const arrayBuffer = await selectedFile.arrayBuffer();
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      
      const trackDur = audioBuffer.duration;
      setDuration(trackDur);

      const channelData = audioBuffer.getChannelData(0);
      const totalSamples = 160;
      const blockSize = Math.max(1, Math.floor(channelData.length / totalSamples));
      const peaks: number[] = [];

      for (let i = 0; i < totalSamples; i++) {
        let sum = 0;
        const blockStart = i * blockSize;
        const actualBlock = Math.min(blockSize, channelData.length - blockStart);
        if (actualBlock <= 0) break;
        for (let j = 0; j < actualBlock; j++) {
          sum += Math.abs(channelData[blockStart + j] || 0);
        }
        peaks.push(sum / actualBlock);
      }

      const maxVal = Math.max(...peaks, 0.001);
      setWaveformPeaks(peaks.map((p) => Math.min(1, p / maxVal)));
      audioCtx.close().catch(() => {});
    } catch (err) {
      console.warn("Waveform decoding fallback triggered:", err);
      generateFallbackPeaks();
    } finally {
      setWaveformLoading(false);
    }
  };

  const generateFallbackPeaks = () => {
    const fallback = Array.from({ length: 160 }, (_, i) => {
      const base = 0.25 + 0.5 * Math.abs(Math.sin(i * 0.14) * Math.cos(i * 0.08));
      return Math.min(1, Math.max(0.12, base));
    });
    setWaveformPeaks(fallback);
  };

  // Draw dynamic waveform and playhead scrubber onto canvas
  useEffect(() => {
    const canvas = waveformCanvasRef.current;
    if (!canvas || waveformPeaks.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const effDuration = duration || (audioRef.current?.duration ?? 0);
    const progress = effDuration > 0 ? Math.min(1, Math.max(0, currentTime / effDuration)) : 0;
    const progressX = progress * width;

    const barCount = waveformPeaks.length;
    const spacing = width / barCount;
    const barWidth = Math.max(2, spacing - 1.5);

    // Draw bars
    waveformPeaks.forEach((peak, i) => {
      const x = i * spacing;
      const barHeight = Math.max(4, peak * (height - 16));
      const y = (height - barHeight) / 2;

      if (x + barWidth <= progressX) {
        // Played section: neon indigo-violet gradient
        const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
        grad.addColorStop(0, "#818cf8");
        grad.addColorStop(1, "#6366f1");
        ctx.fillStyle = grad;
      } else {
        // Unplayed section: soft translucent bars
        ctx.fillStyle = "rgba(255, 255, 255, 0.22)";
      }

      ctx.beginPath();
      const radius = Math.min(barWidth / 2, 2);
      ctx.roundRect(x, y, barWidth, barHeight, radius);
      ctx.fill();
    });

    // Draw scrubber playhead
    if (progressX > 0 && progressX < width) {
      // Vertical playhead line
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(progressX, 0);
      ctx.lineTo(progressX, height);
      ctx.stroke();

      // Scrubber head diamond/circle indicator
      ctx.fillStyle = "#818cf8";
      ctx.beginPath();
      ctx.arc(progressX, 8, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw hover preview line
    if (hoverPos !== null) {
      ctx.strokeStyle = "rgba(165, 180, 252, 0.75)";
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(hoverPos, 0);
      ctx.lineTo(hoverPos, height);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [waveformPeaks, currentTime, duration, hoverPos]);

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

    // Compute waveform amplitude peaks
    computeWaveform(selectedFile);

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
        if (data.fallback_notice) setFallbackNotice(data.fallback_notice);
        else setFallbackNotice(null);
        if (data.timing_source) setTimingSource(data.timing_source);
        else setTimingSource(null);
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
      audioRef.current.currentTime = Math.max(0, seconds);
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (audioRef.current.paused) {
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    } else {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const handleWaveformClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const effDuration = duration || (audioRef.current?.duration ?? 0);
    seekTo(ratio * effDuration);
  };

  const handleWaveformMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const ratio = x / rect.width;
    const effDuration = duration || (audioRef.current?.duration ?? 0);
    setHoverPos(x);
    setHoverTime(ratio * effDuration);
  };

  const handleWaveformMouseLeave = () => {
    setHoverPos(null);
    setHoverTime(null);
  };

  const formatDisplayTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = Math.floor(secs % 60);
    const ms = Math.floor((secs % 1) * 100);
    return `${mins.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
  };

  const getSegmentWords = (seg: LyricsSegment): LyricsWordTiming[] => {
    if (seg.words && seg.words.length > 0) return seg.words;
    const tokens = seg.text.trim().split(/\s+/).filter(Boolean);
    if (tokens.length === 0) return [];
    const dur = Math.max(0.05, seg.end - seg.start);
    const step = dur / tokens.length;
    return tokens.map((word, i) => ({
      word,
      start: Number((seg.start + i * step).toFixed(3)),
      end: Number((seg.start + (i + 1) * step).toFixed(3)),
    }));
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
    lrc += `[by:VOICE AI Studio]\r\n\r\n`;

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

  const generateASSContent = () => {
    const formatASSTime = (seconds: number) => {
      const centis = Math.round(Math.max(0, seconds) * 100);
      const cs = centis % 100;
      const totalSec = Math.floor(centis / 100);
      const s = totalSec % 60;
      const totalMin = Math.floor(totalSec / 60);
      const m = totalMin % 60;
      const h = Math.floor(totalMin / 60);
      return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}.${cs.toString().padStart(2, "0")}`;
    };

    let ass = "[Script Info]\r\n";
    ass += `; Script generated by VOICE App Studio\r\n`;
    ass += `Title: ${title || "Karaoke"}\r\n`;
    ass += `ScriptType: v4.00+\r\n`;
    ass += `WrapStyle: 0\r\n`;
    ass += `ScaledBorderAndShadow: yes\r\n`;
    ass += `PlayResX: 1920\r\n`;
    ass += `PlayResY: 1080\r\n\r\n`;
    ass += `[V4+ Styles]\r\n`;
    ass += `Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\r\n`;
    ass += `Style: Default,Arial,48,&H0000FFFF,&H00FFFFFF,&H00101010,&H60000000,1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1\r\n`;
    ass += `Style: Karaoke,Arial,52,&H0000FFFF,&H00FFFFFF,&H00101010,&H60000000,1,0,0,0,100,100,1,0,1,3.5,2.5,2,40,40,70,1\r\n\r\n`;
    ass += `[Events]\r\n`;
    ass += `Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\r\n`;

    segments.forEach((s) => {
      const startStr = formatASSTime(s.start);
      const endStr = formatASSTime(s.end);
      if (s.words && s.words.length > 0) {
        let karaokeText = "";
        let prevEnd = s.start;
        s.words.forEach((w) => {
          const leadIn = w.start - prevEnd;
          if (leadIn > 0.05) {
            karaokeText += `{\\k${Math.round(leadIn * 100)}}`;
          }
          const durCs = Math.max(1, Math.round((w.end - w.start) * 100));
          karaokeText += `{\\kf${durCs}}${w.word} `;
          prevEnd = w.end;
        });
        ass += `Dialogue: 0,${startStr},${endStr},Karaoke,,0,0,0,,${karaokeText.trim()}\r\n`;
      } else {
        const totalDurCs = Math.max(10, Math.round((s.end - s.start) * 100));
        ass += `Dialogue: 0,${startStr},${endStr},Default,,0,0,0,,{\\kf${totalDurCs}}${s.text.trim()}\r\n`;
      }
    });

    return ass;
  };

  const exportASS = () => {
    if (segments.length === 0) return;
    const ass = generateASSContent();
    const safeTitle = (title || "karaoke").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_");
    downloadFile(ass, `${safeTitle}.ass`, "text/plain;charset=utf-8");
  };

  const [isExportingVideo, setIsExportingVideo] = useState(false);
  const [videoExportError, setVideoExportError] = useState("");

  const exportVideo = async () => {
    if (!file || segments.length === 0) return;
    setIsExportingVideo(true);
    setVideoExportError("");
    try {
      const ass = generateASSContent();
      const fd = new FormData();
      fd.append("audio", file);
      fd.append("ass_content", ass);
      fd.append("title", (title || "karaoke").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_"));

      const res = await fetch("/api/lyrics/export-video", {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "FFmpeg видео экспорт амжилтгүй боллоо.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(title || "karaoke").replace(/[^a-zA-Z0-9_\-\u0400-\u04FF]/g, "_")}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setVideoExportError(err.message || "Видео үүсгэхэд алдаа гарлаа.");
    } finally {
      setIsExportingVideo(false);
    }
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
    setWaveformPeaks([]);
    setDuration(0);
    setCurrentTime(0);
    setIsPlaying(false);
    setFallbackNotice(null);
    setTimingSource(null);
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
            Дуу хөгжим болон видеоноос үгийн түвшний синхрончлолтой (.LRC) болон хадмал (.SRT / .VTT) автоматаар үүсгэх.
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
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • {duration > 0 ? formatDisplayTime(duration) : "Уншиж байна..."}
                  </div>
                </div>
              </div>

              <button
                className="btn-secondary"
                onClick={handleClear}
                style={{ fontSize: "0.82rem", padding: "6px 12px" }}
              >
                Өөр файл сонгох
              </button>
            </div>

            {/* Dynamic Audio Waveform & Interactive Timeline Scrub Bar */}
            {audioUrl && (
              <div
                style={{
                  background: "rgba(15, 23, 42, 0.65)",
                  borderRadius: "12px",
                  padding: "16px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                {/* Timeline Header with Player Controls */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.84rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <button
                      type="button"
                      onClick={togglePlay}
                      className="btn-primary"
                      style={{
                        padding: "6px 14px",
                        fontSize: "0.85rem",
                        borderRadius: "6px",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                      title={isPlaying ? "Түр зогсоох" : "Тоглуулах"}
                    >
                      <span>{isPlaying ? "⏸ Зогсоох" : "▶ Тоглуулах"}</span>
                    </button>
                    <span style={{ fontFamily: "monospace", color: "#a5b4fc", fontWeight: 600 }}>
                      {formatDisplayTime(currentTime)}
                    </span>
                    <span style={{ color: "var(--text-muted, #666)" }}>/</span>
                    <span style={{ fontFamily: "monospace", color: "var(--text-muted, #888)" }}>
                      {formatDisplayTime(duration || (audioRef.current?.duration ?? 0))}
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {hoverTime !== null && (
                      <span
                        style={{
                          fontFamily: "monospace",
                          fontSize: "0.78rem",
                          background: "rgba(99, 102, 241, 0.25)",
                          color: "#c7d2fe",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          border: "1px solid rgba(99, 102, 241, 0.4)",
                        }}
                      >
                        Товшиж шилжих: {formatDisplayTime(hoverTime)}
                      </span>
                    )}
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted, #777)" }}>
                      {waveformLoading ? "Долгион шинжилж байна..." : "Интерактив таймлайн"}
                    </span>
                  </div>
                </div>

                {/* Canvas Waveform Container */}
                <div
                  ref={waveformContainerRef}
                  onClick={handleWaveformClick}
                  onMouseMove={handleWaveformMouseMove}
                  onMouseLeave={handleWaveformMouseLeave}
                  style={{
                    position: "relative",
                    width: "100%",
                    height: "72px",
                    background: "rgba(0, 0, 0, 0.35)",
                    borderRadius: "8px",
                    cursor: "pointer",
                    overflow: "hidden",
                    border: "1px solid rgba(255, 255, 255, 0.05)",
                  }}
                  title="Хүссэн секундийн долгион дээр дарж шууд тоглуулах"
                >
                  <canvas
                    ref={waveformCanvasRef}
                    width={800}
                    height={72}
                    style={{ width: "100%", height: "100%", display: "block" }}
                  />
                </div>

                {/* Native Audio (Hidden or auxiliary) */}
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  onEnded={() => setIsPlaying(false)}
                  style={{ display: "none" }}
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
                  <option value="tiny">Tiny (Хамгийн хурдан, 39M)</option>
                  <option value="base">Base (Ердийн, 74M)</option>
                  <option value="small-q5_0">Small-q5_0 (Quantized, 244M • RTX Санал болгох)</option>
                  <option value="small">Small (Стандарт, 244M)</option>
                  <option value="medium">Medium (Өндөр нарийвчлал, 769M)</option>
                  <option value="large-v3-turbo">Large-v3-Turbo (Хамгийн нарийн, 809M)</option>
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
              <div style={{ color: "var(--text-muted, #888)", fontSize: "0.82rem", marginTop: "2px", display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <span>Нийт {segments.length} мөр тайлагдсан.</span>
                {timingSource === "whisper_token_timestamps" && (
                  <span style={{ fontSize: "0.75rem", color: "#34d399", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", padding: "1px 6px", borderRadius: "4px" }}>
                    🎯 Жинхэнэ Whisper Token Цаглавар
                  </span>
                )}
                {timingSource === "linear_interpolation_fallback" && (
                  <span style={{ fontSize: "0.75rem", color: "#fbbf24", background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.3)", padding: "1px 6px", borderRadius: "4px" }}>
                    ⚡ Линейн үгийн хуваалт
                  </span>
                )}
              </div>
            </div>

            {/* Export Toolbar */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <button className="btn-secondary" onClick={exportASS} title="Aegisub стандартын үгийн түвшний караоке субтитр" style={{ borderColor: "rgba(99, 102, 241, 0.4)", color: "var(--accent)" }}>
                ✨ Караоке (.ASS)
              </button>
              <button
                className="btn-secondary"
                onClick={exportVideo}
                disabled={isExportingVideo}
                title="FFmpeg ашиглан караоке субтитртэй MP4 видео экспортлох"
                style={{ borderColor: "rgba(16, 185, 129, 0.4)", color: "#10b981" }}
              >
                {isExportingVideo ? "🎬 Видео үүсгэж байна..." : "🎬 Видео (.MP4)"}
              </button>
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
            {videoExportError && (
              <div style={{ marginTop: "8px", color: "#ef4444", fontSize: "0.85rem" }}>
                ⚠️ {videoExportError}
              </div>
            )}
          </div>

          {fallbackNotice && (
            <div
              style={{
                padding: "8px 14px",
                background: "rgba(245, 158, 11, 0.12)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                color: "#fbbf24",
                borderRadius: "8px",
                fontSize: "0.85rem",
                marginBottom: "14px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>⚠️</span>
              <span>{fallbackNotice}</span>
            </div>
          )}

          {/* Synchronized Lyrics Container */}
          <div
            ref={listRef}
            style={{
              maxHeight: "520px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              paddingRight: "6px",
            }}
          >
            {segments.map((seg, idx) => {
              const isActive = activeSegmentIndex === idx;
              const words = getSegmentWords(seg);

              return (
                <div
                  key={idx}
                  data-index={idx}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    padding: "12px 14px",
                    borderRadius: "10px",
                    background: isActive ? "rgba(99, 102, 241, 0.18)" : "rgba(255, 255, 255, 0.02)",
                    border: isActive ? "1px solid rgba(99, 102, 241, 0.5)" : "1px solid rgba(255, 255, 255, 0.04)",
                    boxShadow: isActive ? "0 0 16px rgba(99, 102, 241, 0.2)" : "none",
                    transition: "all 0.22s cubic-bezier(0.4, 0, 0.2, 1)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
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
                        fontSize: isActive ? "1.02rem" : "0.95rem",
                        fontWeight: isActive ? 600 : 400,
                        transition: "font-size 0.2s, font-weight 0.2s",
                      }}
                    />

                    <div style={{ fontFamily: "monospace", fontSize: "0.78rem", color: "var(--text-muted, #777)", whiteSpace: "nowrap" }}>
                      {formatDisplayTime(seg.end)}
                    </div>
                  </div>

                  {/* Word-level Karaoke Sync Tokens */}
                  {words.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", paddingLeft: "4px" }}>
                      {words.map((w, wIdx) => {
                        const isWordActive = currentTime >= w.start && currentTime <= w.end;
                        return (
                          <button
                            key={wIdx}
                            type="button"
                            onClick={() => seekTo(w.start)}
                            title={`${w.word} • [${formatDisplayTime(w.start)} - ${formatDisplayTime(w.end)}] (Товшиж сонсох)`}
                            style={{
                              fontSize: "0.8rem",
                              padding: "2px 8px",
                              borderRadius: "5px",
                              cursor: "pointer",
                              border: isWordActive
                                ? "1px solid #818cf8"
                                : "1px solid rgba(255, 255, 255, 0.07)",
                              background: isWordActive
                                ? "linear-gradient(135deg, rgba(99, 102, 241, 0.45), rgba(168, 85, 247, 0.45))"
                                : "rgba(255, 255, 255, 0.03)",
                              color: isWordActive ? "#ffffff" : "var(--text-muted, #aaa)",
                              fontWeight: isWordActive ? 600 : 400,
                              boxShadow: isWordActive ? "0 0 12px rgba(99, 102, 241, 0.55)" : "none",
                              transform: isWordActive ? "scale(1.06)" : "scale(1)",
                              transition: "all 0.15s cubic-bezier(0.4, 0, 0.2, 1)",
                            }}
                          >
                            {w.word}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
