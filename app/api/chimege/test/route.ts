import { NextRequest, NextResponse } from "next/server";
import { encodeSilence } from "@/lib/wav-encoder";

const STT_URL = "https://api.chimege.com/v1.2/transcribe";

export async function POST(req: NextRequest) {
  try {
    const { token } = await req.json();
    const cleanToken = (token || "").trim();

    if (!cleanToken) {
      return NextResponse.json({ valid: false, message: "Token хоосон байна." }, { status: 400 });
    }

    // Generate 0.5s silence WAV exactly like DuudlagaFlow WavEncoder.EncodeSilence(0.5)
    const silenceBlob = encodeSilence(0.5, 16000);
    const audioBuffer = Buffer.from(await silenceBlob.arrayBuffer());

    const res = await fetch(STT_URL, {
      method: "POST",
      headers: {
        Token: cleanToken,
        "Content-Type": "audio/wav",
      },
      body: audioBuffer,
    });

    if (res.ok) {
      return NextResponse.json({ valid: true, message: "Chimege API Token амжилттай баталгаажлаа! (Зөв)" });
    }

    const body = await res.text();
    if (res.status === 403 || res.status === 401) {
      return NextResponse.json({ valid: false, message: `Token буруу байна: ${body || "Forbidden"}` }, { status: 401 });
    }

    return NextResponse.json({ valid: false, message: `Алдаа гарлаа (${res.status}): ${body}` }, { status: res.status });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Холболтын алдаа";
    return NextResponse.json({ valid: false, message }, { status: 500 });
  }
}
