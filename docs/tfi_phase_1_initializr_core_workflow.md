# TFI Phase 1 — Initializr Core Workflow

## Objective

Implement the first complete end-to-end user workflow of Token Factory Initializr (TFI).

The first phase should intentionally behave like a developer-oriented Initializr:

> **Browse Models → Select Candidate Models → Select Token Factory → Generate Configuration**

The primary goal is NOT recommendation, natural-language intent recognition, model scoring, or advanced configuration.

The primary goal is:

> A user should be able to enter TFI, select the models they want, choose the Token Factory implementation they use, and receive a valid configuration that can be copied and used.

The current supported Token Factory implementations should be modeled as extensible providers, initially:

* LiteLLM
* NewAPI

Do not hard-code the workflow around LiteLLM.

---

# 1. Product Mental Model

TFI is an Initializr for Token Factory configurations.

The user should think:

```text
I need some models
        ↓
I select the models I want
        ↓
I tell TFI what Token Factory I use
        ↓
TFI generates the configuration
        ↓
I copy/use the configuration
```

This is the fundamental product loop.

Do NOT introduce unnecessary concepts into this first phase.

In particular, do not make these required for the MVP:

* natural-language intent
* model recommendation
* model ranking
* scoring
* model comparison
* AI-generated recommendations
* account/login
* persistent projects
* generated configuration URLs
* A2A protocol
* agent integration

Those can be added later.

---

# 2. Required User Journey

The complete journey should be:

```text
┌──────────────────────┐
│  Model Catalog       │
│                      │
│  Search / Filter     │
│  Provider            │
│  Capability          │
│                      │
│  ○ model A           │
│  ○ model B           │
│  ○ model C           │
└──────────┬───────────┘
           │
           │ select
           ▼
┌──────────────────────┐
│ Candidate Models     │
│                      │
│ ✓ model A            │
│ ✓ model C            │
│                      │
│ 2 models selected    │
└──────────┬───────────┘
           │
           │ choose
           ▼
┌──────────────────────┐
│ Token Factory        │
│                      │
│ ○ LiteLLM            │
│ ○ NewAPI             │
└──────────┬───────────┘
           │
           │ generate
           ▼
┌──────────────────────┐
│ Configuration        │
│                      │
│ generated config     │
│                      │
│ [Copy] [Download]    │
└──────────────────────┘
```

The exact visual layout can remain consistent with the existing TFI design.

The important requirement is that the state transition is complete and functional.

---

# 3. Define the Core Domain Model

Do not let React component state become the domain model.

Introduce an explicit application state representing the Initializr session.

Conceptually:

```ts
type InitializrState = {
  selectedModels: SelectedModel[];
  tokenFactory: TokenFactoryId | null;
};
```

A selected model should contain the normalized information required for configuration generation.

For example:

```ts
type SelectedModel = {
  modelId: string;
  provider: string;
  dataSource: string;
  ...
};
```

Use the existing normalized model schema where possible.

Do NOT create a second incompatible model representation inside the UI.

---

# 4. Token Factory Abstraction

Introduce an explicit Token Factory abstraction.

Conceptually:

```ts
type TokenFactoryId =
  | "litellm"
  | "newapi";
```

Then define a configuration generator contract.

For example:

```ts
interface TokenFactoryGenerator {
  id: TokenFactoryId;

  name: string;

  generate(
    models: SelectedModel[],
    context: GenerationContext
  ): GeneratedConfig;
}
```

The exact interface may differ according to the existing architecture, but the important property is:

> Model selection must be independent from Token Factory implementation.

The architecture should allow:

```text
Selected Models
      │
      ├── LiteLLM Generator
      │
      ├── NewAPI Generator
      │
      └── Future Generator
```

rather than:

```text
Selected Models
      │
      └── LiteLLM-specific logic
```

---

# 5. Model Catalog

The existing model list should become the source from which users select candidate models.

The model catalog should support at least:

* display model name
* model ID
* provider
* data source
* relevant capabilities if already available
* selection state

Existing filtering functionality should continue to work.

At minimum the user should be able to:

1. inspect models
2. select a model
3. unselect a model
4. see which models are currently selected

Do not redesign the model catalog unless necessary.

---

# 6. Candidate Model Selection

The selected models are the user's explicit candidates.

Use terminology consistently:

> **Candidate Models**

or

> **Selected Models**

Do not call them "recommended models" because TFI has not performed recommendation yet.

The system must maintain a single source of truth for selection.

For example:

```text
Model Catalog
      │
      │ select
      ▼
selectedModels
      │
      ├── Model A
      ├── Model C
      └── Model F
```

The same selection state should drive:

* selected count
* selected model list
* remove action
* Token Factory generation

Avoid maintaining separate duplicated arrays such as:

```ts
checkedModels
selectedModels
candidateModels
```

unless there is a clearly defined reason.

Prefer one canonical selection state.

---

# 7. Selection UX

The user must always understand:

* which models are selected
* how many models are selected
* how to remove a model
* what will be generated

Recommended interaction:

```text
Selected models: 3

✓ gpt-oss-120b
✓ qwen3-32b
✓ kimi-k3

[Remove]
```

The selection UI can be a sidebar, drawer, sticky summary, bottom bar, or dedicated section depending on the current TFI design.

Do not force a specific layout if the existing UI already has a good model selection structure.

The requirement is behavioral, not visual.

---

# 8. Token Factory Selection

After the user has selected candidate models, they must be able to select the target Token Factory.

Initial options:

```text
LiteLLM
NewAPI
```

Represent these as actual product capabilities rather than arbitrary UI strings.

For example:

```ts
const tokenFactories = [
  {
    id: "litellm",
    name: "LiteLLM",
    ...
  },
  {
    id: "newapi",
    name: "NewAPI",
    ...
  }
];
```

The Token Factory selection should be part of the Initializr state:

```ts
{
  selectedModels: [...],
  tokenFactory: "litellm"
}
```

Do not infer the Token Factory from the selected models.

---

# 9. Generation Preconditions

Generation must have explicit validation.

The minimum requirements are:

```text
selectedModels.length > 0
AND
tokenFactory !== null
```

If no model is selected:

```text
Generation is unavailable
```

If no Token Factory is selected:

```text
Choose a Token Factory
```

Do not allow the UI to silently generate an empty or invalid configuration.

Validation should exist at the domain/action level rather than only being expressed through disabled buttons.

---

# 10. Generation Flow

When the user clicks:

```text
Generate Configuration
```

the application should:

```text
InitializrState
      ↓
Validate
      ↓
Resolve Token Factory Generator
      ↓
Transform Selected Models
      ↓
Generate Configuration
      ↓
Display Generated Artifact
```

Conceptually:

```ts
const result = generateConfig({
  models: selectedModels,
  tokenFactory,
});
```

The result should be an explicit generated artifact:

```ts
type GeneratedConfig = {
  format: string;
  content: string;
  filename?: string;
};
```

The exact schema can evolve later.

---

# 11. LiteLLM Generator

LiteLLM should be the first fully working generator.

The generator should transform the normalized selected model data into the existing TFI LiteLLM model-list format.

For example, conceptually:

```yaml
model_list:
  - model_name: ...
    litellm_params:
      model: ...
      api_base: ...
```

Do NOT blindly invent fields.

Use the existing model/provider metadata available in TFI and the existing LiteLLM output contract.

If the current data model does not contain enough information to produce a correct LiteLLM configuration, identify the missing fields explicitly rather than silently generating fake values.

The generator must be deterministic:

```text
same selected models
+
same Token Factory
=
same generated configuration
```

---

# 12. NewAPI Generator

Implement NewAPI through the same generator abstraction.

Do not copy LiteLLM generation code and modify strings.

Instead:

```text
TokenFactoryGenerator
├── LiteLLMGenerator
└── NewAPIGenerator
```

Each implementation owns its own output format.

If the current TFI repository does not yet contain enough information to correctly define the NewAPI output schema, do NOT invent an incompatible schema.

Instead:

1. establish the generator interface
2. establish the NewAPI adapter boundary
3. implement the known supported configuration format
4. clearly isolate any remaining format-specific work

The architecture must nevertheless allow the UI flow to select NewAPI.

---

# 13. Configuration Preview

After generation, show the generated configuration as a developer-oriented artifact.

The preview should support:

* syntax-highlighted code/config
* copy
* download if already supported
* clear indication of Token Factory
* clear indication of selected model count

Example:

```text
LiteLLM configuration

3 models

┌──────────────────────────────────────┐
│ model_list:                          │
│   - model_name: ...                  │
│     litellm_params:                  │
│       ...                            │
│                                      │
└──────────────────────────────────────┘

[Copy Configuration]
```

The generated configuration should be the primary output of the Initializr.

Do not bury it behind unnecessary UI.

---

# 14. Copy Must Copy the Generated Artifact

The Copy action must copy the exact generated configuration content.

It should not copy:

* UI labels
* Markdown wrappers
* explanatory text
* code fences

unless the generated artifact itself intentionally contains them.

Use the raw configuration as the clipboard payload.

After copying, provide a clear success state:

```text
Copied
```

and then return to the normal state.

---

# 15. Download

If download already exists, make sure it downloads the same generated artifact.

For example:

```text
GeneratedConfig.content
        ↓
download
        ↓
appropriate filename
```

Do not maintain a second independently generated version for download.

Copy and download must consume the same generated artifact.

---

# 16. URL / Persistence Is Not Required Yet

Do NOT make generated URLs part of Phase 1 unless the current implementation already supports them cleanly.

The first milestone is:

```text
select
→ choose Token Factory
→ generate
→ copy
```

Only after this loop is stable should TFI introduce:

```text
/generate/<id>
```

or another shareable generated configuration URL.

---

# 17. URL Query / Browser State

Do not require login or server-side persistence for the first implementation.

The Initializr state can initially live in client state.

However, structure the state so that URL persistence can be added later:

```text
Current
UI state
  ↓
InitializrState

Future
URL / persisted project
  ↓
InitializrState
```

This keeps Phase 1 simple without creating a dead-end architecture.

---

# 18. Navigation / Page Structure

The user should be able to understand the workflow without reading documentation.

The page should communicate the progression:

```text
1. Select Models
2. Choose Token Factory
3. Generate Configuration
```

This does not necessarily mean implementing a traditional multi-page wizard.

A single-page Initializr experience is acceptable and may be preferable.

The important thing is that the conceptual progression is obvious.

Avoid turning this into a complex stepper if the current design does not need one.

---

# 19. Empty State

When no models are selected:

```text
No models selected
Select models from the catalog to continue.
```

The UI should make the next action obvious.

Do not show an empty configuration preview as if generation succeeded.

---

# 20. Error Handling

Generation errors must be visible and actionable.

Examples:

```text
Unable to generate LiteLLM configuration.

The selected model is missing required provider information.
```

Do not silently:

* drop models
* generate partial configs
* replace missing values with fake values
* substitute another provider
* pretend generation succeeded

For a first implementation, correctness is more important than graceful degradation.

---

# 21. Architecture Boundary

Keep these responsibilities separate:

```text
Model Catalog
    ↓
Selection State
    ↓
Initializr State
    ↓
Token Factory Generator
    ↓
Generated Artifact
    ↓
Presentation
```

Specifically:

### Model Catalog owns

* displaying models
* searching
* filtering
* selecting

### Initializr state owns

* selected models
* selected Token Factory

### Token Factory generator owns

* Token Factory-specific transformation
* output schema
* configuration serialization

### UI owns

* interaction
* loading state
* validation feedback
* preview
* copy/download

Do NOT put LiteLLM-specific configuration generation inside:

* ModelCard
* ModelSelector
* Navbar
* generic UI components

---

# 22. Design System Boundary

Continue using:

`@tokyo3rdhq/magi-design-system`

for shared visual primitives.

Reuse existing components for:

* Button
* Card
* Badge
* Checkbox
* Input
* FormField
* Segmented
* Banner
* EmptyState
* layout primitives
* typography
* theme
* spacing
* icons

Do not create new generic components merely to implement this workflow.

If a new component is genuinely product-specific, it may live inside TFI.

Examples of legitimate TFI-owned components:

```text
ModelCard
ModelSelector
SelectedModelList
TokenFactorySelector
ConfigPreview
ConfigOutput
```

These are product concepts, not generic Design System primitives.

---

# 23. Provider vs Token Factory

Be careful not to confuse:

```text
Model Provider
```

with:

```text
Token Factory
```

For example:

```text
Data Source: Hugging Face
Provider: novita
Model: some-model
```

does NOT mean:

```text
Token Factory: novita
```

The Token Factory is the target configuration implementation:

```text
LiteLLM
NewAPI
```

Provider information belongs to model metadata.

Token Factory information belongs to the generation target.

These must remain separate domain concepts.

---

# 24. Data Flow Example

A complete example should work conceptually like this:

```text
Model Catalog

NVIDIA
  └── gpt-oss-120b

Hugging Face
  └── some-model
       provider: novita

AMD
  └── another-model
```

User selects:

```text
✓ gpt-oss-120b
✓ some-model
✓ another-model
```

Application state:

```ts
{
  selectedModels: [
    {
      modelId: "gpt-oss-120b",
      dataSource: "nvidia",
      provider: "nvidia"
    },
    {
      modelId: "some-model",
      dataSource: "huggingface",
      provider: "novita"
    },
    {
      modelId: "another-model",
      dataSource: "amd",
      provider: "amd"
    }
  ],
  tokenFactory: "litellm"
}
```

Then:

```text
Generate
   ↓
LiteLLMGenerator
   ↓
GeneratedConfig
   ↓
ConfigPreview
   ↓
Copy
```

This entire path must work without manual intervention.

---

# 25. Testing Requirements

Add tests for the workflow.

At minimum:

## Selection

* select model
* deselect model
* multiple model selection
* selected count
* selection persistence while filtering/searching

## Validation

* no models
* models selected but no Token Factory
* models + Token Factory

## Generator

* LiteLLM generator
* NewAPI generator
* deterministic output
* selected models correctly represented
* provider metadata correctly propagated
* missing required metadata produces an error

## UI Integration

Verify:

```text
select model
→ selected model appears
→ choose Token Factory
→ generate
→ configuration appears
→ copy returns exact generated content
```

The most important test is the complete end-to-end user journey.

---

# 26. Do Not Over-Engineer Phase 1

Explicitly defer:

* AI model recommendation
* natural-language requirement input
* intent recognition
* model scoring
* Elo
* model ranking
* agent integration
* MCP
* A2A
* user accounts
* project persistence
* configuration history
* generated URL persistence
* collaborative configuration
* analytics-driven recommendations

These are future layers.

The Phase 1 question is simply:

> Can a user reliably turn a model selection into a Token Factory configuration?

---

# 27. Implementation Order

Implement in this order.

### Step 1 — Audit

Understand the existing TFI implementation.

Identify:

* model catalog
* current selection state
* current selected-model UI
* current Token Factory UI
* current config generation code
* current LiteLLM implementation
* current NewAPI implementation
* existing copy/download behavior

Do not rewrite working functionality unnecessarily.

### Step 2 — Establish State

Create the canonical Initializr state:

```text
selectedModels
tokenFactory
```

### Step 3 — Connect Model Selection

Make the existing model list feed the canonical selection state.

### Step 4 — Connect Token Factory Selection

Make LiteLLM/NewAPI selection feed the same Initializr state.

### Step 5 — Establish Generator Interface

Separate:

```text
Initializr State
        ↓
Generator
```

### Step 6 — Implement LiteLLM

Make the complete LiteLLM flow work.

### Step 7 — Implement NewAPI

Connect NewAPI through the same abstraction.

### Step 8 — Generated Artifact

Create one canonical generated artifact consumed by:

* preview
* copy
* download

### Step 9 — Validation

Prevent invalid generation.

### Step 10 — End-to-End Test

Verify the entire user journey from model selection to usable configuration.

---

# 28. Definition of Done

Phase 1 is complete only when a new user can perform this journey without developer intervention:

```text
Open TFI
   ↓
See model catalog
   ↓
Select one or more models
   ↓
See selected model candidates
   ↓
Select LiteLLM or NewAPI
   ↓
Click Generate
   ↓
See generated configuration
   ↓
Copy configuration
   ↓
Paste it elsewhere
```

And the generated configuration must correspond exactly to:

```text
User-selected models
+
User-selected Token Factory
```

There must be no hidden recommendation layer.

There must be no implicit provider substitution.

There must be no fake configuration data.

There must be no manual editing required merely to make the generated artifact usable.

---

# Final Product Principle

For Phase 1, TFI is not yet an AI model recommender.

It is an **Initializr**.

The product loop is:

> **Select → Configure → Generate**

The most important milestone is therefore not adding more features.

It is making this loop:

> **Model List → Candidate Models → Token Factory → Configuration**

completely reliable, deterministic, understandable, and extensible.

Once this foundation works, later phases can add:

```text
User Requirement
       ↓
Intent Recognition
       ↓
Model Recommendation
       ↓
Candidate Models
       ↓
Token Factory
       ↓
Configuration
```

But do not implement that future complexity before the Phase 1 Initializr loop is complete.

