import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

const JSON_HEADERS = { "Cache-Control": "no-store" };

async function forward(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  // The backend is intentionally development-only until authentication and
  // project authorization have shipped. Fail closed even if someone deploys
  // this Next.js app accidentally.
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json(
      {
        detail:
          "The Pixi API proxy is development-only until authentication and project authorization are implemented.",
      },
      { status: 503, headers: JSON_HEADERS },
    );
  }

  const { path } = await context.params;
  if (
    !path.length ||
    path.length > 12 ||
    path.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        !/^[A-Za-z0-9_-]+$/.test(segment),
    )
  ) {
    return NextResponse.json(
      { detail: "Invalid Pixi API path." },
      { status: 400, headers: JSON_HEADERS },
    );
  }

  const baseText =
    process.env.PIXI_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
  let base: URL;
  try {
    base = new URL(baseText);
  } catch {
    return NextResponse.json(
      { detail: "PIXI_API_BASE_URL must be a valid HTTP(S) URL." },
      { status: 500, headers: JSON_HEADERS },
    );
  }

  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash
  ) {
    return NextResponse.json(
      { detail: "PIXI_API_BASE_URL must be a credential-free HTTP(S) base URL." },
      { status: 500, headers: JSON_HEADERS },
    );
  }

  const length = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(length) && length > 20_000_000) {
    return NextResponse.json(
      { detail: "Request body exceeds the local development proxy limit (20 MB)." },
      { status: 413, headers: JSON_HEADERS },
    );
  }

  const basePath = base.toString().replace(/\/+$/, "");
  const target = `${basePath}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers({ Accept: request.headers.get("accept") ?? "application/json" });
  const contentType = request.headers.get("content-type");
  const idempotencyKey = request.headers.get("idempotency-key");
  if (contentType) headers.set("Content-Type", contentType);
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(35_000),
    });

    const responseHeaders = new Headers(JSON_HEADERS);
    const upstreamType = upstream.headers.get("content-type");
    const disposition = upstream.headers.get("content-disposition");
    if (upstreamType) responseHeaders.set("Content-Type", upstreamType);
    if (disposition) responseHeaders.set("Content-Disposition", disposition);

    // Never follow or mirror redirects from a configured backend.
    if (upstream.status >= 300 && upstream.status < 400) {
      return NextResponse.json(
        { detail: "Redirects from the Pixi API are not supported." },
        { status: 502, headers: JSON_HEADERS },
      );
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "Cannot reach the Pixi FastAPI backend. Start it locally and confirm PIXI_API_BASE_URL.",
      },
      { status: 502, headers: JSON_HEADERS },
    );
  }
}

export const GET = forward;
export const POST = forward;
