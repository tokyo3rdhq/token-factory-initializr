# TFI × MAGI Website — Visual Detail Consistency Fix

## Context

You are working on the TFI website (`token-factory-initializr`) as a consumer of the MAGI Design System.

The visual language of TFI should remain:

> **MAGI visual language + TFI developer-tool information density**

Do **not** redesign TFI or make it visually identical to the MAGI marketing homepage.

Instead, fix the small but highly visible visual inconsistencies between:

* `magi.website`
* TFI (`token-factory-initializr`)
* `@tokyo3rdhq/magi-design-system`

The goal is to make TFI feel like a first-class MAGI sub-site rather than an independently styled application.

---

# 1. Audit Before Editing

Before making changes:

1. Inspect the current TFI implementation.
2. Inspect the current `@tokyo3rdhq/magi-design-system` implementation.
3. Inspect the actual layout of `magi.website`.
4. Compare the two sites in a browser at:

   * desktop
   * narrow desktop/tablet
   * mobile
5. Identify whether each discrepancy comes from:

   * TFI local CSS
   * incorrect Design System usage
   * incorrect layout container
   * duplicated component styling
   * incorrect asset sizing
   * incorrect positioning/anchoring
6. Prefer fixing the underlying layout/token/component contract rather than adding one-off pixel overrides.

Do not modify the Design System unless the problem is demonstrably caused by a missing or incorrect Design System contract.

---

# 2. Navbar — Secondary Site Title Must Not Push Navigation Off-Center

## Observed Problem

TFI has an additional site/product title in the navbar because it is a MAGI sub-site.

For example, the navbar conceptually contains:

```text
[MAGI] [Token Factory Initializr]          [navigation] [language] [...]
```

The additional TFI title currently participates in the normal horizontal layout and causes the center navigation/menu to visually shift too far to the right.

This makes the navbar feel unbalanced compared with `magi.website`.

## Required Behavior

The navbar should be designed around **visual anchoring**, not simply sequential flex layout.

The primary navigation should remain visually centered relative to the viewport / navbar content area.

The secondary product title must NOT cause the navigation center to drift.

Conceptually:

```text
┌──────────────────────────────────────────────────────────────┐
│ [MAGI] [TFI]              [ NAVIGATION ]        [actions]   │
└──────────────────────────────────────────────────────────────┘
```

The exact implementation is up to the existing architecture, but consider:

* CSS Grid with explicit left / center / right regions
* absolute centering of the central navigation
* a three-column navbar layout
* a balanced container strategy

Avoid simply increasing/decreasing margins until the screenshot looks correct.

### Important

The TFI title is product identity and should remain visible.

Do NOT solve this by:

* removing the TFI title
* hiding it on desktop
* reducing its font size unnaturally
* adding arbitrary `margin-left`
* adding arbitrary negative margins

The correct solution is to decouple the center navigation's position from the width of the left-side branding group.

---

# 3. Navbar Bottom Boundary Must Reach the Viewport Edges

## Observed Problem

The bottom border / visual boundary of the TFI navbar does not extend all the way to the browser viewport edges.

There is visible horizontal space between the navbar boundary and the left/right edges of the page.

Conceptually the current result looks like:

```text
      ┌──────────────────────────────────────┐
      │              Navbar                  │
      └──────────────────────────────────────┘
```

while the intended MAGI-style result is:

```text
┌──────────────────────────────────────────────┐
│                    Navbar                    │
└──────────────────────────────────────────────┘
```

## Required Behavior

The navbar's bottom boundary should span the full viewport width.

The content inside the navbar may still use a constrained/max-width container:

```text
┌──────────────────────────────────────────────┐
│   ┌──────────────────────────────────────┐   │
│   │        constrained navbar content    │   │
│   └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
       ↑
       content container
```

The key distinction is:

> **Navbar background/border = viewport width**
>
> **Navbar content = layout container width**

Do not simply make the navbar content container `width: 100%` if that breaks the existing content alignment.

Instead, separate:

```text
Navbar outer shell
    └── full viewport width
          └── navbar inner container
                └── constrained content
```

The bottom border should belong to the outer navbar shell.

Check for accidental:

* `max-width`
* `margin-inline: auto`
* rounded container
* horizontal padding applied to the border-owning element
* nested container owning the border
* `overflow`
* body/page wrapper constraints

that currently cause the boundary to stop short of the viewport edges.

---

# 4. Favicon Size Must Match MAGI Website

## Observed Problem

The TFI favicon appears visibly larger than the favicon used by `magi.website`.

This creates a subtle but noticeable inconsistency when comparing browser tabs/bookmarks.

## Required Behavior

Use the same favicon visual sizing and asset strategy as the main MAGI website wherever appropriate.

Audit:

* favicon asset
* SVG viewBox
* intrinsic dimensions
* `<link rel="icon">`
* browser rendering
* favicon padding / optical bounds
* app icon vs favicon distinction

Do not assume that identical CSS dimensions automatically produce identical visual size.

SVGs with different internal whitespace or viewBox geometry can appear at different optical sizes even when rendered at the same nominal dimensions.

Therefore compare:

```text
MAGI favicon
TFI favicon
```

at the same browser zoom and inspect the actual SVG geometry.

### Important

Do not enlarge or shrink the favicon arbitrarily just to match a screenshot.

Prefer:

1. shared canonical MAGI favicon asset
2. shared favicon contract
3. consistent SVG viewBox / optical bounds
4. consistent HTML metadata

The favicon should be a brand asset concern, not a product-specific visual variation.

---

# 5. i18n Dropdown — Container Must Fully Contain Menu Items

## Observed Problem

When clicking the i18n/language icon in the top-right of TFI, the dropdown container is visually smaller than its menu items.

The result is approximately:

```text
┌───────────────┐
│ English       │
│ 中文          │
│ Deutsch       │
└───────────────┘
     ↑
items visually protrude
```

The menu items extend outside the apparent dropdown boundary.

This looks like a broken component rather than intentional overflow.

## Required Behavior

The dropdown surface must fully contain every menu item.

For example:

```text
┌─────────────────────┐
│ English             │
│ 中文                │
│ Deutsch             │
└─────────────────────┘
```

Audit:

* dropdown width
* menu item horizontal padding
* menu item min-width
* text width
* icon width
* gap
* box sizing
* border
* border radius
* shadow
* overflow
* positioning
* viewport collision handling

The dropdown width should be determined by the menu content or an explicit component-level minimum width.

Do not fix this by simply hiding overflow:

```css
overflow: hidden;
```

unless the component contract explicitly requires it.

Do not clip text.

Do not allow menu items to visually escape the surface.

---

# 6. i18n Dropdown Must Follow Design System Surface Rules

While fixing the size issue, verify that the language menu uses the existing MAGI Design System semantics for:

* background
* border
* radius
* shadow/elevation
* text color
* hover state
* active/selected state
* focus-visible state
* disabled state if applicable
* spacing
* typography

Do not introduce a new local dropdown visual language.

If TFI currently has custom CSS such as:

```css
.language-menu {
  ...
}
```

determine whether it should instead consume the existing Design System primitive or token.

The goal is not to eliminate all product CSS.

The goal is to prevent TFI from recreating generic Design System behavior locally.

---

# 7. Navbar Vertical / Horizontal Geometry Audit

Because the above problems are all navbar-related, perform a focused navbar geometry audit.

Check:

### Horizontal

* viewport alignment
* max-width
* container width
* left/right padding
* logo width
* secondary product title width
* navigation center
* right-side action group
* language button
* gaps between groups

### Vertical

* navbar height
* logo optical height
* title line-height
* icon size
* icon button hit area
* menu alignment
* border position
* dropdown anchor position

### Optical alignment

Do not judge only by CSS boxes.

Compare the visual result against `magi.website` at the same:

* viewport width
* browser zoom
* device pixel ratio where practical

The goal is **optical consistency**, not merely identical numeric CSS values.

---

# 8. Do Not Introduce One-Off Hacks

Avoid fixes such as:

```css
margin-left: 37px;
margin-right: -18px;
transform: translateX(...);
top: 3px;
width: 143px;
```

unless the value is part of an explicit reusable design-system or component contract.

Especially avoid:

* negative margins to compensate for navbar structure
* arbitrary transforms
* duplicated breakpoint-specific magic numbers
* per-page favicon sizing hacks
* hiding overflow to conceal dropdown sizing problems

Prefer fixing the layout model.

---

# 9. Preserve the TFI Product Experience

Do NOT turn TFI into a copy of the MAGI homepage.

The following are intentionally product-owned and should remain TFI-specific:

* Token Factory branding/title
* model selection UI
* model filters
* provider information
* requirement / intent input
* recommendation UI
* model metadata
* config generation
* config preview
* developer-oriented dense layouts

Only fix the shared visual language and common shell details.

The principle remains:

> **MAGI owns the visual language.**
>
> **TFI owns the product experience.**

---

# 10. Validation Matrix

After implementation, verify at least:

| Area                   | MAGI              | TFI               | Expected                           |
| ---------------------- | ----------------- | ----------------- | ---------------------------------- |
| Navbar outer width     | full viewport     | full viewport     | consistent                         |
| Navbar bottom boundary | full viewport     | full viewport     | consistent                         |
| Main navigation center | visually centered | visually centered | independent of product title width |
| Product title          | N/A               | visible           | must not push nav                  |
| Favicon                | canonical MAGI    | same visual scale | consistent                         |
| Language button        | consistent        | consistent        | same icon/button geometry          |
| Language dropdown      | fully contained   | fully contained   | no overflow                        |
| Dropdown surface       | MAGI tokens       | MAGI tokens       | consistent                         |
| Typography             | MAGI tokens       | MAGI tokens       | consistent                         |
| Spacing                | MAGI tokens       | MAGI tokens       | consistent                         |

Test at minimum:

* desktop wide
* desktop standard
* tablet
* mobile
* light theme if supported
* dark theme

---

# 11. Definition of Done

This task is complete only when:

* [ ] TFI's secondary product title no longer pushes the central navbar navigation to the right.
* [ ] Navbar center alignment is structurally correct rather than achieved through arbitrary offsets.
* [ ] Navbar bottom border/boundary reaches both viewport edges.
* [ ] Navbar content can remain constrained independently from the outer border.
* [ ] TFI favicon has the same optical size as `magi.website`.
* [ ] TFI uses the appropriate canonical MAGI favicon asset/contract.
* [ ] i18n dropdown surface completely contains all menu items.
* [ ] Language menu has no visual protrusion or clipping.
* [ ] Dropdown uses MAGI Design System tokens/components where applicable.
* [ ] No unnecessary local duplicate component styling was introduced.
* [ ] No arbitrary negative-margin/transform hacks were introduced.
* [ ] Desktop and mobile layouts remain correct.
* [ ] Existing TFI developer-tool density and functionality remain unchanged.
* [ ] No unrelated components are redesigned.
* [ ] Changes are minimal and focused on visual consistency.

---

# Final Principle

Do not ask:

> "How can I make this screenshot look closer?"

Ask:

> "What layout, asset, or component contract is causing TFI to visually diverge from the MAGI system?"

Fix the underlying cause.

The desired result is not pixel-copying.

It is:

> **TFI should unmistakably belong to the MAGI product family, even though it remains a distinct developer tool.**

