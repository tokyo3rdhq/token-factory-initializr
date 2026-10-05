// Standard error envelope for /api/v1/* endpoints. Mirrors the
// OpenAI error shape (per docs
// tfi_agent_friendly_model_catalog_api.md §17 and §29) so Agent
// consumers can rely on a single, stable error contract.

export interface PublicApiErrorBody {
  error: {
    message: string;
    type: string;
    param?: string;
    code?: string;
  };
}

const HEADERS = { "Content-Type": "application/json; charset=utf-8" };

export function jsonError(
  status: number,
  body: PublicApiErrorBody,
  extraHeaders: Record<string, string> = {}
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...HEADERS, ...extraHeaders },
  });
}

/** Convenience: invalid_request_error shaped response. */
export function invalidRequest(
  message: string,
  param?: string,
  code?: string
): Response {
  const error: PublicApiErrorBody["error"] = {
    message,
    type: "invalid_request_error",
  };
  if (param) error.param = param;
  if (code) error.code = code;
  return jsonError(400, { error });
}

/** Convenience: not_found shaped response. */
export function notFound(message: string): Response {
  return jsonError(404, {
    error: { message, type: "invalid_request_error", code: "not_found" },
  });
}

/** Standard JSON response with cache-friendly + CORS + ETag headers.
 *
 * Pass an optional ``etag`` to enable HTTP ``If-None-Match`` semantics.
 * When the request's ``If-None-Match`` header matches, the response
 * is a ``304 Not Modified`` with no body and the same ETag.
 */
export function jsonResponse(
  body: unknown,
  init: { status?: number; etag?: string; ifNoneMatch?: string | null } = {}
): Response {
  const status = init.status ?? 200;
  const etag = init.etag;

  if (etag && init.ifNoneMatch && etagMatches(init.ifNoneMatch, etag)) {
    // 304 — no body, just the validating headers.
    return new Response(null, {
      status: 304,
      headers: cacheHeaders(etag, /* longCache */ false),
    });
  }

  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      // Public, agent-facing API — cacheable + open CORS.
      "Access-Control-Allow-Origin": "*",
      // ETag (conditional). Cloudflare strips this on 304 responses
      // automatically; we send it on 200 so clients can validate.
      ...(etag ? { ETag: etag } : {}),
      ...cacheHeaders(etag, /* longCache */ false),
    },
  });
}

/** Plain-text response helper (used by /llms.txt, /agents.md).
 *
 * Same ETag / cache semantics as ``jsonResponse`` — pass a stable
 * content-hash and clients can revalidate cheaply. */
export function textResponse(
  body: string,
  contentType: string,
  init: { status?: number; etag?: string; ifNoneMatch?: string | null } = {}
): Response {
  const status = init.status ?? 200;
  const etag = init.etag;

  if (etag && init.ifNoneMatch && etagMatches(init.ifNoneMatch, etag)) {
    return new Response(null, {
      status: 304,
      headers: cacheHeaders(etag, /* longCache */ true),
    });
  }

  return new Response(body, {
    status,
    headers: {
      "Content-Type": `${contentType}; charset=utf-8`,
      "Access-Control-Allow-Origin": "*",
      ...(etag ? { ETag: etag } : {}),
      ...cacheHeaders(etag, /* longCache */ true),
    },
  });
}

function cacheHeaders(etag: string | undefined, longCache: boolean): Record<string, string> {
  // Text discovery files (llms.txt, agents.md) are stable across
  // the API's lifetime — cache longer. The /api/v1/models list
  // changes per pipeline run — keep a shorter max-age so clients
  // pick up new models within the day, with ETag revalidation as
  // the precise answer.
  const cacheControl = longCache
    ? "public, max-age=3600, s-maxage=86400"
    : "public, max-age=60, s-maxage=300, stale-while-revalidate=60";
  return etag
    ? { "Cache-Control": cacheControl, "X-TFI-Catalog-Version": etag }
    : { "Cache-Control": cacheControl };
}

/** RFC 7232 weak-validator match.
 *
 * Accepts both bare ``"etag-value"`` and the full header form
 * ``W/"etag-value"`` / ``"etag-value", "another"`` so callers
 * passing the raw ``If-None-Match`` value don't need to parse it.
 * Exported so unit tests can lock the contract down. */
export function etagMatches(header: string, etag: string): boolean {
  for (const part of header.split(",")) {
    const tag = part.trim();
    if (tag === "*" || tag === etag || tag === `W/"${etag}"`) {
      return true;
    }
  }
  return false;
}

/** Stable weak ETag for a given content string. */
export function makeEtag(content: string): string {
  // 32-bit FNV-1a — small, fast, collision risk acceptable for ETag
  // (Cloudflare's own cache keys use a similar approach for the
  // 304 use case where collision means a stale hit, not a data
  // leak). We wrap in W/ to mark the validator as weak per RFC 7232
  // because two responses are "equivalent" iff their content is
  // byte-identical, not semantically identical.
  let hash = 0x811c9dc5;
  for (let i = 0; i < content.length; i++) {
    hash ^= content.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  // Convert to unsigned 32-bit hex.
  return `W/"tfi-${(hash >>> 0).toString(16).padStart(8, "0")}"`;
}
