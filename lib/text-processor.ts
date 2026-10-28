import { MONGOLIAN_FILLER_WORDS } from "./constants";
import type { ProcessingMode } from "./types";

const CODESWITCH_REPLACEMENTS: Array<[RegExp, string]> = [
  // Mongolian proper name & phrase phonetic fixes
  [/\bнамайг\s+түшин\s*тулга?\b/giu, "намайг Түвшинтулга"],
  [/\bнамайг\s+түвшин\s*тулга?\b/giu, "намайг Түвшинтулга"],
  [/\bтүшин\s*тулга?\b/giu, "Түвшинтулга"],
  [/\bтүвшин\s+тул\b/giu, "Түвшинтулга"],

  // Conversational English phrases spoken mid-sentence
  [/\bмай\s+нэйм\s+из\b/giu, "my name is"],
  [/\bмай\s+нэм\s+из\b/giu, "my name is"],
  [/\bмай\s+нэймс\b/giu, "my name is"],
  [/\bмай\s+нэмс\b/giu, "my name is"],
  [/\bмай\s+нэйм\s+с\b/giu, "my name is"],
  [/\bмайн\s+нэйм\s+из\b/giu, "my name is"],
  [/\bмайн\s+нэмс\b/giu, "my name is"],
  [/\bми\s+нэйм\s+из\b/giu, "my name is"],
  [/\bмай\s+нэйм\b/giu, "my name"],
  [/\bмай\s+нэм\b/giu, "my name"],
  [/\bват\s+из\s+юур\s+нэйм\b/giu, "what is your name"],
  [/\bватс\s+юур\s+нэйм\b/giu, "what's your name"],
  [/\bай\s+эм\s+фром\s+монголиа\b/giu, "I am from Mongolia"],
  [/\bайм\s+фром\s+монголиа\b/giu, "I'm from Mongolia"],
  [/\bай\s+эм\s+фром\b/giu, "I am from"],
  [/\bай\s+эм\b/giu, "I am"],
  [/\bхау\s+ар\s+юу\b/giu, "how are you"],
  [/\bхау\s+ар\s+юү\b/giu, "how are you"],
  [/\bнайс\s+ту\s+мит\s+юу\b/giu, "nice to meet you"],
  [/\bнайс\s+тү\s+мит\s+юү\b/giu, "nice to meet you"],
  [/\bтэнк\s+юу\s+вэри\s+мач\b/giu, "thank you very much"],
  [/\bтэнк\s+юу\b/giu, "thank you"],
  [/\bтэнк\s+юү\b/giu, "thank you"],
  [/\bэкскюз\s+ми\b/giu, "excuse me"],
  [/\bай\s+донт\s+ноу\b/giu, "I don't know"],
  [/\bай\s+тинк\b/giu, "I think"],
  [/\bай\s+лав\s+юу\b/giu, "I love you"],
  [/\bлетс\s+гоу\b/giu, "let's go"],
  [/\bлэтс\s+гоу\b/giu, "let's go"],
  [/\bгуд\s+морнинг\b/giu, "good morning"],
  [/\bгүүд\s+морнинг\b/giu, "good morning"],
  [/\bгуд\s+найт\b/giu, "good night"],
  [/\bгуд\s+бай\b/giu, "goodbye"],
  [/\bбай\s+бай\b/giu, "bye bye"],
  [/\bхэллоу\s+эвриван\b/giu, "hello everyone"],
  [/\bхэллоу\s+ворлд\b/giu, "hello world"],
  [/\bхэллоу\b/giu, "hello"],
  [/\bхэлоу\b/giu, "hello"],
  [/\bплийз\b/giu, "please"],
  [/\bсорри\b/giu, "sorry"],

  // Multi-word tech & app phrases
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

  // Japanese phrases & pronouns (Cyrillic & Romaji phonetic -> Authentic Japanese Kanji/Kana)
  [/\bваташи\s*но\s+намаэ\s*ва\b/giu, "私の名前は"],
  [/\bваташи\s*но\s+намай\s*ва\b/giu, "私の名前は"],
  [/\bwatashi\s*no\s+namae\s*wa\b/giu, "私の名前は"],
  [/\bваташи\s*но\b/giu, "私の"],
  [/\bваташино\b/giu, "私の"],
  [/\bва\s+та\s+ши\s+но\b/giu, "私の"],
  [/\bwatashi\s*no\b/giu, "私の"],
  [/\bваташи\s*ва\b/giu, "私は"],
  [/\bваташива\b/giu, "私は"],
  [/\bwatashi\s*wa\b/giu, "私は"],
  [/\bваташи\b/giu, "私"],
  [/\bwatashi\b/giu, "私"],
  [/\bбоку\s*но\s+намаэ\s*ва\b/giu, "僕の名前は"],
  [/\bбоку\s*но\b/giu, "僕の"],
  [/\bboku\s*no\b/giu, "僕の"],
  [/\bбоку\s*ва\b/giu, "僕は"],
  [/\bboku\s*wa\b/giu, "僕は"],
  [/\bорэ\s*но\b/giu, "俺の"],
  [/\bорэ\s*ва\b/giu, "俺は"],
  [/\bаната\s*но\b/giu, "あなたの"],
  [/\banata\s*no\b/giu, "あなたの"],
  [/\bаната\s*ва\b/giu, "あなたは"],
  [/\banata\s*wa\b/giu, "あなたは"],
  [/\bкоре\s*ва\b/giu, "これは"],
  [/\bkore\s*wa\b/giu, "これは"],
  [/\bсоре\s*ва\b/giu, "それは"],
  [/\bsore\s*wa\b/giu, "それは"],
  [/\bаре\s*ва\b/giu, "あれは"],
  [/\bare\s*wa\b/giu, "あれは"],
  [/\bхажимэмашитэ\b/giu, "初めまして"],
  [/\bхажимэмаштэ\b/giu, "初めまして"],
  [/\bхажимемашите\b/giu, "初めまして"],
  [/\bhajimemashite\b/giu, "初めまして"],
  [/\bёрошикү\s+онэгайшимас\b/giu, "よろしくお願いします"],
  [/\bёрошику\s+онегайшимас\b/giu, "よろしくお願いします"],
  [/\byoroshiku\s+onegaishimasu\b/giu, "よろしくお願いします"],
  [/\bёрошикү\b/giu, "よろしく"],
  [/\bёрошику\b/giu, "よろしく"],
  [/\byoroshiku\b/giu, "よろしく"],
  [/\bонэгайшимас\b/giu, "お願いします"],
  [/\bонегайшимас\b/giu, "お願いします"],
  [/\bonegaishimasu\b/giu, "お願いします"],
  [/\bаригато\s+гозаймас\b/giu, "ありがとうございます"],
  [/\barigatou?\s+gozaimasu?\b/giu, "ありがとうございます"],
  [/\bаригато\b/giu, "ありがとう"],
  [/\barigatou?\b/giu, "ありがとう"],
  [/\bконничива\b/giu, "こんにちは"],
  [/\bконичива\b/giu, "こんにちは"],
  [/\bkonnichiwa\b/giu, "こんにちは"],
  [/\bконбанва\b/giu, "こんばんは"],
  [/\bkonbanwa\b/giu, "こんばんは"],
  [/\bохаёо\s+гозаймас\b/giu, "おはようございます"],
  [/\bohayou?\s+gozaimasu?\b/giu, "おはようございます"],
  [/\bохаёо\b/giu, "おはよう"],
  [/\bohayou?\b/giu, "おはよう"],
  [/\bсумимасэн\b/giu, "すみません"],
  [/\bсумимасен\b/giu, "すみません"],
  [/\bsumimasen\b/giu, "すみません"],
  [/\bгомэннасай\b/giu, "ごめんなさい"],
  [/\bгоменнасай\b/giu, "ごめんなさい"],
  [/\bgomennasai\b/giu, "ごめんなさい"],
  [/\bсаёонара\b/giu, "さようなら"],
  [/\bsayounara\b/giu, "さようなら"],
  [/\bогэнки\s+дэс\s*ка\b/giu, "お元気ですか"],
  [/\bогенки\s+дес\s*ка\b/giu, "お元気ですか"],
  [/\bogenki\s+desu\s*ka\b/giu, "お元気ですか"],
  [/\bгэнки\s+дэс\b/giu, "元気です"],
  [/\bgenki\s+desu\b/giu, "元気です"],
  [/\bнихонго\b/giu, "日本語"],
  [/\bnihongo\b/giu, "日本語"],
  [/\bмонгоруго\b/giu, "モンゴル語"],
  [/\bmongorugo\b/giu, "モンゴル語"],
  [/\bдайски\b/giu, "大好き"],
  [/\bдайсүки\b/giu, "大好き"],
  [/\bdaisuki\b/giu, "大好き"],
  [/\bсугой\b/giu, "すごい"],
  [/\bсүгой\b/giu, "すごい"],
  [/\bsugoi\b/giu, "すごい"],
  [/\bкавайи\b/giu, "かわいい"],
  [/\bкавай\b/giu, "かわいい"],
  [/\bkawaii\b/giu, "かわいい"],
  [/\bсэнсэй\b/giu, "先生"],
  [/\bсенсей\b/giu, "先生"],
  [/\bsensei\b/giu, "先生"],
  [/\bдайжообү\b/giu, "大丈夫"],
  [/\bдайжобү\b/giu, "大丈夫"],
  [/\bdaijoubu\b/giu, "大丈夫"],
  [/\bганбаттэ\b/giu, "頑張って"],
  [/\bганбатте\b/giu, "頑張って"],
  [/\bganbatte\b/giu, "頑張って"],
  [/\bвакаримашита\b/giu, "分かりました"],
  [/\bвакаримашта\b/giu, "分かりました"],
  [/\bwakarimashita\b/giu, "分かりました"],
  [/\bвакаримасэн\b/giu, "分かりません"],
  [/\bwakarimasen\b/giu, "分かりません"],

  // Single English tech & daily loanwords
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
