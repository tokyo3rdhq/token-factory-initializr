# Data Source / Provider Refactor — Implementation Assessment

> Per `docs/data_source_provider_refactor.md` §26 ("Produce a short
> implementation assessment before changing code").

## Scope summary

The refactor introduces a first-class `data_source` dimension, splits
the single `store` stage into four explicit stages (`snapshot → diff
→ reconcile → publish`), moves the per-provider key namespace from
`{provider}` to `{(data_source, provider)}`, and adds a new
`{data_source}` provider-manifest namespace.

It also adds provider lifecycle reconciliation: removed providers are
explicitly deleted (no longer relying on `put_snapshot` "refuse empty"
as a side-channel guarantee), and incomplete source data is guarded
against accidental destructive deletes.

## Affected layers

| Layer | Files | Type of change |
|---|---|---|
| Schema | `data/models/schema.py` | Add `data_source: str` field |
| Normalize | `data/process/normalize.py` | Read/serialize `data_source` |
| Provider NVIDIA | `data/providers/nvidia.py` | Stamp `data_source="nvidia"` |
| Provider AMD | `data/providers/amd.py` | Stamp `data_source="amd"` |
| Provider HF | `data/providers/huggingface.py` | Stamp `data_source="huggingface"` |
| Storage | `data/storage/cloudflare_kv.py` | New key helpers + new methods; deprecate old |
| New stages | `data/stages/snapshot.py` `diff.py` `reconcile.py` `publish.py` | NEW |
| Removed stage | `data/stages/store.py` | Replaced by 4 stages (keep removed, no callers) |
| Composition | `data/stages/__init__.py` | Insert 4 new stages before summarize |
| Summarize | `data/stages/summarize.py` (or `data/process/summarize.py`) | Report added/updated/removed providers |
| Web storage | `web/functions/lib/kv.ts` | New key shape; add manifest reader |
| Web API | `web/functions/api/{providers,models,generate,manifest}.ts` | Use new key shape |
| Web types | `web/src/types.ts` | Add `data_source`; update `Manifest` shape |
| Web UI | `web/src/pages/{Home,Browse,Generate}.tsx` + components/format.ts | Show `data_source` separately |
| Tests | `data/tests/test_*.py` (10+ files) | Add §22 scenarios; update existing |
| Docs | `AGENTS.md`, `docs/arch_*.md` | Update schema + invariants |

## Migration strategy

§17 forbids indefinite dual-write. We will:

1. **Single cutover**: deploy new pipeline + new web readers in one
   release. Old keys (`tfi:models:${provider}:latest`) become inert;
   they will be removed by the first successful `publish` run that
   deletes providers no longer in the desired state.
2. **Migration window**: documented in commit message and
   `local://migration_notes.md` (created during phase 4).
3. **Source of truth post-cutover**: `tfi:providers:${data_source}:latest`
   + `tfi:models:${data_source}:${provider}:latest`. No dual read.

## Phased implementation

Each phase ships with green tests + a commit. Phase boundaries are
chosen so the build is always runnable.

### Phase 1 — Data model + storage foundation
- Add `data_source` field to `ModelEndpoint`
- Add new key helpers in `data/storage/cloudflare_kv.py`:
  `provider_models_key`, `provider_manifest_key`
- Add new `KVStorage` methods:
  `get_provider_manifest`, `put_provider_manifest`,
  `get_provider_models`, `put_provider_models`,
  `delete_provider_models`
- Update existing `put_snapshot` / `get_snapshot` to delegate to the
  new methods (one-to-one mapping, but using `(data_source, provider)`
  keys derived from the legacy `provider` arg by treating it as both
  the data source and the provider for now — temporary bridge).
- Tests: storage test cases for the new key shape.

### Phase 2 — Source adapters
- Stamp `data_source` on every endpoint dict emitted by NVIDIA, AMD,
  Hugging Face adapters.
- Add test cases verifying the stamped value per provider.

### Phase 3 — New stages (snapshot / diff / reconcile / publish)
- Build `DesiredState` (per data_source → providers → endpoints).
- Build `Diff` (added / updated / removed providers).
- Build `ReconciliationPlan` (added / updated / removed providers,
  per-model counts in summary).
- Build `PublishStage` that applies the plan to KV with the documented
  ordering (PUT models → DELETE stale → PUT manifests LAST).
- Empty-source safety guard: if `desired providers = []` for a source
  that previously had providers, refuse to delete without explicit
  validation flag (configurable; default = refuse).
- Replace `StoreStage` with the new composition. Keep `StoreStage`
  class removed; its callers (none in production, only in tests) get
  updated.
- Update `data/stages/__init__.py` pipeline composition.
- Tests: per §22 scenarios.

### Phase 4 — Web consumer migration
- Update `web/functions/lib/kv.ts` to use new key shape; add
  `loadProviderManifest(env, data_source)`; update `listProviders`
  to enumerate across `(data_source, provider)` pairs via the
  per-source manifests.
- Update `web/functions/api/{providers,models,generate,manifest}.ts`.
- Update `web/src/types.ts`: `data_source` field, updated manifest
  shape, `ProviderManifest` type.
- Update `web/src/pages/*` and `web/src/components/format.ts` to
  surface the data_source dimension (pill color / hierarchy).
- Tests: 42 web tests must still pass.

### Phase 5 — Summarize + notify + docs
- Summarize reports per-source provider lifecycle changes
  (added / updated / removed) so Feishu notifications surface
  removals like `zai-org removed`.
- Update architecture docs (`docs/arch_pipeline.md`, `docs/roadmap.md`)
  with the new key schema and the invariant.

## Risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Empty source accidentally deletes providers | Medium | `PublishStage` requires an explicit `validated: true` flag from the upstream; refuses to delete when desired set is empty + previous had providers |
| HF provider emits new providers (e.g. zai-org reappears) | Low | Idempotent design — `publish` PUTs the manifest, consumers re-read it |
| Web consumers break during cutover | Medium | Single deploy for both data + web; old keys simply become inert |
| Backwards compat for previously-deployed KV keys | High | Old `tfi:models:${provider}:latest` keys are read by no one post-cutover; they accumulate in KV but cost nothing (Cloudflare KV free tier allows 100k keys) |
| Tests lose coverage during refactor | Medium | Each phase keeps existing tests green + adds new ones |

## Definition of done (mapped to §29)

Each phase contributes to one or more §29 items. All 25 must be green
before merge.