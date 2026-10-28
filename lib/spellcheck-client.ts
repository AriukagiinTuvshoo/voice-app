import type { SpellCheckResult } from "./types";

export class SpellCheckClient {
  /**
   * Run full spellcheck and suggestion retrieval on text.
   */
  static async check(text: string): Promise<SpellCheckResult> {
    if (!text || text.trim().length < 2) {
      return { text, misspelled: [], suggestions: {} };
    }

    try {
      const res = await fetch("/api/spellcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, action: "full" }),
      });

      if (!res.ok) {
        throw new Error(`Spellcheck request failed: ${res.statusText}`);
      }

      const data = await res.json();
      return {
        text: data.text || text,
        misspelled: Array.isArray(data.misspelled) ? data.misspelled : [],
        suggestions: data.suggestions || {},
      };
    } catch (err) {
      console.error("Spellcheck error:", err);
      return { text, misspelled: [], suggestions: {} };
    }
  }

  /**
   * Auto-correct text using best candidate suggestions.
   */
  static async autoCorrect(text: string): Promise<{ correctedText: string; fixesCount: number }> {
    const result = await this.check(text);
    if (!result.misspelled || result.misspelled.length === 0) {
      return { correctedText: text, fixesCount: 0 };
    }

    let corrected = text;
    let fixesCount = 0;

    for (const word of result.misspelled) {
      const bestCandidate = result.suggestions[word]?.[0];
      if (bestCandidate && bestCandidate !== word) {
        // Regex word boundary for Cyrillic letters
        const regex = new RegExp(`(?<=[^\\p{L}]|^)${escapeRegExp(word)}(?=[^\\p{L}]|$)`, "gu");
        if (regex.test(corrected)) {
          corrected = corrected.replace(regex, bestCandidate);
          fixesCount++;
        }
      }
    }

    return { correctedText: corrected, fixesCount };
  }
}

function escapeRegExp(string: string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
