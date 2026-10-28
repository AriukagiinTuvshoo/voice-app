import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

const BASE = "https://spellcheck.mn/cms-client/modules/spellchecker";
const MOD = BigInt("10000000008");
const HEADERS = {
  "content-type": "application/json",
  origin: "https://spellcheck.mn",
  referer: "https://spellcheck.mn/",
  accept: "application/json, text/plain, */*",
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceApp/1.0",
};

/**
 * Request key algorithm from spellcheck.mn ($encrypt function).
 * n = (sum of (codePoint + 1) for each char) mod 10000000008
 * key = sha256_hex(String(n))
 */
function encryptSpellCheckKey(text: string): string {
  let n = BigInt(0);
  for (const ch of text) {
    const codePoint = ch.codePointAt(0) ?? 0;
    n += BigInt(codePoint) + BigInt(1);
    n %= MOD;
  }
  return createHash("sha256").update(String(n), "utf8").digest("hex");
}

async function postToSpellCheck(endpoint: string, payload: Record<string, unknown>) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const res = await fetch(`${BASE}/${endpoint}`, {
      method: "POST",
      headers: HEADERS,
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    const body = await res.text();
    if (!res.ok) {
      throw new Error(`${endpoint} status ${res.status}: ${body}`);
    }
    const trimmed = body.trim().replace(/^"|"$/g, "");
    if (trimmed === "Invalid hash.") {
      throw new Error(`Server rejected key for ${endpoint} (Invalid hash)`);
    }
    try {
      return JSON.parse(body);
    } catch {
      return body;
    }
  } catch (err: unknown) {
    clearTimeout(timer);
    throw err;
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const text: string = body.text || "";
    const action: "check" | "suggest" | "full" = body.action || "full";
    const word: string = body.word || "";

    if (action === "suggest" && word) {
      const key = encryptSpellCheckKey(word);
      const suggestions = await postToSpellCheck("suggest", { word, key });
      return NextResponse.json({ word, suggestions: Array.isArray(suggestions) ? suggestions : [] });
    }

    if (!text || text.trim().length < 2) {
      return NextResponse.json({
        text,
        misspelled: [],
        suggestions: {},
        correctedText: text,
      });
    }

    // 1. Check for misspelled words
    const checkKey = encryptSpellCheckKey(text);
    const checkRes = await postToSpellCheck("check", { text, key: checkKey });
    const rawMisspelled: string[] = Array.isArray(checkRes) ? checkRes : [];
    const misspelled = Array.from(new Set(rawMisspelled.map((w) => w.replaceAll("-", ""))));

    if (misspelled.length === 0 || action === "check") {
      return NextResponse.json({
        text,
        misspelled,
        suggestions: {},
        correctedText: text,
      });
    }

    // 2. Fetch suggestions for each unique misspelled word
    const suggestions: Record<string, string[]> = {};
    await Promise.all(
      misspelled.map(async (mWord) => {
        try {
          const sKey = encryptSpellCheckKey(mWord);
          const sRes = await postToSpellCheck("suggest", { word: mWord, key: sKey });
          suggestions[mWord] = Array.isArray(sRes) ? sRes : [];
        } catch {
          suggestions[mWord] = [];
        }
      })
    );

    // 3. Simple auto-correction candidate (first candidate if available)
    let correctedText = text;
    for (const mWord of misspelled) {
      const cand = suggestions[mWord]?.[0];
      if (cand) {
        // Regex replace word boundaries for Cyrillic
        const regex = new RegExp(`(?<=[^\\p{L}]|^)${escapeRegExp(mWord)}(?=[^\\p{L}]|$)`, "gu");
        correctedText = correctedText.replace(regex, cand);
      }
    }

    return NextResponse.json({
      text,
      misspelled,
      suggestions,
      correctedText,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Spellcheck error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
