# TFI Web: Pricing Badge & Tooltip Adaptation

## 1. Role and Objective

You are a senior frontend engineer working on Token Factory Initializr (TFI).

Implement a production-ready pricing display experience for the model catalog, covering model rows, pricing badges, and interactive pricing details tooltips.

Repository: https://github.com/tokyo3rdhq/token-factory-initializr

The implementation must:

- Support the existing `pricing_status` values: `free`, `priced`, and `unknown`.
- Normalize the presentation of heterogeneous pricing dictionaries from Hugging Face, OpenRouter, and Kilo without changing their source data contracts.
- Distinguish zero prices, missing values, and unknown sentinel values correctly.
- Follow the existing `@tokyo3rdhq/magi-design-system` component, token, typography, spacing, and responsive design conventions.
- Reuse existing project abstractions instead of introducing a parallel design system or unnecessary dependencies.

This is an implementation task, not a proposal-only task. Inspect the current codebase, implement the changes, run relevant tests and checks, and report the results.

## 2. Mandatory Pre-Implementation Audit

Before modifying code, inspect the actual repository implementation.

Identify:

1. The model row or card component used by the model catalog.
2. Existing pricing badges, tooltips, popovers, and related reusable components.
3. The TypeScript definitions for `pricing_status` and `pricing`.
4. The actual pricing data flow from API responses to model row rendering.
5. How endpoint-level pricing is associated with models and displayed in the current UI.
6. The installed version and actual exported APIs of `@tokyo3rdhq/magi-design-system`.
7. Existing design tokens, dark/light theme support, responsive breakpoints, accessibility patterns, and component testing conventions.

Inspect `package.json`, lockfiles, TypeScript definitions, existing component implementations, and relevant tests before selecting APIs or adding dependencies.

Do not assume that a component, prop, export, or CSS token exists merely because its name sounds reasonable.

After the audit, continue with implementation. Do not stop after returning an audit report unless a genuine blocker prevents further work.

## 3. Scope and Non-Goals

### In scope

- Pricing badge rendering in model rows.
- Pricing tooltip or lightweight popover.
- A reusable pricing formatting and presentation utility.
- Data-source-aware pricing field labels and unit formatting.
- Correct handling of `free`, `priced`, and `unknown`.
- Responsive, accessible interaction behavior.
- Tests, documentation, and design-system compliance.

### Out of scope

- Do not introduce a `pricing_type` field.
- Do not redesign the backend pricing schema.
- Do not change provider ingestion or KV storage solely to support this UI change.
- Do not implement subscription, prepaid-credit, or one-time-purchase models without corresponding source data.
- Do not invent pricing units or infer billing semantics from field names alone.
- Do not build a new design system, introduce a second tooltip library, or perform an unrelated UI rewrite.
- Do not modify unrelated model selection or configuration generation behavior.

## 4. Existing Data Contract

The existing pricing contract contains:

- `pricing_status`: `free | priced | unknown`
- `pricing`: a provider-specific dictionary of pricing fields and values.

Keep this contract unchanged.

The `pricing` dictionary may contain numeric values or numeric strings. The implementation must handle both safely.

### 4.1 Hugging Face example

```json
{
  "pricing_status": "priced",
  "pricing": {
    "input": 0.1,
    "output": 0.3
  }
}
```

### 4.2 OpenRouter: priced

```json
{
  "pricing_status": "priced",
  "pricing": {
    "prompt": "0.00001",
    "completion": "0.00005",
    "input_cache_read": "0.000001",
    "input_cache_write": "0.0000125",
    "web_search": "0.01",
    "discount": 0
  }
}
```

### 4.3 OpenRouter: unknown

```json
{
  "pricing_status": "unknown",
  "pricing": {
    "prompt": "-1",
    "completion": "-1"
  }
}
```

### 4.4 OpenRouter: free

```json
{
  "pricing_status": "free",
  "pricing": {
    "prompt": "0",
    "completion": "0"
  }
}
```

### 4.5 Kilo: free

```json
{
  "pricing_status": "free",
  "pricing": {
    "prompt": "0",
    "completion": "0",
    "input_cache_read": "0",
    "input_cache_write": "0",
    "request": "0",
    "image": "0",
    "web_search": "0",
    "internal_reasoning": "0"
  }
}
```

### 4.6 Kilo: unknown

```json
{
  "pricing_status": "unknown",
  "pricing": {
    "prompt": "-1",
    "completion": "-1",
    "request": "0",
    "image": "0",
    "web_search": "0",
    "internal_reasoning": "0"
  }
}
```

### 4.7 Kilo: priced

```json
{
  "pricing_status": "priced",
  "pricing": {
    "prompt": "0.00000125",
    "completion": "0.0000025",
    "input_cache_read": "0.0000002",
    "web_search": "0.005",
    "discount": 0
  }
}
```

These examples are representative fixtures, not a complete pricing schema. Do not assume that every provider supports every field.

## 5. Pricing Status Semantics

Implement the following semantics consistently.

### `free`

The endpoint is explicitly confirmed to be free by the source or existing normalized data.

- Display the `Free` badge.
- The tooltip may show known zero-price items.
- Do not claim that every possible operation is free when the source only confirms a subset of pricing fields.
- Do not infer `free` from missing pricing data.

### `priced`

The endpoint has usable, confirmed pricing information.

- Display the `Pricing` badge.
- Render valid, interpretable pricing items.
- Ignore invalid sentinel values such as `-1`.
- Preserve genuine zero-valued items when their meaning is sufficiently established.
- Do not change the overall status to `free` merely because some individual items are zero.

### `unknown`

The endpoint's overall pricing status is unknown.

- Display the `Unknown` badge.
- Never display the endpoint as free based on isolated zero-valued fields.
- Never render `-1` as a negative price.
- Prefer a concise “Pricing information unavailable” tooltip.
- If the UI chooses to expose partial field-level information, clearly mark the information as incomplete and never represent unverified zero values as confirmed free pricing.

The endpoint's `pricing_status` is authoritative for the overall badge. Do not recalculate the status solely from the `pricing` dictionary.

## 6. Pricing Field Presentation

Create a reusable field metadata mapping, following existing project conventions.

Suggested initial mappings:

| Raw field | Display label | Unit policy |
|---|---|---|
| `input` | Input tokens | Resolve using Hugging Face source metadata |
| `prompt` | Input tokens | Resolve using OpenRouter/Kilo source metadata |
| `output` | Output tokens | Resolve using Hugging Face source metadata |
| `completion` | Output tokens | Resolve using OpenRouter/Kilo source metadata |
| `input_cache_read` | Cached input | Source-defined unit |
| `input_cache_write` | Cache write | Source-defined unit |
| `request` | Request | Source-defined unit |
| `image` | Image | Source-defined unit |
| `web_search` | Web search | Source-defined unit |
| `internal_reasoning` | Internal reasoning | Source-defined unit |
| `discount` | Discount | Source-defined semantics |

The mapping must be extensible and must not require a new component for every provider.

Where useful, define a type-safe field metadata structure with properties such as:

- Display label.
- Display order.
- Source applicability.
- Known unit or formatting policy.
- Whether the field is a monetary charge or a pricing modifier.
- Whether the field can safely be normalized to a common unit.

Do not assume that the unit is determined solely by the raw field name. Use existing source contracts and repository documentation to establish units.

If a unit cannot be verified, display the raw numeric value with an explicit “unit not specified” indication, or omit the normalized presentation rather than inventing a unit.

### Field naming normalization

Map synonymous fields to consistent UI labels:

- `input` and `prompt` → Input tokens.
- `output` and `completion` → Output tokens.

Keep the raw field names intact in the data layer. This is a presentation-only mapping.

If multiple aliases occur in the same pricing object, avoid duplicate rows or silently discarding conflicting values. Handle this deterministically and cover it with tests.

## 7. Numeric Parsing and Formatting

Implement a dedicated, testable pricing formatter.

It must:

1. Accept numeric strings and finite numeric values.
2. Reject malformed numbers, `NaN`, and infinities.
3. Treat `-1` as an unknown sentinel for the known source contracts where applicable.
4. Preserve genuine zero values.
5. Distinguish absent fields from explicit zero values.
6. Avoid JavaScript floating-point artifacts in monetary formatting.
7. Preserve sufficient precision for very small prices.
8. Avoid unnecessary trailing zeros while maintaining readability.
9. Never convert an unknown value to `$0`.
10. Never apply a unit conversion unless the source's unit is verified.

Use decimal-safe arithmetic or string-based decimal formatting when converting per-token rates to per-million-token rates.

Only perform conversion to `USD / 1M tokens` for fields whose source contract explicitly establishes a monetary rate per token.

Do not multiply request, image, or web-search charges by one million.

Do not assume all monetary values are USD unless the source contract guarantees it. If currency is unavailable, follow the existing data contract and UI conventions; do not invent currency metadata.

### Discount handling

Treat `discount` separately from ordinary charges.

The example `discount: 0` does not by itself prove whether the value represents a percentage, multiplier, or another provider-specific concept.

Inspect existing source documentation and code to establish its meaning. Until confirmed, do not automatically append `%`, subtract it from prices, or include it in a total.

If its semantics cannot be established, render a neutral representation with an explicit source-defined or unknown unit, or omit the field with a documented reason.

## 8. Pricing Badge UX

Integrate the badge into the existing model row using the established component hierarchy and spacing.

Recommended labels:

- `Free`
- `Pricing`
- `Unknown`

Use the existing badge variants and theme tokens from `@tokyo3rdhq/magi-design-system`, where available.

Do not hardcode colors that conflict with the design system. If no suitable variant exists, use the nearest supported semantic or neutral variant and document the choice.

The badge must:

- Remain visually compact.
- Align consistently with existing model metadata.
- Avoid causing row-height changes or layout shifts.
- Work at mobile and desktop widths.
- Remain understandable without relying on color alone.

Do not display a guessed “From $X” price in this task. A future summary-price feature would require explicit rules for selecting a comparable price across endpoints and charge categories.

## 9. Pricing Tooltip / Popover

Use the existing tooltip, popover, or equivalent overlay abstraction if available and suitable.

Preferred behavior:

- Desktop: open on hover and keyboard focus.
- Touch devices: provide an appropriate click/tap interaction.
- Escape closes the overlay when supported by the existing primitive.
- Overlay interaction must not trigger model selection or navigation.
- The badge must remain compatible with any enclosing clickable model row.
- Prevent clipping by scroll containers and viewport edges where the existing overlay primitive supports collision handling.
- Avoid rendering a large, raw JSON block.

Use a compact structured layout with:

1. A heading such as `Pricing details`.
2. A concise unit/currency note when verified.
3. One row per valid pricing item.
4. Human-readable labels.
5. Right-aligned, consistently formatted values.
6. A clear fallback state when details are unavailable.

For long pricing dictionaries, constrain the width and allow content to wrap or scroll according to existing design-system conventions. Avoid excessively wide tooltips.

### Suggested content by status

**Free**

- Heading: `Pricing details`
- Status: `Free`
- Display known zero-price items when useful.
- Do not imply that unlisted operations are free.

**Priced**

- Heading: `Pricing details`
- Status: `Priced`
- Display all supported, interpretable pricing entries.
- Omit invalid sentinel values and missing values.
- Keep modifiers such as discount separate from monetary charges.

**Unknown**

- Heading: `Pricing details`
- Message: `Pricing information unavailable`
- Do not show misleading zero prices.
- If partial details are displayed, label them explicitly as incomplete.

## 10. magi-design-system Compliance — Mandatory

TFI must use `@tokyo3rdhq/magi-design-system` as the source of truth for shared UI conventions.

Before implementation, inspect the installed package and the current TFI integration. Follow the actual APIs and documentation available in the repository.

### Components and tokens

- Reuse existing button, badge, typography, tooltip/popover, spacing, and layout primitives where appropriate.
- Use existing design tokens for color, background, borders, radius, typography, and spacing.
- Do not introduce arbitrary one-off design tokens or duplicate shared component implementations.
- Do not use raw hex colors or hardcoded theme-specific colors when design tokens already cover the use case.
- Do not create a custom tooltip implementation if the design system already exposes a suitable primitive.
- If the required primitive does not exist, implement the smallest project-consistent fallback and document why it is necessary.

### Dark and light themes

- Verify the experience in both supported themes.
- Ensure badge text, tooltip text, borders, surfaces, focus indicators, and secondary labels remain legible.
- Avoid hardcoding black backgrounds or white text.
- Preserve TFI's existing visual language and dark Apple-like aesthetic without bypassing the shared system.

### Typography and spacing

- Use the established typography hierarchy.
- Keep the tooltip information dense but readable.
- Use existing spacing scales instead of arbitrary pixel values.
- Align labels and numeric values consistently.
- Use tabular numerals or the closest supported typography option for prices if available.

### Responsive behavior

- Inspect and follow the responsive conventions already implemented in `magi-design-system`.
- Ensure the badge does not overflow or dominate compact model rows.
- Ensure pricing details remain readable on narrow screens.
- Do not assume hover exists on touch devices.
- Avoid fixed positioning or widths that break existing layouts.

### Accessibility

- Use semantic and accessible interaction primitives.
- Ensure the badge can be reached by keyboard.
- Provide a visible focus state using existing tokens.
- Use appropriate accessible names and relationships for the tooltip/popover.
- Avoid hover-only access to essential pricing information.
- Ensure the overlay does not interfere with the model row's keyboard or click behavior.
- Respect reduced-motion conventions if transitions are introduced.

### Design-system changes

Do not modify `magi-design-system` merely to accommodate a single TFI feature unless an actual reusable primitive is missing and a shared change is justified.

If a shared change is genuinely required, keep it minimal, maintain backward compatibility, and report it separately from the TFI implementation.

## 11. Endpoint-Level Semantics

Pricing belongs to an endpoint, not necessarily to a canonical model.

A model may have multiple endpoints with different pricing statuses.

- Use the endpoint's own `pricing_status` and `pricing` when rendering endpoint-specific information.
- Do not merge pricing dictionaries from different endpoints into one misleading set of prices.
- If the current model row represents a canonical model with multiple endpoints, inspect the existing product behavior and preserve its intended semantics.
- If the row summarizes multiple endpoints, do not arbitrarily choose the first endpoint's pricing. Use an explicit existing selection or summary rule; if none exists, keep the change scoped and document the unresolved product decision.
- Do not change model identity, endpoint identity, filtering, or selection behavior as a side effect of the pricing UI work.

## 12. Suggested Implementation Structure

Follow existing repository conventions; these names are suggestions, not mandatory filenames.

Possible separation:

- `pricingMetadata`: field labels, display order, source-specific unit metadata.
- `parsePricingValue`: safe parsing and sentinel handling.
- `formatPricingValue`: precision-safe formatting.
- `normalizePricingEntries`: convert raw pricing data into presentation-ready entries without mutating the source object.
- `PricingBadge`: status badge.
- `PricingTooltip` or `PricingPopover`: structured overlay.

Keep pure formatting logic separate from React components so it can be tested independently.

Avoid duplicating pricing logic across multiple model row components.

Do not add dependencies unless the existing stack cannot support the required behavior and a dependency is justified.

## 13. Testing Requirements

Add unit tests for pricing parsing, normalization, and formatting.

Cover at least:

1. Hugging Face `input` / `output` numeric values.
2. OpenRouter `prompt` / `completion` string values.
3. Kilo's small decimal rates.
4. Numeric strings and numeric values representing zero.
5. The `-1` unknown sentinel.
6. Missing and `null` fields.
7. Malformed strings, `NaN`, and infinity.
8. `pricing_status: free` with zero-valued entries.
9. `pricing_status: unknown` with both `-1` and zero values.
10. `pricing_status: priced` with valid prices and `discount: 0`.
11. Unknown pricing keys.
12. Alias collisions such as both `input` and `prompt`.
13. Very small values and precision-safe unit conversions.
14. Fields with different units, ensuring token conversions are not applied indiscriminately.
15. Empty pricing dictionaries.
16. Endpoint-specific pricing when a model has multiple endpoints.

Add component tests, where the existing test framework supports them, for:

- All three badge states.
- Tooltip content for free, priced, and unknown endpoints.
- Keyboard focus and activation.
- Touch/click behavior if supported by the component.
- No accidental triggering of enclosing model-row selection.
- Long pricing lists and responsive layouts.

Run the relevant test suite, lint, TypeScript checks, and production build.

Do not claim checks passed unless they were actually executed.

## 14. Documentation

Update relevant developer documentation only where needed.

Document:

- The three `pricing_status` values.
- How invalid sentinel values are handled.
- Which source-specific pricing fields are supported.
- Unit and currency assumptions.
- The distinction between unknown, missing, and zero.
- Why the frontend does not introduce `pricing_type`.
- Any known source fields whose unit or semantics remain unresolved.

Do not update the canonical backend contract merely to document frontend presentation behavior.

## 15. Definition of Done

The task is complete when:

- The model row displays the correct pricing badge.
- Hover/focus and touch interaction work through the chosen accessible primitive.
- Pricing dictionaries render as structured, human-readable details.
- Hugging Face, OpenRouter, and Kilo examples are handled correctly.
- `-1` is never rendered as a negative price.
- Unknown values are never misrepresented as zero.
- Price units and discount semantics are not guessed.
- Endpoint-level pricing semantics are preserved.
- No `pricing_type` field has been introduced.
- The UI follows `@tokyo3rdhq/magi-design-system` conventions in both supported themes and responsive layouts.
- Tests, lint, TypeScript checks, and build results are reported accurately.
- Any remaining source metadata gaps are documented explicitly.

## 16. Final Engineering Report

After implementation, provide a concise report containing:

1. Summary of user-visible changes.
2. Files changed and the purpose of each.
3. Pricing normalization and formatting rules.
4. How magi-design-system components and tokens were reused.
5. Tests and validation commands executed, with actual results.
6. Known limitations, especially unresolved pricing units or discount semantics.
7. Any remaining product decisions required before displaying a normalized price summary.

Prioritize correctness, consistency, and minimal scope over premature abstraction.
