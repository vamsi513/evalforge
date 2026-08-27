import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
const KEY = process.env.EVALFORGE_API_KEY ?? "";

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { error: text || "upstream error" };
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = `${BASE}/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  try {
    const upstream = await fetch(url, { headers, cache: "no-store" });
    return NextResponse.json(await parseBody(upstream), { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "API unreachable" }, { status: 503 });
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = `${BASE}/${path.join("/")}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  try {
    const body = await req.json();
    const upstream = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
    return NextResponse.json(await parseBody(upstream), { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "API unreachable" }, { status: 503 });
  }
}
