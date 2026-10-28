import { NextRequest, NextResponse } from "next/server";
import { BASE_PY_URL, ensurePythonServerReady } from "@/lib/ensure-py-server";

const LOCAL_TTS_URL = process.env.LOCAL_TTS_URL || `${BASE_PY_URL}/tts`;
const LOCAL_HEALTH_URL = process.env.LOCAL_TTS_HEALTH || `${BASE_PY_URL}/health`;

export async function GET() {
  try {
    await ensurePythonServerReady(3500);
    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 2500);
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
      message: "VoiceStudio AI холбогдож байна...",
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
    const cloneProfile = body.cloneProfile ?? null;

    if (!text) {
      return NextResponse.json(
        { error: "Уншуулах текст хоосон байна." },
        { status: 400 }
      );
    }

    await ensurePythonServerReady(4500);

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 30000);

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
        cloneProfile,
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
          "X-TTS-Source": "voicestudio-server",
        },
      });
    }

    const errJson = await pyRes.json().catch(() => ({}));
    return NextResponse.json(
      { error: errJson.detail || "Аудио үүсгэхэд алдаа гарлаа. Дахин оролдоно уу." },
      { status: pyRes.status || 500 }
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "TTS алдаа гарлаа";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
