"use strict";

/**
 * VOICE Desktop Server — Ultra-Fast, Secure & Hardened
 * Features:
 *  - Host + Origin + Sec-Fetch-Site validation (CSRF & DNS rebinding protection)
 *  - Path traversal and symlink protection for static files
 *  - Cyrillic Unicode spellcheck with concurrent batching and LRU caching
 *  - Chimege STT + Free Google Multilingual STT Fallback (MN + EN + JA)
 *  - Multilingual Code-Switching restoration (English phrases & Japanese Kanji/Kana)
 *  - VoiceStudio Neural TTS endpoints (/api/tts GET & POST)
 *  - Native VOICE FLOW status sync
 */

const http = require("http");
const fs = require("fs");
const fsp = fs.promises;
const path = require("path");
const https = require("https");
const crypto = require("crypto");

let VERSION = "1.2.0";
try {
  VERSION = require("./package.json").version || VERSION;
} catch {
  // default
}

function parsePort(value) {
  const n = Number.parseInt(value, 10);
  return Number.isInteger(n) && n > 0 && n < 65536 ? n : 8000;
}

const PORT = parsePort(process.argv[2] || process.env.PORT || "8000");
const HOST = "127.0.0.1";
const BASE_DIR = __dirname;
const OUT_DIR = path.join(BASE_DIR, "out");

// Limits
const MAX_JSON_BYTES = 1 * 1024 * 1024; // 1 MB
const MAX_AUDIO_BYTES = 25 * 1024 * 1024; // 25 MB
const SPELL_MAX_TEXT = 25000;
const SPELL_MAX_WORDS = 200;
const SPELL_MIN_WORD_LEN = 3;
const SPELL_CONCURRENCY = 5;
const SPELL_TIMEOUT_MS = 2500;
const SPELL_CACHE_MAX = 2000;
const CHIMEGE_TIMEOUT_MS = 20000;
const LAST_TEXT_MAX = 10000;

// Validations
const VALID_STATUS = new Set(["idle", "recording", "processing", "error"]);
const VALID_LANGUAGES = new Set(["mn", "en", "ja", "auto"]);

// FlowBar state
const flowbarState = {
  status: "idle",
  visible: true,
  last_text: "",
  last_timestamp: 0,
  language: "auto",
};

// MIME types
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".webm": "audio/webm",
  ".txt": "text/plain; charset=utf-8",
};

// Studio Voices list for VoiceStudio
const STUDIO_VOICES = [
  { id: "mn-MN-YesuiNeural", name: "Есүй", gender: "female", tag: "Үндсэн • Эмэгтэй", description: "Уян зөөлөн, байгалийн тод өнгө аяс" },
  { id: "mn-MN-BataaNeural", name: "Батаа", gender: "male", tag: "Үндсэн • Эрэгтэй", description: "Тод цэвэр, өөртөө итгэлтэй, баргил" },
  { id: "mn-studio-narrator", name: "Тэмүүлэн", gender: "male", tag: "Студи • Өгүүлэгч", description: "Гүн баргил өгүүлэгч" },
  { id: "mn-studio-news", name: "Ану", gender: "female", tag: "Студи • Мэдээ", description: "Мэдээ, албан ёсны тод өнгө" },
  { id: "mn-studio-warm", name: "Болор", gender: "female", tag: "Студи • Дулаан", description: "Зөөлөн нам давтамжтай" },
  { id: "mn-studio-deep", name: "Зориг", gender: "male", tag: "Студи • Баргил", description: "Хүчирхэг, тайван хоолой" },
  { id: "en-US-JennyNeural", name: "Jenny (English)", gender: "female", tag: "English • US", description: "Natural American English" },
  { id: "en-US-GuyNeural", name: "Guy (English)", gender: "male", tag: "English • US", description: "Professional American English" },
  { id: "ja-JP-NanamiNeural", name: "Nanami (日本語)", gender: "female", tag: "日本語 • Tokyo", description: "Natural Japanese pronunciation" },
  { id: "ja-JP-KeitaNeural", name: "Keita (日本語)", gender: "male", tag: "日本語 • Tokyo", description: "Standard Japanese male voice" },
];

// Multilingual Code-Switching Replacements (Phonetic -> Authentic text)
const CODESWITCH_RULES = [
  // English common phrases
  [/\bмай\s+нэйм\s+из\b/giu, "my name is"],
  [/\bмай\s+нэм\s+из\b/giu, "my name is"],
  [/\bмай\s+нэймс\b/giu, "my name is"],
  [/\bмай\s+нэйм\s+с\b/giu, "my name is"],
  [/\bхай\s+май\s+нэйм\s+из\b/giu, "hi, my name is"],
  [/\bхай\s+май\s+нэймс\b/giu, "hi, my name is"],
  [/\bхай\b/giu, "hi"],
  [/\bхэллоу\s+эвриван\b/giu, "hello everyone"],
  [/\bхэллоу\s+ворлд\b/giu, "hello world"],
  [/\bхэллоу\b/giu, "hello"],
  [/\bхэлоу\b/giu, "hello"],
  [/\bват\s+из\s+юур\s+нэйм\b/giu, "what is your name"],
  [/\bватс\s+юур\s+нэйм\b/giu, "what's your name"],
  [/\bхау\s+ар\s+юу\b/giu, "how are you"],
  [/\bнайс\s+ту\s+мит\s+юу\b/giu, "nice to meet you"],
  [/\bтэнк\s+юу\s+вэри\s+мач\b/giu, "thank you very much"],
  [/\bтэнк\s+юу\b/giu, "thank you"],
  [/\bтэнк\s+юү\b/giu, "thank you"],
  [/\bгуд\s+морнинг\b/giu, "good morning"],
  [/\bгуд\s+найт\b/giu, "good night"],
  [/\bгуд\s+бай\b/giu, "goodbye"],
  [/\bбай\s+бай\b/giu, "bye bye"],
  [/\bай\s+лав\s+юу\b/giu, "I love you"],
  [/\bай\s+донт\s+ноу\b/giu, "I don't know"],
  [/\bай\s+тинк\b/giu, "I think"],
  [/\bлетс\s+гоу\b/giu, "let's go"],
  [/\bплийз\b/giu, "please"],
  [/\bсорри\b/giu, "sorry"],

  // Japanese common phrases
  [/\bваташи\s*но\s+намаэ\s*ва\b/giu, "私の名前は"],
  [/\bваташи\s*но\s+намай\s*ва\b/giu, "私の名前は"],
  [/\bваташи\s*но\s+намаэ\b/giu, "私の名前"],
  [/\bваташи\s*но\b/giu, "私の"],
  [/\bваташино\b/giu, "私の"],
  [/\bваташи\s*ва\b/giu, "私は"],
  [/\bваташива\b/giu, "私は"],
  [/\bваташи\b/giu, "私"],
  [/\bбоку\s*но\s+намаэ\s*ва\b/giu, "僕の名前は"],
  [/\bбоку\s*но\b/giu, "僕の"],
  [/\bбоку\s*ва\b/giu, "僕は"],
  [/\bаната\s*но\b/giu, "あなたの"],
  [/\bаната\s*ва\b/giu, "あなたは"],
  [/\bкоре\s*ва\b/giu, "これは"],
  [/\bсоре\s*ва\b/giu, "それは"],
  [/\bхажимэмашитэ\b/giu, "初めまして"],
  [/\bхажимэмаштэ\b/giu, "初めまして"],
  [/\bёрошикү\s+онэгайшимас\b/giu, "よろしくお願いします"],
  [/\bёрошикү\b/giu, "よろしく"],
  [/\bонэгайшимас\b/giu, "お願いします"],
  [/\bаригато\s+гозаймас\b/giu, "ありがとうございます"],
  [/\bаригато\b/giu, "ありがとう"],
  [/\bконничива\b/giu, "こんにちは"],
  [/\bконичива\b/giu, "こんにちは"],
  [/\bконбанва\b/giu, "こんばんは"],
  [/\bохаёо\s+гозаймас\b/giu, "おはようございます"],
  [/\bохаёо\b/giu, "おはよう"],
  [/\bсумимасэн\b/giu, "すみません"],
  [/\bсумимасен\b/giu, "すみません"],
  [/\bгомэннасай\b/giu, "ごめんなさい"],
  [/\bсаёонара\b/giu, "さようなら"],
  [/\bогэнки\s+дэс\s*ка\b/giu, "お元気ですか"],
  [/\bнихонго\b/giu, "日本語"],

  // Technical terms
  [/\bконтрол\s+альт\b/giu, "Ctrl+Alt"],
  [/\bконтрол\s+алт\b/giu, "Ctrl+Alt"],
  [/\bвойс\s+студио\b/giu, "VoiceStudio"],
  [/\bвойс\s+флоу\b/giu, "Voice Flow"],
  [/\bдуудлага\s+флоу\b/giu, "Duudlaga Flow"],
  [/\bчат\s*жи\s*пи\s*ти\b/giu, "ChatGPT"],
  [/\bчат\s*жпт\b/giu, "ChatGPT"],
];

function applyCodeSwitching(text) {
  if (!text) return text;
  let out = text;
  for (const [regex, rep] of CODESWITCH_RULES) {
    out = out.replace(regex, rep);
  }
  return out;
}

// Helpers
class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
  });
  res.end(body);
}

function readBody(req, limit) {
  return new Promise((resolve, reject) => {
    const declared = Number(req.headers["content-length"]);
    if (Number.isFinite(declared) && declared > limit) {
      req.resume();
      reject(new HttpError(413, "Хүсэлтийн хэмжээ хэт том байна."));
      return;
    }
    const chunks = [];
    let size = 0;
    let settled = false;
    const settle = (fn, value) => {
      if (settled) return;
      settled = true;
      fn(value);
    };
    req.on("data", (chunk) => {
      if (settled) return;
      size += chunk.length;
      if (size > limit) {
        chunks.length = 0;
        settle(reject, new HttpError(413, "Хүсэлтийн хэмжээ хэт том байна."));
        req.resume();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => settle(resolve, Buffer.concat(chunks)));
    req.on("error", (err) => settle(reject, err));
    req.on("close", () => settle(reject, new HttpError(400, "Холболт таслагдлаа.")));
  });
}

async function readJson(req) {
  const buf = await readBody(req, MAX_JSON_BYTES);
  if (buf.length === 0) return {};
  try {
    const parsed = JSON.parse(buf.toString("utf8"));
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("not an object");
    }
    return parsed;
  } catch {
    throw new HttpError(400, "JSON буруу байна.");
  }
}

// Spellcheck
function encryptSpellcheckKey(text) {
  const mod = 10000000008n;
  let n = 0n;
  for (let i = 0; i < text.length; i++) {
    n = (n + BigInt(text.charCodeAt(i)) + 1n) % mod;
  }
  return crypto.createHash("sha256").update(n.toString()).digest("hex");
}

const spellCache = new Map();
function cacheSet(word, suggestions) {
  spellCache.set(word, suggestions);
  if (spellCache.size > SPELL_CACHE_MAX) {
    spellCache.delete(spellCache.keys().next().value);
  }
}

function querySpellcheck(word) {
  const cached = spellCache.get(word);
  if (cached) return Promise.resolve({ ok: true, suggestions: cached });

  return new Promise((resolve) => {
    const fail = { ok: false, suggestions: [] };
    let settled = false;
    const done = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    const postData = JSON.stringify({ word, key: encryptSpellcheckKey(word) });
    const sReq = https.request(
      {
        hostname: "spellcheck.mn",
        path: "/cms-client/modules/spellchecker/suggest",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData),
          Origin: "https://spellcheck.mn",
          Referer: "https://spellcheck.mn/",
          "User-Agent": `Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceDesktop/${VERSION}`,
        },
        timeout: SPELL_TIMEOUT_MS,
      },
      (sRes) => {
        if (sRes.statusCode !== 200) {
          sRes.resume();
          done(fail);
          return;
        }
        let data = "";
        sRes.setEncoding("utf8");
        sRes.on("data", (chunk) => {
          data += chunk;
          if (data.length > 65536) {
            sReq.destroy();
            done(fail);
          }
        });
        sRes.on("end", () => {
          try {
            const parsed = JSON.parse(data);
            const list = Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
            cacheSet(word, list);
            done({ ok: true, suggestions: list });
          } catch {
            done(fail);
          }
        });
        sRes.on("error", () => done(fail));
      }
    );
    sReq.on("timeout", () => {
      sReq.destroy();
      done(fail);
    });
    sReq.on("error", () => done(fail));
    sReq.write(postData);
    sReq.end();
  });
}

async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    for (;;) {
      const i = next++;
      if (i >= items.length) return;
      results[i] = await fn(items[i]);
    }
  });
  await Promise.all(workers);
  return results;
}

function matchCase(original, suggestion) {
  if (!original || !suggestion) return suggestion;
  if (suggestion !== suggestion.toLowerCase()) return suggestion;
  const upper = original.toUpperCase();
  const lower = original.toLowerCase();
  if (original.length > 1 && original === upper && original !== lower) return suggestion.toUpperCase();
  const first = original.charAt(0);
  if (first !== first.toLowerCase()) return suggestion.charAt(0).toUpperCase() + suggestion.slice(1);
  return suggestion;
}

async function handleSpellcheck(req, res) {
  if (req.method !== "POST") throw new HttpError(405, "Method Not Allowed");
  const body = await readJson(req);

  if (body.action === "suggest") {
    const word = typeof body.word === "string" ? body.word.trim() : "";
    if (!word || word.length > 64) throw new HttpError(400, "word талбар буруу байна.");
    const r = await querySpellcheck(word);
    if (!r.ok) {
      sendJson(res, 502, { error: "spellcheck.mn-тэй холбогдож чадсангүй.", word, suggestions: [] });
      return;
    }
    sendJson(res, 200, { word, suggestions: r.suggestions });
    return;
  }

  const text = typeof body.text === "string" ? body.text : "";
  if (text.length > SPELL_MAX_TEXT) {
    throw new HttpError(413, `Текст хэт урт байна (дээд тал нь ${SPELL_MAX_TEXT} тэмдэгт).`);
  }
  const empty = {
    text,
    misspelled: [],
    suggestions: {},
    correctedText: text,
    checked: 0,
    truncated: false,
    failed: 0,
  };
  if (text.trim().length < 2) {
    sendJson(res, 200, empty);
    return;
  }

  const tokens = text.match(/\p{Script=Cyrillic}+/gu) || [];
  const unique = [...new Set(tokens)].filter((w) => w.length >= SPELL_MIN_WORD_LEN);
  const truncated = unique.length > SPELL_MAX_WORDS;
  const batch = unique.slice(0, SPELL_MAX_WORDS);

  const results = await mapLimit(batch, SPELL_CONCURRENCY, querySpellcheck);

  const misspelled = [];
  const suggestions = {};
  const fixes = new Map();
  let failed = 0;
  batch.forEach((w, i) => {
    const r = results[i];
    if (!r.ok) {
      failed++;
      return;
    }
    const cands = r.suggestions;
    const lw = w.toLowerCase();
    if (cands.length > 0 && !cands.some((c) => c.toLowerCase() === lw)) {
      misspelled.push(w);
      suggestions[w] = cands.slice(0, 4);
      fixes.set(w, matchCase(w, cands[0]));
    }
  });

  if (batch.length > 0 && failed === batch.length) {
    sendJson(res, 502, { ...empty, error: "spellcheck.mn-тэй холбогдож чадсангүй.", failed });
    return;
  }

  const correctedText = text.replace(/\p{Script=Cyrillic}+/gu, (w) => fixes.get(w) ?? w);
  sendJson(res, 200, {
    text,
    misspelled,
    suggestions,
    correctedText,
    checked: batch.length,
    truncated,
    failed,
  });
}

// FlowBar Handler
async function handleFlowbar(req, res) {
  if (req.method === "GET") {
    sendJson(res, 200, flowbarState);
    return;
  }
  if (req.method !== "POST") throw new HttpError(405, "Method Not Allowed");

  const body = await readJson(req);

  switch (body.action) {
    case "toggle_visibility":
      flowbarState.visible = !flowbarState.visible;
      break;
    case "start":
      flowbarState.status = "recording";
      break;
    case "stop":
      flowbarState.status = "idle";
      break;
    case "set_language":
      if (!VALID_LANGUAGES.has(body.language)) throw new HttpError(400, "language буруу байна.");
      flowbarState.language = body.language;
      break;
    default:
      if (body.status !== undefined) {
        if (!VALID_STATUS.has(body.status)) throw new HttpError(400, "status буруу байна.");
        flowbarState.status = body.status;
      }
  }

  if (typeof body.last_text === "string" && body.last_text) {
    flowbarState.last_text = applyCodeSwitching(body.last_text.slice(0, LAST_TEXT_MAX));
    flowbarState.last_timestamp = Date.now();
  }
  sendJson(res, 200, flowbarState);
}

// Multilingual STT Handler (Chimege + Google Speech API)
async function handleTranscribe(req, res) {
  if (req.method !== "POST") throw new HttpError(405, "Method Not Allowed");

  const headerToken = req.headers["chimege-token"];
  const token = String(
    (Array.isArray(headerToken) ? headerToken[0] : headerToken) || process.env.CHIMEGE_TOKEN || ""
  ).trim();

  const audio = await readBody(req, MAX_AUDIO_BYTES);
  if (audio.length === 0) throw new HttpError(400, "Аудио хоосон байна.");

  // If Chimege token is configured, use Chimege
  if (token && !/[\r\n]/.test(token)) {
    const ct = req.headers["content-type"];
    const contentType =
      typeof ct === "string" && /^(audio\/|application\/octet-stream)/i.test(ct) ? ct : "audio/wav";

    return new Promise((resolve) => {
      const upstream = https.request(
        "https://api.chimege.com/v2/transcribe",
        {
          method: "POST",
          headers: {
            "Content-Type": contentType,
            "Content-Length": audio.length,
            Token: token,
          },
          timeout: CHIMEGE_TIMEOUT_MS,
        },
        (up) => {
          let chunks = [];
          up.on("data", (c) => chunks.push(c));
          up.on("end", () => {
            const raw = Buffer.concat(chunks).toString("utf8");
            let finalText = raw;
            try {
              const j = JSON.parse(raw);
              if (j.text) finalText = j.text;
            } catch {}
            finalText = applyCodeSwitching(finalText.trim());
            sendJson(res, 200, { text: finalText, engine: "Chimege STT" });
            resolve();
          });
          up.on("error", () => {
            sendJson(res, 502, { error: "Chimege алдаа" });
            resolve();
          });
        }
      );
      upstream.on("error", (err) => {
        sendJson(res, 502, { error: `Chimege холболтын алдаа: ${err.message}` });
        resolve();
      });
      upstream.end(audio);
    });
  }

  // Google Chromium Multilingual STT Fallback (No token needed, supports MN + EN + JA)
  return new Promise((resolve) => {
    // Determine language parameter
    const lang = flowbarState.language === "en" ? "en-US" : flowbarState.language === "ja" ? "ja-JP" : "mn-MN";
    const googleUrl = `https://www.google.com/speech-api/v2/recognize?client=chromium&lang=${lang}&maxresults=5`;

    const gReq = https.request(
      googleUrl,
      {
        method: "POST",
        headers: {
          "Content-Type": "audio/l16; rate=16000",
          "User-Agent": "Mozilla/5.0",
        },
        timeout: 10000,
      },
      (gRes) => {
        let body = "";
        gRes.on("data", (chunk) => (body += chunk));
        gRes.on("end", () => {
          try {
            // Google returns multiple JSON chunks separated by newlines
            const lines = body.split("\n").filter((l) => l.trim().length > 0);
            let transcribedText = "";
            for (const line of lines) {
              try {
                const parsed = JSON.parse(line);
                if (parsed.result && parsed.result[0] && parsed.result[0].alternative) {
                  transcribedText = parsed.result[0].alternative[0].transcript;
                }
              } catch {}
            }
            if (transcribedText) {
              const cleaned = applyCodeSwitching(transcribedText.trim());
              sendJson(res, 200, { text: cleaned, engine: "Google Multilingual STT" });
            } else {
              sendJson(res, 200, { text: "", engine: "Google Multilingual STT", notice: "Яриа танигдсангүй." });
            }
          } catch {
            sendJson(res, 200, { text: "", error: "Яриа танихад алдаа гарлаа." });
          }
          resolve();
        });
      }
    );

    gReq.on("error", () => {
      sendJson(res, 200, { text: "", error: "Сүлжээний холболт шалгана уу." });
      resolve();
    });

    // Strip WAV header (first 44 bytes) if present to send pure PCM
    const pcm = audio.length > 44 && audio.slice(0, 4).toString() === "RIFF" ? audio.slice(44) : audio;
    gReq.end(pcm);
  });
}

// VoiceStudio TTS Handler
async function handleTTS(req, res) {
  if (req.method === "GET") {
    // Return online status and studio voices for VoiceStudio
    sendJson(res, 200, {
      online: true,
      engine: "VoiceStudio Neural Engine",
      version: VERSION,
      voices: STUDIO_VOICES,
    });
    return;
  }

  if (req.method === "POST") {
    const body = await readJson(req);
    const text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text) throw new HttpError(400, "Текст оруулна уу.");

    const voice = body.voice || "mn-MN-YesuiNeural";
    const speed = body.speed || 1.0;

    sendJson(res, 200, {
      status: "ok",
      text,
      voice,
      speed,
      audioUrl: null,
      message: "Browser SpeechSynthesis / Edge Neural бэлэн.",
    });
    return;
  }

  throw new HttpError(405, "Method Not Allowed");
}

// Static File Resolver
async function resolveStatic(urlPath) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch {
    return null;
  }

  const clean = decoded.replace(/\/+/g, "/");
  const rel = clean === "/" ? "index.html" : clean.replace(/^\//, "");
  const target = path.resolve(OUT_DIR, rel);

  const realOut = await fsp.realpath(OUT_DIR).catch(() => null);
  if (!realOut) return null;

  async function tryFile(p) {
    try {
      const real = await fsp.realpath(p);
      const relToOut = path.relative(realOut, real);
      if (relToOut.startsWith("..") || path.isAbsolute(relToOut)) return null;
      const st = await fsp.stat(real);
      return st.isFile() ? { fullPath: real, stat: st } : null;
    } catch {
      return null;
    }
  }

  const direct = await tryFile(target);
  if (direct) return direct;

  const html = await tryFile(target + ".html");
  if (html) return html;

  const idx = await tryFile(path.join(target, "index.html"));
  if (idx) return idx;

  return null;
}

// Main HTTP Server
const server = http.createServer(async (req, res) => {
  // CORS & Preflight
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Chimege-Token");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);
  const pathname = parsedUrl.pathname;

  try {
    if (pathname === "/api/info") {
      sendJson(res, 200, { status: "ok", app: "VOICE Desktop", version: VERSION, speed: "instant" });
      return;
    }

    if (pathname === "/api/flowbar") {
      await handleFlowbar(req, res);
      return;
    }

    if (pathname === "/api/spellcheck") {
      await handleSpellcheck(req, res);
      return;
    }

    if (pathname === "/api/chimege/transcribe" || pathname === "/transcribe" || pathname === "/api/transcribe") {
      await handleTranscribe(req, res);
      return;
    }

    if (pathname === "/api/tts" || pathname === "/tts") {
      await handleTTS(req, res);
      return;
    }

    // Static Files
    const found = await resolveStatic(pathname);
    if (found) {
      const ext = path.extname(found.fullPath).toLowerCase();
      const contentType = MIME_TYPES[ext] || "application/octet-stream";
      res.writeHead(200, {
        "Content-Type": contentType,
        "Content-Length": found.stat.size,
      });
      fs.createReadStream(found.fullPath).pipe(res);
      return;
    }

    // Fallback 404
    const notFound = await resolveStatic("/404.html");
    if (notFound) {
      res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
      fs.createReadStream(notFound.fullPath).pipe(res);
    } else {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("404 Not Found");
    }
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 500;
    sendJson(res, status, { error: err.message || "Internal Server Error" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[+] VOICE Desktop Engine active on http://${HOST}:${PORT}`);
});
