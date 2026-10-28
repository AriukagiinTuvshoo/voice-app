import { NextRequest, NextResponse } from "next/server";
import { BASE_PY_URL, ensurePythonServerReady } from "@/lib/ensure-py-server";
import { processTranscriptText } from "@/lib/text-processor";

const LOCAL_STT_URL = process.env.LOCAL_STT_URL || `${BASE_PY_URL}/transcribe`;

/**
 * Plain-text STT endpoint designed for iPhone (iOS Shortcuts / iOS Keyboard Extension)
 * and Android Keyboard clients.
 * Accepts multipart/form-data (`audio` file) OR raw audio body (M4A, WAV, CAF, MP3, WEBM)
 * and returns plain UTF-8 text directly so mobile clients and iOS Shortcuts need zero JSON parsing.
 */
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    const langParam = req.nextUrl.searchParams.get("lang") || "mn";
    let audioBuffer: Buffer;
    let language = langParam;

    if (contentType.includes("multipart/form-data")) {
      const formData = await req.formData();
      const file = (formData.get("audio") || formData.get("file")) as Blob | null;
      if (!file) {
        return new NextResponse("Аудио файл олдсонгүй", { status: 400 });
      }
      audioBuffer = Buffer.from(await file.arrayBuffer());
      const formLang = formData.get("language") as string | null;
      if (formLang) language = formLang.trim();
    } else {
      audioBuffer = Buffer.from(await req.arrayBuffer());
    }

    if (!audioBuffer || audioBuffer.length < 100) {
      return new NextResponse("", { status: 200 });
    }

    await ensurePythonServerReady(4500);

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 28000);

    const pyForm = new FormData();
    const pyBlob = new Blob([audioBuffer], { type: "audio/wav" });
    pyForm.append("audio", pyBlob, "mobile_audio.wav");
    pyForm.append("language", language);

    const pyRes = await fetch(LOCAL_STT_URL, {
      method: "POST",
      body: pyForm,
      signal: ctrl.signal,
    });
    clearTimeout(timer);

    if (pyRes.ok) {
      const data = await pyRes.json().catch(() => ({}));
      const rawText = (data.text || "").trim();
      if (rawText) {
        const cleaned = processTranscriptText(rawText, {
          mode: "clean",
          autoPunctuation: true,
          removeFillers: true,
          language: (language === "en" || language === "ja" || language === "auto" ? language : "mn"),
        });
        return new NextResponse(cleaned, {
          status: 200,
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "no-store",
          },
        });
      }
    }

    return new NextResponse("", {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "STT Error";
    return new NextResponse(msg, { status: 500 });
  }
}
