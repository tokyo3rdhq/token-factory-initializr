# UI Optimization Plan: Homepage Spacing + Sidebar Design

## Context
- Current spacing: `.tfi-home-headline { margin-top: 0 }` produces a 37px eyebrow→headline gap vs 24px headline→subhead. Already satisfies `eyebrow-h1 > h1-subhead` but needs a larger gap for "breathability" and a larger sidebar margin-top to match.
- Sidebar panels (Human/Agent) use flat borders, no rounded corners, no soft shadows — appear too tight vs `Browse.tsx`/`Generate.tsx` which use DS `Card` and `Button`.
- Doc links have an unnecessary `border-top` divider that widens the line beyond its content.

## Approach
### Step 1 — Increase eyebrow→headline gap
- Target: `.tfi-home-headline { margin-top: var(--magi-space-5); }` (from `0`).
- This moves the headline down by ~9px (var(--magi-space-5) ≈ 20px) within a Stack gap of 4px, giving eyebrow→headline ≈ 42px > headline→subhead (24px).

### Step 2 — Update sidebar margin-top
- Target: `.tfi-home-sidebar { margin-top: 52px; }`.
- This matches the new headline top position (eyebrow top + stack gap + magi-eyebrow height + headline margin-top), keeping sidebar and headline at the same visual top edge.

### Step 3 — Refactor sidebar panels for DS Card/Button style
- Replace flat `.tfi-home-human-panel` with a DS `Card`-style wrapper: rounded corners (`--magi-radius-md`), soft shadow (`--magi-shadow-sm`), elevated background (`--magi-surface-elevated`).
- Replace flat `.tfi-home-agent-panel` with a DS `Card`-style wrapper.
- Replace `.tfi-home-browse-btn` (single button, ~36px) with a DS `Button` (`size="sm"` or larger) for consistency.
- Keep `.tfi-home-copy-btn` as-is (it's a copy icon, not a selectable button).

### Step 4 — Verify geometry
- Re-measure on deployed page: sidebar.top == h1.top; panels not narrower than sidebar.

## Critical Files
- `web/src/styles.css` — CSS rules for eyebrow, headline, sidebar, panels, browse-btn, doc-links
- `web/src/pages/Home.tsx` — JSX render structure (imports Button, Card from DS)

## Verification
- Navigate to deployed homepage; confirm sidebar top equals h1 top.
- Confirm agent panel and browse button render without overflow.

## Assumptions
- `--magi-space-5` and `--magi-radius-md` tokens exist in the DS theme.
- Importing `Card` and `Button` from DS is safe (already imported in Home.tsx).