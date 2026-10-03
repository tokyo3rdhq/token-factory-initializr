# Token Factory Initializr — MAGI Design System Consumer Compliance & UX Remediation

## Role

You are a senior frontend engineer + design-system engineer + product UX reviewer working on:

**Token Factory Initializr (TFI)**

TFI is a developer-oriented MAGI product for selecting AI models and generating gateway configuration, currently focused on LiteLLM.

The target product is:

`https://token-factory-initializr.pages.dev/`

The parent brand is:

`https://magi.website/`

The shared Design System is:

`@tokyo3rdhq/magi-design-system`

Repository:

`https://github.com/tokyo3rdhq/magi-design-system`

---

# 1. Primary Objective

Audit and remediate the TFI web application so that it is a **first-class MAGI product consumer**.

The goal is NOT to redesign TFI from scratch.

The goal is:

> Preserve TFI's developer-tool information architecture and functionality while bringing its visual language, typography, spacing, components, interaction states, accessibility, and content quality into alignment with the current MAGI Design System.

The resulting experience should feel like:

```text
MAGI
  └── TFI
      └── a specialized developer tool
```

not:

```text
MAGI website
  └── visually copied into TFI
```

---

# 2. Source of Truth

Treat the following as authoritative, in this order:

### 1. MAGI Design System

`@tokyo3rdhq/magi-design-system`

Current design-system version:

```text
0.6.0
```

The Design System currently defines:

* design tokens
* typography
* spacing
* radius
* motion
* breakpoints
* color modes
* accent system
* layout primitives
* UI primitives
* brand foundation
* theme mechanism
* accessibility rules
* Experience Guidelines
* Component Contracts

Relevant documents include:

```text
docs/brand.md
docs/guidelines.md
docs/component-contracts.md
docs/usage-guide.md
docs/tokens.md
docs/migration-guide.md
docs/integration-prompt.md
docs/contracts/data-magi-app-scope-contract.md
```

The Design System explicitly follows:

> Visual consistency without forcing product-level sameness.

and:

> MAGI owns the visual language. Products own the product experience.

Do not violate this boundary.

---

# 3. Product Reference

Use:

`https://magi.website/`

as the primary brand reference.

Current MAGI visual/content characteristics include:

* dark-first
* restrained
* near-monochrome
* minimal
* technical
* precise
* calm
* premium
* strong typography hierarchy
* limited decorative elements
* concise product language

Current MAGI homepage positioning:

```text
Personal AI Lab

Personal AI, at the edge.
```

Do not copy these exact marketing messages into TFI.

Use them only as evidence of the overall brand voice.

---

# 4. TFI Product Boundary

TFI is a developer tool.

Its product-specific experience includes concepts such as:

```text
Model
Provider
Capability
Model selection
Model filtering
Selected models
Requirements
Intent
Recommendations
Configuration
LiteLLM
Generated configuration
Copy
Download
Generated URL
```

These are PRODUCT concepts.

Do not move them into the MAGI Design System merely to make the UI look consistent.

The Design System should provide:

```text
Button
Card
Badge
Input
Checkbox
FormField
Segmented
Banner
EmptyState
Container
Section
Stack
Theme
Brand
Typography
Spacing
Color
Motion
```

TFI owns:

```text
ModelCard
ModelSelector
ModelFilter
ProviderFilter
CapabilityFilter
SelectedModelList
RequirementInput
IntentInput
RecommendationPanel
ConfigPreview
ConfigOutput
GeneratedUrl
```

unless an existing Design System primitive is genuinely appropriate.

---

# 5. First Step — Audit Before Editing

Before changing code, inspect:

```text
1. TFI source tree
2. package.json
3. MAGI Design System dependency/version
4. global CSS
5. local component CSS
6. theme implementation
7. typography implementation
8. layout implementation
9. all hard-coded colors
10. all hard-coded spacing
11. all hard-coded radius
12. all hard-coded font sizes
13. all hard-coded font weights
14. all SVG / icon usage
15. all buttons
16. all inputs
17. all cards
18. all badges
19. all form fields
20. all responsive breakpoints
21. all user-facing copy
22. all loading/error/empty states
23. all accessibility attributes
```

Also inspect the currently deployed TFI site if browser tooling is available.

Do not rely solely on source code.

---

# 6. Audit Output

Before implementation, produce a structured audit.

Use:

```text
P0 — broken usability/accessibility/functional issue

P1 — significant MAGI Design System or UX inconsistency

P2 — polish / cleanup / content improvement

INFO — intentional product-specific behavior
```

For every finding include:

```text
ID
Severity
Location
Current behavior
Why it is inconsistent
Design System reference
Recommended fix
```

Example:

```text
P1-UI-001

Location:
ModelCard

Current:
Card uses custom background and border colors.

Problem:
Colors do not use MAGI semantic tokens.

Reference:
magi-design-system token contract.

Fix:
Replace hard-coded colors with semantic MAGI tokens.
```

---

# 7. Brand Audit

Check:

### Logo

TFI should use the canonical MAGI brand assets/components.

Prefer:

```tsx
<MagiMark />
<MagiWordmark />
<MagiLockup />
```

where appropriate.

Do not:

* recreate the MAGI logo
* inline a modified logo
* change logo geometry
* recolor the logo with product accent
* add gradients
* add glow
* add shadows
* create a TFI-specific logo variant

Follow:

```text
docs/brand.md
```

---

# 8. Theme Audit

TFI must consume the MAGI theme system.

Verify:

```text
data-magi-app
AppTheme
data-magi-theme
data-magi-accent
```

where applicable.

Verify both:

```text
Dark
Light
```

if the product supports both.

Do not implement a second independent theme system.

Do not create:

```text
TFI dark colors
TFI light colors
```

as a parallel token system.

---

# 9. Color Audit

Search the entire TFI frontend for:

```text
#000
#fff
#ffffff
#000000
rgb(...)
rgba(...)
hsl(...)
hsla(...)
```

and other literal color values.

Classify each occurrence:

### Allowed

* third-party library requirement
* data visualization where semantic tokens are insufficient
* actual source asset
* product-specific domain visualization with explicit justification

### Should normally be replaced

* page background
* text
* secondary text
* borders
* cards
* inputs
* buttons
* focus rings
* hover states
* disabled states
* status colors

Use MAGI semantic tokens instead.

Do not invent new colors just to make TFI look more polished.

---

# 10. Typography Audit

Compare TFI typography against the Design System.

Check:

```text
font family
font size
line height
font weight
letter spacing
heading hierarchy
body hierarchy
metadata
labels
code/configuration text
```

Pay special attention to:

```text
H1
H2
section heading
form label
helper text
button text
model name
provider name
metadata
code preview
empty state
error state
```

Do not create an independent typography scale.

TFI may legitimately use denser typography for technical content, but the underlying typography system must remain MAGI-compatible.

---

# 11. Spacing Audit

Look for arbitrary values such as:

```css
margin: 7px;
padding: 13px;
gap: 11px;
margin-top: 23px;
```

Determine whether they can be mapped to MAGI spacing tokens.

Use the existing spacing scale.

Do not blindly replace every value.

Product-specific layout may require a value that is not directly represented by a token, but such cases should be deliberate rather than accidental.

---

# 12. Radius and Surface Audit

TFI should not introduce a competing visual language through:

```text
different border radius
excessive rounded cards
pill-shaped everything
strong shadows
heavy glassmorphism
gradient surfaces
neon borders
```

Compare:

```text
Card
Input
Button
Badge
Panel
Code preview
Filter controls
```

against MAGI surface and radius conventions.

The visual language should remain:

```text
restrained
near-monochrome
technical
quiet
```

---

# 13. Component Audit

Identify custom implementations that duplicate Design System primitives.

Examples:

```text
CustomButton
CustomCard
CustomInput
CustomBadge
CustomCheckbox
CustomFormField
CustomBanner
```

For each determine:

```text
Can it use the Design System component directly?
```

If yes, migrate it.

If no, document why it remains product-owned.

Do NOT move product-specific components into the Design System just to eliminate local CSS.

---

# 14. Button Audit

Check all buttons for:

```text
variant
size
height
padding
radius
font
icon
icon spacing
hover
active
focus
disabled
loading
```

Use MAGI Button wherever appropriate.

Do not create a second TFI button visual language.

Button labels should be concise and functional.

Prefer:

```text
Generate
Copy
Download
Reset
Select all
Clear
```

over verbose marketing language.

---

# 15. Form Audit

TFI has important forms and controls.

Audit:

```text
RequirementInput
IntentInput
ProviderFilter
CapabilityFilter
ModelFilter
Checkbox
Segmented
```

Verify:

* label semantics
* helper text
* error text
* required state
* disabled state
* focus state
* keyboard behavior
* aria relationships
* placeholder usage
* validation messages

Use:

```text
FormField
Input
Checkbox
Segmented
```

from the Design System where applicable.

---

# 16. Model Card Audit

Model cards are product-owned.

Do NOT make them identical to generic MAGI Cards if that harms information density.

However, they must use MAGI visual language.

Audit:

```text
model name
provider
model family
capabilities
metadata
badges
selection state
hover
focus
disabled
selected
```

Important:

Selected state must be visually obvious without relying only on color.

Do not introduce loud glowing selected states.

Prefer restrained emphasis.

---

# 17. Provider Identity vs MAGI Accent

Provider identity and MAGI accent are different concepts.

Do not use provider logos/colors as if they were MAGI theme accents.

For example:

```text
NVIDIA green
AMD red
Hugging Face yellow
```

may be legitimate product metadata when provider identity needs to be shown.

But:

```text
provider brand color
        ≠
MAGI product accent
```

Keep those concepts separate.

---

# 18. Icon Audit

Use the MAGI Iconography Contract.

Generic UI icons should normally use Lucide.

Examples:

```text
Search
Filter
Copy
Download
Refresh
Chevron
ExternalLink
Settings
Close
Check
```

Do not create:

```text
MagiSearch
MagiCopy
MagiFilter
```

merely to duplicate Lucide.

Use custom MAGI icons only for genuine MAGI/product concepts.

Do not use emoji as primary UI icons.

---

# 19. Navigation Audit

TFI navigation should follow MAGI Experience Guidelines.

Check:

```text
brand
product identity
navigation
external links
GitHub
documentation
language
theme
```

Avoid turning every navigation item into an icon-only control.

External destinations may use a subtle external-link indicator.

Do not use country flags as language selectors.

Use language names.

---

# 20. Header Audit

The TFI header should communicate:

```text
MAGI
+
Token Factory Initializr
```

without becoming visually heavy.

Do not duplicate the full marketing navigation of `magi.website`.

TFI is a product application.

Its header should prioritize:

```text
identity
product context
utility navigation
```

rather than marketing conversion.

---

# 21. Hero / Page Introduction Audit

Do not blindly copy the MAGI homepage hero.

TFI needs a product-oriented introduction.

The page should quickly communicate:

```text
What is this?
What can I generate?
What should I do first?
```

Avoid vague copy such as:

```text
The future of AI starts here
Build something amazing
Power your AI workflow
```

Prefer precise developer-oriented language.

For example, conceptually:

```text
Generate your model configuration.

Select the models and providers you need,
then generate a ready-to-use LiteLLM configuration.
```

Use the actual product semantics and current capabilities.

Do not invent functionality that does not exist.

---

# 22. Content / Copy Audit

Audit every visible string.

Classify:

```text
Navigation
Heading
Description
Label
Placeholder
Helper
Button
Badge
Empty state
Error
Success
Loading
Tooltip
Code output
```

Look for:

### A. Marketing fluff

Replace vague claims with concrete descriptions.

### B. Redundant wording

Reduce unnecessary repetition.

### C. Inconsistent terminology

For example, do not alternate between:

```text
Model Provider
Provider
Model Source
Source
Vendor
```

unless they represent different concepts.

### D. Inconsistent capitalization

Choose a consistent UI capitalization strategy.

### E. Developer terminology

Use terminology that matches the actual data model.

If the product distinguishes:

```text
data source
provider
model
```

the UI copy must preserve those distinctions.

---

# 23. Product Terminology Contract

Create a small terminology table during the audit:

```text
Concept
Canonical term
Avoid
Notes
```

Example:

```text
Model
Provider
Data source
Capability
Configuration
```

Do not introduce synonyms unless there is a strong UX reason.

This is especially important because TFI is becoming an agent-facing/developer-facing tool.

---

# 24. Code / Configuration Preview Audit

Configuration output is a technical surface.

It should NOT be styled like marketing content.

Check:

```text
monospace font
syntax readability
contrast
line height
overflow
horizontal scrolling
copy action
download action
responsive behavior
```

The code/configuration surface may intentionally be denser than normal MAGI UI.

This is acceptable.

The goal is:

```text
MAGI visual language
+
developer-tool density
```

not:

```text
marketing-site whitespace everywhere
```

---

# 25. Responsive Audit

Test at minimum:

```text
mobile
tablet
desktop
wide desktop
```

Check:

* model cards
* filter controls
* selected model list
* configuration preview
* header
* buttons
* forms
* tables/lists
* horizontal overflow

Do not simply stack everything vertically.

Preserve the product's information hierarchy.

---

# 26. Accessibility Audit

Verify:

```text
keyboard navigation
focus visibility
label association
aria-describedby
aria-labelledby
button semantics
checkbox semantics
segmented control semantics
error association
color contrast
reduced motion
icon-only labels
```

Use the Design System's Component Contracts as the reference.

Do not solve accessibility by adding arbitrary ARIA attributes without understanding the component semantics.

---

# 27. Visual Anti-Patterns

Explicitly search for and remove:

```text
generic AI gradients
neon glow
purple/blue AI gradients
excessive glassmorphism
floating glowing blobs
large decorative AI illustrations
heavy drop shadows
excessive pills
excessive rounded cards
random gradients
emoji as UI icons
inconsistent icon libraries
overly colorful provider UI
marketing copy inside developer workflows
```

MAGI should feel:

```text
quiet
precise
technical
premium
restrained
```

not:

```text
generic AI SaaS
cyberpunk
gaming UI
AI startup template
```

---

# 28. Do Not Overcorrect

Do NOT make TFI visually identical to `magi.website`.

TFI legitimately needs:

```text
higher information density
more controls
more metadata
more filters
more technical text
code/configuration previews
selection states
provider/model information
```

These are product requirements.

Do not remove them merely to achieve visual simplicity.

---

# 29. CSS Architecture Audit

Determine whether TFI has local CSS that duplicates:

```text
tokens
foundation
component styles
theme
```

If yes:

### Replace

when Design System already provides the required behavior.

### Keep

when it is genuinely product-specific.

### Refactor

when local CSS is fighting the Design System.

Do not introduce a second token system.

Do not use:

```css
--tfi-primary
--tfi-bg
--tfi-text
--tfi-border
```

when the corresponding MAGI semantic tokens already exist.

If a genuinely TFI-specific token is required, document why.

---

# 30. Data / UI Boundary

Do not let UI cleanup accidentally change TFI's data semantics.

The current TFI data architecture distinguishes:

```text
data_source
provider
model
```

The UI should preserve these concepts.

Do not rename or merge them merely for visual simplification.

---

# 31. Remediation Strategy

After the audit, fix in this order:

### P0

Functional/accessibility issues.

### P1

Design System violations and major visual inconsistencies.

Prioritize:

```text
theme
colors
typography
layout
components
brand
forms
navigation
icons
```

### P2

Content and visual polish:

```text
copy
spacing refinement
micro-interactions
metadata presentation
responsive polish
```

Do not start with P2 while P1 Design System drift remains.

---

# 32. Migration Preference

Prefer:

```text
existing Design System primitive
```

over:

```text
new local primitive
```

Prefer:

```text
existing MAGI token
```

over:

```text
new TFI token
```

Prefer:

```text
existing Experience Guideline
```

over:

```text
new TFI convention
```

unless the TFI product genuinely requires a different behavior.

---

# 33. Visual Validation

After remediation, compare TFI against:

```text
magi.website
MAGI Design System showroom
```

Validate:

```text
color
typography
spacing
radius
buttons
inputs
cards
badges
icons
focus
theme
brand
navigation
```

Do not judge only individual components.

Judge the whole visual rhythm.

The key question:

> Does TFI look like it belongs to the MAGI product family while still clearly being a developer tool?

---

# 34. Deliverables

Before implementation:

```text
1. Audit report
2. P0/P1/P2 findings
3. Terminology table
4. Component migration map
5. Token drift report
6. Copy/content issues
```

After implementation:

```text
1. Changed files
2. Design System components adopted
3. Tokens migrated
4. Copy changes
5. Accessibility fixes
6. Responsive fixes
7. Remaining intentional deviations
```

---

# 35. Definition of Done

The TFI consumer migration is complete when:

* [ ] TFI consumes the current MAGI Design System
* [ ] no parallel theme system exists
* [ ] no unnecessary parallel token system exists
* [ ] MAGI brand assets are used correctly
* [ ] dark/light behavior follows MAGI
* [ ] colors use semantic MAGI tokens
* [ ] typography follows MAGI typography
* [ ] spacing follows MAGI spacing
* [ ] radius follows MAGI conventions
* [ ] generic UI icons follow MAGI Iconography Contract
* [ ] buttons use the MAGI Button where applicable
* [ ] form controls use MAGI primitives where applicable
* [ ] accessibility follows Component Contracts
* [ ] terminology is consistent
* [ ] marketing fluff is removed from functional UI
* [ ] developer-oriented information density is preserved
* [ ] configuration/code surfaces remain technical and readable
* [ ] provider identity remains distinct from MAGI accent
* [ ] responsive behavior is intentional
* [ ] loading/error/empty states are consistent
* [ ] no unnecessary new Design System primitives are introduced
* [ ] product-specific components remain product-owned
* [ ] existing TFI functionality remains intact
* [ ] build/typecheck/lint/tests pass

---

# 36. Final Design Principle

The final TFI experience should communicate:

> **MAGI visual language. TFI product experience.**

Or more concretely:

```text
MAGI owns:
    brand
    visual language
    tokens
    typography
    primitives
    accessibility rules
    interaction conventions

TFI owns:
    model discovery
    model selection
    provider filtering
    capability filtering
    requirements
    intent
    recommendations
    configuration generation
    LiteLLM output
```

Do not confuse visual consistency with product sameness.

The goal is not to make TFI look like the MAGI homepage.

The goal is to make someone immediately recognize:

> “This is a MAGI product — and specifically, this is a serious developer tool for generating model configurations.”

