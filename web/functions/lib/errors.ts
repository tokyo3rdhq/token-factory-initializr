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

/** Standard JSON response with cache-friendly + CORS headers. */
export function jsonResponse(
  body: unknown,
  init: ResponseInit = {}
): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      // Public, agent-facing API — cacheable + open CORS.
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=300",
      ...(init.headers || {}),
    },
  });
}

/** Plain-text response helper (used by /llms.txt, /agents.md). */
export function textResponse(
  body: string,
  contentType: string,
  init: ResponseInit = {}
): Response {
  return new Response(body, {
    ...init,
    headers: {
      "Content-Type": `${contentType}; charset=utf-8`,
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=300",
      ...(init.headers || {}),
    },
  });
}
