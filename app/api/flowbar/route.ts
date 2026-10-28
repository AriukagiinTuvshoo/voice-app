import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";

const BASE_PY_URL = process.env.LOCAL_PY_URL || "http://127.0.0.1:8000";

let lastSpawnAttempt = 0;

function ensureNativeTtsServerStarted() {
  const now = Date.now();
  if (now - lastSpawnAttempt < 8000) return;
  lastSpawnAttempt = now;

  try {
    const cwd = process.cwd();
    const venvPython = path.join(cwd, ".venv", "Scripts", "python.exe");
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : "python";

    const child = spawn(
      pythonCmd,
      ["-m", "uvicorn", "tts_server:app", "--host", "127.0.0.1", "--port", "8000"],
      {
        cwd,
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      }
    );
    child.unref();
  } catch (err) {
    console.error("Failed to auto-spawn tts_server.py:", err);
  }
}

export async function GET() {
  try {
    const res = await fetch(`${BASE_PY_URL}/flowbar/status`, { cache: "no-store" });
    if (!res.ok) {
      ensureNativeTtsServerStarted();
      return NextResponse.json({ status: "offline", visible: false });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    ensureNativeTtsServerStarted();
    return NextResponse.json({ status: "offline", visible: false });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (body.insertText) {
      const res = await fetch(`${BASE_PY_URL}/insert-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: body.insertText }),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data);
    }

    const res = await fetch(`${BASE_PY_URL}/flowbar/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data);
  } catch {
    ensureNativeTtsServerStarted();
    return NextResponse.json({ status: "offline" }, { status: 503 });
  }
}
