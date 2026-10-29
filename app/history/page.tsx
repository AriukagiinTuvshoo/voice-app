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
  StarIcon,
} from "@/components/Icons";

interface SummaryData {
  summary: string;
  key_points: string[];
  action_items: string[];
  decisions: string[];
}

export default function HistoryPage() {
  const router = useRouter();
  const { settings, setWorkspaceText } = useSettings();
  const [records, setRecords] = useState<TranscriptionRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "starred">("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [summarizingId, setSummarizingId] = useState<string | null>(null);
  const [expandedSummaries, setExpandedSummaries] = useState<Record<string, SummaryData>>({});
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const update = () => setRecords(HistoryStore.getAll());
    update();
    const unsubscribe = HistoryStore.subscribe(update);
    return () => unsubscribe();
  }, []);

  const starredCount = records.filter((r) => Boolean(r.starred)).length;

  const filtered = records
    .filter((r) => (filterMode === "starred" ? Boolean(r.starred) : true))
    .filter((r) => r.text.toLowerCase().includes(searchQuery.toLowerCase().trim()));

  const handleToggleStar = (id: string) => {
    HistoryStore.toggleStar(id);
  };

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
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
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

  const handleSummarize = async (id: string, text: string) => {
    if (expandedSummaries[id]) {
      // Toggle collapse
      setExpandedSummaries((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }

    setSummarizingId(id);
    try {
      const res = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (res.ok) {
        const data = await res.json();
        setExpandedSummaries((prev) => ({ ...prev, [id]: data }));
      }
    } catch (e) {
      console.error("Summarize error", e);
    } finally {
      setSummarizingId(null);
    }
  };

  return (
    <section className="page">
      <header className="page-header" style={{ alignItems: "flex-start", gap: "16px" }}>
        <div>
          <h2>Ярианы түүх</h2>
          <p>Таны VOICE систем дээр таниулсан бичвэрүүдийн жагсаалт ба AI тойм.</p>
        </div>

        {records.length > 0 && (
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
            <button
              className="btn-danger"
              onClick={handleClearAll}
              style={{ fontSize: "12px", padding: "6px 12px" }}
            >
              <TrashIcon width={14} height={14} />
              <span>Түүх цэвэрлэх</span>
            </button>
          </div>
        )}
      </header>

      {/* Search & Filter Toolbar */}
      {records.length > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
            marginBottom: "16px",
          }}
        >
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              className={`btn-secondary ${filterMode === "all" ? "active" : ""}`}
              onClick={() => setFilterMode("all")}
              style={{
                fontSize: "12px",
                padding: "6px 14px",
                background: filterMode === "all" ? "var(--primary, #6366f1)" : undefined,
                color: filterMode === "all" ? "#fff" : undefined,
                borderColor: filterMode === "all" ? "var(--primary, #6366f1)" : undefined,
              }}
            >
              Бүгд ({records.length})
            </button>
            <button
              className={`btn-secondary ${filterMode === "starred" ? "active" : ""}`}
              onClick={() => setFilterMode("starred")}
              style={{
                fontSize: "12px",
                padding: "6px 14px",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: filterMode === "starred" ? "#f59e0b" : undefined,
                color: filterMode === "starred" ? "#000" : undefined,
                borderColor: filterMode === "starred" ? "#f59e0b" : undefined,
              }}
            >
              <StarIcon width={14} height={14} filled={filterMode === "starred"} />
              <span>Онцолсон ({starredCount})</span>
            </button>
          </div>

          <div style={{ flex: 1, maxWidth: "340px", minWidth: "220px" }}>
            <input
              type="text"
              placeholder="Түүхээс хайх..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
              style={{
                width: "100%",
                padding: "7px 12px",
                fontSize: "13px",
                borderRadius: "8px",
              }}
            />
          </div>
        </div>
      )}

      {records.length === 0 || filtered.length === 0 ? (
        <div className="empty-state">
          <p>
            {records.length === 0
              ? "Одоогоор ярианы түүх байхгүй байна."
              : searchQuery
              ? "Өөр түлхүүр үгээр хайж үзнэ үү."
              : filterMode === "starred"
              ? "Түүхэн дэх одон дээр дарж чухал бичвэрүүдээ энд онцолж хадгална уу."
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
            const summary = expandedSummaries[record.id];

            return (
              <article key={record.id} className="history-card">
                <header className="history-card-header">
                  <div
                    className="history-meta-group"
                    style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}
                  >
                    <button
                      type="button"
                      onClick={() => handleToggleStar(record.id)}
                      title={record.starred ? "Онцолсноос хасах" : "Онцлох (Favorite)"}
                      style={{
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        color: record.starred ? "#f59e0b" : "var(--muted)",
                        padding: "2px 4px",
                        display: "inline-flex",
                        alignItems: "center",
                        borderRadius: "4px",
                      }}
                    >
                      <StarIcon width={16} height={16} filled={Boolean(record.starred)} />
                    </button>
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

                {/* AI Summary View */}
                {summary && (
                  <div
                    style={{
                      marginTop: "12px",
                      marginBottom: "12px",
                      padding: "14px 16px",
                      background: "rgba(99, 102, 241, 0.08)",
                      border: "1px solid rgba(99, 102, 241, 0.25)",
                      borderRadius: "10px",
                      fontSize: "0.88rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 600, color: "var(--primary, #6366f1)" }}>
                      <SparklesIcon width={16} height={16} />
                      <span>AI Дүгнэлт ба Хийх ажлууд</span>
                    </div>

                    {summary.summary && (
                      <div>
                        <strong>Товч тойм:</strong> {summary.summary}
                      </div>
                    )}

                    {summary.key_points && summary.key_points.length > 0 && (
                      <div>
                        <strong>📌 Гол санаанууд:</strong>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                          {summary.key_points.map((pt, idx) => (
                            <li key={idx} style={{ marginTop: "2px" }}>{pt}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {summary.decisions && summary.decisions.length > 0 && (
                      <div>
                        <strong>🎯 Шийдвэрүүд:</strong>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                          {summary.decisions.map((dec, idx) => (
                            <li key={idx} style={{ marginTop: "2px", color: "#10b981" }}>{dec}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {summary.action_items && summary.action_items.length > 0 && (
                      <div>
                        <strong>✅ Хийх ажлууд (Action Items):</strong>
                        <ul style={{ listStyleType: "none", margin: "4px 0 0 0", padding: 0 }}>
                          {summary.action_items.map((act, idx) => (
                            <li key={idx} style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
                              <input type="checkbox" defaultChecked={false} style={{ cursor: "pointer" }} />
                              <span>{act}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <footer className="history-card-footer">
                  <button
                    className="btn-secondary"
                    onClick={() => handleSummarize(record.id, record.text)}
                    disabled={summarizingId === record.id}
                    title="Гол санаа, шийдвэр, хийх ажлыг автоматаар ялгаж харах"
                  >
                    <SparklesIcon width={14} height={14} />
                    <span>
                      {summarizingId === record.id
                        ? "Товчилж байна..."
                        : summary
                        ? "Товчлол хаах"
                        : "AI Товчлол"}
                    </span>
                  </button>
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
