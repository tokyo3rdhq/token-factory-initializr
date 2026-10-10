# Task: Rebuild the TFI Start Homepage — Lobe Icons Information Architecture, MAGI Design System

## 0. Objective

Redesign the existing homepage of `https://start.magi.website` because the current implementation does not meet the expected visual quality.

Use `https://icons.lobehub.com/` as the primary reference for page structure, content hierarchy, and the interaction pattern that separates Agent and Human onboarding.

Implement the page using the existing `@tokyo3rdhq/magi-design-system` conventions and the current TFI codebase.

**This is a focused homepage reconstruction, not an open-ended visual redesign.**

The result should feel like a polished MAGI product page: minimal, deliberate, information-dense without clutter, technically credible, and consistent with the rest of `magi.website`.

### Priority order

1. Correct use of the existing MAGI Design System.
2. Reproduce the reference's Agent/Human information architecture.
3. Clear hierarchy and excellent visual alignment.
4. Working copy interaction and navigation.
5. Responsive behavior and accessibility.

Do not sacrifice design-system compliance to imitate the reference.

---

## 1. Mandatory repository inspection

Before editing code, inspect the actual repository. Do not assume any component, token, route, or feature exists.

Read and inspect:

* The homepage entry point and current route implementation.
* Existing header, navigation, footer, and page-container components.
* The installed `@tokyo3rdhq/magi-design-system` version, package exports, CSS entry points, tokens, typography utilities, layout primitives, component APIs, and documentation available in the repository.
* Existing theme configuration, dark/light mode behavior, CSS scoping conventions, and global styles.
* Existing i18n implementation and translation-file structure.
* Current `/browse` route and the actual model-browsing and config-generation flow.
* The real implementation and response format of `/llms.txt`, `/agents.md`, and the relevant API endpoints.
* Existing icon dependencies and clipboard utilities, if any.

Use the installed package and source code as the authority. Do not invent design-system APIs or copy implementation examples from an incompatible version.

If the current homepage has already been modified, identify which elements should be retained and which elements cause the poor result. Do not layer a second redesign over the first one without understanding the existing DOM and styles.

Before coding, provide a brief implementation plan. Then implement the page rather than stopping at recommendations.

---

## 2. Reference interpretation

Reference: `https://icons.lobehub.com/`

Study the actual rendered page at desktop and mobile widths if browser inspection is available. Inspect the source implementation when useful.

Reproduce these principles:

* A clear, centered main content region.
* A compact, unambiguous page introduction.
* Two audience-specific sections represented by `I'm an Agent` and `I'm a Human`.
* A simple tab or switcher that changes the main instructional content in place.
* Instructions that are immediately usable, not buried inside decorative cards.
* Copyable Agent instructions with an obvious copy affordance.
* Human instructions with a clear next step.
* Secondary documentation links that remain easy to discover without competing with the primary content.
* Minimal borders, subtle separators, restrained color, and deliberate whitespace.

Do not reproduce LobeHub branding, logo, exact copy, unrelated icon catalogs, or unrelated sections.

Do not transform this page into a generic SaaS landing page.

### Explicitly prohibited visual patterns

* Giant gradient hero backgrounds.
* Neon or cyberpunk colors.
* Decorative blurred gradient blobs.
* Large floating glassmorphism cards.
* Three oversized feature cards with icons and paragraphs.
* A dashboard-like grid of metrics.
* Unnecessary illustrations or decorative SVG artwork.
* Large rounded panels nested inside other large rounded panels.
* Excessive shadows, pills, badges, and colored surfaces.
* Arbitrary iconography used merely to fill empty space.
* Oversized headings that push the actual onboarding content below the fold.
* Multiple competing primary buttons.
* A second navigation bar inside the page.

If a proposed visual element does not improve hierarchy, comprehension, or interaction, omit it.

---

## 3. MAGI Design System is mandatory

The installed `@tokyo3rdhq/magi-design-system` is the source of truth for implementation.

### 3.1 Tokens

Use the actual available semantic tokens and utilities for:

* Page and surface backgrounds.
* Primary and secondary text.
* Muted text.
* Borders and separators.
* Primary action and link colors.
* Typography sizes, weights, and line heights.
* Spacing.
* Border radii.
* Focus indicators.
* Theme behavior.

Do not guess token names. Inspect their definitions and existing usages first.

Do not introduce arbitrary hex colors, new spacing scales, new radius scales, or parallel CSS variables when the design system already provides an equivalent.

Do not create a local design system just for this homepage.

### 3.2 Components

Prefer existing components and primitives for:

* Site navigation.
* Buttons and links.
* Tabs or segmented controls.
* Code or instruction surfaces.
* Icon buttons.
* Layout and page containers.
* Theme and accessibility behavior.

Verify their actual props and supported variants before using them.

If no suitable Tabs component exists, implement a small accessible tab component using existing project conventions. Do not install another component library just to obtain Tabs.

### 3.3 Brand

* Preserve the existing MAGI brand assets and their intended rendering.
* Do not redraw, replace, distort, or arbitrarily recolor the MAGI logo.
* Do not use the reference site's brand colors as a replacement for MAGI tokens.
* Follow the current TFI accent-color convention only where emphasis is necessary.
* Keep the overall palette restrained and consistent with existing MAGI pages.

### 3.4 CSS

* Follow the existing CSS entry-point and theme setup.
* Scope homepage-specific rules to the homepage.
* Avoid broad selectors that unintentionally change the navbar, footer, or other routes.
* Do not add competing global styles or override design-system defaults without a documented reason.
* Remove obsolete styles introduced by the previous implementation when safe to do so.

---

## 4. Exact page structure

Keep the existing site-wide navigation and footer. Do not redesign either.

The homepage content must follow this exact order:

1. Existing site navigation.
2. Compact introductory block.
3. Two-option audience switcher.
4. One content panel whose content depends on the selected audience.
5. Muted documentation links for `llms.txt` and `agents.md`.
6. Existing footer.

Do not insert a second hero, testimonial section, pricing section, FAQ, feature grid, or other landing-page content.

### 4.1 Main container

Use the existing MAGI page-layout primitive or its equivalent.

Target visual proportions at desktop:

* Main content width: approximately 680–760px.
* Main content centered horizontally.
* Introductory block begins approximately 80–112px below the bottom of the site navigation, adjusted to match the existing site's rhythm.
* Main content should not stretch across the entire viewport.
* Use a consistent vertical spacing scale derived from the design system.
* Keep the page visually balanced when the Human tab has more content than the Agent tab.
* Avoid fixed heights that create empty space or clip content.

These are layout targets, not permission to bypass existing layout tokens. Use the closest supported token or layout utility.

### 4.2 Introductory block

Use the following copy, unless existing product terminology requires a minor consistency correction:

Eyebrow, optional and visually understated:

`TOKEN FACTORY INITIALIZR`

Main heading:

`Find the right models. Generate your config.`

Description:

`Explore available models and turn your selection into a configuration for your AI gateway.`

Requirements:

* One heading only.
* Heading should be prominent but not oversized.
* Keep the description to a comfortable reading width.
* Do not add a decorative illustration or large icon.
* Do not add a primary CTA here; the main onboarding panel should own the next action.
* Use existing MAGI typography styles.

### 4.3 Audience switcher

Display two adjacent options:

* `I'm an Agent`
* `I'm a Human`

The switcher should sit directly below the introduction, with a clear visual relationship to the content panel beneath it.

Requirements:

* Use the existing Tabs or segmented-control component if available.
* Otherwise, implement a compact, accessible tab switcher.
* Avoid giant pill-shaped buttons.
* Avoid oversized icons inside the tabs.
* Avoid separate full-page navigation or route changes when switching tabs.
* The active tab should be obvious through a restrained background, border, or text treatment supported by the design system.
* Inactive text should remain readable.
* Keep both tabs visually balanced and approximately equal in width.
* Do not add an unrelated third option.

Interaction:

* Clicking a tab changes the content panel without navigating away.
* Preserve the selected tab during ordinary component rerenders.
* If the project already supports URL-based tab state, follow its conventions. Do not introduce new routing complexity just for this page.
* Support keyboard navigation and the appropriate ARIA tab semantics if using the tabs pattern.

---

## 5. Agent tab — exact content and behavior

The Agent tab should reproduce the central idea of the Lobe Icons Agent onboarding: one instruction that can be copied and used immediately.

### Content

Heading:

`Give your agent the context it needs.`

Supporting text:

`Read the TFI instructions first, then discover available models through the API.`

Instruction surface:

`Read https://start.magi.website/llms.txt to learn how to use TFI, then discover available models through its API and help me choose suitable models for my task.`

Before implementing this text, verify that the URL exists and its actual content explains the intended workflow. If the repository contains a canonical Agent prompt or skill, reuse it or align the copy with it. Do not invent unsupported API capabilities.

### Instruction surface layout

Use a single, compact surface:

* The instruction text occupies the main area.
* A copy icon button sits at the right side, vertically aligned with the text.
* The text wraps naturally on narrow screens.
* The copy control must never overlap the text.
* Use a subtle border or surface treatment from MAGI tokens.
* Do not create a large card around the heading, another card around the text, and a third card around the links.
* Do not use a large code-editor aesthetic, syntax highlighting, line numbers, or a terminal mockup.
* Use a monospace style only if it improves the presentation of the actual instruction without harming readability.

The copy icon should use an existing project icon or icon package. Do not add a dependency merely to obtain one icon.

### Copy behavior

* Copy the exact instruction string to the clipboard.
* Use the existing clipboard helper if the project has one; otherwise use the browser Clipboard API with proper error handling.
* Give the icon button an accessible label such as `Copy agent instructions`.
* After a successful copy, provide concise success feedback, such as `Copied`.
* If copying fails, provide visible failure feedback and a usable fallback, such as selecting the text for manual copying.
* Do not claim success before the copy operation succeeds.
* Prevent repeated clicks from producing duplicate or confusing feedback.
* Ensure the button has visible hover, focus, active, and disabled states where applicable.

### Agent tab visual hierarchy

1. Small heading.
2. One concise explanation.
3. One instruction surface with copy action.
4. Shared documentation links below the panel.

Nothing else is needed.

Do not add a list of imaginary agent capabilities, a feature matrix, or multiple alternative prompts.

---

## 6. Human tab — exact content and behavior

The Human tab should explain the existing TFI workflow in three compact steps. This is an onboarding guide, not a feature-card section.

Heading:

`Build your model configuration in three steps.`

Supporting text:

`Choose what you need, explore the catalog, and generate a configuration for your gateway.`

### Step 1

Title:

`Define your needs`

Description:

`Identify your task and the capabilities you need, such as chat or vision.`

### Step 2

Title:

`Browse models`

Description:

`Compare available models, providers, sources, and supported capabilities.`

### Step 3

Title:

`Generate config`

Description:

`Choose a supported gateway, select your models, and generate its configuration.`

All descriptions must reflect the current application. Inspect the actual product before implying that natural-language recommendations, automatic model ranking, or configuration validation already exists.

### Layout requirements

Render the three steps as a single ordered vertical sequence, not three oversized cards.

Each step contains:

* A small numbered marker: `01`, `02`, `03`.
* A concise title.
* A single short description.

Desktop:

* Align all step markers to one vertical axis.
* Align all titles and descriptions to a second vertical axis.
* Use consistent marker width, text alignment, and vertical spacing.
* Use subtle separators only if they improve readability.
* Keep the overall content width consistent with the Agent panel.

Mobile:

* Retain the same ordered sequence.
* Keep markers and text aligned.
* Let descriptions wrap naturally.
* Do not convert the sequence into a horizontally scrolling carousel.

Do not give each step a different accent color. Do not add decorative icons to the numbered markers. Do not add nested cards or oversized backgrounds.

### Primary action

Use one primary action after the three steps:

`Browse models`

It must navigate to the existing model-browsing route, expected to be `/browse`. Verify the actual router configuration before wiring it.

Requirements:

* Reuse the existing button component and supported primary variant.
* Use the project's existing router or link component.
* Do not create a duplicate browsing page.
* Do not implement model selection or configuration generation inside the homepage.
* Keep the button visually prominent but not oversized.

Human tab visual hierarchy:

1. Small heading.
2. One concise explanation.
3. Three vertically aligned steps.
4. One primary `Browse models` action.
5. Shared documentation links below the panel.

---

## 7. Shared documentation links

Both tabs must display the same two documentation links beneath the active content panel:

* `llms.txt`
* `agents.md`

Requirements:

* Verify the actual URLs and the files' contents.
* Use real routes or absolute URLs supported by the deployment.
* Reuse the project's standard link styling.
* Render the links as small, muted, readable text.
* Keep them visually secondary to the main content.
* Use a small separator such as `·` only if it matches existing typography conventions.
* Place them in one shared component or one shared markup location, not separately duplicated inside each tab.
* Switching tabs must not make the links jump to a different location or change their styling.
* Open in the same tab unless the project's documentation-link convention explicitly requires otherwise.
* Do not invent a `skills.md` endpoint or claim that `agents.md` contains instructions it does not actually contain.

Suggested presentation:

`llms.txt  ·  agents.md`

No icon is required for either link.

---

## 8. Visual specification

The target is a compact, refined product onboarding page, not a marketing hero.

### Surface and contrast

* Use the existing page background.
* Use a single subtle surface for the instruction block only if the design system calls for it.
* Keep most of the page on the base canvas.
* Use borders and separators sparingly.
* Maintain adequate contrast for muted descriptions and documentation links.
* Never use reduced opacity as the sole way to indicate an interactive or disabled state.

### Typography

* Use the existing MAGI typography scale.
* Establish hierarchy through size, weight, and spacing rather than color alone.
* The main heading should be visually distinct but compact.
* Section headings should be clearly subordinate to the main heading.
* Descriptions should remain comfortable to read.
* Avoid excessive uppercase labels, letter spacing, and decorative typography.

### Shape and spacing

* Use the existing design-system radii.
* Keep the copy surface's corner radius modest.
* Use a consistent spacing rhythm.
* Avoid large rounded containers around the entire page.
* Avoid nested rounded surfaces.
* Align the main heading, tabs, content panel, CTA, and documentation links to the same content axis.

### Motion

* No elaborate tab animations.
* No entrance animations or scroll-triggered effects.
* If a transition is already part of the design system, keep it subtle.
* Respect `prefers-reduced-motion`.

### Icons

* Use icons only for actual controls, such as copy.
* Reuse existing icon conventions.
* Do not add decorative icons to every step.
* Do not introduce an icon library for this page alone.

---

## 9. Responsive requirements

Validate the page at these viewport widths:

* Desktop: `1440px`.
* Laptop: `1024px`.
* Tablet: `768px`.
* Mobile: `375px`.

At all widths:

* The page must remain centered and readable.
* The header must continue using the existing responsive navigation behavior.
* No horizontal overflow.
* The two audience options must remain easy to tap.
* The copy icon must stay inside the instruction surface.
* Text must wrap without clipping or overlapping.
* The Human step markers must remain aligned with their text.
* The primary CTA must remain usable.
* Documentation links must not overflow.

On mobile, reduce outer margins using existing responsive conventions rather than shrinking text excessively.

Do not solve responsive problems with arbitrary absolute positioning.

---

## 10. Accessibility and i18n

* Use semantic HTML.
* Use the existing i18n system and translation conventions.
* Do not introduce a second localization mechanism.
* Ensure all new user-facing strings follow the repository's translation conventions.
* Provide accessible labels for icon-only buttons.
* Ensure visible keyboard focus.
* Support keyboard navigation between tabs.
* Expose selected tab state to assistive technologies.
* Maintain sufficient text and control contrast.
* Ensure the copy interaction is understandable without relying on color alone.
* Preserve browser zoom and text resizing behavior.

---

## 11. Scope restrictions

Do not:

* Redesign the global navigation or footer.
* Modify model browsing or configuration-generation logic.
* Change API contracts or backend behavior.
* Add new backend endpoints.
* Add analytics instrumentation.
* Add new UI dependencies without justification.
* Add fake product data or unsupported feature claims.
* Modify the design-system package merely to accommodate a one-off homepage.
* Refactor unrelated pages or application architecture.
* Remove existing functionality that is outside this task.

Keep the diff focused and explain any unavoidable changes outside the homepage.

---

## 12. Required implementation and verification process

### Phase A — Inspect

Identify the homepage files, existing components, design-system version, theme setup, routes, i18n conventions, and documentation URLs.

### Phase B — Implement

Rebuild the homepage using the exact content hierarchy and constraints above. Reuse the existing design system and application conventions.

### Phase C — Verify functionality

Test:

* Both audience tabs switch correctly.
* Tab state and accessibility semantics are correct.
* The copy button copies the exact instruction.
* Success and failure states work.
* `Browse models` reaches the actual existing browse route.
* `llms.txt` and `agents.md` links resolve correctly.
* No unrelated route or functionality regresses.

### Phase D — Verify design quality

Inspect the rendered page at the four required viewport widths.

Check specifically:

* Content width and centering.
* Vertical rhythm.
* Typography hierarchy.
* Alignment of heading, switcher, panel, CTA, and documentation links.
* Copy icon positioning.
* Text wrapping.
* Border and radius consistency.
* Dark/light theme compatibility where supported.
* Keyboard focus visibility.
* Absence of unnecessary cards, gradients, icons, and decorative elements.

If browser screenshots or a browser automation tool are available, inspect the actual rendered result. Do not treat a successful build as proof of visual correctness.

Compare the result against the reference's information architecture and the actual MAGI design-system implementation. Make a second refinement pass if the rendered page still looks generic, oversized, cluttered, or inconsistent.

### Phase E — Run project checks

Run the repository's available:

* Lint.
* Type check.
* Tests.
* Production build.

Use the project's actual scripts. Do not invent scripts or claim checks passed if they were not executed.

---

## 13. Definition of done

The task is complete only when all of the following are true:

* The homepage has the specified information architecture.
* The Agent and Human tabs work.
* The Agent instruction can be copied.
* The Human three-step guide is clear and compact.
* The primary CTA uses the real existing browse route.
* Both documentation links are verified.
* The page uses MAGI Design System tokens and components where applicable.
* The page does not introduce a parallel visual system.
* The layout works at the required viewport widths.
* Accessibility and project checks have been performed.
* No unrelated product behavior has been changed.

In your completion report, list:

1. Files changed.
2. Components and design-system tokens reused.
3. Verified navigation and documentation URLs.
4. Tests, lint, type-check, and build results.
5. Viewports inspected.
6. Any design-system limitations or intentional exceptions.

**Do not report completion based solely on code generation. The rendered result and actual interactions must be verified wherever the available environment permits.**

