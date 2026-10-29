"""Tests for :class:`data.stages.filter.FilterStage`.

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
from data.stages.filter import FilterStage



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
def _ep(provider: str, pricing_status: str | None = None, model_id: str = "x/1") -> "ModelEndpoint":
    from data.models.schema import ModelEndpoint
    from datetime import datetime, timezone
    return ModelEndpoint(
        provider=provider,
        model_id=model_id,
        data_source=provider,
        fetched_at=datetime.now(timezone.utc),
        pricing_status=pricing_status,
        name=model_id.split("/")[-1],
        description=None,
        capabilities={},
        architecture={"input": ["text"], "output": ["text"]},
        lab="test",
        metadata={},
    )


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


def test_filter_stage_keeps_all_eligible_endpoints():
    """All eligible endpoints (free / paid / unknown) are kept; none dropped
    for being non-free."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", model_id="paid/b"),
            _ep("nvidia", pricing_status="priced", model_id="unknown/c"),
        ],
    }
    FilterStage().execute(ctx)
    out = ctx.data["filtered"]["nvidia"]
    assert [ep.model_id for ep in out] == ["free/a", "paid/b", "unknown/c"]


def test_filter_stage_drops_malformed_records():
    """Endpoints missing required identity fields are dropped."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "amd": [
            _amd_ep(pricing_status="free", model_id="MiMo"),
            {**_amd_ep(pricing_status="paid"), "model_id": None},  # malformed
            {**_amd_ep(pricing_status="unknown"), "provider": ""},  # malformed
        ],
    }
    FilterStage().execute(ctx)
    out = ctx.data["filtered"]["amd"]
    assert [ep["model_id"] for ep in out] == ["MiMo"]
    assert ctx.metrics["filter"]["amd"]["dropped"] == 2


def test_filter_stage_records_metrics_per_provider():
    """Per-provider in/out/dropped counters must be recorded."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free"),
            _ep("nvidia", pricing_status="priced"),
        ],
        "amd": [_amd_ep(pricing_status="free")],
        "huggingface": [_hf_ep(pricing_status="free"), _hf_ep(pricing_status="paid")],
    }
    FilterStage().execute(ctx)
    metrics = ctx.metrics["filter"]
    assert metrics["nvidia"] == {"in": 2, "out": 2, "dropped": 0}
    assert metrics["amd"] == {"in": 1, "out": 1, "dropped": 0}
    assert metrics["huggingface"] == {"in": 2, "out": 2, "dropped": 0}


def test_filter_stage_aliases_parsed_for_downstream():
    """``parsed`` must point at the filtered output so NormalizeStage
    (which reads ``parsed``) sees the post-qualification data."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", model_id="paid/b"),
        ],
    }
    FilterStage().execute(ctx)
    assert [ep.model_id for ep in ctx.data["filtered"]["nvidia"]] == ["free/a", "paid/b"]
    assert ctx.data["parsed"] is ctx.data["filtered"]


def test_filter_stage_unknown_provider_passthrough():
    """Unknown providers pass through and are counted in metrics."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "weird-provider": [_ep("weird-provider", pricing_status="free")],
    }
    FilterStage().execute(ctx)
    assert len(ctx.data["filtered"]["weird-provider"]) == 1
    assert ctx.metrics["filter"]["weird-provider"] == {
        "in": 1,
        "out": 1,
        "dropped": 0,
    }


def test_filter_stage_empty_parsed():
    """Empty / missing parsed dict must be a no-op, not a crash."""
    ctx = PipelineContext()
    FilterStage().execute(ctx)
    assert ctx.data["filtered"] == {}
    assert ctx.data["parsed"] == {}

    ctx2 = PipelineContext()
    ctx2.data["parsed"] = {}
    FilterStage().execute(ctx2)
    assert ctx2.data["filtered"] == {}


def test_filter_stage_is_idempotent():
    """Running the Stage twice on already-filtered data is a no-op."""
    ctx = PipelineContext()
    ctx.data["parsed"] = {
        "nvidia": [
            _ep("nvidia", pricing_status="free", model_id="free/a"),
            _ep("nvidia", pricing_status="priced", model_id="paid/b"),
        ],
    }
    FilterStage().execute(ctx)
    first = ctx.data["filtered"]["nvidia"]
    FilterStage().execute(ctx)
    second = ctx.data["filtered"]["nvidia"]
    assert len(first) == len(second) == 2
    for m in ctx.metrics["filter"].values():
        assert m["dropped"] == 0


def test_filter_stage_stage_name():
    """The Stage exposes a stable ``name`` for logging / metrics."""
    assert FilterStage.name == "filter"
