"""Pipeline DSL tests.

Per docs/arch_pipeline.md §15, these tests verify:

1. `.then()` can register Stages sequentially
2. Stages execute in registration order
3. Context is passed between Stages
4. `.end()` does NOT auto-execute
5. `.run()` executes the pipeline
6. Stage failure is correctly handled by Pipeline (recording + abort)
7. PipelineSummary contains per-stage metrics

Pipeline / Stage / Context / execution order are the only things tested
here. Business logic (normalize, validate, etc.) is tested in
``test_process.py`` / ``test_providers.py`` and is NOT re-tested here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import patch

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timezone

from data.models.schema import ModelEndpoint
from data.pipeline import Pipeline, PipelineContext, PipelineResult, StageResult, StageStatus
from data.stages import (
    EnrichStage,
    FetchStage,
    NormalizeStage,
    NotifyStage,
    ParseStage,
    PROVIDER_FETCHERS,
    SummarizeStage,
    ValidateStage,
    build_default_pipeline,
)


def _mk_ep(provider: str, model_id: str) -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
        data_source=provider,
        model_id=model_id,
        free=True,
        fetched_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# DSL: definition + composition
# ---------------------------------------------------------------------------


def test_pipeline_then_returns_self_for_chaining():
    p = Pipeline()
    stage_a = ParseStage()
    stage_b = NormalizeStage()
    same = p.then(stage_a).then(stage_b)
    assert same is p
    assert len(p) == 2


def test_pipeline_end_does_not_execute():
    """Per spec §3, .end() marks definition as complete; it must NOT execute."""
    executed: List[str] = []

    class RecordingStage:
        name = "record"

        def execute(self, context: PipelineContext) -> PipelineContext:
            executed.append("ran")
            return context

    p = Pipeline().then(RecordingStage()).end()
    assert executed == []


def test_pipeline_end_returns_pipeline():
    p = Pipeline()
    assert p.end() is p


def test_default_pipeline_has_twelve_stages_in_canonical_order():
    """Per refactor doc §6:

        fetch → parse → filter_free → normalize → validate → enrich
        → snapshot → diff → reconcile → publish → summarize → notify
    """
    p = build_default_pipeline()
    assert [s.name for s in p.stages] == [
        "fetch", "parse", "filter_free", "normalize", "validate", "enrich",
        "snapshot", "diff", "reconcile", "publish",
        "summarize", "notify",
    ]


def test_default_pipeline_does_not_import_pipeline_in_misplaced_way():
    """Sanity: pipeline/ package must not import from stages/."""
    from data import pipeline as pkg

    # pipeline package must remain free of business-specific imports.
    # (We allow it to import context/stage/result/pipeline modules of itself.)
    src = Path(pkg.__file__).parent
    for f in src.glob("*.py"):
        if f.name == "__init__.py":
            continue
        text = f.read_text()
        assert "data.stages" not in text, (
            f"pipeline/{f.name} must not import data.stages "
            f"(one-way dependency: main → pipeline → stages)"
        )


def test_provider_registry_lists_all_providers():
    assert {n for n, _ in PROVIDER_FETCHERS} == {
        "nvidia", "amd", "huggingface", "openrouter", "models_dev",
    }


# ---------------------------------------------------------------------------
# Execution: order, context, error handling, metrics
# ---------------------------------------------------------------------------


def test_run_executes_stages_in_order():
    seen: List[str] = []

    class OrderStage:
        def __init__(self, name: str) -> None:
            self.name = name

        def execute(self, context: PipelineContext) -> PipelineContext:
            seen.append(self.name)
            return context

    result = (
        Pipeline()
        .then(OrderStage("a"))
        .then(OrderStage("b"))
        .then(OrderStage("c"))
        .end()
        .run()
    )
    assert seen == ["a", "b", "c"]
    assert len(result.stages) == 3
    assert all(s.status == StageStatus.SUCCESS for s in result.stages)


def test_run_passes_context_between_stages():
    ctx = PipelineContext()
    ctx.data["seed"] = 0

    class AppendStage:
        def __init__(self, name: str, key: str, value: int) -> None:
            self.name = name
            self.key = key
            self.value = value

        def execute(self, context: PipelineContext) -> PipelineContext:
            context.data[self.key] = self.value
            return context

    result = (
        Pipeline()
        .then(AppendStage("a", "k1", 1))
        .then(AppendStage("b", "k2", 2))
        .then(AppendStage("c", "k3", 3))
        .end()
        .run(ctx)
    )

    assert ctx.data == {"seed": 0, "k1": 1, "k2": 2, "k3": 3}
    assert result.context is ctx


def test_run_handles_stage_exception_and_aborts():
    class BoomStage:
        name = "boom"

        def execute(self, context: PipelineContext) -> PipelineContext:
            raise RuntimeError("intentional failure")

    class SentinelStage:
        """Sentinel stage must still run after a failure so NotifyStage can alert."""

        name = "sentinel"

        def execute(self, context: PipelineContext) -> PipelineContext:
            return context  # observe it ran

    result = (
        Pipeline()
        .then(BoomStage())
        .then(SentinelStage())
        .end()
        .run()
    )

    # Pipeline aborts on first failure but continues running so NotifyStage
    # can fire the failure alert (see data/stages/notify.py).
    assert result.aborted is True
    assert len(result.stages) == 2
    assert result.status_by_name() == {"boom": StageStatus.FAILED, "sentinel": StageStatus.SUCCESS}
    assert result.stages[0].error is not None
    assert "intentional failure" in result.stages[0].error
    # Context.errors must record the failure
    assert any(e["stage"] == "boom" for e in result.context.errors)


def test_run_starts_with_no_context_default():
    """Per spec §6, run() must accept no context and use a fresh one."""
    result = Pipeline().end().run()
    assert isinstance(result.context, PipelineContext)


def test_run_records_per_stage_duration():
    class SleepStage:
        def __init__(self, name: str, ms: int) -> None:
            self.name = name
            self._ms = ms

        def execute(self, context: PipelineContext) -> PipelineContext:
            import time
            time.sleep(self._ms / 1000.0)
            return context

    result = (
        Pipeline()
        .then(SleepStage("a", 10))
        .then(SleepStage("b", 20))
        .end()
        .run()
    )

    durations = {s.name: s.duration_s for s in result.stages}
    assert durations["a"] >= 0.01
    assert durations["b"] >= 0.02
    assert result.total_s >= 0.03


def test_pipeline_result_summary_lines_are_stable():
    result = Pipeline().then(ParseStage()).end().run()
    lines = result.summary_lines()
    assert lines[0].startswith("stage")
    assert any("parse" in line for line in lines)
    assert any(line.startswith("total") for line in lines)


# ---------------------------------------------------------------------------
# Behavior preservation: the canonical pipeline must still produce the
# same logical outcome when run with mocked providers (no network).
# ---------------------------------------------------------------------------


def test_normalize_stage_passes_nvidia_endpoints_through_unchanged():
    ep = _mk_ep("nvidia", "google/gemma")
    ctx = PipelineContext()
    ctx.data["parsed"] = {"nvidia": [ep]}
    out = NormalizeStage().execute(ctx)
    assert out.data["endpoints"][0] is ep


def test_normalize_stage_calls_normalize_endpoints_for_amd_dicts():
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "amd": [{"provider": "amd", "model_id": "MiMo", "free": True}],
    }
    out = NormalizeStage().execute(ctx)
    assert len(out.data["endpoints"]) == 1
    assert isinstance(out.data["endpoints"][0], ModelEndpoint)


def test_validate_stage_splits_valid_invalid():
    ctx = PipelineContext()
    ctx.data["endpoints"] = [_mk_ep("amd", "good"), _mk_ep("amd", "bad id")]
    out = ValidateStage().execute(ctx)
    assert len(out.data["valid"]) == 1
    assert len(out.data["invalid"]) == 1


def test_enrich_stage_forwards_valid_to_enriched():
    a1 = _mk_ep("amd", "x/1")
    a2 = _mk_ep("nvidia", "y/2")
    ctx = PipelineContext()
    ctx.data["valid"] = [a1, a2]
    ctx.data["openrouter_models"] = []
    out = EnrichStage().execute(ctx)
    # EnrichStage preserves same-model-across-providers (doc §12) rather
    # than deduplicating. With no OpenRouter observations, no provenance
    # is added and the records pass through unchanged.
    assert out.data["enriched"] == [a1, a2]
    assert all(ep.provenance == {} for ep in out.data["enriched"])
    # Same-model-different-provider must coexist as separate endpoints.
    b1 = _mk_ep("nvidia", "google/gemma-4")
    b2 = _mk_ep("amd", "google/gemma-4")
    ctx2 = PipelineContext()
    ctx2.data["valid"] = [b1, b2]
    ctx2.data["openrouter_models"] = []
    out2 = EnrichStage().execute(ctx2)
    assert len(out2.data["enriched"]) == 2
    facts = out2.artifacts["enrich_facts"]
    assert facts["total_endpoints"] == 2
    assert facts["openrouter_matches"] == 0
    assert facts["total_provenance_additions"] == 0


def test_summarize_stage_populates_manifest_artifact():
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1"), _mk_ep("nvidia", "y/1")]
    ctx.state["fetch_errors"] = {"huggingface": "Network timeout"}
    out = SummarizeStage().execute(ctx)
    assert out.artifacts["manifest"]["total"] == 2
    assert out.artifacts["manifest"]["providers"]["amd"]["count"] == 1
    assert out.artifacts["manifest"]["providers"]["huggingface"]["status"] == "failed"


def test_notify_stage_does_not_raise_when_webhook_unset():
    ctx = PipelineContext()
    ctx.artifacts["manifest"] = {"total": 0, "providers": {}}
    out = NotifyStage().execute(ctx)
    assert out is ctx


def test_notify_stage_fires_alert_on_errors():
    """When context.errors is non-empty, NotifyStage must call send_alert."""
    ctx = PipelineContext()
    ctx.artifacts["manifest"] = {"total": 0, "providers": {}}
    ctx.errors.append({"stage": "store", "error": "KV init failed"})
    with patch("data.stages.notify.send_alert") as mock_alert, \
         patch("data.stages.notify.send_summary"):
        NotifyStage().execute(ctx)
    mock_alert.assert_called_once()
    msg = mock_alert.call_args[0][0]
    assert "store" in msg
    assert "KV init failed" in msg


def test_notify_stage_skips_alert_when_no_errors():
    """Without context.errors, NotifyStage must NOT call send_alert."""
    ctx = PipelineContext()
    ctx.artifacts["manifest"] = {"total": 0, "providers": {}}
    with patch("data.stages.notify.send_alert") as mock_alert, \
         patch("data.stages.notify.send_summary"):
        NotifyStage().execute(ctx)
    mock_alert.assert_not_called()


def test_parse_stage_forwards_fetched_data():
    ctx = PipelineContext()
    ctx.data["fetched"] = {
        "amd": [{"provider": "amd", "model_id": "x", "free": True}],
        "nvidia": [_mk_ep("nvidia", "y")],
    }
    out = ParseStage().execute(ctx)
    assert set(out.data["parsed"].keys()) == {"amd", "nvidia"}
    assert out.data["parsed"]["amd"][0]["model_id"] == "x"


# ---------------------------------------------------------------------------
# End-to-end DSL run with mocked fetchers
# ---------------------------------------------------------------------------


def test_dsl_full_run_with_mocked_providers():
    """End-to-end: every Stage runs, manifest is built, no exceptions raised."""
    fake_fetched = {
        "nvidia": [_mk_ep("nvidia", "google/gemma")],
        "amd": [{"provider": "amd", "model_id": "MiMo", "free": True}],
        "huggingface": [{
            "provider": "huggingface",
            "model_id": "meta-llama/Llama-3.2-3B",
            "free": True,
        }],
    }

    def fake_fetch_all_async(_providers):
        import asyncio
        async def _coro():
            return fake_fetched, {}
        return _coro()

    with patch("data.stages.fetch._fetch_all_async", fake_fetch_all_async):
        pipeline = (
            Pipeline()
            .then(FetchStage())
            .then(ParseStage())
            .then(NormalizeStage())
            .then(ValidateStage())
            .then(EnrichStage())
            .then(SummarizeStage())
            .end()
        )
        result = pipeline.run()

    assert result.aborted is False
    manifest = result.context.artifacts["manifest"]
    assert manifest["total"] == 3


def test_dsl_partial_failure_isolated():
    """If one provider fails, others' data must survive (AGENTS.md §10)."""
    fake_fetched = {
        "nvidia": [_mk_ep("nvidia", "x/y")],
        "amd": [],
        "huggingface": [],
    }
    fake_errors = {"huggingface": "Network error"}

    def fake_fetch_all_async(_providers):
        import asyncio
        async def _coro():
            return fake_fetched, fake_errors
        return _coro()

    with patch("data.stages.fetch._fetch_all_async", fake_fetch_all_async):
        pipeline = (
            Pipeline()
            .then(FetchStage())
            .then(ParseStage())
            .then(NormalizeStage())
            .then(ValidateStage())
            .then(EnrichStage())
            .then(SummarizeStage())
            .end()
        )
        result = pipeline.run()

    manifest = result.context.artifacts["manifest"]
    assert manifest["providers"]["nvidia"]["status"] == "success"
    assert manifest["providers"]["huggingface"]["status"] == "failed"
    assert manifest["providers"]["huggingface"]["error"] == "Network error"


# ---------------------------------------------------------------------------
# Stage protocol conformance
# ---------------------------------------------------------------------------


def test_every_default_stage_satisfies_stage_protocol():
    p = build_default_pipeline()
    for s in p.stages:
        # name is a non-empty str
        assert isinstance(s.name, str) and s.name
        # callable execute
        assert callable(getattr(s, "execute", None))


def test_fetch_stage_providers_injectable():
    """Spec §12: adding a new provider should not require pipeline edits."""
    def fake_provider():
        return [_mk_ep("openrouter", "openrouter/auto")]

    custom = FetchStage(providers=[("openrouter", fake_provider)])
    assert ("openrouter", fake_provider) in custom.providers

def test_summarize_stage_writes_aggregated_manifest_to_kv():
    """SummarizeStage must write tfi:manifest:latest and the dated copy.

    Refactor Phase 5 fix: StoreStage was deleted, so the aggregated
    manifest write moved here. The CI Validate step depends on the
    dated key being present.
    """
    from data.storage.cloudflare_kv import manifest_key

    class RecordingKV:
        def __init__(self):
            self.written: dict[str, dict] = {}
            self.account_id = "x"
            self.api_token = "y"
        def put(self, key, value, ttl=None):
            self.written[key] = value
        def from_env(cls):
            raise RuntimeError("from_env must not be used; kv was injected")

    kv = RecordingKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1"), _mk_ep("nvidia", "y/1")]
    ctx.state["fetch_errors"] = {}
    out = SummarizeStage(kv=kv).execute(ctx)
    assert out is ctx
    assert manifest_key() in kv.written, "tfi:manifest:latest must be written"
    today = datetime.utcnow().strftime("%Y-%m-%d")
    dated_key = manifest_key(today)
    assert dated_key in kv.written, f"{dated_key} must be written"
    assert kv.written[manifest_key()] == kv.written[dated_key]


def test_summarize_stage_records_kv_init_error():
    """When KV init fails, SummarizeStage records to context.errors."""
    from data.stages.summarize import SummarizeStage

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("CLOUDFLARE_ACCOUNT_ID", None)
        os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        os.environ.pop("CLOUDFLARE_KV_NAMESPACE_ID", None)
        ctx = PipelineContext()
        ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
        SummarizeStage().execute(ctx)
    assert any(e["stage"] == "summarize" for e in ctx.errors)


# ---------------------------------------------------------------------------
# Manifest regression guard (SummarizeStage sanity check)
#
# Guards against the 2026-10-08 incident where a stale local
# ``python main.py`` run with pre-refactor code clobbered the
# production tfi:manifest:latest (962 -> 1 endpoints). The guard
# refuses the write when the new total drops sharply vs. the old;
# the dated daily snapshot is still written so today's record is
# preserved.
# ---------------------------------------------------------------------------


def test_summarize_guard_trips_on_regression():
    """A new manifest with <50% of the previous total aborts the
    tfi:manifest:latest write and surfaces to context.errors.
    The dated key is still written so today's record survives."""
    from data.stages.summarize import SummarizeStage

    class FakeKV:
        def __init__(self, previous):
            self.previous = previous
            self.written: dict[str, dict] = {}
        def get(self, key):
            return self.previous
        def put(self, key, value, ttl=None):
            self.written[key] = value
        def from_env(cls):
            raise RuntimeError("from_env must not be used; kv was injected")

    # Healthy production state at 962 endpoints; clobber attempt
    # produces 1 endpoint (the broken-run shape we saw 2026-10-08).
    kv = FakeKV(previous={
        "version": "2026-10-08",
        "generated_at": "2026-10-08T05:00:00+00:00",
        "total": 962,
        "providers": {},
    })

    ctx = PipelineContext()
    # 1 endpoint, same shape as the clobbering run that wiped prod.
    ctx.data["enriched"] = [_mk_ep("nvidia", "nvidia/legacy")]
    ctx.state["fetch_errors"] = {}
    SummarizeStage(kv=kv).execute(ctx)

    # tfi:manifest:latest was NOT overwritten.
    from data.storage.cloudflare_kv import manifest_key
    assert manifest_key() not in kv.written, (
        "guard must refuse to overwrite tfi:manifest:latest on regression"
    )
    # Dated daily snapshot WAS written so today's record survives.
    from datetime import datetime as _dt
    today = manifest_key(_dt.utcnow().strftime("%Y-%m-%d"))
    assert today in kv.written, (
        "dated daily snapshot must still be written when guard trips"
    )
    # The regression surfaces to context.errors with diagnostic data.
    guard_errors = [e for e in ctx.errors if "manifest regression guard" in e.get("error", "")]
    assert len(guard_errors) == 1, ctx.errors
    err = guard_errors[0]
    assert err["stage"] == "summarize"
    assert err["old_total"] == 962
    assert err["new_total"] == 1


def test_summarize_guard_skips_when_old_total_is_zero():
    """First-ever run (old manifest missing/empty) bypasses the guard."""
    from data.stages.summarize import SummarizeStage

    class FakeKV:
        def __init__(self):
            self.written: dict[str, dict] = {}
        def get(self, key):
            return None
        def put(self, key, value, ttl=None):
            self.written[key] = value
        def from_env(cls):
            raise RuntimeError("from_env must not be used; kv was injected")

    kv = FakeKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
    ctx.state["fetch_errors"] = {}
    SummarizeStage(kv=kv).execute(ctx)

    from data.storage.cloudflare_kv import manifest_key
    # Guard skipped: latest key IS written.
    assert manifest_key() in kv.written
    # No regression error recorded.
    assert not any("manifest regression guard" in e.get("error", "") for e in ctx.errors)


def test_summarize_guard_accepts_normal_fluctuation():
    """Small shrink (e.g. 962 -> 900 = 6.4% drop) is not a regression."""
    from data.stages.summarize import SummarizeStage

    class FakeKV:
        def __init__(self, previous):
            self.previous = previous
            self.written: dict[str, dict] = {}
        def get(self, key):
            return self.previous
        def put(self, key, value, ttl=None):
            self.written[key] = value
        def from_env(cls):
            raise RuntimeError("from_env must not be used; kv was injected")

    kv = FakeKV(previous={
        "version": "2026-10-08",
        "total": 1000,
        "providers": {},
    })

    ctx = PipelineContext()
    # 900 endpoints = 90% of old; well above the 50% threshold.
    ctx.data["enriched"] = [_mk_ep("amd", f"x/{i}") for i in range(900)]
    ctx.state["fetch_errors"] = {}
    SummarizeStage(kv=kv).execute(ctx)

    from data.storage.cloudflare_kv import manifest_key
    assert manifest_key() in kv.written
    assert not any("manifest regression guard" in e.get("error", "") for e in ctx.errors)


def test_summarize_guard_survives_kv_get_failure():
    """If the guard's GET fails (network, 5xx), the write still proceeds.

    We don't want a transient KV hiccup to block every daily run."""
    from data.stages.summarize import SummarizeStage

    class FakeKV:
        def __init__(self):
            self.written: dict[str, dict] = {}
            self.get_attempts = 0
        def get(self, key):
            self.get_attempts += 1
            raise RuntimeError("transient KV GET failure")
        def put(self, key, value, ttl=None):
            self.written[key] = value
        def from_env(cls):
            raise RuntimeError("from_env must not be used; kv was injected")

    kv = FakeKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
    ctx.state["fetch_errors"] = {}
    SummarizeStage(kv=kv).execute(ctx)

    from data.storage.cloudflare_kv import manifest_key
    assert kv.get_attempts == 1
    # Write proceeded despite the GET failure.
    assert manifest_key() in kv.written
