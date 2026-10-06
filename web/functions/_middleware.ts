// Global Pages Functions middleware.
//
// Adds CORS headers to every API response so a future move to
// cross-origin hosting doesn't require touching each handler. Also
// sets short cache-control on /api/* responses to encourage
// browser revalidation against the live KV without drowning it
// in traffic.
//
// Pages Functions automatically applies this to every route under
// /functions/, which covers /api/* and /generated/*.
//
// CORS posture:
//   - GET endpoints (`/api/manifest`, `/api/providers`, `/api/models`,
//     `/api/v1/*`, `/generated/{id}`): `Access-Control-Allow-Origin: *`
//     because they're public, read-only catalog data — there is no
//     value in restricting who can read them, and an attacker can
//     trivially proxy anyway.
//   - POST endpoints (`/api/generate`): an explicit allowlist. The
//     write side writes to KV (capped at 50 models per request + 5 min
//     TTL), and we don't want a malicious site to be able to spam
//     generation requests from the browser of any visitor. The
//     allowlist below is the production site + the Cloudflare Pages
//     preview domain + the two `wrangler pages dev` origins.

export async function onRequest(context: EventContext): Promise<Response> {
  const res = await context.next();
  const headers = new Headers(res.headers);

  // CORS — read endpoints are public; the write endpoint
  // (`POST /api/generate`) gets an origin allowlist.
  const url = new URL(context.request.url);
  const isWriteEndpoint = url.pathname === "/api/generate";
  if (isWriteEndpoint) {
    const origin = context.request.headers.get("Origin");
    if (origin && WRITE_ORIGIN_ALLOWLIST.has(origin)) {
      headers.set("Access-Control-Allow-Origin", origin);
      headers.set("Vary", "Origin");
    }
    // No `*` for the write path: if Origin is missing or not in the
    // allowlist, the browser will block the cross-origin request and
    // the same-origin POST will still succeed.
  } else {
    headers.set("Access-Control-Allow-Origin", "*");
  }
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type");

  // Cache guidance. The manifest + models lists are static between
  // data pipeline runs (which happen once per day), so 60s browser
  // cache + 5 min shared cache is generous.
  if (
    url.pathname.startsWith("/api/manifest") ||
    url.pathname.startsWith("/api/providers") ||
    url.pathname.startsWith("/api/models")
  ) {
    headers.set(
      "Cache-Control",
      "public, max-age=60, s-maxage=300, stale-while-revalidate=60"
    );
  } else if (url.pathname.startsWith("/generated/")) {
    // Generated configs are TTL artifacts; never cache them
    // upstream — every fetch must hit KV so expiry is honored.
    headers.set("Cache-Control", "no-store");
  }

  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers,
  });
}

// Origin allowlist for `POST /api/generate`. Same-origin requests
// always succeed because they don't trigger a CORS preflight at all.
//
// Update this set when the production domain moves or when a new
// preview environment is added.
const WRITE_ORIGIN_ALLOWLIST: ReadonlySet<string> = new Set([
  "https://start.magi.website",
  "https://token-factory-initializr.pages.dev",
  // Local dev — `wrangler pages dev` listens on :8788 by default.
  "http://localhost:8788",
  "http://127.0.0.1:8788",
]);

// Handles the CORS preflight quickly without dispatching to a handler.
export async function onRequestOptions(context: EventContext): Promise<Response> {
  const origin = context.request.headers.get("Origin");
  const allowed =
    origin !== null && WRITE_ORIGIN_ALLOWLIST.has(origin)
      ? origin
      : "*"; // read endpoints stay public; OPTIONS for write without origin falls back to *
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": allowed,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    },
  });
}

// Minimal ambient types — Pages Functions inject these via
// @cloudflare/workers-types at build time.
type EventContext = {
  request: Request;
  next(): Promise<Response>;
};
