# Task: Implement the SEO and GEO Roadmap for Token Factory Initializr (TFI)

## 1. Project Context

Product: Token Factory Initializr (TFI)
Production URL: https://start.magi.website
Repository: https://github.com/tokyo3rdhq/token-factory-initializr

TFI is a developer-oriented tool for discovering AI models and generating configuration for supported AI gateways, currently targeting LiteLLM, NewAPI, and Bifrost. Verify the actual supported features and deployment state before making product claims.

Current architecture:

* React 18 SPA
* TypeScript and Vite
* Cloudflare Pages and Pages Functions
* Cloudflare KV for model data
* Shared design system: `@tokyo3rdhq/magi-design-system`
* Public model API and machine-readable documentation, including `llms.txt` and `agents.md`

The goal is to improve organic search discoverability, make product information easier for search engines and AI systems to understand, and measure whether these improvements lead to meaningful product usage.

## 2. Core Strategy

Implement the work in three phases, in order:

1. **Phase 1 — Technical SEO:** Ensure important pages are crawlable, indexable, correctly rendered, and equipped with appropriate metadata.
2. **Phase 2 — Product Discoverability:** Improve product descriptions, API documentation, model-data discoverability, and a small number of useful technical guides.
3. **Phase 3 — Measurement and Expansion:** Establish SEO and referral baselines, then use actual evidence to decide which additional pages or content are worth building.

Do not implement all three phases indiscriminately in one pass. Start with the audit and Phase 1. Record Phase 2 and Phase 3 work as separate tasks when appropriate.

### Principles

* Preserve the existing architecture and user-facing workflows.
* Follow the installed MAGI Design System for any UI changes.
* Prefer accurate product information over keyword density.
* Do not fabricate search-volume data, ranking improvements, product features, or AI citation results.
* Do not create large numbers of programmatic SEO pages without a demonstrated user need and unique useful content.
* Do not treat `llms.txt`, `agents.md`, structured data, or AI-specific metadata as guaranteed ranking mechanisms.
* Do not add a new analytics vendor or paid service without explicit justification and approval.
* Keep all changes small, testable, and deployable independently.

---

# Phase 0 — Audit and Baseline

Before modifying code, inspect the repository and the production website.

## 0.1 Inspect the application

Identify:

* Homepage route and page component.
* `/browse` route and its rendering behavior.
* Any existing model-detail or other public routes.
* Vite configuration and HTML entry template.
* Cloudflare Pages Functions and routing rules.
* Existing `robots.txt`, `sitemap.xml`, canonical URLs, metadata, Open Graph tags, and structured data.
* Existing `llms.txt`, `agents.md`, API documentation, and related routes.
* Current i18n implementation and translation conventions.
* Existing analytics and privacy configuration.
* Existing CI workflows and available lint, type-check, test, and build commands.

Inspect the actual deployed routes and verify their HTTP behavior when network access is available. Distinguish source-code observations from verified production behavior.

Do not assume that a route exists merely because it is mentioned in documentation.

## 0.2 Establish a route inventory

Create an internal audit table containing:

* Route or resource.
* Intended audience.
* Search value.
* Current HTTP status.
* Crawlability and indexability.
* Metadata and canonical behavior.
* Rendering behavior.
* Recommended action.

At minimum, assess:

* `/`
* `/browse`
* `/robots.txt`
* `/sitemap.xml`
* `/llms.txt`
* `/agents.md`
* Existing public API documentation and relevant model-detail routes, if any.

Do not assume that every route should be indexed. Public API endpoints, generated configuration URLs, and user-specific or temporary resources may require different indexing policies.

## 0.3 Audit report

Before implementing, summarize:

1. Existing SEO infrastructure.
2. Confirmed issues.
3. Issues that require production or Search Console access to verify.
4. The smallest implementation plan.
5. Any required environment variables or external configuration.

Do not stop after the audit. Proceed with Phase 1 when the repository provides enough evidence to implement safely.

---

# Phase 1 — Technical SEO

## 1.1 Page metadata

Implement or correct page metadata using the project's existing architecture.

For the homepage, use the following starting copy:

**Title**

`TFI — Discover Free AI Models & Generate Gateway Configs`

**Meta description**

`Explore AI models across providers, compare capabilities, and generate configurations for LiteLLM, NewAPI, and Bifrost with Token Factory Initializr.`

Verify the supported gateway list before publishing this description. Do not claim a gateway is supported if the actual application does not support it.

Requirements:

* Use a descriptive, unique title.
* Add a concise meta description.
* Set the canonical URL to the correct production URL.
* Include appropriate Open Graph metadata for sharing.
* Preserve the existing MAGI brand and favicon conventions.
* Avoid duplicate or conflicting tags.
* Follow existing localization conventions if multiple locales are supported.

Do not add a metadata library unless the existing implementation genuinely requires one.

### `/browse` metadata

Inspect the actual page and its rendered content before choosing its title and description.

Use distinct metadata for `/browse` if it is a meaningful public landing page. Do not copy the homepage title and description verbatim.

Determine whether its main content is visible to search crawlers. If the current React SPA relies on client-side API fetching, evaluate whether the current production output provides enough useful content for indexing.

Do not introduce SSR, prerendering, or a new framework without demonstrating a concrete limitation and documenting the smallest viable solution.

If rendering changes are necessary, propose the implementation and its trade-offs before expanding the task scope.

## 1.2 Crawlability and indexability

Inspect:

* `robots.txt`
* HTTP status codes
* Canonical URLs
* `noindex` directives
* Redirects and trailing-slash behavior
* Cloudflare Pages routing and fallback behavior
* JavaScript rendering of important content
* Internal links to public pages

Requirements:

* Important public pages must be accessible to crawlers.
* Do not block CSS or JavaScript resources required to render public content.
* Do not accidentally mark the homepage or valuable public catalog pages as `noindex`.
* Do not use `robots.txt` as a substitute for an appropriate indexing directive.
* Do not assume that a page is indexed simply because it returns HTTP 200.
* Avoid duplicate canonical URLs caused by inconsistent hostnames, protocols, or paths.

Inspect the behavior of query parameters and filter states on `/browse`. Avoid creating an unlimited number of crawlable URL variants for equivalent filtered views.

Do not remove useful search functionality merely to simplify indexing.

## 1.3 Sitemap

Create or update `sitemap.xml` if the audit confirms that a sitemap is missing or incomplete.

Requirements:

* Include the canonical homepage.
* Include `/browse` only if it is intended to be indexed and provides useful public content.
* Include additional public landing pages only when they genuinely exist and have independent value.
* Use absolute canonical production URLs.
* Do not include API endpoints, temporary generated configuration URLs, private resources, or arbitrary filter combinations by default.
* Do not invent `lastmod` values or update them on every deployment without meaningful content changes.
* Ensure the sitemap is served with the correct content type and HTTP status.
* Keep sitemap generation compatible with the current Vite and Cloudflare Pages build process.

For a small site, a static sitemap is acceptable if the public URL inventory is stable. Do not introduce dynamic sitemap infrastructure without a clear need.

## 1.4 Structured data

Evaluate whether structured data is appropriate for the actual homepage.

Potential types to evaluate include:

* `WebSite`
* `SoftwareApplication`

Only implement a schema type when its required properties are supported by verified product information.

Requirements:

* Use valid JSON-LD.
* Keep structured data consistent with visible page content.
* Use the real canonical URL and verified brand information.
* Do not invent ratings, reviews, pricing, download counts, or unsupported offers.
* Do not add unrelated schemas merely to increase the number of rich-result opportunities.
* Validate the resulting JSON-LD and ensure it does not introduce duplicate or contradictory metadata.

Structured data does not guarantee a rich result or better ranking.

## 1.5 Search Console readiness

Prepare the application for Google Search Console monitoring.

* Document the canonical production URL and recommended verification method.
* Verify whether an existing verification token or DNS verification is already configured before adding anything.
* If a verification token is required, use a documented environment variable or the project's existing configuration mechanism.
* Never commit private verification credentials or unrelated secrets.
* Document the sitemap URL for submission.

Do not claim that Search Console has been configured, verified, or submitted unless the required account access and actions are actually available.

## 1.6 Phase 1 acceptance criteria

* Important routes have verified metadata and canonical behavior.
* Crawlability issues found in the audit are fixed.
* Sitemap is present and valid when appropriate.
* Structured data is valid if implemented.
* SPA and Cloudflare Pages routing behavior is documented and tested.
* Existing API and product functionality remain unchanged.
* Lint, type-check, tests, and production build pass where available.
* Remaining external verification requirements are explicitly documented.

Complete Phase 1 before starting Phase 2.

---

# Phase 2 — Product Discoverability

Do not start this phase until Phase 1 is complete or its remaining blockers are explicitly documented.

The objective is to make TFI's actual capabilities and data useful to developers, search engines, and AI systems.

## 2.1 Homepage content

Review the homepage copy without redesigning the page.

Ensure the visible text explains, accurately and concisely:

* What Token Factory Initializr does.
* Who it is for.
* What users can do with the model catalog.
* Which gateway configuration formats are supported.
* Where to browse models and access technical documentation.

Preserve the current Agent/Human onboarding structure and the direct `Browse models` CTA.

Do not add a long marketing section merely to target keywords. Do not disrupt the existing minimal MAGI visual language.

## 2.2 Public model catalog

Inspect the current `/browse` experience and the model API.

Improve discoverability using existing capabilities, where supported:

* Clear page title and introductory description.
* Text that explains the meaning of providers, data sources, and capabilities.
* Links to API documentation.
* Links to relevant model details, if a stable public detail route exists.
* Accurate model-source attribution and update timestamps, if those fields are available.
* Clear empty states and understandable filter terminology.

Do not generate individual SEO pages for every model unless the repository already has a suitable stable detail route and each page can provide meaningful, indexable information.

Do not add new API fields or change the API contract solely for SEO.

Do not render large quantities of hidden keyword text. Important content should be visible and useful to users.

## 2.3 Machine-readable documentation

Audit and maintain the existing:

* `/llms.txt`
* `/agents.md`
* Public API documentation

Ensure they accurately describe the current product and deployed endpoints.

Document relevant details where verified:

* Product purpose and scope.
* Public API base URL.
* Available model, provider, and endpoint resources.
* Supported filters and query semantics.
* Pagination, limits, and error behavior, if implemented.
* Data-source semantics and provenance.
* Relevant configuration-generation conventions.
* Known limitations and data freshness behavior.

Use links to the canonical human-readable documentation where appropriate.

Do not invent endpoints or imply that planned features are already implemented.

Do not duplicate the entire API reference into every machine-readable file. Keep the files concise and internally consistent.

These resources primarily improve machine consumption and agent usability. Do not claim that their existence directly improves Google rankings.

## 2.4 Technical guides

Create only a small number of useful guides based on actual TFI functionality.

Potential topics to validate against the current implementation:

1. Generate LiteLLM configuration from TFI model data.
2. Understand the differences between model IDs, providers, and data sources.
3. Discover models through the public API.
4. Understand the difference between a listed free model, free inference availability, quotas, and upstream credit requirements.

For each proposed guide:

* Confirm that the topic is relevant to actual user problems.
* Prefer concrete examples and tested configurations.
* Explain assumptions and limitations.
* Link to the relevant catalog or API documentation.
* Avoid unsupported performance, cost, or reliability claims.
* Use canonical URLs and appropriate metadata.
* Follow the existing MAGI Design System if a UI page is required.

Do not create all potential guides automatically. Start with the one or two topics that best match confirmed user needs.

Do not produce thin, repetitive, or automatically generated provider/capability pages solely to increase indexed URL count.

## 2.5 Phase 2 acceptance criteria

* Product messaging is accurate and consistent.
* Existing API documentation and machine-readable resources match the deployed API.
* New content, if any, is useful, technically accurate, and linked from relevant pages.
* No duplicate-content explosion or unnecessary routing changes are introduced.
* The existing homepage and browsing workflow remain intact.

---

# Phase 3 — Measurement and Expansion

This phase establishes evidence for future SEO and GEO investments. Do not fabricate historical baselines or promise ranking improvements.

## 3.1 Search measurement

Use Google Search Console as the primary source for Google organic search data.

Track, where available:

* Search impressions.
* Organic clicks.
* Click-through rate.
* Average position, with appropriate caveats.
* Queries.
* Landing pages.
* Indexing and crawl issues.

Document how to compare periods and how to distinguish new content effects from normal fluctuations.

Do not add a Search Console API integration unless it is necessary and authorized.

## 3.2 Product conversion measurement

Review existing analytics before introducing new instrumentation.

The desired funnel is:

`Organic landing → Browse models → Select candidates → Generate config`

If existing analytics supports these events, document how to analyze the funnel.

If event instrumentation is missing:

* Propose a minimal event schema and implementation plan.
* Reuse the existing analytics system, if present.
* Do not add a new analytics vendor or send model selections, credentials, full prompts, or sensitive query values to analytics.
* Obtain approval before implementing a new analytics integration.

Measure meaningful product usage rather than page views alone.

## 3.3 GEO and AI referrals

Define GEO operationally as the discoverability of TFI in AI-assisted search and the traffic or citations that can actually be observed.

Potential observations:

* Referral sessions from identifiable AI platforms.
* Landing pages reached from those referrals.
* Whether TFI is cited or recommended in a fixed set of relevant research questions.
* Which public resources are cited, when attribution is available.

Requirements:

* Clearly distinguish observed traffic, manual spot checks, and third-party estimates.
* Do not claim complete visibility into AI-generated answers.
* Do not assume that every AI crawler fetch can be identified from logs.
* Do not treat a single mention as evidence of stable discoverability.
* Do not add speculative AI-specific metadata or hidden content.
* Do not create an automated GEO monitoring system unless the expected benefit justifies its maintenance cost.

Start with a lightweight manual baseline. Automate only after a repeatable need is demonstrated.

## 3.4 Expansion criteria

Use the collected evidence to decide whether to invest in:

* Additional integration guides.
* Useful model-comparison pages.
* Stable, indexable model-detail pages.
* More detailed capability explanations.
* Improved catalog rendering for crawlers.

Do not expand simply because competitors have many indexed URLs.

---

# 3. Technical Constraints

* Preserve React 18, TypeScript, Vite, Cloudflare Pages, and Pages Functions unless the audit identifies a concrete blocker.
* Do not introduce SSR, a new framework, or a new analytics service without a separate justification and approval.
* Follow `@tokyo3rdhq/magi-design-system` for any visible UI changes.
* Preserve the existing API contracts.
* Do not expose secrets or sensitive data in HTML, metadata, client-side code, logs, or analytics.
* Do not break the existing model browsing, model selection, or configuration-generation flows.
* Do not add new dependencies unless necessary.
* Do not modify unrelated pages or refactor unrelated architecture.
* Keep the implementation compatible with existing CI and deployment conventions.

# 4. Execution Protocol

Work incrementally.

## Step 1

Inspect the repository and production routes. Deliver the concise audit and Phase 1 plan.

## Step 2

Implement Phase 1 only. Run validation and summarize the result.

## Step 3

After Phase 1 is validated, identify the smallest valuable Phase 2 change. Implement only the highest-value content or documentation improvement supported by the audit.

## Step 4

Document the Phase 3 measurement plan. Implement new analytics only if an existing authorized setup supports it or approval is obtained.

If the task environment supports only one uninterrupted implementation session, complete Phase 1 first and clearly separate any Phase 2 changes in the diff and report. Do not silently expand the scope.

# 5. Required Final Report

Provide a concise report containing:

1. **Audit findings:** Confirmed issues and unverified assumptions.
2. **Phase 1 changes:** Files changed and behavior improved.
3. **Phase 2 status:** What was implemented and what remains deferred.
4. **Phase 3 plan:** Metrics and external configuration still required.
5. **Validation:** Exact lint, type-check, test, and build commands executed and their results.
6. **Production verification:** Which URLs were checked and which checks require manual verification.
7. **Risks and follow-ups:** Any remaining indexing, rendering, content, or measurement concerns.

Do not claim pages are indexed, rankings improved, Search Console is configured, or AI citations increased unless reliable evidence establishes those facts.

The primary objective is a technically sound, discoverable, trustworthy TFI product—not maximizing the number of SEO artifacts.

