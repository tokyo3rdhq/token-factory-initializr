// GET /generated/{id}[/prompt]
//
// Public endpoint per AGENTS.md §19 and §20.
//
//   GET /generated/{id}        -> YAML body (Content-Type: text/yaml)
//   GET /generated/{id}/prompt -> agent prompt (text/plain)
//
// Both URLs share the same artifact TTL. The prompt path is
// computed at fetch time so it always points at the canonical
// share URL the caller used.
//
// Honors the embedded expires_at — KV's expirationTtl is
// best-effort, so we re-check on read.

import { loadGenerated, type Env } from "../lib/kv";
import { generateAgentPrompt } from "../lib/litellm";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
  params: { id: string };
}): Promise<Response> {
  const url = new URL(context.request.url);
  const wantsPrompt = url.pathname.endsWith("/prompt");

  const art = await loadGenerated(context.env, context.params.id);
  if (!art) {
    return text("artifact not found or expired\n", 404);
  }
  if (art.expires_at <= Date.now()) {
    return text("artifact expired\n", 410);
  }

  if (wantsPrompt) {
    const generatedUrl = `${url.origin}/generated/${art.id}`;
    return new Response(generateAgentPrompt(generatedUrl), {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  return new Response(art.config_yaml, {
    headers: {
      "Content-Type": "text/yaml; charset=utf-8",
      "Content-Disposition": `inline; filename="${art.id}.yaml"`,
    },
  });
}

function text(body: string, status: number): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}