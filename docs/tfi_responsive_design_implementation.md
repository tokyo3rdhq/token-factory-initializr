# Task: Implement Responsive Design for Token Factory Initializr (TFI)

## 1. Objective

Implement production-ready, mobile-first responsive design across the Token Factory Initializr (TFI) website.

**Website:** https://start.magi.website  
**Product:** Token Factory Initializr — a model catalog and configuration generation tool.  
**Shared design system:** `@tokyo3rdhq/magi-design-system` (already upgraded to the latest version in the current repository).

TFI's core user journey is:

1. Browse and discover available models.
2. Search and filter the model catalog.
3. Select one or more models.
4. Choose a supported configuration target, such as LiteLLM, NewAPI, or Bifrost.
5. Generate, inspect, and copy/download the resulting configuration.

The goal is not simply to make existing desktop layouts narrower. Adapt the information architecture, navigation, model discovery, selection controls, and configuration workflow to mobile, tablet, laptop, and desktop screens while preserving TFI's existing functionality.

## 2. Mandatory: Audit the Existing Implementation First

Before editing code, inspect the current repository and identify:

- The frontend framework, routing structure, page components, and styling approach.
- The currently installed `@tokyo3rdhq/magi-design-system` version and its actual exported APIs.
- The existing `Grid`, `Breakpoint` type, responsive `Button` API, and any other available responsive primitives.
- Existing page layouts, navigation, footer, model browse interface, filter controls, selection state, and configuration-generation flow.
- Existing Tailwind configuration, CSS breakpoints, custom media queries, and CSS class-generation behavior.
- Existing localization, loading states, error states, empty states, and analytics instrumentation.
- Existing tests, linting, type checking, build scripts, and available visual testing tools.

Read the installed package's TypeScript declarations and relevant documentation when necessary. Do not rely exclusively on assumptions or examples in this prompt.

Produce a concise implementation plan, then execute it. Do not stop after producing the plan.

### Design-system integration rules

- Treat `@tokyo3rdhq/magi-design-system` as the shared source of truth for MAGI visual foundations and supported reusable components.
- Prefer its existing layout primitives, design tokens, and responsive APIs over duplicate implementations.
- Use the actual public API signatures supported by the installed package.
- Do not assume that a component or prop exists without verifying it.
- Do not hardcode internal `.magi-*` component classes when a public component API is available.
- Keep application-specific layout and interaction logic inside TFI.
- Do not modify the shared design-system package unless a genuine missing capability prevents implementation. If a gap is found, explain it and choose the smallest appropriate solution.

## 3. Responsive Design Principles

### Visual identity

Preserve TFI's existing MAGI visual identity:

- Dark, refined, Apple-inspired visual language.
- Cyan accent appropriate to TFI, consistent with the existing theme configuration.
- Restrained borders, surfaces, spacing, and typography.
- Clear hierarchy and high information density where the task requires it.
- Consistent branding and component behavior across MAGI products.

Do not introduce an unrelated design language, excessive gradients, decorative animations, or unnecessary visual elements.

### Mobile-first behavior

Design from small screens upward. Responsive behavior must be intentional at each breakpoint rather than merely scaling the desktop layout.

Use existing design-system breakpoint tokens and conventions wherever available. Avoid creating competing breakpoint systems or scattering arbitrary media-query values throughout the codebase.

Test at these viewport widths:

- 320 px
- 375 px
- 430 px
- 640 px
- 768 px
- 1024 px
- 1280 px
- 1440 px

Also test intermediate widths where navigation, filter panels, or model cards are likely to transition between layouts.

## 4. Page-by-Page Requirements

### A. Global header and navigation

Audit and adapt the header across all routes.

Requirements:

- Keep the MAGI/TFI branding legible and appropriately sized.
- Preserve navigation hierarchy, active states, language controls, and existing destinations.
- Prevent navigation items from colliding, wrapping unpredictably, or pushing the logo out of alignment.
- On narrow screens, replace the desktop navigation with a compact, accessible mobile menu when appropriate.
- Ensure the menu can be opened and closed using keyboard and touch input.
- Support Escape-to-close where applicable, visible focus, and correct accessibility attributes.
- Avoid layouts where the logo, navigation, and primary action compete for insufficient horizontal space.
- Do not allow fixed headers or overlays to obscure page content.

Use the existing navigation implementation if it can be adapted cleanly. Avoid introducing a new dependency solely for the mobile menu.

### B. Home / entry page

Preserve the existing product positioning and user journey.

Requirements:

- Scale headings and supporting text fluidly without oversized mobile hero typography.
- Allow introductory copy to wrap naturally.
- Stack primary and secondary actions when necessary.
- Ensure buttons are easy to tap and remain visually distinct.
- Reflow feature descriptions, product cards, and other multi-column sections into suitable mobile layouts.
- Use the design system's responsive `Grid` when appropriate and supported by its actual API.
- Keep the main path to browsing models obvious.
- Avoid excessive vertical spacing that pushes the primary action far below the initial viewport.

Do not rewrite product copy or redesign the information architecture unnecessarily.

### C. Browse page — highest priority

The Browse page is a data-dense model discovery interface. Give it the most attention during implementation and visual validation.

#### Search and filters

Adapt the search and filtering controls to the available width.

Desktop:
- Preserve the existing efficient browsing workflow.
- Keep frequently used filters visible where practical.
- Maintain a clear relationship between search, filters, result count, and the model list.

Tablet:
- Reflow filter groups into fewer columns.
- Allow filter controls to wrap or occupy dedicated rows when needed.
- Prevent search fields and filter chips from becoming excessively narrow.

Mobile:
- Give model search a prominent, usable position.
- Move secondary or numerous filters into a collapsible panel, drawer, or other compact interaction if necessary.
- Keep the distinction between active filters and available filters clear.
- Provide a clear way to reset filters.
- Display active filter selections and result count without consuming excessive vertical space.
- Ensure the filter interface does not permanently occupy most of the viewport.
- Preserve existing filter semantics, including model/provider search, capability filters, and any other currently supported filters.

Do not remove filters or change their meaning simply to fit a small screen.

#### Model list

Inspect the existing model-list structure before deciding how it should reflow.

On desktop:
- Preserve the efficient scanning of model names, provider information, capabilities, and other important metadata.
- Maintain appropriate alignment and spacing.
- Avoid adding unnecessary card borders or nested containers if the existing list is already visually effective.

On tablet and mobile:
- Prevent important metadata from being clipped or becoming unreadably compressed.
- If the current table or horizontal layout no longer works, use a responsive model-card or compact-row presentation.
- Prioritize model identity, provider, key capabilities, relevant availability/status information, and the selection control.
- Place secondary metadata in a compact secondary row or a disclosure area if appropriate.
- Keep long model IDs readable, with wrapping or deliberate truncation and a way to inspect the full value.
- Avoid horizontal page scrolling.
- Do not hide essential information without providing an accessible alternative.

Do not force every desktop column into a narrow mobile row. Choose a layout that supports model discovery and comparison.

#### Model selection

Model selection is a core product interaction and must remain clear at every viewport.

Requirements:

- Make selection controls easy to tap.
- Preserve selected and unselected visual states.
- Keep bulk-selection actions, including Select All Visible if currently supported, consistent with existing semantics.
- Clearly distinguish visible results from the entire catalog.
- Preserve selection when users change filters or search, according to the existing application behavior.
- Ensure selection controls remain associated with the correct model when the list changes.
- Do not silently discard selected models during responsive layout changes.
- Keep selected-model counts and any selection summary visible where appropriate.

#### Selected-model action area

If the existing interface provides actions for proceeding to configuration generation, adapt that area for small screens.

A compact sticky bottom action bar may be used if it improves usability, provided that:

- It does not cover model content, filter controls, or other interactive elements.
- The page reserves enough bottom space for the bar.
- It respects mobile safe-area insets.
- It communicates the selected-model count and primary next action.
- It does not duplicate or conflict with an existing sticky action area.
- It does not intercept keyboard navigation or obscure focused controls.

Prefer normal document flow when a sticky element would add more complexity than value.

### D. Generate / configuration-generation page

Adapt the existing configuration-generation flow without changing its business logic.

Requirements:

- Reflow multi-column layouts into a logical single-column sequence on narrow screens.
- Keep configuration target selection visible and easy to operate.
- Ensure supported targets such as LiteLLM, NewAPI, and Bifrost remain accessible wherever they are currently offered.
- Keep selected-model summaries readable without allowing long model IDs to break the layout.
- Make generated configuration code readable and scrollable within its own container when appropriate.
- Preserve syntax highlighting, copy, download, regenerate, and other existing actions.
- Make action buttons wrap or stack cleanly.
- Avoid horizontal overflow caused by long code lines, JSON, YAML, or command snippets.
- Preserve loading, error, success, and empty states.
- Ensure copy/download controls remain usable on touch devices and provide existing feedback.
- Do not modify the generated configuration schema, model IDs, provider mappings, or output semantics as part of this responsive task.

If the workflow includes generated results, previews, or agent-oriented prompts, preserve all existing behavior and adapt their presentation rather than removing them.

### E. Other routes and shared components

Inspect every existing route, including any model details, initialization, generated-result, or documentation views.

Apply consistent responsive behavior to:

- Page containers and section spacing.
- Headings and typography.
- Cards, badges, labels, and metadata.
- Forms, inputs, checkboxes, segmented controls, and other interactive elements.
- Tables, code blocks, and long identifiers.
- Empty, loading, error, and success states.
- Footer columns, links, and legal or product information.

Do not assume every route has the same layout requirements. Keep route-specific behavior appropriate to its purpose.

## 5. Layout, Typography, and Overflow

Use the design system's existing tokens and layout primitives whenever possible.

Requirements:

- Prefer constrained, centered page containers over arbitrary fixed widths.
- Use fluid sizing and responsive spacing where supported by the existing design system.
- Avoid excessive nested containers and duplicated padding.
- Prevent fixed-width components from exceeding their parent containers.
- Ensure flex and grid children can shrink where necessary; inspect `min-width` behavior on long content.
- Apply `min-width: 0`, `overflow-wrap`, `word-break`, or controlled horizontal scrolling only where semantically appropriate.
- Keep code blocks independently scrollable instead of causing page-level overflow.
- Use responsive heading sizes that preserve hierarchy without overwhelming mobile screens.
- Avoid text clipping, overlapping badges, broken button labels, and inconsistent card heights where these harm usability.
- Preserve sufficient contrast and readable text sizes.

Do not use `overflow: hidden` on the page or major containers merely to conceal layout defects.

## 6. Tailwind and CSS Compatibility

If the project uses Tailwind, verify that responsive class names generated by the installed design system are compatible with the current build configuration.

In particular:

- Verify that dynamically selected responsive classes are discoverable by the production CSS build.
- Prefer statically declared class maps or explicitly safelisted classes if the current build requires them.
- Do not assume runtime-generated class strings will be included in the final stylesheet.
- Avoid duplicating responsive styles already provided by the design system.
- Keep custom media queries limited to genuine TFI-specific requirements.
- Avoid broad global overrides that unintentionally change shared MAGI components.
- Keep component-specific responsive rules scoped and understandable.

If the project does not use Tailwind, do not introduce it just for responsive design.

## 7. Accessibility and Interaction

Responsive behavior must not compromise accessibility.

Verify:

- Semantic headings and landmarks.
- Keyboard access to all navigation, filters, selection controls, and generation actions.
- Visible focus indicators.
- Appropriate accessible names for icon-only buttons.
- Sufficient touch target sizes, aiming for approximately 44 × 44 CSS pixels where practical.
- Appropriate contrast for text, disabled states, selected states, and borders.
- Correct dialog/drawer focus management if a modal filter interface is introduced.
- No keyboard traps.
- No reliance on color alone to communicate selection or status.
- Usable behavior at 200% browser zoom.
- Reduced-motion preferences are respected.
- Sticky controls do not obscure keyboard focus or essential content.

Use existing accessible components and patterns whenever possible.

## 8. Preserve Existing Functionality

This is a responsive implementation task, not a feature rewrite.

Do not unintentionally change:

- Routes, links, or navigation destinations.
- API requests, response handling, or model filtering semantics.
- Model selection and bulk-selection behavior.
- Configuration-generation logic or output.
- Download and clipboard functionality.
- Localization or translated content.
- Existing SEO metadata.
- Google Analytics / GA4 event names, triggers, or semantics.
- Existing loading, error, and empty-state behavior.
- Existing keyboard and screen-reader support.

Avoid duplicate analytics events caused by introducing mobile-specific copies of existing controls. Prefer a single responsive implementation or ensure equivalent controls do not double-count the same user action.

Do not add new dependencies unless clearly justified.

## 9. Validation and Testing

Use the repository's existing test and build conventions.

### Automated validation

Run applicable checks, including:

- Unit and component tests.
- Linting.
- Type checking.
- Production build.
- Existing end-to-end tests.

Add or update tests for responsive interaction logic where appropriate, especially mobile navigation, filters, selection state, and configuration actions.

### Visual validation

Use the available browser or visual testing tools to inspect the actual rendered application at the target viewport widths.

At minimum, validate:

- Header and mobile navigation.
- Home page primary actions.
- Browse search and filters.
- Model rows/cards and selection controls.
- Selected-model action area.
- Configuration target selection.
- Generated code and copy/download actions.
- Footer and any remaining routes.

Check for:

- Horizontal page overflow.
- Clipped or overlapping controls.
- Unusable filter panels.
- Excessive whitespace or compressed text.
- Buttons that wrap badly or become inaccessible.
- Sticky elements covering content.
- Layout regressions between adjacent breakpoints.

A successful build alone does not prove the interface is responsive. Do not claim visual validation unless it was actually performed.

## 10. Definition of Done

The task is complete when:

1. All existing TFI routes have been audited and adapted where needed.
2. The Browse page supports efficient model discovery and selection on mobile, tablet, and desktop.
3. The configuration-generation workflow remains functional at all tested widths.
4. The current `@tokyo3rdhq/magi-design-system` responsive APIs are reused appropriately.
5. No avoidable horizontal page overflow exists at the target viewport widths.
6. Existing functionality, routing, localization, analytics, and generated configuration semantics are preserved.
7. Accessibility and touch usability have been checked.
8. Relevant automated checks pass, or any failures are explicitly documented.
9. Actual viewport-based visual checks have been performed when tooling is available.
10. The implementation avoids unnecessary dependencies, duplicated design-system primitives, and unrelated refactoring.

## 11. Final Report

After implementation, provide a concise report containing:

- Main files and components changed.
- Responsive behavior implemented for each major route.
- Design-system APIs reused and any limitations discovered.
- Important mobile-specific UX decisions.
- Tests, type checks, and builds actually executed, including their results.
- Viewport widths visually inspected and any remaining issues.
- Any follow-up work that belongs in the shared design system rather than TFI.

Implement the changes directly in the existing repository. Prioritize a coherent, production-ready user experience over superficial CSS-only fixes.
