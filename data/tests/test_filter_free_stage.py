"""Tests for :class:`data.stages.filter_free.FilterFreeStage`.

The Stage now *qualifies* endpoints rather than filtering to free-only.
Per docs/tfi_model_endpoint_support_paid_model.md §5.1:

* Every eligible endpoint (free / paid / unknown) is kept.
* Only malformed records (missing required identity field) are dropped.
* ``pricing_status`` is classified per-provider when the parser did not
  already stamp it.
* Per-provider in/out/dropped metrics are recorded; ``dropped`` counts
  malformed rejections only.
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


def _ep(
    provider: str,
    free: bool,
    pricing_status: str | None = None,
    model_id: str = "x/1",
) -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
        model_id=model_id,
        free=free,
        pricing_status=pricing_status,
        fetched_at=datetime.now(timezone.utc),
        name=model_id.split("/")[-1],
        description="",
        capabilities={},
        architecture=None,
        metadata={},
    )


def _amd_ep(pricing_status: str | None = None, model_id: str = "x/1") -> dict:
    return {
        "data_source": "amd",
        "provider": "amd",
        "model_id": model_id,
        "free": pricing_status == "free",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id,
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
        "pricing_status": pricing_status,
    }


def _hf_ep(pricing_status: str | None = None, model_id: str = "x/1") -> dict:
    """Build a minimal HF-style dict endpoint for filter stage tests.
    
    Note: ``pricing_status`` parameter is accepted for backward compatibility
    but ignored — the endpoint's pricing classification is now the
    responsibility of the qualify stage.
    """
    return {
        "data_source": "huggingface",
        "provider": "huggingface",
        "model_id": model_id,
        "free": False,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id.split("/")[-1],
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
        "status": "live",
        "pricing": None,
    }


def test_filter_free_stage_keeps_all_eligible_endpoints():
    """All eligible endpoints (free / paid / unknown) are kept; none dropped
    for being non-free."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", pricing_status="paid", model_id="paid/b"),
            _ep("nvidia", pricing_status="priced", pricing_status="unknown", model_id="unknown/c"),
        ],
    }
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["nvidia"]
    assert [ep.model_id for ep in out] == ["free/a", "paid/b", "unknown/c"]


def test_filter_free_stage_drops_malformed_records():
    """Endpoints missing required identity fields are dropped."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "amd": [
            _amd_ep(pricing_status="free", model_id="MiMo"),
            {**_amd_ep(pricing_status="paid"), "model_id": None},  # malformed
            {**_amd_ep(pricing_status="unknown"), "provider": ""},  # malformed
        ],
    }
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["amd"]
    assert [ep["model_id"] for ep in out] == ["MiMo"]
    assert ctx.metrics["filter_free"]["amd"]["dropped"] == 2


def test_filter_free_stage_classifies_amd_missing_pricing_status():
    """AMD dict endpoints without pricing_status get it classified."""
    ctx = PipelineContext()
    ep = {**_amd_ep(pricing_status=None)}
    ep.pop("pricing", None)
    ctx.data["parsed"] = {"amd": [ep]}
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["amd"]
    assert out[0]["pricing_status"] == "unknown"


def test_filter_free_stage_classifies_hf_missing_pricing_status():
    """HF dict endpoints without pricing_status get it classified."""
    ctx = PipelineContext()
    ep = {**_hf_ep(pricing_status=None)}
    ep["pricing"] = {"input": 0, "output": 0}
    ctx.data["parsed"] = {"huggingface": [ep]}
    FilterFreeStage().execute(ctx)
    out = ctx.data["filtered"]["huggingface"]
    assert out[0]["pricing_status"] == "free"


def test_filter_free_stage_records_metrics_per_provider():
    """Per-provider in/out/dropped counters must be recorded."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", pricing_status="free"),
            _ep("nvidia", pricing_status="priced", pricing_status="paid"),
        ],
        "amd": [_amd_ep(pricing_status="free")],
        "huggingface": [_hf_ep(pricing_status="free"), _hf_ep(pricing_status="paid")],
    }
    FilterFreeStage().execute(ctx)
    metrics = ctx.metrics["filter_free"]
    assert metrics["nvidia"] == {"in": 2, "out": 2, "dropped": 0}
    assert metrics["amd"] == {"in": 1, "out": 1, "dropped": 0}
    assert metrics["huggingface"] == {"in": 2, "out": 2, "dropped": 0}


def test_filter_free_stage_aliases_parsed_for_downstream():
    """``parsed`` must point at the filtered output so NormalizeStage
    (which reads ``parsed``) sees the post-qualification data."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", pricing_status="paid", model_id="paid/b"),
        ],
    }
    FilterFreeStage().execute(ctx)
    assert [ep.model_id for ep in ctx.data["filtered"]["nvidia"]] == ["free/a", "paid/b"]
    assert ctx.data["parsed"] is ctx.data["filtered"]


def test_filter_free_stage_unknown_provider_passthrough():
    """Unknown providers pass through and are counted in metrics."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "weird-provider": [_ep("weird-provider", pricing_status="free", pricing_status="unknown")],
    }
    FilterFreeStage().execute(ctx)
    assert len(ctx.data["filtered"]["weird-provider"]) == 1
    assert ctx.metrics["filter_free"]["weird-provider"] == {
        "in": 1,
        "out": 1,
        "dropped": 0,
    }


def test_filter_free_stage_empty_parsed():
    """Empty / missing parsed dict must be a no-op, not a crash."""
    ctx = PipelineContext()
    FilterFreeStage().execute(ctx)
    assert ctx.data["filtered"] == {}
    assert ctx.data["parsed"] == {}

    ctx2 = PipelineContext()
    ctx2.data["parsed"] = {}
    FilterFreeStage().execute(ctx2)
    assert ctx2.data["filtered"] == {}


def test_filter_free_stage_is_idempotent():
    """Running the Stage twice on already-filtered data is a no-op."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", pricing_status="paid", model_id="paid/b"),
        ],
    }
    FilterFreeStage().execute(ctx)
    first = ctx.data["filtered"]["nvidia"]
    FilterFreeStage().execute(ctx)
    second = ctx.data["filtered"]["nvidia"]
    assert len(first) == len(second) == 2
    for m in ctx.metrics["filter_free"].values():
        assert m["dropped"] == 0


def test_filter_free_stage_stage_name():
    """The Stage exposes a stable ``name`` for logging / metrics."""
    assert FilterFreeStage.name == "filter_free"
