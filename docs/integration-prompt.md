# Integration Prompt — `xxx.magi.website`

> **Purpose**: this is a copy-paste prompt for an AI coding agent that needs to integrate `@tokyo3rdhq/magi-design-system` into a new or existing `xxx.magi.website` product. Replace the `{...}` placeholders, paste the whole document (or the body after "Prompt") into the agent's input, and let it execute.
>
> **Last verified against**: `@tokyo3rdhq/magi-design-system@0.1.0`. Re-check if you upgrade.

---

## Prompt

You are a senior frontend engineer working on the **MAGI** product family. Your task is to integrate `@tokyo3rdhq/magi-design-system` (the shared MAGI design system) into a new or existing product site. Do not redesign the design system, do not invent your own tokens, do not copy-paste CSS — consume the package.

### Product context

- **MAGI** is an independent AI lab. The main portal lives at https://magi.website and links to a family of product sites under `*.magi.website`. Every product site must visually belong to the same family.
- The visual language is **dark-first, near-monochrome, restrained**. Apple-level restraint + developer-infrastructure aesthetic. **No CRT / terminal / neon styling.** See [`architecture.md`](./architecture.md) and the package's [`README.md`](../packages/design-system/README.md) for details.
- All products share typography, spacing, surfaces, borders, radius, motion, and accessibility rules via `@tokyo3rdhq/magi-design-system`. Each product may override **only** its accent color via `<ProductTheme accent="…" />`.

### Inputs (fill in before starting)

Replace each `{…}` with the actual value. If a value is unknown, ask the user before guessing.

```
PRODUCT_NAME       = {Human-readable product name, e.g. "Token Factory Initializr"}
PRODUCT_SLUG       = {URL-safe slug, e.g. "token-factory-initializr"}
SUBDOMAIN          = {DNS subdomain, e.g. "token-factory-initializr"} → URL: https://{SUBDOMAIN}.magi.website
PRODUCT_DESCRIPTION= {One sentence describing the product}
ACCENT_PRESET      = {One of: green | cyan | violet | amber | white}
                    Default if unsure: cyan.
REPO_PATH          = {Absolute path to the product repo on disk, e.g. /home/.../token-factory-initializr}
STACK              = {Build framework + UI framework, e.g. "Astro 4 + Tailwind" or "Cloudflare Pages + React 18 + Vite"}
NODE_VERSION       = {Node.js version used in CI, default 20}
```

### Non-negotiable rules

These are **hard constraints**. Violating any of them breaks the family contract.

1. **Do not redefine tokens** — no local copies of `--magi-*`, no per-component hex values, no Tailwind colors that bypass the design system. Spec §29.
2. **Do not introduce another UI library** — no MUI / Chakra / Radix-based full UI framework unless one is already a peer dependency. Spec §4.
3. **Do not reintroduce CRT / terminal / neon styling.** Spec §36.
4. **Do not fork the package** — consume via `npm install @tokyo3rdhq/magi-design-system`. Spec §2.
5. **`<body>` must carry `data-magi-app`** — foundation styles only scope themselves against this attribute. See [`architecture.md` §3](./architecture.md).
6. **`<ProductTheme>` is the only sanctioned way to change the accent** — set inline custom properties on a subtree, do not write global CSS to override `--magi-accent`. Spec §10.
7. **All user-visible text must be styled through design-system utilities or components** — `.magi-h1`, `<ProductHeader>`, etc. Avoid hand-rolled typographic CSS unless a new pattern is justified.

### Pre-flight

Before any code changes:

1. **Read the existing product's stack** — confirm framework, UI library, package manager, build tooling. The product may already have a peer dependency on a UI library; if it does, prefer to consume that via the design system's primitives rather than fight it.
2. **Read [`docs/migration-guide.md`](./migration-guide.md)** — it has concrete steps for Astro + Tailwind and for Cloudflare Pages + React + Vite. The product you are integrating may match one of these profiles.
3. **Read [`docs/tokens.md`](./tokens.md)** — every token you might need is documented with values and recommended usage.
4. **Skim [`docs/architecture.md`](./architecture.md)** — explains why plain CSS (not CSS Modules), why `body[data-magi-app]`, why `data-magi-app` on `<body>`. Skipping this leads to wasted debugging.

### Required steps

The order matters. Do not skip steps even if they seem trivial.

1. **Install the package**:
   ```bash
   cd {REPO_PATH}
   npm install @tokyo3rdhq/magi-design-system
   ```
2. **Import the stylesheet once at the application entry point**. Find the file that mounts the app (e.g. `src/main.tsx`, `src/layouts/Layout.astro`, `src/_app.tsx`) and add:
   ```ts
   import '@tokyo3rdhq/magi-design-system/styles.css';
   ```
3. **Mark `<body>`**. If you control the HTML template (Astro `<body>` tag, Vite `index.html`):
   ```html
   <body data-magi-app>
     <!-- existing root element -->
   </body>
   ```
   If you don't, set it from JavaScript before the first render:
   ```ts
   document.body.setAttribute('data-magi-app', '');
   ```
4. **Wrap your app in `<ProductTheme>`** at the highest practical level — usually just inside `<body>`, around the entire routes tree:
   ```tsx
   import { ProductTheme } from '@tokyo3rdhq/magi-design-system';

   <ProductTheme accent="{ACCENT_PRESET}" name="{PRODUCT_SLUG}">
     <App />
   </ProductTheme>
   ```
   If you are using Astro with server-rendered pages (no React islands), use a custom element wrapper or skip `<ProductTheme>` for now and rely on the default `green` accent — `data-magi-product` and the four accent tokens will only be set when React is mounted. Note this gap in the deliverable.
5. **Replace existing components** with design-system primitives where applicable:

   | Existing pattern | Replacement |
   | --- | --- |
   | `<button class="btn-primary">` | `<Button variant="primary">` |
   | `<button class="btn-secondary">` | `<Button variant="secondary">` |
   | `<div class="card">` | `<Card variant="elevated">` |
   | `<div class="container">` | `<Container size="xl">` |
   | `<section class="section">` | `<Section spacing="lg">` |
   | `<span class="badge">` | `<Badge variant="accent">` |

   Do not replace product-specific components (`ModelCard`, `ProviderTabs`, etc.) — those stay in the product. Just make sure they **use** the design-system primitives internally.
6. **Replace ad-hoc typography with utility classes**:
   - Hero headline → `className="magi-display"` or `<h1 className="magi-h1">`
   - Section title → `className="magi-h2"`
   - Body copy → `className="magi-body"` / `magi-body-lg`
   - Eyebrow → `className="magi-eyebrow"`
7. **Verify** (next section).

### Acceptance criteria

The integration is **complete** only when **all** of these are true:

- [ ] `@tokyo3rdhq/magi-design-system` is in `dependencies` (not `devDependencies`) in `{REPO_PATH}/package.json`.
- [ ] The product site loads without console errors or warnings from missing tokens / undefined CSS classes.
- [ ] The dark gradient backdrop is visible on every page (body bg is `#000` with a subtle radial gradient at top).
- [ ] The accent color (`{ACCENT_PRESET}`) appears on: the top nav active link / button hover state, the eyebrow label, primary buttons.
- [ ] Tab-navigating the page surfaces a visible focus ring (the 2px black inner + 2px accent outer ring).
- [ ] No `rgba(0, 200, 83, …)` or `#00c853` literals appear in `{REPO_PATH}/src/**/*.css` — those would mean tokens are being duplicated.
- [ ] No class names from a competing UI framework (MUI `MuiButton`, Chakra `chakra-button`, etc.) leak into the rendered DOM unless that framework was already a dependency.
- [ ] No reintroduction of CRT / terminal styling (no `.glitch`, `.pulse-glow`, `.terminal-text`, scanlines, blinking cursors, etc.).
- [ ] `@media (prefers-reduced-motion: reduce)` disables transitions and animations.
- [ ] On mobile (≤ 768 px) and desktop (≥ 1024 px), the layout reflows correctly using `Container`, `Section`, `Stack`.
- [ ] All buttons / badges / cards used in the product import from the package, not from a local copy.
- [ ] The product's README has been updated with a one-line note: "Uses `@tokyo3rdhq/magi-design-system` for shared visual language."

### How to verify

Run these checks and capture their output:

1. **Build succeeds**:
   ```bash
   cd {REPO_PATH}
   npm run build 2>&1 | tail -20
   ```
2. **TypeScript passes** (only relevant if the product uses TS):
   ```bash
   npx tsc --noEmit 2>&1 | tail -20
   ```
3. **No duplicate token values** — find any local hex that duplicates a design-system token:
   ```bash
   rg -n '#(00c853|00C853|000000|1d1d1f|f5f5f7|86868b|6e6e73)' src/
   rg -n 'rgba\(255, ?255, ?255, ?0\.08\)' src/
   ```
   Both should return zero results (or only results inside a deliberate `color-mix()` that derives from `--magi-*`).
4. **Smoke test the live site**:
   - Open the dev server (`npm run dev` or the equivalent)
   - Confirm: dark backdrop, accent on primary CTA, focus ring on Tab, no console errors
   - Confirm: switching `<ProductTheme accent>` to a different preset visibly changes the accent everywhere

### Out of scope

Do **not** attempt any of the following as part of this integration:

- Adding new components to the design system (open an issue in `tokyo3rdhq/magi-design-system` instead)
- Refactoring product business logic
- Replacing the product's framework (Astro → React, etc.)
- Adding Tailwind / Next / Vite coupling to the design system itself
- Modifying tokens globally — token overrides happen at the `<ProductTheme>` level only

### References

- [`@tokyo3rdhq/magi-design-system` package README](../packages/design-system/README.md) — full API reference
- [`docs/tokens.md`](./tokens.md) — every CSS custom property with values and recommended use
- [`docs/architecture.md`](./architecture.md) — implementation decisions (plain CSS over CSS Modules, `body[data-magi-app]` scoping, side-effect import pattern)
- [`docs/migration-guide.md`](./migration-guide.md) — concrete step-by-step for Astro + Tailwind (magi-portal profile) and Cloudflare Pages + React + Vite (token-factory-initializr profile)
- [Original spec](../packages/design-system/README.md) — design rationale, what's in / out of scope per phase
- [GitHub repo](https://github.com/tokyo3rdhq/magi-design-system) — issues + releases

### Deliverable

When you finish, report:

1. List of files touched (relative to `{REPO_PATH}`)
2. The install command you ran and its output
3. The build / typecheck results
4. A short paragraph: "What now looks visually different from before" — call out any genuine visual change (focus ring appearing is one; if everything looks identical aside from that, say so).
5. Anything you couldn't do and why (e.g. "framework is Svelte, ProductTheme not yet ported").

If any acceptance criterion fails, **stop** and report; do not paper over it with custom CSS.