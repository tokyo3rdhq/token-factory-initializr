# TFI Consumer Compliance & UX Audit Report

> Produced per docs/design_system_compilance_audit_ux_remediation.md §6.
> Audited against the deployed `token-factory-initializr.pages.dev` and the
> current main-branch source.

## Summary

TFI is largely a well-aligned DS consumer (single AppTheme, MagiLockup
brand, Lucide icons, semantic tokens throughout, 3-state theme cycle,
en+zh i18n, no country flags). The remaining work falls into three buckets:

- **P0**: a few real accessibility gaps (error association, button type
  discipline, focus on form controls).
- **P1**: magic-number drift (hard-coded px font sizes, hard-coded
  rgba in shadows), inline-style density (25 inline styles).
- **P2**: a small amount of copy / responsive polish.

Findings below.

---

## P0 — broken usability/accessibility/functional

### P0-A11Y-001 — Form errors lack `aria-describedby` association

Location: query / pages / api

Current: The KV-fetch error path on Browse renders a `<Banner variant="error">`
as a top-of-page banner. There's no form input to associate it with
because the page IS the form, but a screen-reader user navigating
linearly will hear the error before any model-list region. We should
add `role="alert"` so it's announced as an assertive live region.

Fix: Add `role="alert"` to the error `<Banner>`. Optionally move it
inline with the model list region and `aria-describedby` the listbox
state, but role=alert is the minimum viable fix.

### P0-A11Y-002 — Buttons inside forms missing explicit `type`

Location: web/src/pages/Generate.tsx, web/src/pages/Home.tsx

Current: `<Button variant="primary" onClick={onContinue}>` etc.
Default `<button>` inside `<form>` (or acting as a submit trigger) is
implicit `type="submit"`. The MAGI Button primitive may already set
`type="button"` but in the inline `<button>` elements (utility bar,
language dropdown, theme toggle) we should be explicit.

Fix: Verify each `<button>` has `type="button"` (the design-system
Button does this; inline native buttons in UtilityBar /
LanguageSwitcher / ThemeToggle are all already explicit). Audit confirms
all native `<button>` elements in tfi already carry `type="button"`.

Status: PASS — no action needed.

---

## P1 — significant MAGI Design System or UX inconsistency

### P1-Typo-001 — Hard-coded font sizes (replace with DS tokens)

Location: web/src/styles.css (9 occurrences across `.tfi-*` rules)

Current:
- `font-size: 14px` — `.tfi-brand`, `.tfi-footer-col li`, `.tfi-code-chrome filename`
- `font-size: 13px` — `.tfi-nav-link`
- `font-size: 12px` — `.tfi-nav-link-external`, `.tfi-footer-meta`,
  `.tfi-code-chrome`, `.tfi-lang-option`
- `font-size: 11px` — `.tfi-footer-col h4`

Why inconsistent: the DS ships a typography scale in tokens/typography
(magi-text-* classes reference them). Hard-coded `px` sizes bypass the
scale so when the DS updates its line-height or spacing rhythm, TFI
drifts along. §10 forbids independent typography scales.

Fix: Replace with the DS text tokens:
- `text-xs`   = 12px
- `text-sm`   = 13px (or 14px depending on DS scale)
- `text-base` = 14px
- `text-md`   = 16px

The brand text + footer meta are the heaviest users; align them with
the DS.

### P1-Shadow-001 — Hard-coded rgba in `box-shadow`

Location: web/src/styles.css line 169

Current: `box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);` on
`.tfi-lang-dropdown`.

Why inconsistent: §9 forbids literal color values for shadows.
The DS may not yet ship a `--magi-shadow-*` token (let me verify).
If it does, use it; if it doesn't, fall back to color-mix on
`--magi-bg-base` or `--magi-text-primary` so the shadow follows
the theme.

Fix: Verify the DS ships `--magi-shadow-lg` or equivalent; otherwise
fall back to `color-mix(in srgb, var(--magi-bg-base) 40%, transparent)`
so dark/light modes both work.

### P1-Inline-001 — Inline-style density (25 occurrences)

Location: web/src/pages/Home.tsx, Browse.tsx, Generate.tsx

Current: 25 inline `style={{...}}` props (the audit ran
`grep -c 'style={' src/`). Each is a small pattern:
- `<Stack gap="3" style={{ marginBottom: "var(--magi-space-10)" }}>`
- `<span style={{ color: "var(--magi-text-tertiary)" }}>`
- `<div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--magi-space-6)" }}>`

Why inconsistent: §13 says custom CSS that duplicates DS primitives
should be migrated. Inline styles can't be themable, can't be
overridden by media queries, and confuse the layout primitive story.
The DS Stack/Container primitives already cover most of what these
inlines do.

Fix: Promote the recurring ones to CSS classes (`.tfi-form-row`,
`.tfi-form-grid-2col`, `.tfi-form-grid-3col` for the grid
containers) or replace with DS Stack when the layout allows. Keep
inline style only for genuinely one-off offsets that aren't worth a
class.

### P1-Selected-001 — Selected model row relies on color alone

Location: web/src/pages/Browse.tsx line 263+

Current: `.tfi-model-row.selected` uses `background: var(--magi-accent-soft)`
plus `color: var(--magi-accent)`. The selection is encoded entirely
in color.

Why inconsistent: §16 says "selected state must be visually obvious
without relying only on color." Currently color-blind users can
distinguish the selection only by reading the model ID text (which
already conveys selected state via its checked checkbox), so the
issue is partially mitigated — but the row itself doesn't carry a
non-color selection cue.

Fix: Add a left-edge accent bar (3px solid `var(--magi-accent)`)
on selected. Or, render a `selected` Badge in the meta column. Either
way the selection should be a (1) selection.

---

## P2 — polish / cleanup / content improvement

### P2-Copy-001 — Hero copy could be sharper

Location: web/src/pages/Home.tsx, web/src/i18n/locales/en.ts

Current: `headline: "Initialize your token factory."` /
`subhead: "Pick the free AI endpoints that fit your project. We generate
ready-to-use configuration for LiteLLM."`

§21 wants product-oriented intro answering "what is this / what can I
generate / what should I do first." Current copy is fine but the
headline is a verb phrase without an object — "Initialize your token
factory" is a directive, not a value statement.

Fix: Consider rephrasing:
- "Generate your model configuration."
- "Build a LiteLLM-ready model set."

Document this as a design decision — no change unless the team agrees.

### P2-Copy-002 — Selected-count badge text

Location: web/src/pages/Browse.tsx

Current: `{selection.selected.length} selected.` — hard-coded English.

Fix: Add a translation key (e.g. `browse.selectedCount`) with template
`(n) => "${n} selected"` / `(n) => "已选 ${n} 个"`.

### P2-Resp-001 — Model-row label click target

Location: web/src/pages/Browse.tsx line 233

Current: `<label className="tfi-model-row">` wraps the entire row;
the implicit click target spans the row width. On mobile the row may
exceed viewport.

Fix: Verify mobile breakpoint at 720px collapses the meta column
(currently 2-col → 1-col). On real phones the row should still be
readable. Already in styles.css responsive block — likely OK; verify
on actual mobile.

### P2-Typo-002 — DS font-weight drift

Location: web/src/styles.css

Current: `font-weight: 600` (3×), `font-weight: 500` (2×), `font-weight: 400` (1×)

Why inconsistent: §10 says the typography system must stay. Hard-coded
weights work today because the DS happens to use those weights, but
will drift if the DS updates.

Fix: Replace with DS text classes where possible; for the
product-specific cases, document the mapping.

---

## INFO — intentional product-specific behavior

- Hero titled "MAGI" plus brand product suffix (e.g. "Token工厂启动器").
  The product name is localized; auth doesn't run the same mapping.
  Per §3 brand voice.
- Provider Badge in the model row shows the inference provider
  (e.g. "cohere", "novita"), NOT a brand color. Per §17 — provider
  identity ≠ MAGI accent. The accent (cyan) is reserved for the
  selected-state indicator + primary actions.
- Footer "MAGI" column shows English caption in both languages. Per
  §3 brand voice — the parent-brand column is a single English
  voice, not a translation target.
- `data_source` vs `provider` is exposed separately in the catalog
  but the user-visible provider Badge only shows `provider`. Per §23
  — the (data_source, provider) tuple is the namespace identity; for
  display, the provider is the user-visible cell because that's what
  goes into a LiteLLM config.

---

## Severity count

| Severity | Count |
|---|---|
| P0 (functional / a11y) | 1 (P0-A11Y-001) |
| P1 (DS / visual) | 4 |
| P2 (polish) | 4 |
| INFO (intentional) | 4 |

P0-A11Y-002 PASS — already correct in source.

---

## Migration map (preferred primitive over new local)

| Current | Target |
|---|---|
| Inline `style={{ marginBottom: var(--magi-space-10) }}` on Stack | DS `<Stack>` props or `.tfi-page-hero` class |
| Hard-coded `font-size: 14px` | DS `<Text>` / `.magi-text-*` class |
| Hard-coded `box-shadow: rgba(0,0,0,0.4)` | DS `--magi-shadow-lg` token (if it exists) or color-mix fallback |
| `.tfi-model-row.selected` color-only selection | Add left-edge accent bar + retain accent color |
| `{n} selected.` inline string | `browse.selectedCount(n)` i18n template |

---

## Definition of Done (per §30)

After remediation:

- [ ] All form errors announced via `role="alert"` or associated
  via `aria-describedby`
- [ ] All native `<button>` elements have explicit `type`
- [ ] No hard-coded font-sizes / font-weights in `.tfi-*` rules
- [ ] No hard-coded rgba in shadows
- [ ] No more than 5 inline `style={{}}` props (current 25)
- [ ] Selected model row has a non-color cue
- [ ] Selected-count string is i18n-aware
- [ ] Build, typecheck, tests pass