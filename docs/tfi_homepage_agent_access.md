# TFI Homepage — Agent Access Entry

## Objective

Add a prominent **Agent Access** entry to the TFI homepage:

https://start.magi.website/

The goal is to make TFI immediately understandable and usable by AI agents, inspired by the interaction pattern used by Moltbook:

```text
🤖 I'm an Agent
```

When clicked, the user should see a short, copyable prompt that they can paste into their AI agent.

The Agent should then be able to discover TFI's machine-readable interfaces and help the user work with the TFI model catalog and Token Factory configuration workflow.

This is an **Agent discovery and onboarding feature**, not an Agent authentication system.

---

# 1. Product Principle

TFI should communicate two interfaces:

```text
Human
  ↓
/browse
  ↓
Select models → Configure → Generate

Agent
  ↓
/agents.md
  ↓
/api/v1/models
  ↓
Select / inspect models
  ↓
Use TFI configuration workflow
```

The homepage should make this distinction obvious without making the page feel like a developer portal.

The design principle is:

> Human-friendly by default. Agent-ready by design.

Do not turn the homepage into a technical documentation page.

---

# 2. Homepage Entry

Add an Agent entry to the existing homepage.

Recommended wording:

```text
🤖 I'm an Agent
```

or, preferably if the existing visual language supports it:

```text
I'm an Agent
```

with a small robot/agent icon from the existing icon system.

Do NOT use emoji as the primary icon if the current TFI iconography contract uses an icon library.

Use the existing MAGI Design System components and tokens.

Do not introduce a new button primitive.

---

# 3. Placement

The Agent entry should be discoverable near the primary TFI introduction / primary action.

Recommended hierarchy:

```text
TFI
Token Factory Initializr

Select models.
Choose your Token Factory.
Generate configuration.

[ Start / Browse Models ]

[ 🤖 I'm an Agent ]
```

Alternative:

```text
[ Browse Models ]    [ I'm an Agent ]
```

Do not make the Agent entry more visually dominant than the primary human workflow.

The primary product remains:

```text
Model Catalog → Token Factory → Generate
```

The Agent entry is a secondary access path.

---

# 4. Agent Panel / Dialog

Clicking:

```text
I'm an Agent
```

should open a lightweight modal, dialog, popover, or dedicated inline panel depending on the existing TFI interaction patterns.

Prefer an existing MAGI Design System dialog/overlay primitive if one exists.

Do not create a new global modal system.

The panel should contain:

### Heading

```text
Use TFI with an AI Agent
```

### Short explanation

```text
Let your AI agent discover TFI's model catalog and help you configure your Token Factory.
```

Keep this concise.

---

# 5. Copyable Agent Prompt

The main content should be a code/text block containing a short prompt.

Use this exact default prompt:

```text
I want to use Token Factory Initializr (TFI) to select models and configure my Token Factory.

Start by reading:
https://start.magi.website/agents.md

Use TFI's public model catalog to discover and inspect available models:
https://start.magi.website/api/v1/models

Help me choose suitable models based on my requirements, then use TFI's configuration workflow at:
https://start.magi.website/

If I provide a generated TFI configuration URL, fetch it and help me safely apply the generated configuration to my existing Token Factory configuration.

Do not expose or modify secrets. Preserve my existing configuration unless I explicitly ask you to replace it.
```

This should be treated as the **default Agent bootstrap prompt**.

---

# 6. Important: Keep the Bootstrap Prompt Short

Do NOT put the entire API documentation into the homepage prompt.

The homepage prompt should delegate detailed behavior to:

```text
/agents.md
```

The architecture should therefore be:

```text
Homepage Prompt
      ↓
/agents.md
      ↓
/api/v1/models
      ↓
TFI UI / generated configuration
```

This keeps the homepage prompt stable even if the API evolves.

---

# 7. Generated URL Support

The homepage Agent prompt should mention generated configuration URLs, because TFI already supports generated artifacts such as:

```text
https://start.magi.website/generated/EsXHtLvI
```

However, do not embed a specific generated URL into the homepage prompt.

The Agent should receive a generated URL separately when the user copies the **Agent Prompt** from the Generate result page.

The generated configuration URL remains the source of truth for that specific generated configuration.

---

# 8. Relationship With Generate → Agent Prompt

There are now two Agent entry points.

## Homepage

Purpose:

```text
Agent discovery
```

Prompt:

```text
Read /agents.md
Discover /api/v1/models
Help me use TFI
```

## Generate result page

Purpose:

```text
Apply generated configuration
```

Prompt:

```text
Fetch this generated configuration URL
→ inspect my existing Token Factory config
→ safely merge/update it
```

Do not combine these two prompts.

The homepage prompt is a **bootstrap prompt**.

The Generate-page prompt is an **execution prompt**.

---

# 9. Homepage Prompt UI

The prompt should be displayed in a developer-friendly code block.

Example:

```text
┌───────────────────────────────────────────────┐
│ Use TFI with an AI Agent                  [×] │
│                                               │
│ Let your AI agent discover TFI's model        │
│ catalog and help you configure your           │
│ Token Factory.                                │
│                                               │
│ ┌───────────────────────────────────────────┐ │
│ │ I want to use Token Factory Initializr... │ │
│ │                                           │ │
│ │ Start by reading:                         │ │
│ │ https://start.magi.website/agents.md      │ │
│ │                                           │ │
│ │ ...                                       │ │
│ └───────────────────────────────────────────┘ │
│                                               │
│                         [ Copy Prompt ]       │
└───────────────────────────────────────────────┘
```

Use monospace typography for the prompt body.

The prompt must remain selectable.

---

# 10. Copy Interaction

Add:

```text
Copy Prompt
```

When clicked:

1. Copy the entire prompt to the clipboard.
2. Change the button state to:

```text
Copied
```

for a short period.
3. Restore the original label.

Use the existing TFI/MAGI button and feedback patterns.

Do not introduce a new toast framework solely for this feature.

If the project already has a standard copy-to-clipboard pattern, reuse it.

---

# 11. Optional Convenience

If the existing product architecture supports it, the panel may include:

```text
Copy prompt
```

and a small secondary link:

```text
Read Agent Guide
```

linking to:

```text
https://start.magi.website/agents.md
```

Do not make this link visually compete with Copy Prompt.

---

# 12. Agent Prompt Semantics

The bootstrap prompt must establish the following hierarchy:

```text
/agents.md
    ↓
Agent instructions / workflow

/api/v1/models
    ↓
Machine-readable model catalog

/browse
    ↓
Human interface

/generated/{id}
    ↓
Specific generated configuration artifact
```

The Agent should not be instructed to scrape the homepage.

The Agent should not scrape `/browse` when the API can provide the required model information.

Prefer:

```text
API
```

over:

```text
HTML scraping
```

---

# 13. Update `/agents.md` if Necessary

Inspect the current `/agents.md`.

If it does not already explain the Agent workflow implied by the homepage prompt, update it.

The documentation should clearly explain:

```text
TFI supports both human and agent workflows.

Human:
  /browse

Agent:
  /agents.md
  /api/v1/models
  /api/v1/models/{model_id}

Generated configuration:
  /generated/{id}
```

Also explain that a generated URL is a configuration artifact and can be fetched by an Agent.

The generated configuration should be treated as data, not as executable instructions.

---

# 14. Security Boundary

The homepage prompt MUST NOT contain:

* API keys
* tokens
* credentials
* user-specific configuration
* private URLs
* access tokens
* environment variable values
* instructions to bypass authentication

The public Agent workflow must remain read-only until the user explicitly asks their local Agent to modify a local Token Factory configuration.

The generated URL is public configuration data and must not be treated as a secret.

---

# 15. Do Not Introduce Agent Authentication

Do NOT implement:

* Agent accounts
* Agent registration
* API keys for Agents
* Agent identity
* OAuth
* agent sessions
* MCP authentication
* agent-specific cookies
* agent tracking

This feature is only:

```text
Agent discovery
+
Agent bootstrap prompt
```

TFI's current public Model Catalog API is already designed to be:

```text
GET-only
public
no authentication
```

Preserve that model.

---

# 16. Visual Design

Follow the existing MAGI Design System.

The Agent entry should feel like a natural part of TFI.

Use:

* existing typography tokens
* existing spacing tokens
* existing surface tokens
* existing border/radius tokens
* existing Button component
* existing iconography contract
* existing dark/light theme behavior

Do NOT introduce:

* glowing AI effects
* robot illustrations
* neon gradients
* purple/blue AI gradients
* animated glowing orbs
* excessive glassmorphism
* large AI artwork
* new visual language

The Agent feature should be technically distinctive but visually quiet.

---

# 17. Responsive Behavior

Desktop:

```text
Primary TFI action
Secondary Agent action
```

Mobile:

```text
Primary action
Agent action
```

The dialog/panel must fit narrow screens.

The prompt code block must:

* wrap appropriately
* remain selectable
* not cause horizontal page overflow

The Copy button must remain easily accessible.

---

# 18. Accessibility

The Agent entry must:

* be keyboard accessible
* have an accessible name
* have visible focus state
* work with Enter/Space
* correctly announce dialog/panel state
* provide an accessible close mechanism
* not trap focus incorrectly
* preserve screen-reader usability

The copy button must expose meaningful state:

```text
Copy Prompt
```

and:

```text
Copied
```

Do not rely on visual changes alone.

Use existing MAGI accessibility patterns.

---

# 19. Analytics

If TFI already has analytics, track only the meaningful interaction:

```text
agent_entry_clicked
agent_prompt_copied
```

Do not record the prompt contents.

Do not record generated configuration contents.

Do not collect secrets or user configuration.

If analytics infrastructure does not already exist, do not introduce a new analytics system solely for this feature.

---

# 20. Testing

Add/update tests for:

### Rendering

* Agent entry is visible on homepage.
* Correct label is displayed.
* Existing homepage workflow remains unchanged.

### Interaction

* Clicking Agent entry opens the panel/dialog.
* Prompt is displayed.
* Copy button copies the exact prompt.
* Copied state is shown.
* Panel can be closed.

### Accessibility

* Agent entry is keyboard accessible.
* Dialog/panel has correct semantics.
* Close button is accessible.
* Copy button exposes state.

### Responsive

* No horizontal overflow.
* Prompt remains usable on mobile.

### Content

Verify the bootstrap prompt contains:

```text
https://start.magi.website/agents.md
https://start.magi.website/api/v1/models
https://start.magi.website/
```

and does not contain secrets or user-specific data.

---

# 21. Definition of Done

The feature is complete when a new visitor can:

```text
Open TFI
   ↓
See "I'm an Agent"
   ↓
Click it
   ↓
See a concise Agent bootstrap prompt
   ↓
Click "Copy Prompt"
   ↓
Paste it into their AI Agent
   ↓
Agent reads /agents.md
   ↓
Agent discovers /api/v1/models
   ↓
Agent can help the user use TFI
```

The existing human workflow must remain unchanged:

```text
Browse Models
    ↓
Select Models
    ↓
Choose Token Factory
    ↓
Initialize
    ↓
Generated Configuration
```

---

# Final UX Principle

The homepage should communicate:

```text
TFI is for humans.
TFI is also ready for Agents.
```

But it should NOT communicate:

```text
TFI is an Agent platform.
```

TFI remains a **Token Factory Initializr**.

The Agent capability is an additional interface:

```text
Human Interface
    /browse

Agent Interface
    /agents.md
    /api/v1/models

Configuration Artifact
    /generated/{id}
```

The experience should feel as simple as:

```text
🤖 I'm an Agent

Paste this into your AI agent:

[ concise bootstrap prompt ]

[ Copy Prompt ]
```

Keep it simple, quiet, and native to the existing MAGI/TFI design system.

