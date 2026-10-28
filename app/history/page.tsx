"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { HistoryStore } from "@/lib/history-store";
import type { TranscriptionRecord } from "@/lib/types";
import { useSettings } from "@/components/AppShell";

export default function HistoryPage() {
  const router = useRouter();
  const { setWorkspaceText } = useSettings();
  const [records, setRecords] = useState<TranscriptionRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

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

  return (
    <section className="page">
      <small>VOICE HISTORY</small>
      <h1>Түүх</h1>
      <p>Өмнө хадгалсан бичлэг болон transcript-уудаа эндээс удирдана.</p>

      <div className="history-controls">
        <input
          type="text"
          className="search-input"
          placeholder="Түүхээс хайх (Search transcripts)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <div className="history-actions">
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
              Бүгдийг устгах
            </button>
          )}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-page">
          <div>◌</div>
          <h2>
            {searchQuery
              ? "Хайлтад тохирох бичлэг олдсонгүй."
              : "Одоогоор хадгалсан бичлэг байхгүй."}
          </h2>
          <p>
            {searchQuery
              ? "Өөр түлхүүр үгээр хайна уу."
              : "Шинэ бичлэг хийсний дараа энд автоматаар хадгалагдана."}
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
              second: "2-digit",
            });

            return (
              <article key={record.id} className="history-card">
                <header className="history-card-header">
                  <div className="history-meta-group">
                    <span className="stats-badge">
                      {record.language.toUpperCase()}
                    </span>
                    <span className="stats-badge">
                      {record.engine || "voice"}
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
                  <time>{dateStr}</time>
                </header>

                <p className="history-card-text">{record.text}</p>

                <footer className="history-card-footer">
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
                    {copiedId === record.id ? "Хуулагдлаа!" : "Copy"}
                  </button>
                  <button
                    className="btn-danger"
                    onClick={() => handleDelete(record.id)}
                  >
                    Устгах
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
