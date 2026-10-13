# Refactor TFI Footer — Information Architecture, Content Audit, and MAGI Design System

## Objective

Refactor the footer of Token Factory Initializr (TFI) at `https://start.magi.website`.

The current footer feels cluttered, and its copy, links, and resource references may be outdated or inconsistent with the product's current direction. Audit the existing implementation and deliver a clean, maintainable footer that helps humans, AI agents, and developers discover the right resources.

Repository: https://github.com/tokyo3rdhq/token-factory-initializr

The product is evolving from a free-model discovery tool into a general-purpose AI model catalog and gateway configuration tool. Do not frame TFI as exclusively free-model-only unless a specific link or feature genuinely concerns free models.

**This is a focused footer refactor, not a homepage redesign or a new documentation project.**

## 1. Inspect the existing implementation

Before editing, inspect:

* The current footer component and all related styles.
* The existing application shell, header, and global layout.
* The installed version and actual usage of `@tokyo3rdhq/magi-design-system`.
* Existing theme tokens, typography, spacing, responsive layout, and icon conventions.
* Current routing and link-handling conventions.
* The actual implemented public pages and API endpoints.
* The content and availability of `/llms.txt` and `/agents.md`.
* The GitHub repository URL and relevant project documentation.
* Any existing links to external documentation, issue trackers, community resources, or related MAGI sites.
* Localization conventions and translation files, if the site supports multiple languages.
* Existing accessibility, lint, test, and build requirements.

Create an inventory of the current footer links and classify each as:

1. Verified and useful.
2. Valid but outdated or poorly labeled.
3. Duplicated.
4. Broken or pointing to nonexistent resources.
5. Unverified and requiring further inspection.
6. Planned functionality that must not be presented as currently available.

Verify internal links against actual routes and external links against authoritative destinations where practical. Do not assume a link exists just because it appears in an old document or previous implementation.

After this audit, proceed with the refactor. Do not stop at an inventory unless a genuine blocker prevents implementation.

## 2. Footer information architecture

Use a compact, deliberate structure with a clear hierarchy. Prefer a small number of useful groups over a long collection of unrelated links.

Use the following as the proposed information architecture, adapting labels and removing any group that lacks verified resources.

### Group A — Product

Purpose: Help human users return to the main workflow.

Potential links, only when verified:

* Browse Models → the actual model-browsing route.
* API Reference → the actual API documentation or the most useful existing API entry point.
* About TFI → only if an existing, meaningful destination exists.

Do not create an About page solely to fill a footer column.

### Group B — For Agents

Purpose: Make TFI's machine-readable resources discoverable.

Potential links:

* `llms.txt` → `/llms.txt`.
* `agents.md` → `/agents.md`.
* Models API → `/api/v1/models`.
* Model Details API → documentation for `/api/v1/models/{id}`, or the actual route if linking directly to the API is appropriate.

Only include endpoints that actually exist and return the documented contract.

Use concise, human-readable labels. Avoid repeating every API endpoint in multiple columns.

The Agent resources should be visually discoverable without making the footer look like a raw API directory.

### Group C — Developers

Purpose: Provide a clear path for contribution and technical investigation.

Potential links, only when verified:

* GitHub Repository → `https://github.com/tokyo3rdhq/token-factory-initializr`.
* Issues / Bug Reports → the repository's actual issue tracker.
* Contributing → a real contributing guide, if present.

Do not create placeholder contribution links or link to nonexistent files.

### Optional Group D — MAGI / Legal

Only include this group if the repository or product already has meaningful, verified destinations, such as:

* MAGI main website.
* Privacy Policy.
* Terms of Service.
* Other relevant official project resources.

Do not invent legal documents, social profiles, support channels, or related products.

If there are too few valid links for four groups, use two or three columns instead. Do not retain empty groups or create unnecessary links to make the layout symmetrical.

## 3. Footer content and brand copy

Rewrite the footer's brand description to match TFI's current product direction.

The copy should communicate that TFI helps users discover AI models, compare provider-specific options, and generate configurations for supported gateways.

Use concise, factual language. For example, a possible starting point is:

"Discover AI models, compare provider options, and generate configurations for supported AI gateways."

Treat this as a draft, not mandatory final wording. Refine it based on the actual implemented capabilities.

Requirements:

* Do not describe TFI exclusively as a free-model directory.
* Do not claim that all models are free, unlimited, always available, or directly callable.
* Do not claim that every gateway, provider, or model format is supported.
* Do not describe planned natural-language recommendations or subscriptions as existing features unless they are implemented.
* Avoid generic marketing slogans and lengthy explanations.
* Keep link labels specific and easy to understand.
* Ensure the footer copy agrees with the homepage, API documentation, `llms.txt`, and `agents.md`.

Use the existing translation mechanism if the site is localized. Do not introduce a new i18n framework or hardcode translated text in a way that conflicts with existing conventions.

## 4. Visual design — follow MAGI Design System

The footer must feel like a natural extension of the existing TFI site.

Mandatory requirements:

* Use `@tokyo3rdhq/magi-design-system` and the existing global tokens wherever applicable.
* Follow the existing dark-first visual language.
* Reuse established typography, spacing, colors, borders, and responsive breakpoints.
* Use existing icon components and conventions.
* Avoid introducing a second design system or independent footer-specific token set.
* Keep the footer visually subordinate to the main browsing experience.
* Ensure readable contrast for muted text and links.
* Make interactive states consistent with existing navigation and link styles.
* Use a restrained separator or subtle border if consistent with the current design system.
* Avoid large decorative backgrounds, oversized branding, excessive columns, card grids, or unnecessary badges.

Do not redraw or replace the canonical MAGI logo. Reuse the existing approved brand assets and component conventions.

### Suggested layout

Desktop:

* A compact brand and description area.
* Two or three small, clearly labeled link groups.
* A restrained bottom row for copyright and verified legal or brand links, if appropriate.

Mobile:

* Stack the groups vertically.
* Preserve logical reading order.
* Avoid horizontal overflow.
* Keep link targets comfortably usable.
* Do not force desktop columns into a cramped mobile grid.

These are layout guidelines, not instructions to build a rigid template. Fit the structure to the actual link inventory and existing site design.

## 5. Link management and maintainability

Make the footer easy to maintain.

If the existing implementation supports a shared navigation or resource configuration, reuse it. Otherwise, introduce a small, local, typed footer-link configuration only if it genuinely reduces duplication.

Requirements:

* Keep link labels, destinations, grouping, and optional external-link behavior together.
* Avoid repeating the same destination across several groups without a clear reason.
* Prefer the project's existing route helpers or link components.
* Use proper external-link handling consistent with the existing codebase.
* Do not add dependencies merely to manage a short list of links.
* Do not build a generic CMS, plugin system, or global navigation framework for this task.
* Keep footer-specific configuration local unless there is an existing shared source of truth.

If a link is temporarily unverified, do not silently publish it. Resolve it, remove it, or document the unresolved item in the final report.

## 6. Accessibility and responsive behavior

Ensure that:

* Footer groups use semantic structure and accessible headings.
* Links are actual links with meaningful accessible names.
* Keyboard navigation and visible focus indicators work.
* Muted text and links meet the application's applicable contrast requirements.
* External links follow the project's existing safe-link conventions.
* Decorative icons do not create redundant screen-reader output.
* Responsive layouts do not cause overflow or clipping.
* Footer spacing remains consistent with the global page shell.

Do not add interaction controls that have no real behavior.

## 7. Scope boundaries

Do not:

* Redesign the header, homepage, or `/browse` model list.
* Change API behavior or response schemas.
* Create new product pages simply to populate footer groups.
* Invent privacy policies, terms, social links, or support destinations.
* Add analytics or tracking events.
* Add a new documentation framework.
* Introduce unnecessary dependencies.
* Replace MAGI Design System components with bespoke styles.
* Modify unrelated components or routing logic.
* Claim that a link is live without verifying its destination.

You may update existing footer copy and link labels, and fix incorrect links when the intended destination is clear.

If the audit reveals that an important resource genuinely does not exist, report it as a follow-up rather than expanding the task into building that resource.

## 8. Verification

After implementation:

1. Run the existing lint, type-check, test, and production build commands where available.
2. Inspect the footer on desktop and mobile widths.
3. Verify every internal footer link against the actual application routes.
4. Verify external destinations where practical.
5. Confirm `/llms.txt`, `/agents.md`, and any linked API endpoints are real and consistent with their descriptions.
6. Check that the footer works in supported themes and locales.
7. Confirm there are no duplicate links, placeholder destinations, empty groups, or stale Free-only positioning.
8. Review the diff to ensure unrelated UI and functionality remain unchanged.

Do not claim a browser check, external link check, or production verification unless it was actually performed. Clearly distinguish source-code verification from live-site verification.

## 9. Completion report

Report:

* The main problems found in the original footer.
* The final group structure and rationale.
* Links added, removed, renamed, or corrected.
* The updated brand description.
* Components, styles, and translation files changed.
* How the implementation reuses MAGI Design System.
* Responsive and accessibility checks performed.
* Tests, type checking, linting, and build results.
* Any missing resources that should be considered as separate follow-up work.

**Definition of done:** The footer is concise, visually consistent with MAGI Design System, aligned with TFI's current general model-catalog direction, and contains only useful, verified links. Human users, AI agents, and developers can find their relevant resources quickly without the footer becoming a second navigation menu.

