import { MONGOLIAN_FILLER_WORDS } from "./constants";
import type { ProcessingMode } from "./types";

const CODESWITCH_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bконтрол\s+альт\b/giu, "Ctrl+Alt"],
  [/\bконтрол\s+алт\b/giu, "Ctrl+Alt"],
  [/\bвойс\s+студио\b/giu, "VoiceStudio"],
  [/\bвойс\s+флоу\b/giu, "Voice Flow"],
  [/\bдуудлага\s+флоу\b/giu, "Duudlaga Flow"],
  [/\bнекст\s+жэй\s*эс\b/giu, "Next.js"],
  [/\bнекст\s+жи\s*эс\b/giu, "Next.js"],
  [/\bнекст\s+жс\b/giu, "Next.js"],
  [/\bнод\s+жэй\s*эс\b/giu, "Node.js"],
  [/\bтайп\s*скрипт\b/giu, "TypeScript"],
  [/\bжава\s*скрипт\b/giu, "JavaScript"],
  [/\bчат\s*жи\s*пи\s*ти\b/giu, "ChatGPT"],
  [/\bчат\s*жпт\b/giu, "ChatGPT"],
  [/\bжемини\s+плас\b/giu, "Gemini Plus"],
  [/\bаригато\s+гозаймас\b/giu, "ありがとうございます (Arigatou gozaimasu)"],
  [/\bаригато\b/giu, "ありがとう (Arigatou)"],
  [/\bконничива\b/giu, "こんにちは (Konnichiwa)"],
  [/\bконичива\b/giu, "こんにちは (Konnichiwa)"],
  [/\bохаёо\b/giu, "おはよう (Ohayou)"],
  [/\bсумимасэн\b/giu, "すみません (Sumimasen)"],
  [/\bсумимасен\b/giu, "すみません (Sumimasen)"],
  [/\bсаёонара\b/giu, "さようなら (Sayounara)"],
  [/\bсугой\b/giu, "すごい (Sugoi)"],
  [/\bкавай\b/giu, "かわいい (Kawaii)"],
  [/\bсэнсэй\b/giu, "先生 (Sensei)"],
  [/\bфэйсбүүк/giu, "Facebook"],
  [/\bфейсбүүк/giu, "Facebook"],
  [/\bинстаграм/giu, "Instagram"],
  [/\bтелеграм/giu, "Telegram"],
  [/\bюүтүб/giu, "YouTube"],
  [/\bворд\b/giu, "Word"],
  [/\bэксел\b/giu, "Excel"],
  [/\bвиндоус\b/giu, "Windows"],
  [/\bайфон\b/giu, "iPhone"],
  [/\bандроид\b/giu, "Android"],
  [/\bпайтон\b/giu, "Python"],
  [/\bпитон\b/giu, "Python"],
  [/\bреакт\b/giu, "React"],
  [/\bжемини\b/giu, "Gemini"],
  [/\bклод\b/giu, "Claude"],
  [/\bантигравити\b/giu, "Antigravity"],
];

export function restoreCodeSwitchingTerms(text: string): string {
  let out = text;
  for (const [pattern, replacement] of CODESWITCH_REPLACEMENTS) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

/**
 * Clean up and process text according to processingMode and settings.
 */
export function processTranscriptText(
  text: string,
  options: {
    mode: ProcessingMode;
    autoPunctuation?: boolean;
    removeFillers?: boolean;
    language?: string;
  }
): string {
  if (!text) return "";
  let result = restoreCodeSwitchingTerms(text.trim());

  if (options.mode === "raw") {
    return result;
  }

  // 1. Remove filler words if requested or if clean/polished mode
  const shouldRemoveFillers = options.removeFillers || options.mode === "clean" || options.mode === "polished";
  if (shouldRemoveFillers && options.language !== "en" && options.language !== "ja") {
    result = removeMongolianFillers(result);
  }

  // 2. Standard formatting (capitalization & punctuation spacing)
  result = normalizePunctuationAndSpacing(result);

  if (options.autoPunctuation !== false) {
    result = capitalizeSentences(result);
    // Ensure final punctuation if it looks like a complete sentence
    if (result.length > 5 && !/[.!?…。！？]$/.test(result)) {
      result += ".";
    }
  }

  // 3. Polished formatting (paragraphs / readability)
  if (options.mode === "polished") {
    result = polishText(result);
  }

  return result;
}

/**
 * Capitalize first letter after start or sentence terminators.
 */
export function capitalizeSentences(text: string): string {
  return text.replace(/(^|[.!?…]\s+)([\p{L}])/gu, (_, prefix, letter) => {
    return prefix + letter.toUpperCase();
  });
}

/**
 * Remove common filler words from Mongolian Cyrillic speech.
 */
export function removeMongolianFillers(text: string): string {
  let cleaned = text;
  for (const filler of MONGOLIAN_FILLER_WORDS) {
    // Match filler word as a standalone token or bounded by punctuation/spaces
    const regex = new RegExp(`(?<=[^\\p{L}]|^)${filler}(?=[^\\p{L}]|$)`, "giu");
    cleaned = cleaned.replace(regex, "");
  }
  return normalizePunctuationAndSpacing(cleaned);
}

/**
 * Normalize whitespace, comma/period spacing.
 */
export function normalizePunctuationAndSpacing(text: string): string {
  return text
    .replace(/\s+/g, " ") // collapse multiple spaces
    .replace(/\s+([,.:;!?])/g, "$1") // fix space before punctuation
    .replace(/([,:;!?])(?=[^\s,:;!?])/gu, "$1 ") // add space after punctuation (excluding dot in Next.js/numbers)
    .replace(/\s{2,}/g, " ")
    .trim();
}

/**
 * Polish text for better readability:
 * Break into readable paragraphs if long, format lists if present.
 */
function polishText(text: string): string {
  const sentences = text.match(/[^.!?…]+[.!?…]+/g) || [text];
  if (sentences.length > 4) {
    // Group into paragraphs of 2-3 sentences
    const paragraphs: string[] = [];
    let currentPara: string[] = [];
    for (const s of sentences) {
      currentPara.push(s.trim());
      if (currentPara.length >= 3) {
        paragraphs.push(currentPara.join(" "));
        currentPara = [];
      }
    }
    if (currentPara.length > 0) {
      paragraphs.push(currentPara.join(" "));
    }
    return paragraphs.join("\n\n");
  }
  return text;
}

/**
 * Compute stats for a text: word count and character count.
 */
export function getTextStats(text: string): { wordCount: number; charCount: number } {
  const trimmed = text.trim();
  const wordCount = trimmed ? trimmed.split(/\s+/).length : 0;
  const charCount = text.length;
  return { wordCount, charCount };
}
