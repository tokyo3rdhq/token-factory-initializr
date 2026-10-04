"""Unit tests for the NVIDIA cross-source signal path in
``data.stages.normalize._apply_cross_source_signals_to_nvidia_endpoint``.

NVIDIA's provider constructs ``ModelEndpoint`` objects directly with
``architecture`` derived from labels (often empty input) and
``capabilities`` from legacy attributes (often empty for live RSC).
When an OpenRouter / models.dev observation matches, the normalize
stage merges those signals into the NVIDIA endpoint so capability
flags like ``vision``, ``tool_calling``, ``reasoning`` light up.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data.models.schema import ModelEndpoint
from data.stages.normalize import (
    _apply_cross_source_signals_to_nvidia_endpoint,
    _build_cross_source_index,
)
from data.identity_matcher import _normalize_id


def _make_nvidia_ep(model_id: str = "z-ai/glm-5-3-flash", **overrides) -> ModelEndpoint:
    defaults = dict(
        provider="nvidia",
        data_source="nvidia",
        model_id=model_id,
        free=True,
        fetched_at=datetime.now(timezone.utc),
        description="NVIDIA raw description",
        capabilities={"chat": True},
        architecture={"input": [], "output": ["text"]},
        metadata={},
    )
    defaults.update(overrides)
    return ModelEndpoint(**defaults)


def _or_obs(model_id: str = "z-ai/glm-5.3-flash", **overrides) -> dict:
    defaults = {
        "model_id": model_id,
        "data_source": "openrouter",
        "description": "GLM-5.3-Flash is a native multimodal model from Z.ai.",
        "architecture": {"input": ["text", "image", "video"], "output": ["text"]},
        "context_length": 1048576,
        "metadata": {
            "supported_parameters": ["tools", "tool_choice", "reasoning"],
            "reasoning": {"default_enabled": True},
        },
    }
    if "architecture" in overrides:
        defaults["architecture"] = overrides.pop("architecture")
    defaults.update(overrides)
    if "metadata" in overrides:
        defaults["metadata"] = {**defaults["metadata"], **overrides["metadata"]}
    return defaults


def _md_obs(model_id: str = "openbmb/minicpm5-2b", **overrides) -> dict:
    defaults = {
        "model_id": model_id,
        "data_source": "models_dev",
        "description": "Dense 2B-class open-source model for on-device use.",
        "architecture": {"input": ["text"], "output": ["text"]},
        "context_length": 131072,
        "metadata": {
            "supported_parameters": ["tools", "tool_choice", "reasoning"],
            "reasoning": {"default_enabled": False},
        },
    }
    defaults.update(overrides)
    if "metadata" in overrides:
        defaults["metadata"] = {**defaults["metadata"], **overrides["metadata"]}
    return defaults


# ---------------------------------------------------------------------------
# architecture merging
# ---------------------------------------------------------------------------


def test_or_image_input_merges_into_architecture():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(), [_or_obs()],
    )
    assert ep.architecture["input"] == ["text", "image", "video"]
    assert ep.architecture["output"] == ["text"]


def test_or_modalities_union_with_existing_nvidia_modalities():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(architecture={"input": ["audio"], "output": ["audio"]}),
        [_or_obs()],
    )
    assert "audio" in ep.architecture["input"]
    assert "image" in ep.architecture["input"]
    assert "video" in ep.architecture["input"]
    assert ep.architecture["output"] == ["audio", "text"]


def test_empty_existing_architecture_filled_from_or():
    ep = _make_nvidia_ep(architecture=None)
    ep2 = _apply_cross_source_signals_to_nvidia_endpoint(ep, [_or_obs()])
    assert ep2.architecture == {"input": ["text", "image", "video"], "output": ["text"]}


# ---------------------------------------------------------------------------
# capability merging
# ---------------------------------------------------------------------------


def test_or_image_modality_promotes_vision():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(), [_or_obs()],
    )
    assert ep.capabilities["vision"] is True


def test_or_audio_output_promotes_speech():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(),
        [_or_obs(architecture={"input": ["text"], "output": ["audio"]})],
    )
    assert ep.capabilities["speech"] is True


def test_or_embedding_output_promotes_embedding():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(capabilities={}),
        [_or_obs(architecture={"input": ["text"], "output": ["embedding"]})],
    )
    assert ep.capabilities["embedding"] is True
    assert ep.capabilities.get("chat", False) is False


def test_or_tools_param_promotes_tool_calling():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(), [_or_obs()],
    )
    assert ep.capabilities["tool_calling"] is True


def test_or_reasoning_supported_parameter_promotes_reasoning():
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(), [_or_obs()],
    )
    assert ep.capabilities["reasoning"] is True


def test_existing_native_capability_preserved():
    """If NVIDIA already set chat (from legacy attributes), cross-source
    signals don't override or remove it — only add what's missing."""
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(capabilities={"chat": True, "tool_calling": True}),
        [_or_obs()],
    )
    assert ep.capabilities["chat"] is True
    assert ep.capabilities["tool_calling"] is True
    assert ep.capabilities["vision"] is True
    assert ep.capabilities["reasoning"] is True


# ---------------------------------------------------------------------------
# models.dev path
# ---------------------------------------------------------------------------


def test_models_dev_fills_via_slug_fallback():
    """AMD's ``MiniCPM5-2B`` matches models.dev's ``openbmb/minicpm5-2b``
    via slug fallback. This test goes through the cross-source indexer
    + applier, matching the AMD path."""
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(
            model_id="MiniCPM5-2B",
            architecture=None,
            capabilities={},
        ),
        [_md_obs()],
    )
    assert ep.architecture == {"input": ["text"], "output": ["text"]}
    assert ep.capabilities["chat"] is True  # text output implies chat
    assert ep.capabilities["tool_calling"] is True
    assert ep.capabilities["reasoning"] is True


def test_multiple_sources_union_modalities():
    """When OR + models.dev both have observations for the same model,
    both contribute to architecture and capabilities."""
    obs_list = [
        _or_obs(),  # multimodal: text+image+video -> text
        _md_obs(architecture={"input": ["audio"], "output": ["audio"]}),
    ]
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(architecture=None, capabilities={}),
        obs_list,
    )
    assert "image" in ep.architecture["input"]
    assert "audio" in ep.architecture["input"]
    assert "video" in ep.architecture["input"]
    assert ep.capabilities["vision"] is True
    assert ep.capabilities.get("speech", False) is True


# ---------------------------------------------------------------------------
# Index lookup contract (version-separator unification)
# ---------------------------------------------------------------------------


def test_index_lookup_matches_nvidia_dash_to_or_dot():
    """The cross-source index normalizes ids so NVIDIA's
    ``z-ai/glm-5-3-flash`` can be looked up against the OR observation
    ``z-ai/glm-5.3-flash``."""
    idx = _build_cross_source_index([_or_obs(model_id="z-ai/glm-5.3-flash")])
    assert _normalize_id("z-ai/glm-5-3-flash") in idx
    observations = idx[_normalize_id("z-ai/glm-5-3-flash")]
    ep = _apply_cross_source_signals_to_nvidia_endpoint(
        _make_nvidia_ep(model_id="z-ai/glm-5-3-flash"), observations,
    )
    assert ep.capabilities["vision"] is True


def test_index_merges_or_and_models_dev_observations():
    idx = _build_cross_source_index(
        [_or_obs(model_id="z-ai/glm-5.3-flash")],
        [_md_obs(model_id="z-ai/glm-5-3-flash")],
    )
    # Both should normalize to the same key and merge.
    key = _normalize_id("z-ai/glm-5-3-flash")
    assert key in idx
    assert len(idx[key]) == 2
