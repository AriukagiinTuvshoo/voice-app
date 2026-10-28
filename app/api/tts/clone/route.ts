import { NextRequest, NextResponse } from "next/server";
import { BASE_PY_URL, ensurePythonServerReady } from "@/lib/ensure-py-server";

export async function GET(req: NextRequest) {
  try {
    await ensurePythonServerReady(3500);
    const id = req.nextUrl.searchParams.get("id");
    if (id) {
      const res = await fetch(`${BASE_PY_URL}/clones/${encodeURIComponent(id)}/sample`, {
        cache: "no-store",
      });
      if (!res.ok) {
        return NextResponse.json({ error: "Sample not found" }, { status: 404 });
      }
      const buf = await res.arrayBuffer();
      return new NextResponse(buf, {
        headers: {
          "Content-Type": "audio/wav",
          "Content-Disposition": `inline; filename="${id}.wav"`,
        },
      });
    }

    const res = await fetch(`${BASE_PY_URL}/clones`, { cache: "no-store" });
    if (!res.ok) return NextResponse.json([]);
    const list = await res.json();
    return NextResponse.json(list);
  } catch {
    return NextResponse.json([]);
  }
}

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

    await ensurePythonServerReady(4500);

    const pyForm = new FormData();
    pyForm.append("audio", audio, "sample.wav");
    pyForm.append("name", name);

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 30000);

    const res = await fetch(`${BASE_PY_URL}/clone-voice`, {
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

export async function DELETE(req: NextRequest) {
  try {
    await ensurePythonServerReady(2500);
    const id = req.nextUrl.searchParams.get("id");
    if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
    await fetch(`${BASE_PY_URL}/clones/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    return NextResponse.json({ deleted: id });
  } catch {
    return NextResponse.json({ error: "Delete failed" }, { status: 500 });
  }
}
