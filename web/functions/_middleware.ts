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

export async function onRequest(context: EventContext): Promise<Response> {
  const res = await context.next();
  const headers = new Headers(res.headers);

  // CORS — same-origin in production, but a developer may proxy via
  // a different host (or serve via the Pages preview domain) and
  // still want the browser to allow fetches.
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type");

  // Cache guidance. The manifest + models lists are static between
  // data pipeline runs (which happen once per day), so 60s browser
  // cache + 5 min shared cache is generous.
  const url = new URL(context.request.url);
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

// Handles the CORS preflight quickly without dispatching to a handler.
export async function onRequestOptions(): Promise<Response> {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    },
  });
}

// Minimal ambient types — Pages Functions inject these via
// @cloudflare/workers-types at build time.
type EventContext = {
  request: Request;
  next(): Promise<Response>;
};