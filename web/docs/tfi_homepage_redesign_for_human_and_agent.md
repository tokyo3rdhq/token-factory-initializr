# Task: Redesign the TFI Start Homepage for Agents and Humans

## 1. Objective

Redesign the homepage of **Token Factory Initializr (TFI)** at `https://start.magi.website`, taking inspiration from the agent-friendly onboarding pattern on `https://icons.lobehub.com/`.

The goal is to help two types of visitors immediately understand how to use TFI:

* **AI agents**: copy a concise prompt and discover the machine-readable API documentation.
* **Human users**: understand the product workflow and navigate to the model browser to generate a configuration.

This is a focused homepage UX improvement, not a full-site redesign.

## 2. Repository and Existing Architecture

Before implementing anything:

1. Inspect the repository, current homepage, routing, shared components, design tokens, localization, and existing navigation.
2. Confirm the actual implementation of the current `/` route and the existing model browsing and configuration-generation flow.
3. Inspect the existing `llms.txt` and `agents.md` endpoints or static files. Verify their actual URLs and content.
4. Review the existing `@tokyo3rdhq/magi-design-system` integration and reuse its design tokens and components where appropriate.
5. Check the existing package manager, scripts, linting, type checking, and test conventions.

Known project context:

* Product: Token Factory Initializr (TFI)
* Website: `https://start.magi.website`
* Stack: Cloudflare Pages, React 18, TypeScript, Vite, Pages Functions, Cloudflare KV
* The product helps users select model candidates and generate configurations for supported model gateway implementations.
* Existing model browser: `/browse`
* Existing machine-readable API includes `GET /api/v1/models`; provider and endpoint APIs may also be available.

Treat this context as a starting point, not a substitute for repository inspection. Do not assume that every planned endpoint has already been implemented.

## 3. Design Reference

Reference: `https://icons.lobehub.com/`

Reproduce the relevant interaction pattern, not the reference site's complete visual identity:

* A two-option tab switcher:

  * `I'm an Agent`
  * `I'm a Human`
* The active tab displays a different onboarding panel.
* The Agent panel presents a short, actionable, one-sentence prompt.
* A copy icon sits at the right of the prompt and copies the exact prompt text.
* The Human panel explains the product workflow in three numbered steps.
* Both panels expose subtle links to `llms.txt` and `agents.md`.

Maintain the MAGI design language: dark-first, minimal, refined, technical, and consistent with the existing design system.

Do not copy LobeHub's branding, logo, exact styling, or unrelated homepage sections.

## 4. Information Architecture

Keep the homepage focused and compact. The main content should contain:

1. A product heading and a short description.
2. The Agent/Human tab switcher.
3. The active onboarding panel.
4. A shared footer row containing links to `llms.txt` and `agents.md`.

Preserve existing global navigation and any essential product links unless repository inspection reveals a clear reason to change them.

Do not add unrelated feature cards, testimonials, pricing sections, animated backgrounds, or new marketing content.

## 5. Agent Tab

### 5.1 Tab label

`I'm an Agent`

### 5.2 Prompt

Use a concise prompt that instructs the visiting agent to read the TFI machine-readable instructions and then use the existing API to discover models.

Suggested default prompt:

`Read https://start.magi.website/llms.txt to learn how to use TFI, then discover available models through its API and help me choose suitable models for my task.`

Keep the prompt in a single source of truth in the component or existing localization/content layer. Do not duplicate the string in multiple components.

If repository inspection reveals that `llms.txt` already contains a better canonical agent instruction, align the prompt with it rather than creating conflicting instructions.

### 5.3 Prompt presentation

* Render the prompt in a compact, clearly distinguishable surface.
* Place a copy icon button on the right.
* Keep the prompt readable without excessive wrapping on desktop.
* On narrow screens, allow natural wrapping while keeping the copy button accessible.
* Do not truncate the underlying prompt text.
* Use an existing icon library or the project's established icon component. Do not introduce a new icon dependency solely for this button.

### 5.4 Copy interaction

When the user activates the copy button:

1. Copy the exact displayed prompt to the clipboard using the Clipboard API.
2. Provide accessible feedback, such as a temporary `Copied` label or a tooltip/toast using existing project conventions.
3. If clipboard access fails, show an understandable failure state and provide a practical fallback if the project already has one.
4. Prevent accidental triggering of the tab switcher or parent click handlers.
5. Support keyboard activation and a descriptive accessible label, such as `Copy agent prompt`.

Do not display a successful-copy message before the copy operation succeeds.

### 5.5 Agent documentation links

Display two understated links beneath the prompt:

* `llms.txt`
* `agents.md`

Use the verified canonical URLs, preferably:

* `https://start.magi.website/llms.txt`
* `https://start.magi.website/agents.md`

Before using these exact URLs, verify that they resolve and contain the intended content. If the repository exposes different canonical routes, use those instead.

Use a subtle external-link indicator only if consistent with the existing design system. Links should remain discoverable and keyboard accessible.

## 6. Human Tab

### 6.1 Tab label

`I'm a Human`

### 6.2 Three-step onboarding flow

Display the following three steps in order.

**Step 1 — Define your needs**

Describe what you want to do and identify the model capabilities you need, such as chat, vision, or other supported capabilities.

**Step 2 — Browse models**

Explore available models, inspect their capabilities and available sources, and select suitable candidates.

**Step 3 — Generate config**

Choose a supported Token Factory implementation, select your candidate models, and generate a configuration for your setup.

Adapt the wording to the actual product capabilities discovered in the repository. Do not imply that natural-language recommendations or unsupported capabilities already exist.

### 6.3 Navigation behavior

Provide a clear primary action, preferably `Browse models`, that navigates to the existing `/browse` route.

* Reuse the existing router and navigation conventions.
* Do not introduce a second model-selection flow on the homepage.
* Do not duplicate model browsing or configuration-generation logic.
* If the current product already has an appropriate CTA or route, reuse it.

### 6.4 Step layout

On desktop, prefer a horizontal three-step layout with clear visual hierarchy.

Each step should include:

* A small, visually restrained step number.
* A concise title.
* One short explanatory sentence.

On mobile, stack the steps vertically or use another layout that preserves their order and readability.

Avoid oversized cards, excessive borders, unnecessary icons, and decorative illustrations.

## 7. Shared Documentation Links

Both tab panels must expose the same two links:

* `llms.txt`
* `agents.md`

Prefer implementing them once in a shared footer area below the tab content, so switching tabs does not cause unnecessary layout changes.

Use smaller, muted text with sufficient contrast. These links are secondary navigation, not primary calls to action.

Use real, verified routes. Do not invent documentation content or point to nonexistent pages.

If the same links are already present elsewhere in the homepage, avoid creating redundant copies.

## 8. Visual Direction

Follow the existing MAGI design system and tokens.

Desired qualities:

* Dark-first and premium.
* Minimal, precise, and developer-oriented.
* Strong typography hierarchy and generous but controlled spacing.
* Restrained borders and neutral surfaces.
* Subtle active-tab styling.
* Clear separation between the prompt panel and the human workflow.
* Consistent corner radii, spacing, colors, and focus indicators.
* Responsive behavior without horizontal overflow.

Avoid:

* Generic AI gradients or glowing orbs.
* Excessive glassmorphism and shadows.
* Large decorative illustrations.
* Oversized cards around every step.
* Bright accent colors used indiscriminately.
* Recreating the LobeHub homepage wholesale.

Use existing CSS variables, utility classes, and components wherever possible. Avoid introducing arbitrary hardcoded colors when design tokens already exist.

## 9. Functional and Accessibility Requirements

* The selected tab must have a clear active state.
* Tabs must be keyboard accessible and expose appropriate ARIA roles and relationships.
* Tab content must update correctly when the selected tab changes.
* The copy button must have an accessible name and visible keyboard focus.
* All links must have meaningful destinations.
* Preserve existing internationalization conventions if the project supports multiple languages.
* Respect reduced-motion preferences; this interaction does not require animation.
* Do not add analytics, external tracking, or new backend endpoints as part of this task.

## 10. Implementation Constraints

* Keep the change focused on the homepage and directly related components or styles.
* Reuse existing dependencies and design-system components.
* Do not upgrade React, Vite, TypeScript, or unrelated dependencies.
* Do not introduce a new UI framework.
* Do not modify the existing API contract, model catalog pipeline, configuration generation, or deployment architecture.
* Do not remove existing routes or functionality.
* Avoid unnecessary abstractions for a simple two-tab component.
* Keep the implementation compatible with Cloudflare Pages deployment.

## 11. Validation

After implementation:

1. Run the existing lint, type-check, test, and build scripts that are available in the repository.
2. Fix regressions introduced by this change.
3. Verify that both tabs work and the default tab is intentional.
4. Verify that the copy button copies the exact prompt and handles failure appropriately.
5. Verify that both documentation links resolve.
6. Verify that `Browse models` navigates to the existing `/browse` route.
7. Check desktop and mobile layouts, including a viewport around 375px wide.
8. Check keyboard navigation, visible focus, and accessible tab semantics.
9. Review the final diff and confirm that unrelated files and behaviors remain unchanged.

If browser-based visual testing is available, inspect the actual rendered homepage rather than relying solely on a successful build.

## 12. Completion Report

When finished, provide a concise report containing:

* What changed.
* Which components and files were modified.
* How the Agent and Human tabs behave.
* Which documentation URLs were verified.
* Which validation commands were run and their results.
* Any known limitations or follow-up items.

Implement the change directly. Do not stop after producing a plan unless a genuine blocker requires clarification.

