你现在负责对 Token Factory Initializr 执行一次完整的 MAGI Design System Compliance Audit。

## 项目

Product：

`Token Factory Initializr`

Canonical site：

`https://start.magi.website`

Design System：

`@tokyo3rdhq/magi-design-system`

Design System repository：

`https://github.com/tokyo3rdhq/magi-design-system`

---

# 1. Audit 目标

本次 Audit 的目标不是评价 Token Factory Initializr 的产品设计是否“好”。

而是回答：

> Token Factory Initializr 是否正确使用 MAGI Design System，并且是否保持了合理的 Product / Design System Boundary？

核心关系：

```text id="q3n1jk"
MAGI Design System
        │
        │ visual language
        │ tokens
        │ brand
        │ common primitives
        │ accessibility
        │ experience guidelines
        ▼
Token Factory Initializr
        │
        │ product experience
        │
        ├── model selection
        ├── model filtering
        ├── requirement input
        ├── intent recognition
        ├── recommendation
        ├── configuration
        ├── config preview
        ├── copy
        ├── download
        └── generated output
```

必须遵循：

> MAGI owns visual and interaction language.
> Token Factory Initializr owns product experience.

因此：

**不要要求所有产品组件都进入 Design System。**

---

# 2. Audit 前置要求

首先读取当前 Design System。

必须以当前 repository / installed package 为准。

阅读：

* README.md
* packages/design-system/README.md
* docs/brand.md
* docs/guidelines.md
* docs/component-contracts.md
* docs/architecture-review-framework-agnostic.md
* docs/ADR/*
* CHANGELOG.md

以及实际源码：

* src/tokens
* src/foundation
* src/brand
* src/components
* src/layout
* src/theme
* src/index.ts

不要使用旧版本 Design System 的记忆。

---

# 3. Audit Scope

完整扫描 Token Factory Initializr。

包括：

* package.json
* lockfile
* src/**
* app/**
* components/**
* pages/**
* routes/**
* styles/**
* public/**
* tests/**
* configuration
* build configuration
* deployment configuration

不要假设目录结构。

以实际代码为准。

---

# 4. 建立 Product Architecture Map

首先识别 Token Factory Initializr 当前产品结构。

至少尝试识别：

```text id="j10j1f"
Token Factory Initializr
│
├── App Shell
│   ├── Header
│   ├── Navigation
│   └── Footer
│
├── Model Discovery
│   ├── Model List
│   ├── Model Filter
│   ├── Search
│   └── Model Detail
│
├── Requirement / Intent
│   ├── Requirement Input
│   ├── Intent Input
│   └── Recommendation
│
├── Selection
│   ├── Selected Models
│   └── Selection Summary
│
├── Configuration
│   ├── Target Format
│   ├── Config Preview
│   └── Generated Config
│
└── Output
    ├── Copy
    ├── Download
    └── Generated URL
```

以上只是审计分类示例。

如果当前项目结构不同：

**以实际代码为准。**

---

# 5. Product vs Design System Boundary

这是本次 Audit 最重要的部分。

为每一个 UI component 分类：

```text id="t3g2rj"
Design System Primitive
Product Component
Product Feature
Page Composition
```

例如：

### Design System

合理候选：

* Button
* Card
* Badge
* Input
* Checkbox
* FormField
* Segmented
* Banner
* EmptyState
* Container
* Section
* Stack

### Token Factory Product

合理候选：

* ModelCard
* ModelSelector
* ModelFilter
* ProviderFilter
* CapabilityFilter
* SelectedModelList
* RequirementInput
* IntentInput
* RecommendationPanel
* ConfigPreview
* ConfigOutput
* GeneratedUrl
* ModelMetadata

不要因为这些组件内部使用 Button/Card，就认为它们应该进入 Design System。

---

# 6. Dependency Audit

确认 Token Factory Initializr 是否正确依赖：

```text id="p6r1vz"
@tokyo3rdhq/magi-design-system
```

检查：

* package.json
* lockfile
* import paths
* version
* duplicate installation
* local copy
* vendored components

特别检查是否存在：

```text id="h1p8cu"
packages/design-system
components/ui
components/common
src/components/ui
```

中与 MAGI Design System 重复的 primitive。

---

# 7. Design System Component Reuse Audit

扫描项目中的：

```tsx
<button>
<input>
<label>
<textarea>
<select>
```

以及：

```text id="l5n9ac"
Button
Card
Badge
Input
Checkbox
FormField
Segmented
Banner
EmptyState
```

判断：

### 正确

```tsx id="j3h42q"
import { Button } from '@tokyo3rdhq/magi-design-system'
```

### 可能重复

```tsx id="a5z6m1"
<button className="primary-button">
```

但不要机械判定为 violation。

判断：

```text id="f8v1t7"
Is this:
    │
    ├── common primitive?
    │       ↓
    │   Design System
    │
    └── product-specific behavior?
            ↓
        Product Component
```

---

# 8. Token Compliance Audit

这是重点。

扫描 Token Factory Initializr 中所有：

### Color

搜索：

```text id="e7g4j0"
#000
#000000
#fff
#ffffff
rgb(
rgba(
hsl(
hsla(
```

以及：

```text id="6v5n2z"
black
white
gray
neutral
zinc
slate
```

判断是否应该使用 MAGI semantic token。

重点检查：

```text id="l8f3a2"
background
surface
text
border
accent
success
warning
error
selection
```

---

# 9. Model UI 特别检查

Token Factory Initializr 的核心 UI 是 Model Selection。

因此重点检查：

```text id="s9x7m4"
ModelCard
ModelRow
ModelBadge
ProviderBadge
CapabilityBadge
SelectedModel
ModelFilter
```

检查它们是否自行定义：

* background
* border
* text
* radius
* spacing
* hover
* selected state
* focus state

例如：

```css id="r1q4vc"
.model-card {
  background: #111;
  border: 1px solid #333;
  border-radius: 12px;
}
```

不要立即判定错误。

需要判断：

> 这些视觉属性是否应该绑定 MAGI semantic tokens？

同时检查：

> Model-specific information 是否错误地被表达成 MAGI product accent？

---

# 10. Model Selection State Audit

这是 Token Factory 特别重要的部分。

检查：

```text id="c7m2pv"
default
hover
focus
selected
disabled
loading
error
unavailable
```

特别关注：

### Selected Model

是否有明确的 selected state。

### Focus

键盘用户是否能明确知道当前 focus。

### Disabled

是否同时满足：

* visual
* semantic
* keyboard

### Multiple selection

如果支持：

* checkbox semantics
* selected state
* keyboard
* screen reader

必须符合 Component Contract。

---

# 11. Form Audit

重点审计：

* requirement input
* intent input
* search
* filters
* configuration fields

检查：

```text id="j6q2v1"
label
description
placeholder
error
help text
disabled
required
```

尤其检查：

```text id="u2w5hf"
aria-describedby
aria-labelledby
aria-invalid
```

不要为了视觉而牺牲 semantic form structure。

---

# 12. FormField Compliance

如果 Token Factory Initializr 自己实现了：

```text id="m8v4b3"
FormField
Field
FieldLabel
FieldDescription
FieldError
```

必须与 MAGI Design System 的 FormField contract 对比。

重点：

* id propagation
* label association
* description association
* error association
* aria-describedby merge
* aria-invalid
* required

如果 Design System 已经提供 FormField：

优先复用。

如果产品需要特殊行为：

允许创建 Product-level wrapper。

---

# 13. Intent / Requirement Input Audit

Token Factory Initializr 后续产品方向包括：

```text id="y6x8qp"
Requirement
    ↓
Intent Recognition
    ↓
Model Recommendation
    ↓
Selection
    ↓
Config
```

不要把业务逻辑塞进 Design System。

检查：

### Design System owns

* Input visual language
* focus
* error
* typography
* spacing
* accessibility

### Product owns

* intent parser
* requirement schema
* recommendation logic
* model ranking
* model selection behavior

如果发现：

```text id="r3h7wn"
Design System component
        +
business logic
```

标记为：

`BOUNDARY_VIOLATION`

---

# 14. Recommendation UI Audit

如果当前已经存在 Model Recommendation：

检查：

* recommendation card
* recommendation reason
* selected state
* confidence / score
* capability labels
* explanation
* action

不要把 recommendation UI 强行当成 Design System component。

应该检查：

> Product component 是否正确使用 Design System primitives？

---

# 15. Config Preview Audit

Config Preview 是 Token Factory 的核心 product-specific UI。

允许拥有自己的：

* code block
* syntax highlighting
* model configuration visualization
* copy action
* download action

但是：

### Surrounding UI

应该使用 MAGI Design System：

* Card
* Button
* Badge
* typography
* spacing
* surface
* border

### Code content

可以拥有自己的：

* syntax colors
* monospace typography

但必须明确这是：

`PRODUCT-SPECIFIC CODE PRESENTATION`

不要将 syntax highlighting token 混入 MAGI global semantic tokens。

---

# 16. Copy / Download / Generated URL Audit

检查：

* Copy
* Download
* Open Generated URL
* Copy Agent Prompt

这些属于 product action。

检查它们是否使用 Design System Button / Link contract。

特别检查：

### Success

复制成功后：

* visual feedback
* accessible feedback

### Error

复制失败：

* error feedback

### External URL

如果 generated URL 是外部导航：

检查是否符合 External Links guideline。

---

# 17. Theme Audit

检查 Token Factory Initializr：

```text id="x4v9sd"
Dark
Light
```

如果只支持 Dark：

也必须确认：

> 是否正确继承 MAGI Design System dark theme，而不是自行创建 dark token system。

如果支持 Light：

检查：

```text id="p3f1zq"
AppTheme
data-magi-theme
```

以及所有 product-specific components：

* ModelCard
* ModelList
* ConfigPreview
* RecommendationPanel
* Filter
* Form

是否正确适配。

---

# 18. Accent Audit

检查 Token Factory 是否使用：

```text id="q2x7mh"
data-magi-accent
```

或者 AppTheme accent。

判断 accent 的用途：

### 合理

* CTA
* selected action
* active state
* progress
* product highlight

### 不合理

用 accent 表示：

* provider identity
* model family identity
* capability identity

例如：

```text id="e5y8vb"
OpenAI = green
Google = blue
Anthropic = purple
```

这种属于 Product data visualization / provider identity。

不要把它们错误建模为 MAGI accent。

---

# 19. Provider / Model Identity Audit

Token Factory 有明显的数据型 UI。

检查：

* NVIDIA
* Hugging Face
* AMD
* OpenRouter
* provider badges
* model family badges

如果使用品牌颜色：

不要直接判断为 violation。

需要分类：

```text id="r8c3jw"
MAGI Accent
      ≠
Provider Identity
      ≠
Model Capability Color
```

这是 Token Factory 与主站最大的区别之一。

---

# 20. Typography Audit

检查：

* heading
* body
* label
* metadata
* model id
* provider
* code
* config preview

特别检查：

### Model ID

例如：

```text
nvidia/gpt-oss-120b
```

是否使用适当的 monospace。

### Config

是否使用 monospace。

### Product copy

是否继续使用 MAGI typography。

不要把整个网站变成 monospace / terminal UI。

---

# 21. Spacing Audit

重点检查：

```text id="v6h2ra"
ModelCard
ModelList
FilterPanel
ConfigPanel
```

是否形成自己的 spacing system。

例如：

```css id="b4w7ky"
gap: 13px;
padding: 19px;
margin: 27px;
```

如果这些值只是历史调参：

标记：

`TOKEN_DRIFT`

如果是为了 product-specific dense data layout：

可以保留，但必须说明理由。

---

# 22. Radius / Surface Audit

重点检查：

* model cards
* selection cards
* config card
* filter panel
* dialogs
* badges
* inputs

确认是否形成：

```text id="t9k5hc"
MAGI surface language
```

而不是：

```text id="q8r4ds"
每个组件一个 radius
每个组件一个 shadow
每个组件一个 background
```

---

# 23. Experience Guidelines Audit

阅读：

`docs/guidelines.md`

逐项检查。

---

## Navigation

检查：

* Home
* Models
* Configuration
* Docs
* GitHub
* generated output

是否有清晰的信息架构。

但不要用 Design System 代替 Product IA。

---

## External links

检查：

* GitHub
* Documentation
* Model source
* Provider website
* Generated URL

是否使用合理的：

* text
* icon + text
* external indicator

---

## Icon-only

不要将：

* GitHub
* Docs
* Models
* API
* Provider

默认做成 icon-only。

---

# 24. i18n Audit

如果 Token Factory 支持多语言：

检查：

* language selector
* language names
* html lang
* translated labels
* model metadata
* provider names

不要使用国旗作为语言选择器。

同时注意：

> Model ID / provider name / technical identifier 不应该被翻译。

---

# 25. Accessibility Audit

重点检查 Token Factory 的复杂交互。

至少检查：

### Keyboard

* Tab
* Shift+Tab
* Enter
* Space
* Arrow keys

### Model Selection

* checkbox
* selection
* focus
* keyboard

### Filter

* checkbox
* segmented
* search

### Forms

* labels
* error
* description

### Output

* copy success
* copy failure
* generated URL

---

# 26. Responsive Audit

至少检查：

```text id="r5t7wm"
390px
768px
1280px
1440px
```

重点：

### Desktop

```text
Model list | Configuration
```

如果存在类似布局：

检查是否合理。

### Mobile

不能简单缩放 desktop。

检查：

* filters
* model list
* selection
* config preview
* CTA

是否重新组合。

---

# 27. Dense Data UI Audit

Token Factory 与 `magi.website` 最大区别之一是：

> 它是一个 developer tool / configuration tool。

因此允许比 MAGI 主站更 dense。

不要简单执行：

> MAGI 应该 minimal，所以所有 UI 都应该 spacious。

应该判断：

```text id="j7s2fz"
Density
   │
   ├── readable
   ├── scannable
   ├── technically precise
   └── consistent with MAGI
```

允许：

* compact model rows
* metadata
* badges
* code blocks
* dense tables

但禁止形成另一套视觉语言。

---

# 28. Product-specific CSS Boundary

扫描：

```text id="n1b7kq"
:root
--background
--foreground
--primary
--secondary
--card
--border
--radius
```

如果发现大量 product-level tokens：

分类：

### A

Duplicate MAGI token

→ 应迁移。

### B

Semantic product token

例如：

```text
--model-selected
--config-preview-height
--provider-label
```

→ 合理。

### C

Component implementation token

→ 可以保留。

### D

Legacy token

→ 建议清理。

---

# 29. Design System Override Audit

搜索：

```text id="j5r8xw"
!important
```

以及：

```text id="q6v2pn"
[data-*]
.magi-*
```

检查 Token Factory 是否通过高 specificity 强行覆盖 Design System。

重点关注：

* Button
* Input
* Card
* FormField
* Badge

如果大量 override：

标记：

`DESIGN_SYSTEM_OVERRIDE_DRIFT`

---

# 30. Product Component Extraction Audit

反向检查：

> Token Factory 是否存在值得未来进入 MAGI Design System 的 component contract？

但是本次不要修改 Design System。

寻找：

* repeated semantic component
* repeated state model
* repeated accessibility contract

例如：

```text id="k2h6vf"
ModelCard
```

如果未来 `models.magi.website` 也需要相同组件：

记录：

`CANDIDATE_FOR_SHARED_PRODUCT_COMPONENT`

但不要立即抽取。

---

# 31. Browser Audit

如果项目可以本地启动：

必须实际运行。

至少检查：

```text id="p4c7yn"
Desktop 1440
Desktop 1280
Mobile 390
```

以及：

* Dark
* Light（如果支持）

至少访问：

1. Home
2. Model selection
3. Filtering
4. Selection
5. Configuration
6. Config preview
7. Copy
8. Generated output

---

# 32. Browser State Audit

特别测试：

```text id="w6x1sa"
Initial
Loading
Loaded
Selected
Deselected
Error
Empty
Disabled
Generated
Copied
```

因为 Token Factory 是 workflow application。

不要只检查静态首页。

---

# 33. Visual Compliance

检查：

### MAGI visual language

* dark-first
* near-monochrome
* restrained accent
* precise typography
* controlled surfaces
* minimal decoration

### 避免

* generic AI gradients
* glowing orbs
* excessive neon
* excessive glassmorphism
* random gradients
* unrelated visual metaphors

但不要机械禁止 product-specific visualization。

---

# 34. Final Classification

每个 finding 只能属于：

### P0 — Design System Contract Violation

例如：

* incorrect brand
* duplicated theme system
* broken accessibility contract
* Design System component semantic break
* global token conflict

### P1 — Strong Compliance Issue

例如：

* duplicated primitive
* token drift
* typography drift
* inconsistent component states
* major responsive inconsistency

### P2 — Improvement

例如：

* minor spacing drift
* local styling inconsistency
* unnecessary override

### INFO

合理的 Product-owned implementation。

---

# 35. 不允许的行为

这是 Audit。

**不要修改任何代码。**

不要：

* refactor
* install dependencies
* change UI
* change product UX
* change product IA
* add Design System components
* modify Design System
* migrate components

只进行：

> Inspect → Compare → Classify → Report

---

# 36. 最终报告

最终输出：

## 1. Executive Summary

回答：

> Token Factory Initializr 是否符合 MAGI Design System？

使用：

```text
COMPLIANT
MOSTLY COMPLIANT
PARTIALLY COMPLIANT
NON-COMPLIANT
```

不要给简单的数字评分。

---

## 2. Product / Design System Boundary

输出：

| Area                     | Owner   | Current Implementation | Status |
| ------------------------ | ------- | ---------------------- | ------ |
| Brand                    | MAGI DS |                        |        |
| Theme                    | MAGI DS |                        |        |
| Typography               | MAGI DS |                        |        |
| Model selection          | Product |                        |        |
| Recommendation           | Product |                        |        |
| Config generation        | Product |                        |        |
| Code preview             | Product |                        |        |
| Accessibility primitives | Shared  |                        |        |

---

## 3. Findings

| ID | Severity | Area | File | Finding | Contract | Recommendation |
| -- | -------- | ---- | ---- | ------- | -------- | -------------- |

---

## 4. Token Drift

分别列出：

* Color
* Typography
* Spacing
* Radius
* Surface
* Motion

---

## 5. Component Reuse

分类：

```text id="x2m8dz"
Correctly reused
Duplicated primitive
Product component
Candidate for future shared component
```

---

## 6. Product-specific UI

明确列出哪些 UI：

> 不应该进入 MAGI Design System。

例如：

* ModelCard
* ModelFilter
* RecommendationPanel
* ConfigPreview
* GeneratedConfig

具体以代码实际情况为准。

---

## 7. Accessibility

列出：

* keyboard
* focus
* form
* selection
* error
* loading
* empty
* output

---

## 8. Theme

列出：

* Dark
* Light
* Accent
* Logo
* Surface
* Product-specific states

---

## 9. Responsive

列出：

* Mobile
* Tablet
* Desktop

---

# 37. 最终 Migration Backlog

最后生成：

```text id="j6z0wf"
P0
├── ...
└── ...

P1
├── ...
└── ...

P2
├── ...
└── ...

INFO
├── Product-owned
├── Product-owned
└── Future Design System candidate
```

每个 P0/P1 必须包含：

```text id="w8h3qx"
Problem
Why it matters
Affected files
Relevant Design System contract
Recommended solution
Risk
Scope
```

---

# 38. 最重要的判断原则

整个 Audit 必须遵循：

> MAGI Design System owns the visual language.
>
> Token Factory Initializr owns the product experience.

特别注意：

Token Factory 是一个 developer-oriented configuration product。

因此：

**dense UI、model metadata、filters、code preview、technical identifiers、provider metadata 都可以存在。**

不要因为它们与 MAGI 主站不同，就认为它们违反 Design System。

真正需要判断的是：

```text id="z6m2qk"
Product-specific information
          │
          ▼
Product-owned UI
          │
          ▼
MAGI Design System primitives
          │
          ▼
MAGI visual language
```

最终目标：

> Token Factory Initializr 应该一眼看起来属于 MAGI ecosystem，但不应该看起来像一个被 MAGI Design System 限制住的通用组件 Demo。

Audit 完成后停止。

不要修改任何文件。

