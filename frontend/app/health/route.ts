import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

  try {
    const res = await fetch(`${backendUrl}/health`, {
      cache: "no-store",
    });

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({
        status: "ok",
        frontend: "live",
        backend: data,
      });
    }

    return NextResponse.json(
      { status: "degraded", frontend: "live", backend: "unhealthy" },
      { status: 502 },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { status: "error", frontend: "live", backend: "unreachable", error: msg },
      { status: 503 },
    );
  }
}
