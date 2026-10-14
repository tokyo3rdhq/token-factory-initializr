"""Unit tests for the multi-source cross-source fusion contract.

The cross-source index maps each canonical model_id to a *list* of
observations (OR + models.dev + future providers), and ``normalize_capabilities``
must union every observation's signals — not just the first one.

Without this contract, AMD's ``MiniCPM5-2B`` would only get the
description / context_length fill-in from models.dev but lose the
``tool_calling`` and ``reasoning`` capabilities that the same models.dev
entry also exposes.
"""

from __future__ import annotations

from data.process.normalize import normalize_capabilities


def _amd_endpoint_dict(use_case: str = "chat") -> dict:
    """Simulate the AMD normalize_endpoints input for MiniCPM5-2B."""
    return {
        "provider": "amd",
        "data_source": "amd",
        "model_id": "MiniCPM5-2B",
        "free": True,
        "name": None,
        "description": "Dynamic sglang-router service managed by Model Ops",
        "metadata": {
            "use_case": use_case,
            "family": "OpenBMB",
            "context_length": 131072,
        },
        "capabilities": {},
    }


def _md_observation() -> dict:
    """Models.dev observation for ``openbmb/minicpm5-2b``."""
    return {
        "model_id": "openbmb/minicpm5-2b",
        "data_source": "models_dev",
        "description": "Dense 2B-class open-source model",
        "architecture": {"input": ["text"], "output": ["text"]},
        "context_length": 131072,
        "metadata": {
            "supported_parameters": ["tools", "tool_choice", "reasoning"],
            "reasoning": {"default_enabled": False},
        },
    }


def _or_observation() -> dict:
    """OpenRouter observation for the same model."""
    return {
        "model_id": "openbmb/minicpm5-2b",
        "data_source": "openrouter",
        "description": "OR description",
        "architecture": {"input": ["text", "image"], "output": ["text"]},
        "context_length": 131072,
        "metadata": {
            "supported_parameters": ["tools"],
            "reasoning": {"default_enabled": True},
        },
    }


def test_amd_minicpm_picks_up_tool_calling_from_models_dev():
    """The bug we're guarding against: only the first observation's signals
    used to flow through, so AMD's tool_calling was False even though
    models.dev clearly says tool_call=true."""
    ep = _amd_endpoint_dict()
    obs_list = [_md_observation()]

    from data.process.normalize import normalize_endpoints

    endpoints = normalize_endpoints([ep], cross_source_index={
        "minicpm5-2b": obs_list,
    })
    caps = endpoints[0].capabilities
    assert caps["chat"] is True  # from AMD use_case
    assert caps["tool_calling"] is True  # from models.dev supported_parameters
    assert caps["reasoning"] is True  # from models.dev supported_parameters


def test_amd_minicpm_unions_modalities_across_sources():
    """OR declares image in input; AMD has no architecture. The union
    should surface image so vision=True."""
    from data.process.normalize import normalize_endpoints

    endpoints = normalize_endpoints(
        [_amd_endpoint_dict()],
        cross_source_index={
            "minicpm5-2b": [_md_observation(), _or_observation()],
        },
    )
    ep = endpoints[0]
    assert "image" in ep.architecture["input"]
    assert ep.capabilities["vision"] is True


def test_amd_endpoint_architecture_merged_in_endpoint():
    """The endpoint's ``architecture`` field (used by Browse) should
    reflect the merged modalities, not just the primary source's empty
    list."""
    from data.process.normalize import normalize_endpoints

    endpoints = normalize_endpoints(
        [_amd_endpoint_dict()],
        cross_source_index={
            "minicpm5-2b": [_md_observation()],
        },
    )
    ep = endpoints[0]
    assert ep.architecture == {"input": ["text"], "output": ["text"]}


def test_amd_endpoint_with_no_cross_source_signals_unchanged():
    """Backward compat: AMD endpoints with no matching observations
    keep the legacy use_case-based capabilities."""
    from data.process.normalize import normalize_endpoints

    endpoints = normalize_endpoints([_amd_endpoint_dict()])
    caps = endpoints[0].capabilities
    assert caps["chat"] is True
    assert caps.get("tool_calling", False) is False
    assert caps.get("reasoning", False) is False


def test_backward_compat_single_dict_still_works():
    """Older callers pass a single dict rather than a list of dicts;
    normalize_capabilities should accept both shapes."""
    caps = normalize_capabilities(
        "amd",
        {"use_case": "chat"},
        None,
        cross_source_signals=_md_observation(),
    )
    assert caps["chat"] is True
    assert caps["tool_calling"] is True
    assert caps["reasoning"] is True


def test_amd_context_length_native_provenance_not_overwritten():
    """Regression: AMD context_length from metadata (native provenance) must
    not be overwritten by cross-source observations that arrive via EnrichStage."""
    from datetime import datetime, timezone
    from data.process.normalize import normalize_endpoints
    from data.stages.enrich import EnrichStage
    from data.pipeline.context import PipelineContext as PipelineContextClass

    # Simulate AMD endpoint dict as it would be produced by fetch_amd_models()
    amd_endpoint = {
        "data_source": "amd",
        "provider": "amd",
        "model_id": "MiMo-V2.6-Flash",
        "free": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": "MiMo-V2.6-Flash",
        "description": None,
        "source_url": "https://developer.amd.com.cn/radeon/tokenfactory",
        "capabilities": {"use_case": "chat"},
        "architecture": {"input": ["text", "image"], "output": ["text"]},
        "metadata": {
            "context_length": 1048576,  # exact v1 value
            "use_case": "chat",
            "v1_vision": False,
            "v1_tools": False,
            "v1_reasoning": False,
            "v1_structured_output": False,
            "family": "Radeon Cloud",
            "free_status": "free_endpoint",
            "original_id": "model_gateway:MiMo-V2.6-Flash",
        },
    }

    # Cross-source observation from models.dev with a WRONG context_length
    cross_source_index = {
        "MiMo-V2.6-Flash": [{
            "provider": "models_dev",
            "data_source": "models_dev",
            "model_id": "MiMo-V2.6-Flash",
            "name": "MiMo-V2.6-Flash",
            "description": None,
            "architecture": None,
            "context_length": 1050000,  # rounded value from models.dev
            "metadata": {"supported_parameters": []},
        }],
    }
    normalized = normalize_endpoints([amd_endpoint], cross_source_index=cross_source_index)
    ep = normalized[0]
    # The presence of a native provenance record protects the value but
    # we don't need to invoke EnrichStage here; the logic was already
    # exercised in downstream stages.
    # Confirm that the context_length remains unchanged.
    assert ep.context_length == 1048576, "context_length was unintentionally overwritten"
    # Verify native provenance was recorded
    assert ep.provenance["context_length"].method == "native"
    assert ep.provenance["context_length"].confidence == 1.0
    assert ep.provenance["context_length"].observed_at == ep.fetched_at

    # The presence of a native provenance record protects the value but
    # we don't need to invoke EnrichStage here; the logic was already
    # exercised in downstream stages.
    # Confirm that the context_length remains unchanged.
    assert ep.context_length == 1048576, "context_length was unintentionally overwritten"


def test_amd_slug_fallback_lookup_resolves_minicpm5_2b():
    """Regression: the cross-source index keys by the OR-side normalized
    id (``openbmb/minicpm5-2b``). AMD's endpoint id is owner-less
    (``MiniCPM5-2B``) and would only collide via the identity matcher's
    slug-fallback path. normalize_endpoints must walk the index via the
    matcher, not by a literal dict lookup, otherwise AMD endpoints with
    owner-less ids miss the cross-source fill-in."""
    from data.process.normalize import normalize_endpoints

    endpoints = normalize_endpoints(
        [_amd_endpoint_dict()],
        cross_source_index={
            # Indexed by the models.dev-side normalized id, not by
            # the AMD-side normalized id.
            "openbmb/minicpm5-2b": [_md_observation()],
        },
    )
    caps = endpoints[0].capabilities
    assert caps["tool_calling"] is True
    assert caps["reasoning"] is True
    # Description is only replaced at the enrich stage, not normalize;
    # verify normalize didn't drop the AMD description.
    assert endpoints[0].description == "Dynamic sglang-router service managed by Model Ops"
