import { NextRequest, NextResponse } from "next/server";
import { BASE_PY_URL, ensurePythonServerReady, triggerPythonServerSpawn } from "@/lib/ensure-py-server";

export async function GET() {
  try {
    const res = await fetch(`${BASE_PY_URL}/flowbar/status`, { cache: "no-store" });
    if (!res.ok) {
      triggerPythonServerSpawn();
      return NextResponse.json({ status: "offline", visible: false });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    triggerPythonServerSpawn();
    return NextResponse.json({ status: "offline", visible: false });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    await ensurePythonServerReady(3500);

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
    triggerPythonServerSpawn();
    return NextResponse.json({ status: "offline" }, { status: 503 });
  }
}
