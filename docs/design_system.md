# MAGI Website — Unified Design System

## 0. Design Mission

You are designing websites for **MAGI**, an independent AI infrastructure and product lab.

MAGI operates a family of products under:

* `magi.website` — MAGI main site
* `*.magi.website` — MAGI product sites
* future subdomains — developer tools, AI infrastructure, model services, agents, APIs, and other experimental products

All MAGI websites must feel like they belong to the **same product family**.

The goal is NOT to make every website visually identical.

The goal is:

> **One visual language, multiple products.**

The visual identity should feel:

* Dark
* Premium
* Minimal
* Technical
* Calm
* Precise
* Modern
* Developer-oriented
* AI-native
* Independent rather than corporate

The overall aesthetic is inspired by the restraint and product focus of Apple's modern web design, combined with the visual language of premium developer infrastructure products.

Do NOT directly copy Apple's layouts, assets, wording, or proprietary visual identity.

Think:

> **Apple-level restraint + AI infrastructure + developer tooling + independent lab.**

---

# 1. Core Design Principles

## 1.1 Clarity over decoration

Every visual element must have a purpose.

Do not add:

* decorative cards
* unnecessary gradients
* excessive shadows
* random glowing effects
* meaningless animations
* excessive icons
* ornamental illustrations

If removing an element makes the interface clearer, remove it.

---

## 1.2 One idea per section

Each major viewport/section should communicate one primary idea.

Prefer:

> Large statement
> Short explanation
> One primary action

over:

> Large heading
> 8 cards
> 12 badges
> 4 buttons
> 3 gradients

The page should feel calm even when the product itself is technically complex.

---

## 1.3 Product first

The product is the hero.

For developer tools, the product UI, configuration, API, code, model, workflow, or result should become the visual focal point.

Do not rely on abstract AI imagery to communicate the product.

Avoid generic:

* AI brain graphics
* glowing neural networks
* robot illustrations
* random 3D objects
* stock photography
* meaningless futuristic backgrounds

Prefer:

* real product UI
* code
* terminal output
* API requests
* model cards
* configuration
* diagrams
* structured data
* meaningful product screenshots

---

# 2. Brand Personality

MAGI should feel like:

> **A small, highly technical AI lab building useful infrastructure.**

Not:

* enterprise SaaS
* crypto startup
* generic AI wrapper
* corporate consulting company
* consumer social app
* gaming website

The tone should be:

**quiet confidence.**

Do not use exaggerated marketing language such as:

* "The future of AI"
* "Revolutionary"
* "World-changing"
* "Unleash the power of AI"
* "The ultimate AI platform"

Prefer factual, confident language.

Examples:

> AI infrastructure, built at the edge.

> Tools for building with AI.

> Initialize your token factory.

> Models, endpoints, and configuration in one place.

> Built for developers and agents.

---

# 3. Global Visual Language

## 3.1 Primary appearance

MAGI is **dark-first**.

The default visual environment should use:

* near-black backgrounds
* slightly lighter dark surfaces
* white / near-white typography
* muted gray secondary text
* restrained accent colors

The website should feel closer to a dark product environment than a conventional SaaS dashboard.

---

# 4. Color System

Use semantic design tokens.

Never hard-code colors repeatedly inside individual components.

Recommended foundation:

```css
--magi-bg: #050505;
--magi-bg-elevated: #0a0a0a;
--magi-surface: #111111;
--magi-surface-elevated: #171717;

--magi-text-primary: #f5f5f7;
--magi-text-secondary: #a1a1aa;
--magi-text-tertiary: #71717a;

--magi-border: rgba(255,255,255,0.10);
--magi-border-subtle: rgba(255,255,255,0.06);

--magi-accent: #ffffff;
--magi-accent-muted: #d4d4d8;

--magi-success: #30d158;
--magi-warning: #ff9f0a;
--magi-error: #ff453a;
```

These are starting tokens, not immutable values.

The important principle is:

> **Near-monochrome foundation + restrained semantic colors.**

---

# 5. Accent Colors

MAGI should not use many brand colors simultaneously.

The default MAGI accent is **monochrome / white**.

Individual products may introduce a product accent.

For example:

```text
MAGI
    monochrome

Token Factory Initializr
    blue / cyan accent

API product
    violet / blue accent

Agent product
    green / cyan accent
```

However:

> Product accents must remain subordinate to the MAGI visual system.

A product may have its own identity without looking like it belongs to a completely different company.

Never allow product accents to dominate the entire page.

---

# 6. Typography

Typography is one of the most important parts of the MAGI identity.

Use a modern system / neo-grotesk sans-serif.

Preferred:

```css
font-family:
  Inter,
  -apple-system,
  BlinkMacSystemFont,
  "SF Pro Display",
  "Helvetica Neue",
  Arial,
  sans-serif;
```

For code:

```css
font-family:
  "SFMono-Regular",
  "Cascadia Code",
  "Roboto Mono",
  Menlo,
  monospace;
```

---

## 6.1 Display typography

Hero headlines should be large.

Typical desktop range:

```text
64px – 96px
```

Product hero:

```text
56px – 80px
```

Section heading:

```text
36px – 56px
```

Body:

```text
16px – 20px
```

Small metadata:

```text
12px – 14px
```

Use tight tracking for large headlines.

Example:

```css
letter-spacing: -0.04em;
```

Do not make every text element large.

Large typography should create hierarchy.

---

# 7. Layout

MAGI uses generous whitespace.

Use a centered content container:

```text
max-width: 1200px – 1280px
```

For cinematic hero sections:

```text
max-width: 1400px
```

Typical horizontal padding:

```text
24px mobile
32px tablet
48px desktop
64px+ large desktop
```

Typical section spacing:

```text
96px
128px
160px
200px
```

Large empty areas are intentional.

Do not compress sections simply to fit more information above the fold.

---

# 8. Hero

The hero is the most important visual area.

Recommended structure:

```text
[small eyebrow]

Large headline

Short supporting statement

[Primary CTA] [Secondary CTA]

                    Product / UI / code / visual
```

or:

```text
                LARGE HEADLINE

       concise supporting statement

             [ Primary CTA ]

                  ↓

        product visual / interface
```

Hero copy should be short.

Prefer:

> Personal AI, at the edge.

over:

> MAGI is a revolutionary next-generation AI platform designed to empower developers...

The current MAGI homepage already uses this concise positioning approach:

> "Personal AI, at the edge."

Maintain this level of restraint.

---

# 9. Navigation

Navigation should be extremely quiet.

Desktop:

```text
MAGI        Products   Docs   GitHub        [Get Started]
```

or product site:

```text
MAGI / ProductName       Docs   Models   API   GitHub
```

Characteristics:

* compact
* translucent or near-black
* subtle bottom border
* sticky when appropriate
* minimal number of navigation items

Avoid:

* giant navigation bars
* colorful navigation buttons
* excessive dropdowns
* excessive icons

---

# 10. Glass / Blur

Glassmorphism is allowed but must be restrained.

Use it primarily for:

* navigation
* floating controls
* modal/dialog
* sticky contextual UI
* one important product surface

Example:

```css
background: rgba(10,10,10,0.72);
backdrop-filter: blur(20px);
border: 1px solid rgba(255,255,255,0.08);
```

Do NOT make every card glass.

Avoid the common "AI website" look where every element is:

```text
dark card
+
blur
+
glow
+
gradient border
+
shadow
```

That is explicitly NOT the MAGI aesthetic.

---

# 11. Cards

Cards should be used for information grouping, not decoration.

Preferred:

* flat dark surfaces
* subtle borders
* small radius
* clear hierarchy
* minimal shadow

Avoid excessive rounded cards.

Recommended radius:

```text
6px
8px
12px
16px
```

Use larger radius only for major interactive controls or special product surfaces.

---

# 12. Buttons

Buttons should feel like system controls, not marketing decorations.

Primary:

```text
white background
black text
```

Secondary:

```text
transparent / dark surface
white text
subtle border
```

Example:

```text
[ Get Started ]

[ Learn More ]
```

Use pill-shaped buttons selectively.

Do not make every button a huge capsule.

---

# 13. Borders

Borders should be extremely subtle.

Preferred:

```css
border: 1px solid rgba(255,255,255,0.08);
```

or:

```css
border: 1px solid rgba(255,255,255,0.06);
```

Avoid bright white borders.

The interface should be defined primarily by:

1. typography
2. spacing
3. contrast
4. surface hierarchy

rather than borders.

---

# 14. Shadows and Depth

Depth should be subtle.

Prefer:

* surface contrast
* transparency
* blur
* soft shadows
* lighting

Avoid:

* heavy drop shadows
* neon glow everywhere
* excessive 3D effects

Depth should support hierarchy, not become the visual identity.

---

# 15. Gradients

Gradients are allowed only as **atmospheric accents**.

Good:

```text
very subtle radial glow behind hero
```

Bad:

```text
purple → blue → pink gradient everywhere
```

Never use gradients to compensate for weak hierarchy.

If the page still looks good after removing the gradient, the gradient was optional.

---

# 16. Motion

Motion should feel cinematic but restrained.

Use:

* fade
* opacity
* small vertical translation
* subtle scale
* horizontal movement
* blur-to-sharp transitions

Recommended duration:

```text
150ms – 250ms
```

for interaction.

```text
400ms – 800ms
```

for section reveals.

Avoid:

* excessive bouncing
* spinning objects
* aggressive parallax
* constant animation
* distracting particle effects

The interface should feel alive, not animated for the sake of animation.

---

# 17. Scroll Experience

For marketing pages, scrolling can progressively reveal the product story.

Recommended pattern:

```text
Hero
↓
Problem
↓
Product
↓
Key capabilities
↓
Technical architecture
↓
Use cases
↓
CTA
```

Each section should introduce exactly one new idea.

Scroll animation should reinforce hierarchy.

It must never slow down the user's ability to understand or operate the product.

---

# 18. Developer / Infrastructure UI

MAGI products often involve:

* APIs
* models
* agents
* configuration
* infrastructure
* endpoints
* tokens
* workflows

These should use a slightly more technical visual language.

Use:

* monospace labels
* compact metadata
* code blocks
* terminal-like surfaces
* structured tables
* status indicators
* small uppercase labels
* precise alignment

Example:

```text
MODEL

Qwen3-30B-A3B

CONTEXT
128K

PROVIDER
NVIDIA

STATUS
● AVAILABLE
```

This should feel like a premium developer tool, not a generic SaaS dashboard.

---

# 19. Code and Configuration

Code is a first-class visual element.

Use code to demonstrate real functionality.

Example:

```yaml
model_list:
  - model_name: coding
    litellm_params:
      model: nvidia/...
      api_key: os.environ/NVIDIA_API_KEY
```

Code surfaces should use:

* dark surface
* monospace typography
* subtle syntax colors
* clear padding
* minimal chrome

Avoid making code blocks look like cartoon terminal windows.

---

# 20. Product-Specific Identity

Every `*.magi.website` product must inherit the MAGI Design System.

The inheritance model is:

```text
MAGI Brand
   │
   ├── Typography
   ├── Spacing
   ├── Surface
   ├── Navigation
   ├── Buttons
   ├── Motion
   ├── Layout
   │
   └── Product Theme
          │
          ├── Accent color
          ├── Product icon
          ├── Product-specific visual
          └── Product-specific components
```

The product may customize:

* accent color
* hero visual
* information architecture
* domain-specific components
* terminology

The product must NOT independently redefine:

* typography philosophy
* spacing philosophy
* overall darkness
* border language
* button language
* animation philosophy
* overall visual density

---

# 21. MAGI Brand Header

Every MAGI sub-product should make its relationship with MAGI clear.

Recommended:

```text
MAGI / Token Factory Initializr
```

or:

```text
MAGI
Token Factory Initializr
```

The product name should remain dominant inside the product.

MAGI should act as the parent brand.

---

# 22. Footer

All MAGI sites should share a recognizable footer structure.

Example:

```text
MAGI

Independent AI Lab

Products
    ...

Resources
    Docs
    GitHub

Company
    About
    Contact

© 2026
```

