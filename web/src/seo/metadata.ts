// SEO metadata for the Token Factory Initializr SPA.
//
// The TFI web app is a single-document React 18 SPA served from
// one ``index.html``. There is no per-route server-rendered HTML —
// search engines that crawl the production build hit ``/`` and
// navigate the SPA in their renderer (Google's two-wave indexing).
// For metadata that crawlers MUST see at HTML fetch time
// (canonical, og:url, twitter:card, structured data) we set
// the homepage baseline in ``index.html`` directly.
//
// For per-route metadata that only needs to be visible to social
// scrapers and human visitors who land deep via a redirect, we
// apply a small client-side effect that writes ``document.title``,
// ``<meta name="description">``, ``og:url``, etc. when the route
// changes. This is best-effort — search engines get the homepage
// metadata on first byte; SPA-routed pages are picked up on second-
// wave render.
//
// Architecture per docs/tfi_seo_optimization.md §6 + §13:
//   * static SEO at first byte in ``index.html``
//   * route-aware client-side metadata via this module
//   * JSON-LD structured data via ``structured-data.ts`` (JSON, not
//     scattered string literals)
//   * canonical URLs computed from a single SITE constant so we
//     never accidentally emit a localhost / preview / query URL

export const SITE = {
  /** Production origin. Never read from window.location in SSR-time
   *  contexts (we don't have SSR, but the same caution keeps the
   *  build deterministic). */
  url: "https://start.magi.website",
  /** Human-readable site name — used as `og:site_name`. */
  name: "Token Factory Initializr",
  /** Parent brand — used as `publisher` in JSON-LD + the MAGI link
   *  in the topbar. Kept here so structured-data + UI share one
   *  source of truth. */
  parentBrand: {
    name: "MAGI",
    url: "https://magi.website",
  },
  /** Default locale for SEO purposes. The SPA also supports zh,
   *  but the URL structure is single-locale (client-side toggle) so
   *  we don't emit hreflang — per docs/tfi_seo_optimization.md §25. */
  locale: "en",
} as const;

/** SEO surface for a single route. The values are written to
 *  document.head when the route mounts. */
export interface RouteMeta {
  /** <title> — keep under ~60 chars for SERP snippets. */
  title: string;
  /** <meta name="description"> — keep under ~155 chars. */
  description: string;
  /** <link rel="canonical"> — absolute URL, no trailing slash unless
   *  the canonical itself ends with one. */
  canonical: string;
  /** og:url — usually identical to canonical. */
  ogUrl: string;
  /** og:title / twitter:title. Defaults to `title`. */
  ogTitle?: string;
  /** og:description / twitter:description. Defaults to `description`. */
  ogDescription?: string;
  /** og:image — absolute URL. Reuse site OG image unless this route
   *  needs a different visual. */
  ogImage?: string;
  /** Whether this route should be indexed. Defaults to true. Set
   *  false for shareable-but-not-discoverable routes (artifacts). */
  robotsIndex?: boolean;
}

export const HOME_META: RouteMeta = {
  title: "Token Factory Initializr — AI Model Configuration Generator",
  description:
    "Discover free AI model endpoints from NVIDIA, AMD, and Hugging Face. Select the ones that fit your project and generate ready-to-use configurations for LiteLLM, NewAPI, and Bifrost.",
  canonical: `${SITE.url}/`,
  ogUrl: `${SITE.url}/`,
  ogTitle: "Token Factory Initializr — AI Model Configuration Generator",
  ogDescription:
    "Discover free AI model endpoints. Generate LiteLLM, NewAPI, and Bifrost configurations.",
  ogImage: `${SITE.url}/og-image.png`,
};

export const BROWSE_META: RouteMeta = {
  title: "Browse Free AI Models — Token Factory Initializr",
  description:
    "Browse and filter free AI model endpoints from NVIDIA, AMD, and Hugging Face. Filter by capability, context length, vision, tool calling, and pricing.",
  canonical: `${SITE.url}/browse`,
  ogUrl: `${SITE.url}/browse`,
  ogDescription:
    "Browse and filter free AI model endpoints from NVIDIA, AMD, and Hugging Face.",
  ogImage: `${SITE.url}/og-image.png`,
};

export const GENERATE_META: RouteMeta = {
  title: "Generate Token Factory Configuration — TFI",
  description:
    "Generate ready-to-use LiteLLM, NewAPI, or Bifrost configurations from your selected models.",
  canonical: `${SITE.url}/generate`,
  ogUrl: `${SITE.url}/generate`,
  ogImage: `${SITE.url}/og-image.png`,
  // /generate is functional — selection from /browse drives it. We
  // still index it because users sharing the page (e.g. for a
  // shareable artifact URL workflow) might link to it, but we
  // intentionally do NOT make it a primary landing page.
  robotsIndex: true,
};

/** Route → metadata map. Used by the route-aware SEO effect. */
export const ROUTE_META: Record<string, RouteMeta> = {
  "/": HOME_META,
  "/browse": BROWSE_META,
  "/generate": GENERATE_META,
};

/** Get the metadata for a route path. Falls back to HOME_META for
 *  unknown routes (which include the `<Navigate to="/" replace />`
 *  catch-all — unknown routes always bounce to home anyway). */
export function metaForRoute(pathname: string): RouteMeta {
  // Strip trailing slash for lookup consistency.
  const norm = pathname.replace(/\/+$/, "") || "/";
  return ROUTE_META[norm] ?? HOME_META;
}

/** Built-in / generated routes classification — used by
 *  ``/sitemap.xml`` (only routes with ``indexable`` should appear)
 *  and by the Pages Functions for the ``X-Robots-Tag`` header. */
export const INDEXABLE_PATHS: ReadonlyArray<string> = ["/", "/browse"];