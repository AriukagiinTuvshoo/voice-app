import { NextRequest, NextResponse } from "next/server";

const BASE_PY_URL = process.env.LOCAL_PY_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${BASE_PY_URL}/flowbar/status`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ status: "offline", visible: false });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ status: "offline", visible: false });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (body.insertText) {
      const res = await fetch(`${BASE_PY_URL}/insert-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: body.insertText }),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data);
    }

    const res = await fetch(`${BASE_PY_URL}/flowbar/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ status: "offline" }, { status: 503 });
  }
}
