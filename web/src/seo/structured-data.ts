// JSON-LD structured data for the Token Factory Initializr SPA.
//
// Per docs/tfi_seo_optimization.md §12 + §13:
//   * Use ONLY properties that genuinely apply.
//   * Do NOT fabricate ratings, reviews, pricing, downloads.
//   * Concentrate the JSON-LD strings in this module so the
//     homepage only injects one well-formed <script type="application/ld+json">.
//
// Schema.org types used:
//   * SoftwareApplication — the homepage product description.
//   * Organization        — the publisher (MAGI) record; Google uses
//                          it to disambiguate brand search results.
//
// Why no WebSite + SearchAction? TFI does not host a search-results
// page, so emitting SearchAction would advertise a URL that 404s.

import { SITE } from "./metadata";

export interface SoftwareApplicationLD {
  "@context": "https://schema.org";
  "@type": "SoftwareApplication";
  name: string;
  description: string;
  url: string;
  applicationCategory: string;
  operatingSystem: string;
  publisher: { "@type": "Organization"; name: string; url: string };
  /** Offers is intentionally omitted — TFI is a free tool but has
   *  no formal pricing model (no SKU, no availability constraint),
   *  and Google explicitly warns against speculative Offer fields. */
  offers?: never;
}

/** SoftwareApplication for the homepage.
 *
 *  The properties here are all factual:
 *    - name/url from the product identity (SITE.name / SITE.url)
 *    - description matches the homepage meta description
 *    - applicationCategory "DeveloperApplication" reflects the
 *      primary user (developers wiring AI models into gateways)
 *    - operatingSystem "Any" because the resulting config runs
 *      wherever the user deploys the gateway, not in the browser
 *    - publisher & name/url from the parent MAGI brand
 *  No ratings, no reviews, no downloads, no aggregateRating, no
 *  price. */
export function buildSoftwareApplicationLD(): SoftwareApplicationLD {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: SITE.name,
    description:
      "Discover free AI model endpoints from NVIDIA, AMD, and Hugging Face. Select the ones that fit your project and generate ready-to-use configurations for LiteLLM, NewAPI, and Bifrost.",
    url: `${SITE.url}/`,
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Any",
    publisher: {
      "@type": "Organization",
      name: SITE.parentBrand.name,
      url: SITE.parentBrand.url,
    },
  };
}

export interface OrganizationLD {
  "@context": "https://schema.org";
  "@type": "Organization";
  name: string;
  url: string;
  /** Parent brand is MAGI; the Organization record refers to it,
   *  not to TFI itself. TFI is a sub-product under MAGI, not a
   *  separate organization. */
  parentOrganization?: never;
}

/** Organization record for the homepage. Per §12 we use the
 *  publisher-of-SoftwareApplication organization — the parent brand
 *  MAGI — not a separate TFI organization record (we don't have one). */
export function buildOrganizationLD(): OrganizationLD {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE.parentBrand.name,
    url: SITE.parentBrand.url,
  };
}

/** Stable JSON.stringify for structured data (alphabetical keys at
 *  every level). Stable output is important because the
 *  ``<script type="application/ld+json">`` block lives in the SPA HTML
 *  and Google compares for the same bytes across crawls. */
export function stableJsonLD(value: unknown): string {
  return JSON.stringify(value, (_key, val: unknown) => {
    if (val && typeof val === "object" && !Array.isArray(val)) {
      const sorted: Record<string, unknown> = {};
      for (const k of Object.keys(val as Record<string, unknown>).sort()) {
        sorted[k] = (val as Record<string, unknown>)[k];
      }
      return sorted;
    }
    return val;
  });
}