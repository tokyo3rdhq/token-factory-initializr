"""Unit tests for the models.dev provider.

Models.dev exposes a flat ``{provider/model_id: model_info}`` catalog
at https://models.dev/models.json. The provider translates each entry
into TFI's cross-source observation shape so the normalize stage can
treat models.dev alongside OpenRouter.
"""

from __future__ import annotations

import json

from data.providers.models_dev import (
    DEFAULT_USER_AGENT,
    _build_raw_observation,
)


# ---------------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------------


def test_basic_observation_shape():
    entry = {
        "id": "openbmb/minicpm5-2b",
        "name": "MiniCPM5-2B",
        "description": "Dense 2B-class open-source model",
        "reasoning": True,
        "tool_call": True,
        "temperature": True,
        "release_date": "2026-09-06",
        "last_updated": "2026-09-12",
        "modalities": {"input": ["text"], "output": ["text"]},
        "open_weights": True,
        "limit": {"context": 131072, "output": 131072},
        "license": "apache-2.0",
        "weights": [{"label": "Hugging Face", "url": "https://huggingface.co/openbmb/MiniCPM5-2B"}],
    }
    obs = _build_raw_observation(entry)
    assert obs["model_id"] == "openbmb/minicpm5-2b"
    assert obs["data_source"] == "models_dev"
    assert obs["provider"] == "models_dev"
    assert obs["name"] == "MiniCPM5-2B"
    assert obs["description"] == "Dense 2B-class open-source model"
    assert obs["architecture"] == {"input": ["text"], "output": ["text"]}
    assert obs["context_length"] == 131072
    # Reasoning + tool_call both True → supported_parameters synthesizes
    # the OpenRouter-style signal list the normalize stage already reads.
    assert "reasoning" in obs["metadata"]["supported_parameters"]
    assert "tools" in obs["metadata"]["supported_parameters"]
    assert "tool_choice" in obs["metadata"]["supported_parameters"]
    assert obs["metadata"]["license"] == "apache-2.0"
    assert obs["metadata"]["open_weights"] is True
    assert obs["metadata"]["release_date"] == "2026-09-06"
    # weights URL preserved so consumers can link out.
    assert obs["metadata"]["weights"][0]["url"].startswith("https://huggingface.co/")


def test_observation_skips_when_no_id():
    assert _build_raw_observation({}) == {}
    assert _build_raw_observation({"name": "x"}) == {}


def test_observation_handles_missing_modalities():
    obs = _build_raw_observation({"id": "vendor/model"})
    # Empty / missing modalities collapse to empty input/output lists,
    # which downstream consumers treat as "no architecture info" rather
    # than a malformed value.
    assert obs["architecture"] == {"input": [], "output": []}


def test_observation_handles_missing_limit():
    obs = _build_raw_observation({"id": "vendor/model"})
    assert obs["context_length"] is None


def test_observation_with_image_modality():
    obs = _build_raw_observation({
        "id": "vendor/multimodal",
        "modalities": {"input": ["text", "image"], "output": ["text"]},
    })
    assert obs["architecture"] == {"input": ["text", "image"], "output": ["text"]}


def test_observation_no_capability_signals_when_both_false():
    obs = _build_raw_observation({
        "id": "vendor/plain",
        "reasoning": False,
        "tool_call": False,
    })
    assert obs["metadata"]["supported_parameters"] == []


def test_default_user_agent_is_polite():
    """models.dev returns 403 to the default urllib User-Agent; we ship
    a descriptive UA so fetches succeed."""
    assert "token-factory-initializr" in DEFAULT_USER_AGENT
