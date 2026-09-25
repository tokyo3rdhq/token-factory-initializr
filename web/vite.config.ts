import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the Token Factory Initializr web app.
//
// Builds the React UI to ./dist. Pages Functions (in ./functions) are
// NOT bundled by Vite — they're consumed directly by `wrangler pages
// dev` / `wrangler pages deploy` as JS workers, exactly as the
// Cloudflare Pages docs recommend.
//
// For dev, the typical workflow is:
//
//   1. ``npm install`` once
//   2. ``npm run dev``  (alias for ``wrangler pages dev -- ./dist``)
//
// The Vite dev server is not strictly needed — Pages Functions can
// serve the React app from the built output. We rely on
// ``wrangler pages dev`` (which runs the Workers runtime + serves
// static assets) and a simple build step. The "dev" script just
// rebuilds on file change via ``vite build --watch`` and serves
// the result with ``wrangler pages dev``.
//
// We pass ``--compatibility-date=2026-09-15`` so the dev server
// matches the deployed runtime. The wrangler.toml file carries
// the same value for production.

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 5173,
  },
});