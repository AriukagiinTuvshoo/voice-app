const http = require("http");
const fs = require("fs");
const path = require("path");
const https = require("https");
const crypto = require("crypto");

const PORT = parseInt(process.argv[2] || process.env.PORT || "8000", 10);
const BASE_DIR = __dirname;
const OUT_DIR = path.join(BASE_DIR, "out");

// FlowBar state shared across desktop app
const flowbarState = {
  status: "idle",
  visible: true,
  last_text: "",
  last_timestamp: 0,
  language: "mn",
};

// MIME types dictionary
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".wav": "audio/wav",
  ".mp3": "audio/mpeg",
  ".txt": "text/plain; charset=utf-8",
};

// Spellcheck.mn request key hash algorithm
function encryptSpellcheckKey(text) {
  const mod = 10000000008n;
  let n = 0n;
  for (let i = 0; i < text.length; i++) {
    n = (n + BigInt(text.charCodeAt(i)) + 1n) % mod;
  }
  return crypto.createHash("sha256").update(n.toString()).digest("hex");
}

// Read body helper
function readJsonBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 50 * 1024 * 1024) req.destroy(); // 50MB max
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(body || "{}"));
      } catch {
        resolve({});
      }
    });
    req.on("error", () => resolve({}));
  });
}

function readRawBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", () => resolve(Buffer.alloc(0)));
  });
}

// Spellcheck.mn query
async function querySpellcheck(word) {
  const key = encryptSpellcheckKey(word);
  const postData = JSON.stringify({ word, key });

  return new Promise((resolve) => {
    const options = {
      hostname: "spellcheck.mn",
      path: "/cms-client/modules/spellchecker/suggest",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(postData),
        Origin: "https://spellcheck.mn",
        Referer: "https://spellcheck.mn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceDesktop/1.2",
      },
      timeout: 2000,
    };

    const sReq = https.request(options, (sRes) => {
      let data = "";
      sRes.on("data", (chunk) => (data += chunk));
      sRes.on("end", () => {
        try {
          const parsed = JSON.parse(data);
          resolve(Array.isArray(parsed) ? parsed : []);
        } catch {
          resolve([]);
        }
      });
    });

    sReq.on("error", () => resolve([]));
    sReq.on("timeout", () => {
      sReq.destroy();
      resolve([]);
    });
    sReq.write(postData);
    sReq.end();
  });
}

// HTTP Server
const server = http.createServer(async (req, res) => {
  // CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Chimege-Token");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);
  const pathname = parsedUrl.pathname;

  // ---------------- API Routes ----------------
  if (pathname === "/api/info") {
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ status: "ok", app: "VOICE Desktop", version: "1.2.0" }));
    return;
  }

  if (pathname === "/api/flowbar") {
    if (req.method === "GET") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(flowbarState));
      return;
    }

    if (req.method === "POST") {
      const body = await readJsonBody(req);
      if (body.action === "toggle_visibility") {
        flowbarState.visible = !flowbarState.visible;
      } else if (body.action === "start") {
        flowbarState.status = "recording";
      } else if (body.action === "stop") {
        flowbarState.status = "idle";
      } else if (body.action === "set_language" && body.language) {
        flowbarState.language = body.language;
      } else if (body.status) {
        flowbarState.status = body.status;
      }

      if (body.last_text) {
        flowbarState.last_text = body.last_text;
        flowbarState.last_timestamp = Date.now();
      }

      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(flowbarState));
      return;
    }
  }

  if (pathname === "/api/spellcheck" && req.method === "POST") {
    const body = await readJsonBody(req);
    const action = body.action || "full";
    const word = body.word || "";
    const text = body.text || "";

    if (action === "suggest" && word) {
      const suggestions = await querySpellcheck(word);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ word, suggestions }));
      return;
    }

    if (!text || text.trim().length < 2) {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ text, misspelled: [], suggestions: {}, correctedText: text }));
      return;
    }

    // Split into cyrillic words
    const words = text.match(/[\u0400-\u04FF\u04E8\u04E9\u04AE\u04AF]+/g) || [];
    const misspelled = [];
    const suggestions = {};

    for (const w of words.slice(0, 15)) {
      if (w.length >= 3) {
        const cands = await querySpellcheck(w);
        if (cands.length > 0 && !cands.includes(w)) {
          misspelled.push(w);
          suggestions[w] = cands.slice(0, 4);
        }
      }
    }

    let correctedText = text;
    for (const m of misspelled) {
      const best = suggestions[m]?.[0];
      if (best) {
        correctedText = correctedText.replace(new RegExp(`\\b${m}\\b`, "g"), best);
      }
    }

    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ text, misspelled, suggestions, correctedText }));
    return;
  }

  if (pathname === "/api/chimege/transcribe" && req.method === "POST") {
    const chimegeToken = req.headers["chimege-token"] || process.env.CHIMEGE_TOKEN || "";
    const rawBuffer = await readRawBody(req);

    if (!chimegeToken) {
      res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
      res.end(
        JSON.stringify({
          error: "Chimege Token оруулна уу (Тохиргоо цэснээс оруулах боломжтой).",
        })
      );
      return;
    }

    const cReq = https.request(
      "https://api.chimege.com/v2/transcribe",
      {
        method: "POST",
        headers: {
          "Content-Type": req.headers["content-type"] || "audio/wav",
          "Content-Length": rawBuffer.length,
          Token: chimegeToken,
        },
        timeout: 20000,
      },
      (cRes) => {
        res.writeHead(cRes.statusCode, {
          "Content-Type": cRes.headers["content-type"] || "text/plain; charset=utf-8",
        });
        cRes.pipe(res);
      }
    );

    cReq.on("error", (err) => {
      res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ error: `Chimege холболтын алдаа: ${err.message}` }));
    });

    cReq.write(rawBuffer);
    cReq.end();
    return;
  }

  // ---------------- Static Files Serving ----------------
  let filePath = path.join(OUT_DIR, pathname === "/" ? "index.html" : pathname);

  // Route mapping for clean URLs: /dashboard -> /out/dashboard.html
  if (!fs.existsSync(filePath)) {
    if (fs.existsSync(filePath + ".html")) {
      filePath = filePath + ".html";
    } else if (fs.existsSync(path.join(filePath, "index.html"))) {
      filePath = path.join(filePath, "index.html");
    }
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": contentType });
    fs.createReadStream(filePath).pipe(res);
    return;
  }

  // Fallback 404
  const notFoundPath = path.join(OUT_DIR, "404.html");
  if (fs.existsSync(notFoundPath)) {
    res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
    fs.createReadStream(notFoundPath).pipe(res);
  } else {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("404 Not Found");
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[+] VOICE Desktop Server listening on http://127.0.0.1:${PORT}`);
});
