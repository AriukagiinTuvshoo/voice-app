import { spawn } from "child_process";
import path from "path";
import fs from "fs";

export const BASE_PY_URL = process.env.LOCAL_PY_URL || "http://127.0.0.1:8000";

let lastSpawnAttempt = 0;

async function isPythonServerHealthy(timeoutMs = 1500): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${BASE_PY_URL}/health`, {
      method: "GET",
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

export function triggerPythonServerSpawn() {
  const now = Date.now();
  if (now - lastSpawnAttempt < 5000) return;
  lastSpawnAttempt = now;

  try {
    const cwd = process.cwd();
    const winVenv = path.join(cwd, ".venv", "Scripts", "python.exe");
    const nixVenv = path.join(cwd, ".venv", "bin", "python");

    let pythonCmd = process.platform === "win32" ? "python" : "python3";
    if (fs.existsSync(winVenv)) {
      pythonCmd = winVenv;
    } else if (fs.existsSync(nixVenv)) {
      pythonCmd = nixVenv;
    }

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

export async function ensurePythonServerReady(maxWaitMs = 4500): Promise<boolean> {
  if (await isPythonServerHealthy(1200)) {
    return true;
  }

  triggerPythonServerSpawn();

  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    await new Promise((r) => setTimeout(r, 450));
    if (await isPythonServerHealthy(1200)) {
      return true;
    }
  }

  return false;
}
