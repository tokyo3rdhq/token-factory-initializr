"""Tests for the snapshot → diff → reconcile → publish pipeline.

Per docs/data_source_provider_refactor.md §22:

  * NVIDIA: data_source=nvidia, provider=nvidia
  * AMD:    data_source=amd,    provider=amd
  * Hugging Face multiple providers: provider per inference provider
  * Provider removal: a provider in current but absent from desired
    must result in DELETE.
  * Provider addition: a new provider in desired but not current
    must result in PUT.
  * Provider update: a provider in both → PUT (idempotent).
  * Same provider across data sources → two distinct keys.
  * Idempotency: applying the same desired twice → no-op.
  * Empty / incomplete source: must NOT trigger destructive deletion
    unless source_validated[datasource]=True.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.stages.diff import DiffStage, build_diff
from data.stages.publish import PublishStage, publish_plan
from data.stages.reconcile import ReconcileStage, build_plan
from data.stages.snapshot import SnapshotStage, build_desired_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mk_ep(data_source: str, provider: str, model_id: str) -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
        data_source=data_source,
        model_id=model_id,
        free=True,
        fetched_at=datetime.now(timezone.utc),
    )


class FakeKV:
    """In-memory KV that records every key write/delete."""

    def __init__(self):
        self.store: Dict[str, Any] = {}
        self.deleted: List[str] = []

    def get(self, key: str):
        return self.store.get(key)

    def put(self, key: str, value: dict, ttl: Optional[int] = None):
        self.store[key] = value

    def delete(self, key: str):
        self.deleted.append(key)
        self.store.pop(key, None)

    def get_provider_manifest(self, ds: str):
        return self.store.get(f"tfi:providers:{ds}:latest")

    def put_provider_manifest(self, ds: str, manifest: dict):
        self.store[f"tfi:providers:{ds}:latest"] = manifest

    def get_provider_models(self, ds: str, provider: str):
        return self.store.get(f"tfi:models:{ds}:{provider}:latest")

    def put_provider_models(self, ds: str, provider: str, models: list):
        if not models:
            return
        self.store[f"tfi:models:{ds}:{provider}:latest"] = {
            "data_source": ds,
            "provider": provider,
            "models": models,
        }

    def delete_provider_models(self, ds: str, provider: str):
        self.delete(f"tfi:models:{ds}:{provider}:latest")


# ---------------------------------------------------------------------------
# Snapshot stage
# ---------------------------------------------------------------------------


def test_snapshot_groups_by_data_source_and_provider():
    endpoints = [
        _mk_ep("nvidia", "nvidia", "n/a"),
        _mk_ep("amd", "amd", "a/b"),
        _mk_ep("huggingface", "novita", "openai/gpt-oss-20b"),
        _mk_ep("huggingface", "together", "openai/gpt-oss-20b"),
        _mk_ep("huggingface", "zai-org", "zai-org/glm"),
    ]
    desired = build_desired_state(endpoints)
    assert sorted(desired["data_source_order"]) == ["amd", "huggingface", "nvidia"]
    assert desired["data_sources"]["nvidia"]["provider_order"] == ["nvidia"]
    assert desired["data_sources"]["amd"]["provider_order"] == ["amd"]
    assert sorted(desired["data_sources"]["huggingface"]["provider_order"]) == [
        "novita",
        "together",
        "zai-org",
    ]


def test_snapshot_emits_every_known_source_even_when_empty():
    desired = build_desired_state([])
    assert sorted(desired["data_source_order"]) == ["amd", "huggingface", "nvidia"]
    for ds in desired["data_source_order"]:
        assert desired["data_sources"][ds]["provider_order"] == []


def test_snapshot_stage_populates_artifact():
    ctx = PipelineContext()
    ctx.data["enriched"] = [
        _mk_ep("huggingface", "novita", "openai/gpt-oss-20b"),
        _mk_ep("huggingface", "together", "openai/gpt-oss-20b"),
    ]
    ctx.artifacts["source_validated"] = {"huggingface": True, "nvidia": True, "amd": True}
    out = SnapshotStage().execute(ctx)
    assert "desired_state" in out.artifacts
    assert sorted(out.artifacts["desired_state"]["data_source_order"]) == [
        "amd",
        "huggingface",
        "nvidia",
    ]


# ---------------------------------------------------------------------------
# Diff stage
# ---------------------------------------------------------------------------


def test_diff_identifies_added_updated_removed_providers():
    """Current: novita, together, zai-org.
    Desired: novita, together, deepinfra.
    Expect: added=deepinfra, updated=[novita, together], removed=[zai-org].
    """
    desired = build_desired_state([
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
        _mk_ep("huggingface", "deepinfra", "b"),
    ])
    current_manifests = {
        "huggingface": {"data_source": "huggingface", "providers": ["novita", "together", "zai-org"]},
        "amd": None,
        "nvidia": None,
    }
    diff = build_diff(desired, current_manifests)
    assert diff["huggingface"]["added"] == ["deepinfra"]
    assert sorted(diff["huggingface"]["updated"]) == ["novita", "together"]
    assert diff["huggingface"]["removed"] == ["zai-org"]
    # AMD and NVIDIA unchanged.
    assert diff["amd"] == {"added": [], "updated": [], "removed": []}
    assert diff["nvidia"] == {"added": [], "updated": [], "removed": []}


def test_diff_handles_first_run_when_no_current_manifests():
    """No current manifests exist ⇒ every active provider is \"added\"."""
    desired = build_desired_state([
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
    ])
    diff = build_diff(desired, {"huggingface": None, "amd": None, "nvidia": None})
    assert sorted(diff["huggingface"]["added"]) == ["novita", "together"]
    assert diff["huggingface"]["removed"] == []


def test_diff_tolerates_legacy_manifest_shape_with_dict_providers():
    """Manifests written by older /api/manifest code may use the
    ``providers: {name: {...}}`` shape; diff must accept both shapes."""
    desired = build_desired_state([_mk_ep("amd", "amd", "x")])
    legacy = {"providers": {"amd": {"count": 5, "status": "success"}}}
    diff = build_diff(desired, {"amd": legacy, "nvidia": None, "huggingface": None})
    assert diff["amd"]["updated"] == ["amd"]
    assert diff["amd"]["added"] == []


def test_diff_stage_records_error_when_desired_state_missing():
    ctx = PipelineContext()
    out = DiffStage(kv=FakeKV()).execute(ctx)
    assert any(e["stage"] == "diff" for e in ctx.errors)


# ---------------------------------------------------------------------------
# Reconcile stage
# ---------------------------------------------------------------------------


def test_reconcile_plan_lists_added_updated_removed_per_source():
    desired = build_desired_state([
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
    ])
    diff = {
        "huggingface": {"added": ["novita"], "updated": ["together"], "removed": ["zai-org"]},
        "nvidia": {"added": [], "updated": ["nvidia"], "removed": []},
        "amd": {"added": ["amd"], "updated": [], "removed": []},
    }
    plan = build_plan(desired, diff)
    assert plan["summary"]["added"] == 2
    assert plan["summary"]["updated"] == 2
    assert plan["summary"]["removed"] == 1
    assert plan["by_data_source"]["huggingface"]["removed"] == ["zai-org"]
    assert plan["by_data_source"]["huggingface"]["manifest_providers"] == ["novita", "together"]


def test_reconcile_stage_populates_artifact():
    ctx = PipelineContext()
    ctx.artifacts["desired_state"] = build_desired_state(
        [_mk_ep("amd", "amd", "x")]
    )
    ctx.artifacts["provider_diff"] = {
        "amd": {"added": ["amd"], "updated": [], "removed": []},
        "nvidia": {"added": [], "updated": [], "removed": []},
        "huggingface": {"added": [], "updated": [], "removed": []},
    }
    out = ReconcileStage().execute(ctx)
    assert "reconciliation_plan" in out.artifacts


# ---------------------------------------------------------------------------
# Publish stage
# ---------------------------------------------------------------------------


def _full_pipeline_context(endpoints, kv=None, current_manifests=None, validated=None):
    """Build a PipelineContext pre-populated through the snapshot/diff/reconcile steps.

    Uses a single FakeKV across diff and publish so the diff stage sees
    the current published state that the caller (if any) seeded into
    the kv.
    """
    if kv is None:
        kv = FakeKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = endpoints
    ctx.data["valid"] = endpoints
    ctx.state["fetch_errors"] = {}
    ctx.artifacts["source_validated"] = validated or {
        ds: True for ds in ("amd", "huggingface", "nvidia")
    }
    SnapshotStage().execute(ctx)
    DiffStage(kv=kv).execute(ctx)  # writes into ctx.artifacts["provider_diff"]
    ReconcileStage().execute(ctx)
    return ctx, kv


def test_publish_writes_new_provider_catalogs_and_manifest():
    """First-run scenario: no existing manifests. Publishes only the
    added providers, then writes manifests last."""
    kv = FakeKV()
    endpoints = [
        _mk_ep("huggingface", "novita", "openai/gpt-oss-20b"),
        _mk_ep("huggingface", "together", "openai/gpt-oss-20b"),
    ]
    ctx, kv = _full_pipeline_context(endpoints)
    out = PublishStage(kv=kv).execute(ctx)
    assert "publish_summary" in out.artifacts
    assert out.artifacts["publish_summary"]["added"] == 2
    assert out.artifacts["publish_summary"]["removed"] == 0
    # Manifests written last (both sources appear; amd and nvidia are empty).
    hf_manifest = kv.store["tfi:providers:huggingface:latest"]
    assert hf_manifest["providers"] == ["novita", "together"]
    # Ignore the timestamp when comparing the empty-manifest sources —
    # the publisher stamps ``generated_at`` per source and microsecond
    # drift between calls would flake a strict equality check.
    assert kv.store["tfi:providers:nvidia:latest"]["providers"] == []
    assert kv.store["tfi:providers:amd:latest"]["providers"] == []


def test_publish_removes_provider_from_current_when_removed_from_desired():
    """zai-org was previously published but disappeared from desired →
    publish must DELETE the corresponding key."""
    kv = FakeKV()
    # Seed: pretend zai-org was published yesterday.
    kv.put_provider_models(
        "huggingface",
        "zai-org",
        [{"model_id": "zai-org/glm", "data_source": "huggingface", "provider": "zai-org"}],
    )
    kv.put_provider_manifest(
        "huggingface",
        {"data_source": "huggingface", "providers": ["novita", "together", "zai-org"]},
    )
    # Desired today: zai-org is gone.
    endpoints = [
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
    ]
    ctx, _kv = _full_pipeline_context(endpoints, kv=kv)
    out = PublishStage(kv=kv).execute(ctx)
    assert out.artifacts["publish_summary"]["removed"] == 1
    assert "tfi:models:huggingface:zai-org:latest" in kv.deleted
    # Manifest reflects the new set (no zai-org).
    assert kv.store["tfi:providers:huggingface:latest"]["providers"] == ["novita", "together"]


def test_publish_refuses_to_delete_when_source_unvalidated():
    """Refactor §21 — empty desired set with a previously-published
    provider must NOT trigger DELETE unless source_validated[ds]=True."""
    kv = FakeKV()
    kv.put_provider_models(
        "huggingface", "zai-org", [{"model_id": "z/y", "data_source": "huggingface", "provider": "zai-org"}]
    )
    kv.put_provider_manifest(
        "huggingface", {"data_source": "huggingface", "providers": ["zai-org"]}
    )
    # Pretend today's fetch returned zero endpoints for HF (or didn't
    # run at all) — source_validated[huggingface] = False.
    ctx = PipelineContext()
    ctx.data["enriched"] = []
    ctx.data["valid"] = []
    ctx.state["fetch_errors"] = {"huggingface": "Network timeout"}
    ctx.artifacts["source_validated"] = {"huggingface": False, "nvidia": True, "amd": True}
    SnapshotStage().execute(ctx)
    DiffStage(kv=kv).execute(ctx)
    ReconcileStage().execute(ctx)
    out = PublishStage(kv=kv).execute(ctx)
    # Must NOT have deleted the existing zai-org key.
    assert "tfi:models:huggingface:zai-org:latest" not in kv.deleted
    # The pipeline must have recorded a severe error.
    assert any(e["stage"] == "publish" for e in ctx.errors)


def test_publish_same_provider_across_two_sources_keeps_keys_independent():
    """Refactor §13 — huggingface/together and openrouter/together
    must produce two independent KV keys."""
    kv = FakeKV()
    ctx = PipelineContext()
    # Two endpoints with the same provider name under different data sources.
    ctx.data["enriched"] = [
        ModelEndpoint(
            provider="together",
            data_source="huggingface",
            model_id="h/together-x",
            free=True,
            fetched_at=datetime.now(timezone.utc),
        ),
        ModelEndpoint(
            provider="together",
            data_source="openrouter",
            model_id="o/together-x",
            free=True,
            fetched_at=datetime.now(timezone.utc),
        ),
    ]
    ctx.data["valid"] = ctx.data["enriched"]
    ctx.artifacts["source_validated"] = {
        "huggingface": True, "openrouter": True, "nvidia": True, "amd": True
    }
    SnapshotStage().execute(ctx)
    DiffStage(kv=kv).execute(ctx)
    ReconcileStage().execute(ctx)
    PublishStage(kv=kv).execute(ctx)
    assert (
        kv.store["tfi:models:huggingface:together:latest"]["models"][0]["model_id"]
        == "h/together-x"
    )
    assert (
        kv.store["tfi:models:openrouter:together:latest"]["models"][0]["model_id"]
        == "o/together-x"
    )


def test_publish_is_idempotent_when_run_twice_with_same_desired():
    """Refactor §12 — applying the same desired twice must converge
    with no extra side effects on the second run."""
    kv = FakeKV()
    endpoints = [
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
    ]
    # First run.
    ctx, kv = _full_pipeline_context(endpoints, kv=kv)
    PublishStage(kv=kv).execute(ctx)
    after_first = {k: v for k, v in kv.store.items()}
    # Second run with the same desired.
    ctx, kv = _full_pipeline_context(endpoints, kv=kv)
    PublishStage(kv=kv).execute(ctx)
    # Manifest timestamps may differ between runs, but the provider
    # lists and the model catalogs must be unchanged.
    for key, expected in after_first.items():
        if key.startswith("tfi:providers:") and "generated_at" in expected:
            assert kv.store[key]["providers"] == expected["providers"]
            assert kv.store[key]["data_source"] == expected["data_source"]
        else:
            assert kv.store[key] == expected
    # No extra deletes.
    assert kv.deleted == []


def test_publish_writes_manifest_last_after_models():
    """Refactor §10 — ordering: PUT models → DELETE stale → PUT manifest last.

    The manifest for a data source must be written AFTER every per-
    provider model write for the same source. We check ordering by
    recording the write sequence per source and asserting that for
    every source the manifest write is preceded by all model writes
    for that source.
    """
    kv = RecordingKV()
    endpoints = [
        _mk_ep("huggingface", "novita", "a"),
        _mk_ep("huggingface", "together", "a"),
    ]
    ctx, kv = _full_pipeline_context(endpoints, kv=kv)
    PublishStage(kv=kv).execute(ctx)

    # Group events by data source. Source-of-truth ordering invariant:
    # for each data source, every model event precedes the manifest event.
    by_source: dict[str, list[tuple[str, str]]] = {}
    for kind, key in kv.events:
        # key format: tfi:models:{ds}:{provider}:latest or tfi:providers:{ds}:latest
        if key.startswith("tfi:models:"):
            ds = key.split(":")[2]
        elif key.startswith("tfi:providers:"):
            ds = key.split(":")[2]
        else:
            continue
        by_source.setdefault(ds, []).append((kind, key))

    for ds, events in by_source.items():
        model_events = [(i, e) for i, e in enumerate(events) if e[0] == "model"]
        manifest_events = [(i, e) for i, e in enumerate(events) if e[0] == "manifest"]
        # Every source emits exactly one manifest write.
        assert len(manifest_events) == 1, f"{ds} should have 1 manifest event, got {events}"
        manifest_idx = manifest_events[0][0]
        for model_idx, _ in model_events:
            assert model_idx < manifest_idx, (
                f"{ds}: model event at {model_idx} should precede "
                f"manifest at {manifest_idx}"
            )


class RecordingKV(FakeKV):
    """FakeKV variant that records the write/delete sequence for ordering tests."""

    def __init__(self):
        super().__init__()
        self.events: List[Any] = []

    def put_provider_models(self, ds, provider, models):
        if not models:
            return
        key = f"tfi:models:{ds}:{provider}:latest"
        self.events.append(("model", key))
        super().put_provider_models(ds, provider, models)

    def put_provider_manifest(self, ds, manifest):
        key = f"tfi:providers:{ds}:latest"
        self.events.append(("manifest", key))
        super().put_provider_manifest(ds, manifest)

    def delete_provider_models(self, ds, provider):
        key = f"tfi:models:{ds}:{provider}:latest"
        self.events.append(("delete", key))
        super().delete_provider_models(ds, provider)