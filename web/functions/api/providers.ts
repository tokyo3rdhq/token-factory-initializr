// GET /api/providers
//
// Returns the list of provider names that have entries in the
// current manifest. Falls back to the canonical list (nvidia, amd,
// huggingface) when no manifest is present so the UI at least
// renders the right tabs.

import { listProviders, type Env } from "../lib/kv";

export async function onRequestGet(context: {
  request: Request;
  env: Env;
}): Promise<Response> {
  const providers = await listProviders(context.env);
  return new Response(JSON.stringify(providers), {
    headers: { "Content-Type": "application/json" },
  });
}