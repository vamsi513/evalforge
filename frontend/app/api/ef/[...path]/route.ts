import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
const KEY = process.env.EVALFORGE_API_KEY ?? "";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = `${BASE}/${path.join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  const upstream = await fetch(url, { headers, cache: "no-store" });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const url = `${BASE}/${path.join("/")}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  const body = await req.json();
  const upstream = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
