# TFI Model Source URL Implementation

## Role

You are a senior full-stack engineer working on Token Factory Initializr (TFI), an AI model catalog and configuration-generation product.

Repository: `token-factory-initializer`

Primary goals:

* Add a canonical `source_url` field to model metadata.
* Display the source link in the human-oriented `/browse` interface.
* Expose `source_url` through the public Model Catalog API.
* Keep the implementation consistent with the existing canonical model schema, source adapters, provenance architecture, storage pipeline, and API projection layer.

Follow the existing project architecture and conventions. Inspect the current implementation before making changes.

---

## 1. Product Decision

TFI models may originate from different model catalogs and provider platforms.

Each model should expose a `source_url`: a human-readable URL where users or agents can inspect the model or the source catalog entry associated with it.

Examples:

| Data source  | Model                              | source_url                                                 |
| ------------ | ---------------------------------- | ---------------------------------------------------------- |
| NVIDIA       | `deepseek-ai/deepseek-v4.1-flash`  | `https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash` |
| Hugging Face | `prism-ml/Ternary-Bonsai-27B-gguf` | `https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf`  |
| AMD          | `Qwen3.8-27B`                      | `https://developer.amd.com.cn/radeon/tokenfactory`         |

The AMD URL is a catalog-level page containing model entries rather than a dedicated detail page. This is intentional.

### Field semantics

`source_url` means:

> A human-readable source page associated with this model, where additional information about the model or its availability can be inspected.

It does not necessarily point to a dedicated model detail page.

Do not introduce `detail_url` as an alternative field.

Do not introduce a `sources[]` abstraction in this implementation. A multi-source representation can be considered later if actual product requirements justify it.

---

## 2. Inspect the Existing Architecture

Before editing, locate and understand:

* The canonical model type/schema.
* NVIDIA, AMD, and Hugging Face source adapters.
* Model normalization and enrichment stages.
* Field-level provenance implementation, if present.
* Snapshot, diff, reconcile, and publish stages.
* KV/storage serialization and deserialization.
* Public model projection, such as `toPublicModel()`.
* `/api/v1/models` and `/api/v1/models/{id}` routes.
* Browse model list, model cards, and existing external-link conventions.
* Existing tests and fixtures.

Reuse existing abstractions. Avoid introducing a parallel metadata pipeline.

---

## 3. Canonical Model Schema

Add an optional `source_url` field to the canonical model representation.

Conceptually:

```ts
interface Model {
  // Existing fields...

  source_url?: string;
}
```

Adapt this to the repository's actual schema and naming conventions.

Requirements:

1. `source_url` must be part of canonical model metadata, not a UI-only property.
2. It must survive normalization, serialization, storage, and public projection.
3. It must not participate in model identity, deduplication, or identity matching.
4. It must not replace `data_source`, `provider`, or endpoint metadata.
5. Do not derive the URL dynamically in the Browse component.
6. Do not construct URLs by blindly concatenating `data_source` and `model_id`.
7. Preserve backward compatibility with existing stored records that do not contain `source_url`.

Use the existing optional-field conventions. Do not introduce `null`, empty strings, or placeholder URLs unless that is already the project's established convention.

---

## 4. Source Adapter Implementation

Populate `source_url` in the appropriate source adapter or normalization layer.

### NVIDIA

For the NVIDIA model:

```text
model_id: deepseek-ai/deepseek-v4.1-flash
source_url: https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash
```

Use the existing NVIDIA model metadata to construct or retrieve the official NVIDIA Build URL.

If the source already exposes a canonical URL, prefer that value over reconstructing it.

### Hugging Face

For the Hugging Face model:

```text
model_id: prism-ml/Ternary-Bonsai-27B-gguf
source_url: https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf
```

Use the canonical Hugging Face model page URL.

Handle model IDs containing `/` correctly.

### AMD Radeon Cloud

For the AMD model:

```text
model_id: Qwen3.8-27B
source_url: https://developer.amd.com.cn/radeon/tokenfactory
```

This is a catalog-level URL, not a model-specific detail URL.

Do not fabricate a model-specific URL or append the model ID to the catalog URL.

### General requirements

* Follow the existing source adapter architecture.
* Prefer source-provided URLs when available.
* If a URL must be constructed, keep construction logic inside the relevant adapter or a suitable shared helper.
* Do not add source-specific URL logic to the Browse UI or public API route.
* Do not fabricate URLs for models when a reliable source URL cannot be established.
* Missing URLs must not cause model ingestion or publication to fail.

---

## 5. Provenance Compatibility

The project supports, or may already be implementing, field-level provenance.

If the canonical model's provenance mechanism supports field-level tracking, record the origin of `source_url` using the existing conventions.

For example, conceptually:

```json
{
  "source_url": "https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf",
  "provenance": {
    "source_url": {
      "source": "huggingface",
      "source_field": "model_id",
      "method": "derived"
    }
  }
}
```

This is illustrative only. Reuse the actual provenance schema and method vocabulary in the repository.

Do not add a new provenance abstraction solely for this field.

Do not expose provenance through the public API.

---

## 6. Public Model Catalog API

Expose `source_url` in both:

```text
GET /api/v1/models
GET /api/v1/models/{id}
```

Example public model:

```json
{
  "id": "deepseek-ai/deepseek-v4.1-flash",
  "object": "model",
  "owned_by": "nvidia",
  "data_source": "nvidia",
  "provider": "nvidia",
  "capabilities": ["chat", "reasoning"],
  "source_url": "https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash"
}
```

Requirements:

1. Add `source_url` to the existing public model projection.
2. Both list and detail endpoints must use the same projection logic.
3. Do not duplicate URL construction in API handlers.
4. Do not expose internal provenance or raw source payloads.
5. Preserve the existing API response structure and filtering behavior.
6. Models without a source URL must remain valid API results.
7. Keep the change additive and backward-compatible.

Update API schema definitions or documentation if the repository maintains them.

---

## 7. Browse UI

Display a subtle external-link affordance for models with a valid `source_url`.

### UX requirements

* Use the existing MAGI Design System and iconography conventions.
* Prefer the existing external-link icon, such as the project's Lucide-based icon implementation.
* Do not introduce a new icon library.
* Do not add a prominent button that competes with model selection.
* Do not make the entire model card navigate away when the card is also used to select a model.
* Place the link near the model name or in another location consistent with the existing model-card layout.
* Use a tooltip or accessible label such as **“View source”**.
* Open external source pages in a new tab.
* Use `rel="noopener noreferrer"` when using `target="_blank"`.
* Ensure the link remains independently keyboard-accessible and does not trigger the model card's selection handler.
* Do not render the icon when `source_url` is absent.

### Visual behavior

The source link should be a secondary action.

It should:

* Use existing semantic foreground/muted tokens.
* Have visible hover and keyboard-focus states.
* Remain legible in supported themes.
* Preserve the existing Browse page's information density.
* Avoid arbitrary colors, custom shadows, decorative backgrounds, or excessive spacing.

### Accessibility

Provide an accessible name, for example:

```text
View source for DeepSeek V4.1 Flash
```

Use the project's existing external-link and icon-only control conventions.

Verify nested interactive elements and event propagation. Do not create invalid interactive nesting.

---

## 8. URL Validation and Safety

Treat source URLs as external metadata.

At the appropriate ingestion or normalization boundary:

* Accept only absolute `https:` URLs unless the project has an explicit requirement for additional schemes.
* Reject or omit `javascript:`, `data:`, `file:`, and other unsafe schemes.
* Do not treat a non-empty string as automatically safe.
* Preserve valid URLs without unnecessary rewriting.
* Avoid introducing server-side URL fetching or redirects as part of this feature.

The Browse UI must not use `source_url` as an HTML injection surface.

Do not add URL validation logic independently in multiple layers if a suitable shared utility already exists.

---

## 9. Data Lifecycle and Compatibility

Ensure `source_url` is handled correctly through the existing pipeline:

```text
Source Adapter
    ↓
Normalize
    ↓
Canonical Model
    ↓
Snapshot / Diff / Reconcile
    ↓
Publish
    ↓
Public Projection
    ├── Browse
    └── /api/v1/models
```

Requirements:

* Existing records without `source_url` remain readable.
* New records publish the field when available.
* Updates to a model's source URL propagate through the normal pipeline.
* Removing a previously available URL must not leave a stale URL in the published record.
* URL changes must not create duplicate models.
* Do not introduce a separate KV key or manifest just for `source_url`.
* Do not require a destructive migration unless the current storage implementation makes one unavoidable.

If the project has deterministic snapshot or diff tests, add coverage for URL changes and URL removal.

---

## 10. Tests

Add or update tests using the project's existing test framework.

### Schema and normalization

* Canonical model accepts `source_url`.
* NVIDIA adapter produces the expected NVIDIA URL.
* Hugging Face adapter handles namespaced model IDs correctly.
* AMD adapter uses the catalog-level URL.
* Missing URLs are allowed.
* Invalid URL schemes are rejected or omitted according to the chosen validation contract.

### Storage and pipeline

* `source_url` survives serialization and deserialization.
* Existing records without the field remain readable.
* Updating a URL updates the published model.
* Removing a URL does not preserve stale metadata.
* URL changes do not affect model identity or deduplication.

### Public API

* `/api/v1/models` includes `source_url` when available.
* `/api/v1/models/{id}` includes the same field.
* Models without the field remain valid.
* Provenance is not exposed.
* Existing filters and response contracts remain unchanged.

### Browse UI

* Models with a source URL display the external-link affordance.
* Models without a source URL do not display it.
* Clicking the source link does not trigger model selection.
* The link has an accessible name.
* The link opens safely in a new tab.
* Keyboard focus is visible.

---

## 11. Documentation

Update the public API documentation to describe:

```text
source_url
```

Document that it is an optional URL to a human-readable source page associated with the model.

Explicitly state:

* It may point to a model detail page or a broader catalog page.
* It is not a canonical model identifier.
* It is not guaranteed to be a dedicated detail page.
* It is not a substitute for endpoint or provider metadata.

If `/llms.txt` or `/agents.md` documents the public model schema, add a brief explanation of `source_url` where appropriate.

Do not expose internal provenance details.

---

## 12. Scope Constraints

Do not implement the following as part of this task:

* A `sources[]` array.
* A separate source registry API.
* A new model-detail page inside TFI.
* A new endpoint or provider abstraction.
* Automatic crawling of source pages.
* Runtime availability checks against source URLs.
* URL-based model identity or deduplication.
* A new storage subsystem.
* Unrelated Browse redesigns.
* Unnecessary changes to the MAGI Design System.

Keep the implementation small and consistent with the existing architecture.

---

## 13. Definition of Done

The implementation is complete when:

1. Canonical models support optional `source_url`.
2. NVIDIA, Hugging Face, and AMD adapters populate the expected URLs.
3. AMD correctly uses its catalog-level URL.
4. The field survives the existing ingestion and publication pipeline.
5. Both `/api/v1/models` and `/api/v1/models/{id}` expose it.
6. Browse displays a subtle, accessible external-link action when available.
7. The source link does not interfere with model selection.
8. Existing models without URLs remain compatible.
9. Provenance and internal source payloads remain private.
10. Tests and relevant documentation are updated.
11. No unrelated architectural refactoring is introduced.

## Final Principle

**A model's source URL is canonical public metadata, not UI decoration.**

The same canonical `source_url` must power both the human-oriented Browse experience and the machine-oriented Model Catalog API.

TFI owns the normalized model representation; source platforms remain the destinations for deeper human inspection.

