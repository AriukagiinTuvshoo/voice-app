import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), "public", "downloads", "VOICE-Chrome-Extension.zip");
    if (!fs.existsSync(filePath)) {
      return new NextResponse("Extension zip not found", { status: 404 });
    }
    const fileBuffer = fs.readFileSync(filePath);

    return new NextResponse(fileBuffer, {
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="VOICE-Chrome-Extension.zip"',
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Download error";
    return new NextResponse(msg, { status: 500 });
  }
}
