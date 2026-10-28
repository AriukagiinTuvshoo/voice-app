import { NextRequest, NextResponse } from "next/server";
import { encodeWAV } from "@/lib/wav-encoder";

const LOCAL_TTS_URL = process.env.LOCAL_TTS_URL || "http://127.0.0.1:8000/tts";
const LOCAL_HEALTH_URL = process.env.LOCAL_TTS_HEALTH || "http://127.0.0.1:8000/health";

export async function GET() {
  try {
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 2000);
    const res = await fetch(LOCAL_HEALTH_URL, {
      method: "GET",
      signal: ctrl.signal,
    });
    clearTimeout(timeout);

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({
        online: true,
        model: data.model || "facebook/mms-tts-khk",
        service: "MMS-TTS Local Server",
      });
    }
    return NextResponse.json({ online: false, error: "Server returned non-200" });
  } catch {
    return NextResponse.json({
      online: false,
      message: "Local MMS-TTS server is offline (start with: run-tts.bat or uvicorn tts_server:app --port 8000)",
    });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const text = (body.text || "").trim();

    if (!text) {
      return NextResponse.json(
        { error: "Уншуулах текст хоосон байна." },
        { status: 400 }
      );
    }

    // 1. Try local Python MMS-TTS server
    try {
      const ctrl = new AbortController();
      const timeout = setTimeout(() => ctrl.abort(), 25000);

      const pyRes = await fetch(LOCAL_TTS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
        signal: ctrl.signal,
      });

      clearTimeout(timeout);

      if (pyRes.ok) {
        const audioBuffer = await pyRes.arrayBuffer();
        return new NextResponse(audioBuffer, {
          headers: {
            "Content-Type": "audio/wav",
            "Content-Disposition": 'inline; filename="mms-speech.wav"',
            "X-TTS-Engine": "facebook/mms-tts-khk",
            "X-TTS-Source": "local-server",
          },
        });
      } else {
        const errJson = await pyRes.json().catch(() => null);
        console.warn("Local TTS error:", errJson || pyRes.statusText);
      }
    } catch (e: unknown) {
      console.warn("Local MMS-TTS server connection failed (will use fallback preview tone):", e);
    }

    // 2. Fallback: Friendly sound preview if local python server is not yet started
    const duration = Math.min(2.5, Math.max(0.8, text.length * 0.05));
    const samplesCount = Math.floor(16000 * duration);
    const samples = new Float32Array(samplesCount);
    const baseFreq = 440; // приятный ля тон

    for (let i = 0; i < samplesCount; i++) {
      const t = i / 16000;
      const envelope = Math.exp(-3 * (t / duration));
      samples[i] = 0.25 * Math.sin(2 * Math.PI * baseFreq * t) * envelope;
    }

    const wavBlob = encodeWAV(samples, 16000);
    const buffer = await wavBlob.arrayBuffer();

    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "audio/wav",
        "Content-Disposition": 'inline; filename="offline-preview.wav"',
        "X-TTS-Engine": "fallback-tone",
        "X-TTS-Status": "server-offline",
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "TTS алдаа гарлаа";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
