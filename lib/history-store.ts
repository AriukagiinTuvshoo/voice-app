import type { TranscriptionRecord } from "./types";

const STORAGE_KEY = "voice-transcription-history";

export class HistoryStore {
  static getAll(): TranscriptionRecord[] {
    if (typeof window === "undefined") return [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  static add(item: Omit<TranscriptionRecord, "id" | "timestamp"> & { id?: string; timestamp?: number }): TranscriptionRecord {
    const records = this.getAll();
    const newRecord: TranscriptionRecord = {
      id: item.id || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : "rec_" + Date.now()),
      text: item.text,
      rawText: item.rawText,
      timestamp: item.timestamp || Date.now(),
      durationSeconds: item.durationSeconds || 0,
      language: item.language,
      engine: item.engine || "voice",
      wordCount: item.wordCount || (item.text.trim() ? item.text.trim().split(/\s+/).length : 0),
      charCount: item.charCount || item.text.length,
    };

    records.unshift(newRecord);
    // Cap history at 200 records to prevent storage quota issues
    const trimmed = records.slice(0, 200);
    this.saveAll(trimmed);
    this.notify();
    return newRecord;
  }

  static remove(id: string): void {
    const records = this.getAll().filter((r) => r.id !== id);
    this.saveAll(records);
    this.notify();
  }

  static clear(): void {
    if (typeof window === "undefined") return;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
    this.notify();
  }

  static search(query: string): TranscriptionRecord[] {
    const q = query.toLowerCase().trim();
    if (!q) return this.getAll();
    return this.getAll().filter((r) => r.text.toLowerCase().includes(q));
  }

  static exportAsJSON(): void {
    const data = JSON.stringify(this.getAll(), null, 2);
    downloadFile(data, `voice-history-${new Date().toISOString().slice(0, 10)}.json`, "application/json");
  }

  static exportAsText(): void {
    const items = this.getAll();
    const txt = items
      .map((item) => {
        const date = new Date(item.timestamp).toLocaleString();
        return `[${date}] (${item.language.toUpperCase()}, ${item.durationSeconds}s)\n${item.text}\n`;
      })
      .join("\n----------------------------------------\n\n");
    downloadFile(txt, `voice-history-${new Date().toISOString().slice(0, 10)}.txt`, "text/plain");
  }

  static exportAsSRT(): void {
    const items = this.getAll();
    let currentOffset = 1.0;
    const srtLines: string[] = [];

    items.forEach((item, index) => {
      const dur = item.durationSeconds > 0 ? item.durationSeconds : Math.max(2.5, item.text.length * 0.08);
      const startT = currentOffset;
      const endT = currentOffset + dur;
      currentOffset = endT + 0.8;

      const formatTime = (sec: number) => {
        const hrs = Math.floor(sec / 3600).toString().padStart(2, "0");
        const mins = Math.floor((sec % 3600) / 60).toString().padStart(2, "0");
        const s = Math.floor(sec % 60).toString().padStart(2, "0");
        const ms = Math.floor((sec % 1) * 1000).toString().padStart(3, "0");
        return `${hrs}:${mins}:${s},${ms}`;
      };

      srtLines.push(String(index + 1));
      srtLines.push(`${formatTime(startT)} --> ${formatTime(endT)}`);
      srtLines.push(item.text.trim());
      srtLines.push("");
    });

    const srt = srtLines.join("\r\n");
    downloadFile(srt, `voice-subtitles-${new Date().toISOString().slice(0, 10)}.srt`, "text/plain");
  }

  private static saveAll(records: TranscriptionRecord[]) {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch {}
  }

  private static listeners: Set<() => void> = new Set();

  static subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private static notify() {
    this.listeners.forEach((fn) => fn());
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("voice-history-updated"));
    }
  }
}

function downloadFile(content: string, filename: string, mimeType: string) {
  if (typeof window === "undefined") return;
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
