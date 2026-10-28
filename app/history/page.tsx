"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { HistoryStore } from "@/lib/history-store";
import type { TranscriptionRecord } from "@/lib/types";
import { useSettings } from "@/components/AppShell";
import {
  VolumeIcon,
  CopyIcon,
  CheckIcon,
  TrashIcon,
  SparklesIcon,
} from "@/components/Icons";

export default function HistoryPage() {
  const router = useRouter();
  const { settings, setWorkspaceText } = useSettings();
  const [records, setRecords] = useState<TranscriptionRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const update = () => setRecords(HistoryStore.getAll());
    update();
    const unsubscribe = HistoryStore.subscribe(update);
    return () => unsubscribe();
  }, []);

  const filtered = records.filter((r) =>
    r.text.toLowerCase().includes(searchQuery.toLowerCase().trim())
  );

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleOpenInWorkspace = (text: string) => {
    setWorkspaceText(text);
    router.push("/dashboard");
  };

  const handleDelete = (id: string) => {
    if (confirm("Энэ бичлэгийг устгах уу?")) {
      HistoryStore.remove(id);
    }
  };

  const handleClearAll = () => {
    if (confirm("Бүх түүхийг устгахдаа итгэлтэй байна уу?")) {
      HistoryStore.clear();
    }
  };

  const handlePlayTTS = async (id: string, text: string) => {
    if (!text.trim()) return;
    setPlayingId(id);

    try {
      const res = await fetch("/api/chimege/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          voiceId: settings.defaultVoiceId || "FEMALE3v2",
        }),
      });

      if (!res.ok) {
        throw new Error("TTS алдаа");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      audioRef.current.src = url;
      await audioRef.current.play();
    } catch {
      console.warn("TTS Play error");
    } finally {
      setPlayingId(null);
    }
  };

  return (
    <section className="page">
      <small>VOICE HISTORY</small>
      <h1>Түүх ба Архив</h1>
      <p>Өмнө нь таниулсан болон хадгалсан бүх ярианы бичвэрүүдээ эндээс удирдана.</p>

      <div className="history-controls">
        <input
          type="text"
          className="search-input"
          placeholder="Түүхээс хайх (Search transcripts)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <div className="history-actions" style={{ display: "flex", gap: "8px" }}>
          <button
            className="btn-secondary"
            onClick={() => HistoryStore.exportAsText()}
            disabled={records.length === 0}
            title="TXT файлаар татаж авах"
          >
            Export TXT
          </button>
          <button
            className="btn-secondary"
            onClick={() => HistoryStore.exportAsJSON()}
            disabled={records.length === 0}
            title="JSON файлаар татаж авах"
          >
            Export JSON
          </button>
          {records.length > 0 && (
            <button className="btn-danger" onClick={handleClearAll}>
              <TrashIcon width={14} height={14} />
              <span>Бүгдийг устгах</span>
            </button>
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-page" style={{ border: "1px dashed var(--border)", borderRadius: "24px", padding: "48px 24px" }}>
          <div style={{ color: "var(--muted)", opacity: 0.6, marginBottom: "12px" }}>
            <SparklesIcon width={48} height={48} />
          </div>
          <h2 style={{ fontSize: "18px", margin: "0 0 8px" }}>
            {searchQuery
              ? "Хайлтад тохирох бичлэг олдсонгүй."
              : "Одоогоор хадгалсан бичлэг байхгүй."}
          </h2>
          <p style={{ fontSize: "13px" }}>
            {searchQuery
              ? "Өөр түлхүүр үгээр хайж үзнэ үү."
              : "Шинэ яриа таниулсны дараа таны бичвэрүүд энд автоматаар хадгалагдана."}
          </p>
        </div>
      ) : (
        <div className="history-list">
          {filtered.map((record) => {
            const dateStr = new Date(record.timestamp).toLocaleString("mn-MN", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <article key={record.id} className="history-card">
                <header className="history-card-header">
                  <div className="history-meta-group" style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span className="stats-badge" style={{ color: "var(--accent)" }}>
                      {record.language.toUpperCase()}
                    </span>
                    <span className="stats-badge">
                      {record.engine || "Voice AI"}
                    </span>
                    {record.durationSeconds > 0 && (
                      <span className="stats-badge">
                        {record.durationSeconds} сек
                      </span>
                    )}
                    <span className="stats-badge">
                      {record.wordCount} үг
                    </span>
                  </div>
                  <time style={{ fontSize: "12px", color: "var(--muted)" }}>{dateStr}</time>
                </header>

                <p className="history-card-text">{record.text}</p>

                <footer className="history-card-footer">
                  <button
                    className="btn-secondary"
                    onClick={() => handlePlayTTS(record.id, record.text)}
                    disabled={playingId === record.id}
                  >
                    <VolumeIcon width={14} height={14} />
                    <span>{playingId === record.id ? "Уншиж байна..." : "Сонсох"}</span>
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => handleOpenInWorkspace(record.text)}
                  >
                    Workspace-д нээх
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => handleCopy(record.id, record.text)}
                  >
                    {copiedId === record.id ? <CheckIcon width={14} height={14} /> : <CopyIcon width={14} height={14} />}
                    <span>{copiedId === record.id ? "Хуулагдлаа!" : "Хуулах"}</span>
                  </button>
                  <button
                    className="btn-danger"
                    onClick={() => handleDelete(record.id)}
                  >
                    <TrashIcon width={14} height={14} />
                    <span>Устгах</span>
                  </button>
                </footer>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
