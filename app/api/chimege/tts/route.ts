import { NextRequest, NextResponse } from "next/server";

const TTS_URL = "https://api.chimege.com/v1.2/synthesize";

export async function POST(req: NextRequest) {
  try {
    const {
      text,
      voiceId = "FEMALE3v2",
      speed = 1.0,
      pitch = 1.0,
      sampleRate = 22050,
      token: reqToken,
    } = await req.json();

    const token = reqToken || req.headers.get("x-chimege-token") || process.env.CHIMEGE_API_TOKEN;

    if (!token) {
      return NextResponse.json(
        { error: "Chimege API Token тохируулаагүй байна. Settings хэсэгт token-оо оруулна уу." },
        { status: 401 }
      );
    }

    if (!text || !text.trim()) {
      return NextResponse.json({ error: "Унших текст хоосон байна." }, { status: 400 });
    }

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 30000);

    const res = await fetch(TTS_URL, {
      method: "POST",
      headers: {
        "Content-Type": "text/plain",
        Token: token.trim(),
        "voice-id": String(voiceId),
        speed: String(speed),
        pitch: String(pitch),
        "sample-rate": String(sampleRate),
      },
      body: text.trim(),
      signal: ctrl.signal,
    });

    clearTimeout(timeout);

    if (!res.ok) {
      const errText = await res.text();
      return NextResponse.json(
        { error: `Chimege TTS алдаа (${res.status}): ${errText || res.statusText}` },
        { status: res.status }
      );
    }

    const audioArrayBuffer = await res.arrayBuffer();

    return new NextResponse(audioArrayBuffer, {
      headers: {
        "Content-Type": "audio/wav",
        "Content-Disposition": 'inline; filename="chimege-speech.wav"',
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "TTS хөрвүүлэлтийн алдаа";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
