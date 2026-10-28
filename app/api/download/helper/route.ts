import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), "public", "downloads", "VOICE-Windows-Helper.bat");
    if (!fs.existsSync(filePath)) {
      return new NextResponse("Helper file not found", { status: 404 });
    }
    const fileBuffer = fs.readFileSync(filePath);

    return new NextResponse(fileBuffer, {
      headers: {
        "Content-Type": "application/x-bat",
        "Content-Disposition": 'attachment; filename="VOICE-Windows-Helper.bat"',
      },
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Download error";
    return new NextResponse(msg, { status: 500 });
  }
}
