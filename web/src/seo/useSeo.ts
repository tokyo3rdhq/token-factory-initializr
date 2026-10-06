// Route-aware SEO effect for the TFI SPA.
//
// Why this exists (docs/tfi_seo_optimization.md §6):
//   - The static ``index.html`` only carries homepage metadata.
//     Secondary routes (/browse, /generate) need their own title,
//     description, canonical, og:url so social scrapers and any
//     crawl that does manage to navigate the SPA sees the correct
//     values.
//   - The effect mutates ``document.head`` declaratively — same
//     shape as the React docs recommend for SPA SEO. We keep one
//     effect per route rather than letting each page set
//     ``document.title`` ad hoc so the meta tag set stays consistent.
//
// What this does NOT do:
//   - It does NOT rewrite ``<link rel="canonical">`` to the
//     preview/deployment URL. It always uses the values from
//     ``metaForRoute()`` (which are derived from the single SITE
//     constant) so the canonical is deterministic regardless of
//     where the build is hosted.
//   - It does NOT add structured data — that lives only on the
//     homepage (handled statically in ``index.html``).

import { useEffect } from "react";
import { metaForRoute, type RouteMeta } from "./metadata";

function setMeta(
  attrs: { name?: string; property?: string },
  content: string,
): void {
  // Build the selector. og:* uses property="...", twitter/name use
  // name="..."; we match either in case the page already has one
  // with the other form.
  const selector = attrs.name
    ? `meta[name="${attrs.name}"]`
    : `meta[property="${attrs.property}"]`;
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    if (attrs.name) el.setAttribute("name", attrs.name);
    if (attrs.property) el.setAttribute("property", attrs.property);
    el.setAttribute("data-tfi-managed", "1");
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setCanonical(href: string): void {
  let el = document.head.querySelector<HTMLLinkElement>(
    'link[rel="canonical"]',
  );
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    el.setAttribute("data-tfi-managed", "1");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/** Apply `m` to document head. Always sets the full set of tags
 *  (idempotent — overwrites prior values from earlier navigations). */
function applyMeta(m: RouteMeta): void {
  document.title = m.title;

  setMeta({ name: "description" }, m.description);
  setMeta({ property: "og:title" }, m.ogTitle ?? m.title);
  setMeta({ property: "og:description" }, m.ogDescription ?? m.description);
  setMeta({ property: "og:url" }, m.ogUrl);
  setMeta({ property: "og:type" }, "website");
  setMeta({ property: "og:site_name" }, "Token Factory Initializr");
  setMeta({ property: "og:image" }, m.ogImage ?? `${m.canonical}og-image.png`);

  setMeta({ name: "twitter:card" }, "summary_large_image");
  setMeta({ name: "twitter:title" }, m.ogTitle ?? m.title);
  setMeta({ name: "twitter:description" }, m.ogDescription ?? m.description);
  setMeta({ name: "twitter:image" }, m.ogImage ?? `${m.canonical}og-image.png`);

  // Indexability directive. robotsIndex undefined → default true.
  const indexable = m.robotsIndex !== false;
  setMeta({ name: "robots" }, indexable ? "index, follow" : "noindex, nofollow");

  setCanonical(m.canonical);
}

/** React hook: bind the route's metadata to document.head. Place
 *  it once at the top of every page component. */
export function useSeo(pathname: string): void {
  useEffect(() => {
    applyMeta(metaForRoute(pathname));
  }, [pathname]);
}

// Re-export so consumers can do ``import { metaForRoute } from '../seo/metadata'``
// without a second import line.
export { metaForRoute, type RouteMeta } from "./metadata";