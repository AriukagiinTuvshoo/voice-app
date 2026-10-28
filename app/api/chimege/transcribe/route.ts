import { NextRequest, NextResponse } from "next/server";

const STT_URL = "https://api.chimege.com/v1.2/transcribe";
const STT_LONG_URL = "https://api.chimege.com/v1.2/stt-long";
const STT_LONG_TRANSCRIPT_URL = "https://api.chimege.com/v1.2/stt-long-transcript";

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    let audioBuffer: Buffer;
    let token = req.headers.get("x-chimege-token") || process.env.CHIMEGE_API_TOKEN || "";
    let useStandardStt = true;

    if (contentType.includes("multipart/form-data")) {
      const formData = await req.formData();
      const file = formData.get("audio") as Blob | null;
      if (!file) {
        return NextResponse.json({ error: "Аудио файл илгээгдээгүй байна." }, { status: 400 });
      }
      const arrayBuffer = await file.arrayBuffer();
      audioBuffer = Buffer.from(arrayBuffer);

      const formToken = formData.get("token") as string | null;
      if (formToken) token = formToken.trim();

      const standardParam = formData.get("useStandardStt");
      if (standardParam !== null) {
        useStandardStt = standardParam === "true" || standardParam === "1";
      }
    } else {
      const arrayBuffer = await req.arrayBuffer();
      audioBuffer = Buffer.from(arrayBuffer);
    }

    if (!token) {
      return NextResponse.json(
        { error: "Chimege API token тохируулаагүй байна. Settings хэсэгт token-оо оруулна уу." },
        { status: 401 }
      );
    }

    if (audioBuffer.length === 0) {
      return NextResponse.json({ error: "Хоосон аудио файл байна." }, { status: 400 });
    }

    if (useStandardStt) {
      const transcript = await transcribeStandard(audioBuffer, token);
      return NextResponse.json({ text: transcript, engine: "chimege-standard" });
    } else {
      const transcript = await transcribeLong(audioBuffer, token);
      return NextResponse.json({ text: transcript, engine: "chimege-long" });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Chimege API алдаа";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

async function transcribeStandard(audio: Buffer, token: string): Promise<string> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 45000);

  try {
    const res = await fetch(STT_URL, {
      method: "POST",
      headers: {
        Token: token,
        "Content-Type": "audio/wav",
      },
      body: audio,
      signal: ctrl.signal,
    });
    clearTimeout(timer);

    const body = await res.text();
    if (!res.ok) {
      if (res.status === 403 || res.status === 401) {
        throw new Error(`Token алдаа: ${body || "Хүчингүй token"}`);
      }
      if (res.status === 400) {
        throw new Error(`Аудио алдаа: ${body}`);
      }
      if (res.status >= 500) {
        throw new Error(`Серверийн алдаа (${res.status}): Дахин оролдоно уу`);
      }
      throw new Error(`Алдаа ${res.status}: ${body}`);
    }

    return parseTranscription(body);
  } catch (err: unknown) {
    clearTimeout(timer);
    throw err;
  }
}

async function transcribeLong(audio: Buffer, token: string): Promise<string> {
  // Step 1: Submit audio
  const submitRes = await fetch(STT_LONG_URL, {
    method: "POST",
    headers: {
      Token: token,
      "Content-Type": "application/octet-stream",
    },
    body: audio,
  });

  const submitBody = await submitRes.text();
  if (!submitRes.ok) {
    throw new Error(`Chimege STT Long submit алдаа: ${submitBody}`);
  }

  let uuid = "";
  try {
    const parsed = JSON.parse(submitBody);
    uuid = parsed.uuid;
  } catch {
    throw new Error("Серверийн хариу буруу байна (UUID олдсонгүй)");
  }

  if (!uuid) {
    throw new Error("UUID олдсонгүй");
  }

  // Step 2: Poll for transcript
  const maxAttempts = 40;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 1000));

    const pollRes = await fetch(STT_LONG_TRANSCRIPT_URL, {
      method: "GET",
      headers: {
        Token: token,
        UUID: uuid,
      },
    });

    if (pollRes.ok) {
      const pollBody = await pollRes.text();
      try {
        const result = JSON.parse(pollBody);
        if (result?.done) {
          const text = (result.transcription || "").trim();
          if (!text) throw new Error("Яриа илрээгүй, хоосон хариу");
          return text;
        }
      } catch (e: unknown) {
        if (e instanceof Error && e.message.includes("Яриа илрээгүй")) throw e;
      }
    }
  }

  throw new Error("Хугацаа дууссан (Timeout), дахин оролдоно уу.");
}

function parseTranscription(body: string): string {
  try {
    const json = JSON.parse(body);
    if (json && typeof json.transcription === "string") {
      const t = json.transcription.trim();
      if (t) return t;
    }
  } catch {
    // Treat as plain text
  }

  const plain = body.trim();
  if (!plain) {
    throw new Error("Яриа илрээгүй эсвэл хоосон байна.");
  }
  return plain;
}
