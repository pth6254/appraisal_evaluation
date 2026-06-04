import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND}/api/auth/me`, {
      headers: { Cookie: cookie },
    });
  } catch {
    return NextResponse.json(null, { status: 503 });
  }

  if (!backendRes.ok) {
    return NextResponse.json(null, { status: backendRes.status });
  }

  const data = await backendRes.json();
  return NextResponse.json(data);
}
