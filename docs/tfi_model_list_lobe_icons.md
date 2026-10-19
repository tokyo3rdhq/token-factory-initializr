# Implement Lobe Icons in TFI `/browse` Model List

## Objective

Integrate [`@lobehub/icons`](https://icons.lobehub.com/) into the Token Factory Initializr (TFI) model-browsing page at `https://start.magi.website/browse`.

The goal is to improve model recognition and scanning efficiency by displaying recognizable AI brand icons, while preserving TFI's existing information density, model-selection workflow, and MAGI Design System visual language.

**Required first step:** Read and follow the official Lobe Icons agent instructions:

`https://icons.lobehub.com/skills.md`

Follow the instructions in that document for installing and using `@lobehub/icons`. Also consult the relevant official component documentation when necessary.

Official references:

* https://icons.lobehub.com/
* https://icons.lobehub.com/features/model-icon

Do not assume API names, component props, package exports, or supported model IDs without checking the installed package and its official documentation.

## Icon Identity and Mapping Policy

### 1. Preserve TFI's identity semantics

Before implementing icons, inspect the actual catalog schema and representative records from NVIDIA, AMD, Hugging Face, OpenRouter, and Kilo.

Keep these concepts distinct:

- `model_id`: the model identifier used by the relevant catalog or service.
- `owned_by`: the model publisher/developer attribution, when available.
- `provider`: the provider identifier recorded by the source and normalized by TFI. Its precise semantics may vary by source.
- `data_source`: where TFI discovered or collected the model.
- `endpoint`: the concrete API access point, including its actual `base_url`.

Do not assume that `provider` always identifies the model creator or the operator of the client-facing API endpoint.

For example, a Hugging Face record may have `provider=together` while its client-facing endpoint uses `https://router.huggingface.co/v1`. Do not display a Together icon in a way that implies the client connects directly to Together's native API.

Do not change the public API schema or introduce new required model fields solely to support icons.

### 2. Choose one primary icon per model row

The purpose of icons is to improve scanning and recognition, not to decorate every row with multiple logos.

Use the following resolution policy:

1. Display a model-specific icon when the installed Lobe Icons package provides a reliable match for the actual model identifier.
2. Otherwise, display a provider icon only when the provider identity and its intended visual meaning are sufficiently clear.
3. If neither mapping is reliable, use the existing neutral fallback or render no icon.

Do not render model, provider, publisher, and data-source icons side by side.

Prefer one icon per row. Preserve the model name and existing provider text as the primary textual information.

A model-specific icon is an optional enhancement, not a requirement for every model.

### 3. Build mappings from the actual TFI catalog

Inspect the current production catalog before creating the mapping table.

Determine:

- The most frequently occurring provider identifiers.
- The most common `owned_by` values.
- Which identities have corresponding official Lobe Icons components.
- Which model IDs can be reliably matched by the documented model-icon functionality.
- Where provider, publisher, and endpoint identities differ.

Prioritize mappings that improve recognition across the actual catalog. Do not hard-code a predetermined list of popular brands without checking current data.

Use explicit, deterministic mappings where needed. Do not infer identity from arbitrary substring matches.

Follow the official Lobe Icons agent instructions and installed-package documentation. Verify all component exports and package compatibility before implementation.

### 4. Endpoint-aware presentation

Icons must not imply that two records are the same callable service simply because they share a model ID or model icon.

In particular:

- A model offered by OpenRouter and Kilo may have the same `model_id` but must remain two independently selectable records.
- The icon layer must not merge records, change model identity, or modify endpoint selection.
- A provider icon must not override or conceal the actual endpoint identity.
- Do not introduce a data-source icon as a substitute for a provider or model icon.

If the UI already displays provider and endpoint details, keep those textual labels authoritative.

### 5. Preserve compact layout and behavior

Keep the current compact MAGI Design System model-list layout.

- Use a consistent icon size appropriate to the existing row height, typically around 20–24 px.
- Avoid extra icon containers unless needed for contrast.
- Preserve text alignment, truncation, badges, pricing indicators, selection controls, and actions.
- Do not change sorting, filtering, Select All Visible, selection state, or configuration generation.
- Ensure missing icon mappings never prevent a row from rendering.
- Keep imports tree-shakable and verify dependency compatibility and bundle impact.

### 6. Acceptance tests

In addition to the existing tests, verify:

- A model with a verified model-specific icon.
- A model with a verified provider icon.
- An unsupported provider and model ID.
- A record where `provider` differs from `data_source`.
- A record where `provider` does not identify the client-facing endpoint operator.
- Two records with the same `model_id` from OpenRouter and Kilo remain distinct and independently selectable.
- Missing icons do not affect filters, selection, sorting, or generated configuration.

Do not claim that all catalog records have unique model icons. Report actual mapping coverage and remaining gaps.

## 1. Inspect the repository before making changes

Inspect the existing implementation before editing anything.

Determine:

* The package manager and lockfile.
* The current React, TypeScript, and Vite versions.
* The installed version and peer-dependency compatibility of `@lobehub/icons`, if already present.
* The actual `/browse` route and the components responsible for rendering model rows.
* The existing model data schema, especially `model_id`, `provider`, and `data_source`.
* How provider IDs and model IDs are normalized, if at all.
* The existing design-system imports, styling conventions, theme tokens, and icon conventions.
* Existing tests, lint, type-check, and build commands.

Read the MAGI Design System documentation and existing components before creating new styling abstractions.

Do not rewrite the page or introduce a new component framework.

## 2. Icon display policy

Implement the following hierarchy.

### 2.1 Provider icons: primary and preferred

Display a recognizable provider icon to the left of the model name whenever the model's actual `provider` can be mapped confidently to a supported Lobe Icons provider.

Requirements:

* Use the model's normalized `provider` identity, not `data_source`.
* Prefer explicit, deterministic provider-ID-to-icon mappings.
* Check actual exports and naming conventions in the installed package.
* Support the providers already represented in TFI's real model catalog, prioritizing common providers such as OpenAI, Anthropic, Google/Gemini, DeepSeek, Qwen, Mistral, Meta, NVIDIA, and other providers present in the current data.
* Only include mappings supported by the package and actual catalog.
* Do not assume every provider has an icon.
* Fall back gracefully when the provider is unknown or unsupported.

Do not display an inference provider's logo as if it were the model's creator when the two identities differ.

### 2.2 Model icons: selective enhancement

Use Lobe Icons' documented model-icon functionality where a model ID can be matched reliably.

Requirements:

* Only show a model-specific icon when the mapping is supported by the actual model identifier and the installed library.
* Prefer explicit, verified mappings or documented lookup functionality.
* Do not guess icons based on arbitrary substring matches.
* Do not assume every model from the same provider has an individually supported icon.
* Avoid rendering two nearly identical icons side by side.
* If a reliable model-specific icon is unavailable, show the provider icon instead.

Provider identity remains the default fallback. Model icon matching must never affect model identity, eligibility, filtering, or selection.

### 2.3 Data-source icons: out of scope

Do not use data-source icons as provider icons.

TFI distinguishes:

* `model`: the model itself.
* `provider`: the inference provider or operator.
* `data_source`: where TFI discovered or collected the model.
* `endpoint`: a concrete access point.

Preserve these semantics. Do not change the API schema or introduce a new required field to support icons.

## 3. Create a small, maintainable icon-mapping layer

Implement a dedicated, narrowly scoped helper or component, following existing repository conventions. Possible responsibilities include:

* Resolving a model's provider icon.
* Resolving an optional model-specific icon.
* Applying a consistent fallback policy.
* Keeping library-specific exports out of unrelated page components.

Choose an appropriate implementation based on the actual library API. Do not blindly adopt these conceptual names if the repository uses a different structure.

Mapping requirements:

1. Normalize provider IDs consistently with the existing data model.
2. Map only verified provider identifiers to actual icon components.
3. Use the documented model-icon API where appropriate.
4. Keep mappings deterministic and easy to extend.
5. Avoid dynamic imports or runtime icon-library scanning unless the official instructions specifically recommend them.
6. Avoid downloading icons from a third-party CDN at runtime.
7. Do not add a separate icon registry service or expand the model aggregation pipeline just for this UI enhancement.

Prefer tree-shakable imports and keep the resulting bundle impact reasonable.

If the installed library's peer dependencies conflict with the current React version, investigate compatibility before proceeding. Do not force-install incompatible dependencies or upgrade the entire application without justification. Report the issue and the smallest safe alternative if necessary.

## 4. Integrate into the existing model list

Modify only the relevant model-list presentation components.

### Layout

* Place the icon immediately to the left of the model name.
* Use a consistent visual size, approximately 20–24 px, adjusted to the existing row height.
* Keep the model name as the primary text.
* Preserve existing model IDs, provider labels, capability badges, pricing/free indicators, selection controls, and actions.
* Maintain the current compact list layout. Do not turn model rows into large cards.
* Prevent icons from shifting text alignment or causing row-height changes.
* Ensure long model names continue to truncate or wrap according to existing behavior.

### Styling

Follow `@tokyo3rdhq/magi-design-system` and the repository's existing conventions.

* Reuse existing tokens and components.
* Keep the dark-first appearance coherent with the current TFI interface.
* Use color icons where appropriate for fast brand recognition.
* Ensure icons remain visible against both supported themes, if the application supports light and dark themes.
* Use existing neutral surface tokens for a subtle icon container only if necessary.
* Do not introduce arbitrary brand-colored backgrounds, new global CSS rules, or a separate visual design system.
* Do not modify the global navigation, homepage, footer, filters, or page layout as part of this task.

### Accessibility

* Decorative icons next to an already-readable provider/model name should not create redundant screen-reader announcements.
* If an icon communicates information not otherwise available in text, provide an appropriate accessible label.
* Preserve keyboard navigation, focus behavior, and selection-control accessibility.
* Ensure icon loading or missing mappings never prevent a model row from rendering.

## 5. Fallback behavior

Every model must remain usable, regardless of icon availability.

Implement and verify this fallback sequence:

1. Display a verified model-specific icon when an appropriate match exists and the library supports it.
2. Otherwise display the verified provider icon.
3. Otherwise display the existing generic icon or a small neutral fallback consistent with MAGI Design System conventions.
4. If even the fallback asset is unavailable, render the row without an icon rather than crashing.

Do not use a random logo, an unrelated provider logo, or an invented model match.

No icon failure should break search, filters, selection, select-all-visible, or configuration generation.

## 6. Testing and verification

Add or update tests using the repository's existing testing framework.

Cover at least:

* A model with a verified provider icon.
* A model with a verified model-specific icon, if supported by the actual catalog and library.
* An unknown provider.
* An unsupported or unknown model ID.
* A model whose provider and data source differ.
* The fallback behavior when no matching icon exists.

Verify that the icon integration does not change model IDs, filter results, selection state, or generated configuration.

Run the existing relevant checks:

* Tests.
* Type checking.
* Linting, if configured.
* Production build.

Inspect the final diff for accidental changes to unrelated components or dependencies.

If browser testing or screenshots are available, inspect `/browse` at desktop and mobile widths. Verify row alignment, icon visibility, truncation, and interaction behavior. Do not claim browser verification if it was not performed.

## 7. Scope boundaries

This is a focused UX enhancement, not a redesign.

Do not:

* Redesign the `/browse` page.
* Change the homepage or navigation.
* Change the public API or model-data schema.
* Modify data collection, normalization, or enrichment pipelines.
* Change model filtering, sorting, or selection semantics.
* Change LiteLLM, NewAPI, or Bifrost configuration generation.
* Add unrelated icons across the application.
* Add a runtime CDN dependency.
* Upgrade unrelated dependencies.
* Add new analytics providers or tracking events.
* Claim that every model has a unique icon.

If a broader change appears necessary, explain why and keep it separate from this implementation.

## 8. Completion report

After implementation, report:

1. Files changed and the responsibility of each.
2. The installed `@lobehub/icons` version and the official usage pattern followed.
3. The provider/model mapping strategy and fallback behavior.
4. The actual providers and model families covered.
5. Dependency compatibility and any bundle-size considerations you could verify.
6. Tests, type checks, lint, build, and browser checks actually executed, including failures.
7. Any remaining gaps or unsupported provider/model icons.

**Acceptance criteria:** `/browse` displays correctly matched provider icons, uses model-specific icons only when verified, preserves the existing compact MAGI-style model list, handles missing icons safely, and passes the repository's applicable checks without changing existing product behavior.

