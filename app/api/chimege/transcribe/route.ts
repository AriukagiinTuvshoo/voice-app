import { NextRequest, NextResponse } from "next/server";

const CHIMEGE_STT_URL = "https://api.chimege.com/v1.2/transcribe";
const LOCAL_STT_URL = process.env.LOCAL_STT_URL || "http://127.0.0.1:8000/transcribe";

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    let audioBuffer: Buffer;
    let token = req.headers.get("x-chimege-token") || process.env.CHIMEGE_API_TOKEN || "";

    if (contentType.includes("multipart/form-data")) {
      const formData = await req.formData();
      const file = formData.get("audio") as Blob | null;
      if (!file) {
        return NextResponse.json({ error: "Аудио өгөгдөл илгээгдээгүй байна." }, { status: 400 });
      }
      const arrayBuffer = await file.arrayBuffer();
      audioBuffer = Buffer.from(arrayBuffer);

      const formToken = formData.get("token") as string | null;
      if (formToken) token = formToken.trim();
    } else {
      const arrayBuffer = await req.arrayBuffer();
      audioBuffer = Buffer.from(arrayBuffer);
    }

    if (audioBuffer.length === 0) {
      return NextResponse.json({ error: "Хоосон аудио файл байна." }, { status: 400 });
    }

    // 1. If Chimege token is available, attempt Chimege STT
    if (token) {
      try {
        const transcript = await transcribeChimege(audioBuffer, token);
        if (transcript) {
          return NextResponse.json({ text: transcript, engine: "Chimege STT" });
        }
      } catch (apiErr) {
        console.warn("Chimege STT API call warning:", apiErr);
      }
    }

    // 2. Try Local Python Server STT (Google mn-MN)
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 20000);

      const pyForm = new FormData();
      const pyBlob = new Blob([audioBuffer], { type: "audio/wav" });
      pyForm.append("audio", pyBlob, "audio.wav");

      const pyRes = await fetch(LOCAL_STT_URL, {
        method: "POST",
        body: pyForm,
        signal: ctrl.signal,
      });

      clearTimeout(timer);

      if (pyRes.ok) {
        const pyData = await pyRes.json();
        if (pyData.text) {
          return NextResponse.json({
            text: pyData.text,
            engine: pyData.engine || "AI Voice STT",
          });
        }
        if (pyData.error) {
          return NextResponse.json({
            text: "",
            error: pyData.error,
          });
        }
      }
    } catch (e: unknown) {
      console.warn("Local STT server warning:", e);
    }

    // 3. If neither worked, return empty text with informative message
    return NextResponse.json({
      text: "",
      error: "Яриа танигдсангүй. Микрофондоо тод ярина уу эсвэл Browser Web Speech сонгоно уу.",
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Яриа танихад алдаа гарлаа";
    return NextResponse.json({ error: message, text: "" }, { status: 500 });
  }
}

async function transcribeChimege(audio: Buffer, token: string): Promise<string> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);

  try {
    const res = await fetch(CHIMEGE_STT_URL, {
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
      throw new Error(`API status ${res.status}`);
    }

    try {
      const json = JSON.parse(body);
      if (json && typeof json.transcription === "string") {
        return json.transcription.trim();
      }
    } catch {}

    return body.trim();
  } catch (err: unknown) {
    clearTimeout(timer);
    throw err;
  }
}
