"""Tests for :class:`data.stages.filter_free.FilterFreeStage`.

The Stage is a thin adapter over
:func:`data.providers.free_filter.filter_free`. Per-provider behaviour
is exercised in ``test_free_filter.py``; here we only assert the
Stage-level contract: dispatches per provider, writes ``filtered``,
records metrics, and aliases ``parsed`` for downstream readers.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
if str(_HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(_HERE.parents[1]))

from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.stages.filter_free import FilterFreeStage


def _ep(provider: str, free: bool, model_id: str = "x/1") -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
        model_id=model_id,
        free=free,
        fetched_at=datetime.now(timezone.utc),
        name=model_id.split("/")[-1],
        description="",
        capabilities={},
        architecture=None,
        metadata={},
    )


def _amd_ep(free: bool, model_id: str = "x/1") -> dict:
    return {
        "provider": "amd",
        "model_id": model_id,
        "free": free,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id,
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
    }


def _hf_ep(free: bool, model_id: str = "x/1") -> dict:
    return {
        "provider": "huggingface",
        "model_id": model_id,
        "free": free,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id.split("/")[-1],
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
    }


def test_filter_free_stage_drops_nvidia_non_free():
    """NVIDIA endpoints with free=False are dropped."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", free=True, model_id="free/a"),
            _ep("nvidia", free=False, model_id="runanywhere/b"),
        ],
    }
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["nvidia"]
    assert [ep.model_id for ep in out] == ["free/a"]


def test_filter_free_stage_drops_amd_non_free():
    """AMD endpoints with free=False are dropped."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "amd": [
            _amd_ep(free=True, model_id="MiMo"),
            _amd_ep(free=False, model_id="SomePaid"),
        ],
    }
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["amd"]
    assert [ep["model_id"] for ep in out] == ["MiMo"]


def test_filter_free_stage_passes_hf_through():
    """HF filter is a defensive pass-through; the parser already filters."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "huggingface": [_hf_ep(free=True), _hf_ep(free=True)],
    }
    FilterFreeStage().execute(ctx)
    assert len(ctx.data["filtered"]["huggingface"]) == 2


def test_filter_free_stage_records_metrics_per_provider():
    """Per-provider in/out/dropped counters must be recorded."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", free=True),
            _ep("nvidia", free=False),
            _ep("nvidia", free=True),
            _ep("nvidia", free=False),
        ],
        "amd": [_amd_ep(free=True)],
        "huggingface": [_hf_ep(free=True), _hf_ep(free=True)],
    }
    FilterFreeStage().execute(ctx)
    metrics = ctx.metrics["filter_free"]
    assert metrics["nvidia"] == {"in": 4, "out": 2, "dropped": 2}
    assert metrics["amd"] == {"in": 1, "out": 1, "dropped": 0}
    assert metrics["huggingface"] == {"in": 2, "out": 2, "dropped": 0}


def test_filter_free_stage_aliases_parsed_for_downstream():
    """``parsed`` must point at the filtered output so NormalizeStage
    sees only free endpoints (without needing to read ``filtered``)."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [_ep("nvidia", free=False)],
    }
    FilterFreeStage().execute(ctx)
    assert ctx.data["parsed"]["nvidia"] == []
    assert ctx.data["filtered"]["nvidia"] == []


def test_filter_free_stage_unknown_provider_passthrough():
    """Unknown providers pass through and are counted in metrics."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "future_provider": [_ep("future_provider", free=False)],
    }
    FilterFreeStage().execute(ctx)
    assert len(ctx.data["filtered"]["future_provider"]) == 1
    assert ctx.metrics["filter_free"]["future_provider"] == {
        "in": 1,
        "out": 1,
        "dropped": 0,
    }


def test_filter_free_stage_empty_parsed():
    """Empty / missing parsed dict must be a no-op, not a crash."""
    ctx = PipelineContext()
    FilterFreeStage().execute(ctx)
    assert ctx.data["filtered"] == {}
    assert ctx.metrics["filter_free"] == {}

    ctx2 = PipelineContext()
    ctx2.data["parsed"] = None
    FilterFreeStage().execute(ctx2)
    assert ctx2.data["filtered"] == {}


def test_filter_free_stage_is_idempotent():
    """Running the Stage twice on already-filtered data is a no-op."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [_ep("nvidia", free=True)],
        "amd": [_amd_ep(free=False)],
    }
    FilterFreeStage().execute(ctx)
    snapshot = {k: list(v) for k, v in ctx.data["filtered"].items()}
    metrics_before = dict(ctx.metrics["filter_free"])

    FilterFreeStage().execute(ctx)

    # Same endpoints survive (already filtered); metrics get re-counted
    # (in == out == 0 dropped for all providers).
    for provider, endpoints in snapshot.items():
        assert ctx.data["filtered"][provider] == endpoints
    for provider, m in metrics_before.items():
        new_m = ctx.metrics["filter_free"][provider]
        assert new_m["in"] == m["out"]
        assert new_m["out"] == m["out"]
        assert new_m["dropped"] == 0


def test_filter_free_stage_stage_name():
    """The Stage exposes a stable ``name`` for logging / metrics."""
    assert FilterFreeStage.name == "filter_free"