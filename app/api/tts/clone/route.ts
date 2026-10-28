import { NextRequest, NextResponse } from "next/server";

const CLONE_URL = process.env.LOCAL_CLONE_URL || "http://127.0.0.1:8000/clone-voice";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const audio = formData.get("audio") as Blob | null;
    const name = (formData.get("name") as string) || "Миний хоолой";

    if (!audio) {
      return NextResponse.json(
        { error: "Дуу хоолойн бичлэг эсвэл файл оруулаагүй байна." },
        { status: 400 }
      );
    }

    const pyForm = new FormData();
    pyForm.append("audio", audio, "sample.wav");
    pyForm.append("name", name);

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 20000);

    const res = await fetch(CLONE_URL, {
      method: "POST",
      body: pyForm,
      signal: ctrl.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return NextResponse.json(
        { error: err.detail || "Хоолой шинжлэхэд алдаа гарлаа." },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Сервертэй холбогдож чадсангүй.";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
