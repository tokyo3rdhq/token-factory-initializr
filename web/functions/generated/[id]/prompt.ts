// GET /generated/{id}/prompt
//
// Public agent-prompt endpoint per AGENTS.md §20. Same artifact
// TTL as the YAML endpoint; the prompt is computed at fetch time
// using the current request URL so it always points at the
// canonical share URL.
//
// Honors the embedded ``expires_at`` — KV's expirationTtl is
// best-effort, so we re-check on read.

import { loadGenerated, type Env } from "../../lib/kv";
import { generateAgentPrompt } from "../../lib/litellm";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const id = context.params.id;
  const art = await loadGenerated(context.env, id);
  if (!art) {
    return text("artifact not found or expired\n", 404);
  }
  if (art.expires_at <= Date.now()) {
    return text("artifact expired\n", 410);
  }

  const url = new URL(context.request.url);
  const generatedUrl = `${url.origin}/generated/${art.id}`;
  return new Response(generateAgentPrompt(generatedUrl), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

function text(body: string, status: number): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}