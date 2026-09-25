// GET /api/generated/{id}/prompt
//
// Returns the agent-prompt string for a generated artifact. Same
// id-based lookup as /api/generated/{id}; the prompt is computed
// at fetch time using the current request URL so it always points
// at the canonical share URL.

import { loadGenerated, type Env } from "../../../lib/kv";
import { generateAgentPrompt } from "../../../lib/litellm";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const id = context.params.id;
  const art = await loadGenerated(context.env, id);
  if (!art) {
    return jsonError(404, "artifact not found or expired");
  }
  if (art.expires_at <= Date.now()) {
    return jsonError(410, "artifact expired");
  }

  const url = new URL(context.request.url);
  // Re-root to the public ``/generated/{id}`` share URL.
  const generatedUrl = `${url.origin}/generated/${id}`;

  return new Response(generateAgentPrompt(generatedUrl), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

function jsonError(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}