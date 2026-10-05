"""Regression test for NVIDIA token-subset identity matching.

NVIDIA ``nvidia/nemotron-3.5-lightning-30b-a3b`` only collides with
OR's shorter ``nvidia/nemotron-3.5-lightning`` via the matcher's
token-subset fallback. The NormalizeStage NVIDIA path must walk the
cross-source index via the matcher (not by a literal normalized-key
dict lookup) for that fallback to fire.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.stages.normalize import NormalizeStage


def _make_nvidia_ep(model_id: str, **overrides) -> ModelEndpoint:
    defaults = dict(
        provider="nvidia",
        data_source="nvidia",
        model_id=model_id,
        free=True,
        fetched_at=datetime.now(timezone.utc),
        description="NVIDIA raw",
        capabilities={},
        architecture={"input": [], "output": ["text"]},
        metadata={},
    )
    defaults.update(overrides)
    return ModelEndpoint(**defaults)


def test_nvidia_nemotron_token_subset_lookup_finds_or_observation():
    """NVIDIA's ``nvidia/nemotron-3.5-lightning-30b-a3b`` has a
    longer slug than OR's ``nvidia/nemotron-3.5-lightning``. The
    NormalizeStage NVIDIA path must use the matcher (not a literal
    normalized-key dict lookup) for token-subset fallback to fire.
    Without this fix the cross-source signals don't reach the
    endpoint.
    """
    nvidia_eps = [
        _make_nvidia_ep("nvidia/nemotron-3.5-lightning-30b-a3b"),
    ]
    or_models = [
        {
            "model_id": "nvidia/nemotron-3.5-lightning",
            "data_source": "openrouter",
            "description": "NVIDIA Nemotron 3.5 Lightning",
            "architecture": {"input": ["text"], "output": ["text"]},
            "context_length": 262144,
            "metadata": {
                "supported_parameters": ["reasoning", "tools", "tool_choice"],
                "reasoning": {"mandatory": False},
                "hugging_face_id": "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
            },
        },
    ]

    ctx = PipelineContext()
    ctx.data["parsed"] = {"nvidia": nvidia_eps}
    ctx.data["openrouter_models"] = or_models
    ctx.data["models_dev_models"] = []
    NormalizeStage().execute(ctx)

    ep = ctx.data["endpoints"][0]
    assert ep.capabilities["chat"] is True
    assert ep.capabilities["tool_calling"] is True
    assert ep.capabilities["reasoning"] is True


def test_nvidia_endpoint_no_cross_source_match_unchanged():
    """NVIDIA endpoints without a matching cross-source observation
    pass through with their primary-source signals unchanged."""
    nvidia_eps = [
        _make_nvidia_ep(
            "vendor/unrelated-model",
            description="Vendor native description",
            capabilities={"chat": True},
        ),
    ]
    or_models = [
        {
            "model_id": "nvidia/nemotron-3.5-lightning",
            "data_source": "openrouter",
            "description": "different model",
            "architecture": {"input": ["text"], "output": ["text"]},
            "context_length": 262144,
            "metadata": {"supported_parameters": ["reasoning"]},
        },
    ]

    ctx = PipelineContext()
    ctx.data["parsed"] = {"nvidia": nvidia_eps}
    ctx.data["openrouter_models"] = or_models
    ctx.data["models_dev_models"] = []
    NormalizeStage().execute(ctx)

    ep = ctx.data["endpoints"][0]
    assert ep.description == "Vendor native description"
    assert ep.capabilities == {"chat": True}
