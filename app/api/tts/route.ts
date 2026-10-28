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
      cache: "no-store",
    });
    clearTimeout(timeout);

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({
        online: true,
        data,
      });
    }
    return NextResponse.json({ online: false });
  } catch {
    return NextResponse.json({
      online: false,
      message: "Local TTS server offline (run run-tts.bat)",
    });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const text = (body.text || "").trim();
    const voice = body.voice || body.voiceId || "mn-MN-YesuiNeural";
    const speed = body.speed ?? 1.0;
    const pitch = body.pitch ?? 1.0;
    const preset = body.preset ?? "broadcast";
    const timbreStrength = body.timbreStrength ?? 0.92;

    if (!text) {
      return NextResponse.json(
        { error: "Уншуулах текст хоосон байна." },
        { status: 400 }
      );
    }

    // 1. Try local Python VoiceStudio TTS server
    try {
      const ctrl = new AbortController();
      const timeout = setTimeout(() => ctrl.abort(), 25000);

      const pyRes = await fetch(LOCAL_TTS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          voice,
          speed,
          pitch,
          preset,
          timbreStrength,
        }),
        signal: ctrl.signal,
      });

      clearTimeout(timeout);

      if (pyRes.ok) {
        const contentType = pyRes.headers.get("content-type") || "audio/wav";
        const audioBuffer = await pyRes.arrayBuffer();
        return new NextResponse(audioBuffer, {
          headers: {
            "Content-Type": contentType,
            "Content-Disposition": 'inline; filename="speech.wav"',
            "X-TTS-Source": "local-voicestudio-server",
          },
        });
      }
    } catch (e: unknown) {
      console.warn("Local TTS server not responding, using preview chime:", e);
    }

    // 2. Fallback preview chime if local server is offline
    const duration = Math.min(2.5, Math.max(0.8, text.length * 0.05));
    const samplesCount = Math.floor(16000 * duration);
    const samples = new Float32Array(samplesCount);
    const baseFreq =
      voice.toLowerCase().includes("bataa") || voice.toLowerCase().includes("male")
        ? 330
        : 520;

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
        "Content-Disposition": 'inline; filename="preview.wav"',
        "X-TTS-Status": "server-offline",
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "TTS алдаа";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
