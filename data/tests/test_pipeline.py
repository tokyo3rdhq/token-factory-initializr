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
    StoreStage,
    SummarizeStage,
    ValidateStage,
    build_default_pipeline,
)


def _mk_ep(provider: str, model_id: str) -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
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


def test_default_pipeline_has_eight_stages_in_canonical_order():
    p = build_default_pipeline()
    assert [s.name for s in p.stages] == [
        "fetch", "parse", "normalize", "validate", "enrich",
        "summarize", "store", "notify",
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


def test_provider_registry_lists_three_providers():
    assert {n for n, _ in PROVIDER_FETCHERS} == {"nvidia", "amd", "huggingface"}


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
        "amd": [{"provider": "amd", "model_id": "model_gateway:MiMo", "free": True}],
    }
    out = NormalizeStage().execute(ctx)
    assert len(out.data["endpoints"]) == 1
    assert isinstance(out.data["endpoints"][0], ModelEndpoint)


def test_validate_stage_splits_valid_invalid():
    ctx = PipelineContext()
    ctx.data["endpoints"] = [_mk_ep("amd", "good"), _mk_ep("openai", "bad")]
    out = ValidateStage().execute(ctx)
    assert len(out.data["valid"]) == 1
    assert len(out.data["invalid"]) == 1


def test_enrich_stage_forwards_valid_to_enriched():
    a1 = _mk_ep("amd", "x/1")
    a2 = _mk_ep("nvidia", "y/2")
    ctx = PipelineContext()
    ctx.data["valid"] = [a1, a2]
    out = EnrichStage().execute(ctx)
    # EnrichStage is currently a placeholder; same-model-across-providers
    # is preserved (doc §12) rather than deduplicated.
    assert out.data["enriched"] == [a1, a2]
    # Same-model-different-provider must coexist as separate endpoints.
    b1 = _mk_ep("nvidia", "google/gemma-4")
    b2 = _mk_ep("amd", "google/gemma-4")
    ctx2 = PipelineContext()
    ctx2.data["valid"] = [b1, b2]
    out2 = EnrichStage().execute(ctx2)
    assert len(out2.data["enriched"]) == 2
    assert out2.artifacts["enrich_facts"] == []


def test_summarize_stage_populates_manifest_artifact():
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1"), _mk_ep("nvidia", "y/1")]
    ctx.state["fetch_errors"] = {"huggingface": "Network timeout"}
    out = SummarizeStage().execute(ctx)
    assert out.artifacts["manifest"]["total"] == 2
    assert out.artifacts["manifest"]["providers"]["amd"]["count"] == 1
    assert out.artifacts["manifest"]["providers"]["huggingface"]["status"] == "failed"


def test_store_stage_records_error_when_kv_env_missing():
    """When KV env vars are missing, StoreStage must record to context.errors
    (so NotifyStage can fire an alert) instead of silently no-opping."""
    import os

    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
    ctx.artifacts["manifest"] = {"version": "2026-09-24", "total": 1, "providers": {}}

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CLOUDFLARE_ACCOUNT_ID", None)
        os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        os.environ.pop("CLOUDFLARE_KV_NAMESPACE_ID", None)
        out = StoreStage().execute(ctx)
    assert out is ctx
    # Severe error must be recorded, not swallowed.
    assert any(e["stage"] == "store" for e in ctx.errors)


def test_store_stage_records_error_when_kv_put_fails():
    """When KV put raises, StoreStage must record the per-key error."""
    class BrokenKV:
        def __init__(self):
            self.account_id = "x"
            self.api_token = "y"
        def put_snapshot(self, provider, models):
            raise RuntimeError("upstream 500")
        def put(self, key, value, ttl=None):
            raise RuntimeError("upstream 500")

    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
    ctx.artifacts["manifest"] = {"version": "2026-09-24", "total": 1, "providers": {}}
    StoreStage(kv=BrokenKV()).execute(ctx)
    assert any("put_snapshot(amd)" in e["error"] for e in ctx.errors)


def test_store_stage_records_partial_failure_but_continues():
    """A failure for one provider must not block writes to others."""
    from data.storage.cloudflare_kv import model_key

    class PartialKV:
        def __init__(self):
            self.written = {}
            self.account_id = "x"
            self.api_token = "y"
        def put_snapshot(self, provider, models):
            if provider == "amd":
                raise RuntimeError("upstream 500")
            self.written[model_key(provider)] = (provider, models)
        def put(self, key, value, ttl=None):
            self.written[key] = value

    kv = PartialKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1"), _mk_ep("nvidia", "y/1")]
    ctx.artifacts["manifest"] = {"version": "2026-09-24", "total": 2, "providers": {}}
    StoreStage(kv=kv).execute(ctx)
    assert any("put_snapshot(amd)" in e["error"] for e in ctx.errors)
    # NVIDIA write still happened despite AMD failing.
    assert model_key("nvidia") in kv.written


def test_store_stage_writes_dated_manifest_snapshot():
    """In addition to tfi:manifest:latest, the stage writes tfi:manifest:<YYYY-MM-DD>.

    The dated key lets the GitHub Actions "Validate results" step verify the
    write happened today without depending on previous-run state still at
    tfi:manifest:latest.
    """
    from datetime import datetime, timezone
    from data.storage.cloudflare_kv import manifest_key

    class RecordingKV:
        def __init__(self):
            self.written = {}
            self.account_id = "x"
            self.api_token = "y"
        def put_snapshot(self, provider, models):
            from data.storage.cloudflare_kv import model_key
            self.written[model_key(provider)] = models
        def put(self, key, value, ttl=None):
            self.written[key] = value

    kv = RecordingKV()
    ctx = PipelineContext()
    ctx.data["enriched"] = [_mk_ep("amd", "x/1")]
    ctx.artifacts["manifest"] = {"version": "2026-09-24", "total": 1, "providers": {}}
    StoreStage(kv=kv).execute(ctx)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_key = manifest_key(today)
    assert dated_key in kv.written, f"expected {dated_key} in {list(kv.written)}"
    assert kv.written[manifest_key()] == kv.written[dated_key]


def test_store_stage_dated_key_uses_utc_not_local():
    """The dated key must use UTC, not local time, so multi-region CI runs
    produce the same key on the same calendar day."""
    from data.stages.store import _today_key
    today = _today_key()
    assert today.startswith("tfi:manifest:")
    # "tfi:manifest:" (13 chars) + "YYYY-MM-DD" (10 chars) = 23 chars.
    assert len(today) == 23
    date_part = today.removeprefix("tfi:manifest:")
    from datetime import datetime
    datetime.strptime(date_part, "%Y-%m-%d")


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
        "amd": [{"provider": "amd", "model_id": "model_gateway:MiMo", "free": True}],
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