"""Unit tests for :mod:`data.providers.free_filter`.

Covers the qualification + classification behavior
(docs/tfi_model_endpoint_support_paid_model.md §5.1):

* Every eligible endpoint is kept (free / paid / unknown).
* ``pricing_status`` is classified from source evidence when missing.
* Malformed records are rejected by the Stage, not here.
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
from data.providers.free_filter import (
    classify_pricing,
    filter_free,
    qualify_amd,
    qualify_huggingface,
    qualify_kilo,
    qualify_nvidia,
    qualify_ollama,
    qualify_openrouter,
    PROVIDER_FREE_FILTERS,
)


def _ep(
    provider: str,
    free: bool,
    pricing_status: str | None = None,
    model_id: str = "x/1",
) -> ModelEndpoint:
    """Build a minimal NVIDIA-style ModelEndpoint for filter tests."""
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
    """Build a minimal AMD-style dict endpoint."""
    return {
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
    """Build a minimal HF-style dict endpoint."""
    return {
        "provider": "huggingface",
        "model_id": model_id,
        "free": pricing_status == "free",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id.split("/")[-1],
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
        "pricing_status": pricing_status,
    }


# ---------------------------------------------------------------------------
# classify_pricing
# ---------------------------------------------------------------------------


def test_classify_pricing_missing_is_unknown():
    assert classify_pricing({}) == "unknown"
    assert classify_pricing({"pricing": {}}) == "unknown"
    assert classify_pricing({"pricing": None}) == "unknown"


def test_classify_pricing_all_zero_is_free():
    assert classify_pricing({"pricing": {"input": 0, "output": 0}}) == "free"
    assert classify_pricing({"pricing": {"input": "0", "output": "0.0"}}) == "free"


def test_classify_pricing_non_zero_is_paid():
    assert classify_pricing({"pricing": {"input": "1.4e-7", "output": "2.8e-7"}}) == "paid"
    assert classify_pricing({"pricing": {"input": 0, "output": 1}}) == "paid"


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------


def test_qualify_nvidia_keeps_all_endpoints():
    """NVIDIA qualify keeps free + paid + unknown (pricing_status set by parser)."""
    endpoints = [
        _ep("nvidia", free=True, pricing_status="free", model_id="free/a"),
        _ep("nvidia", free=False, pricing_status="paid", model_id="paid/b"),
        _ep("nvidia", free=False, pricing_status="unknown", model_id="unknown/c"),
    ]
    out = qualify_nvidia(endpoints)
    assert [ep.model_id for ep in out] == ["free/a", "paid/b", "unknown/c"]


def test_qualify_nvidia_empty_input():
    assert qualify_nvidia([]) == []


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


def test_qualify_amd_keeps_all_and_classifies_missing():
    """AMD qualify keeps all endpoints; missing pricing_status → classified."""
    endpoints = [
        _amd_ep(pricing_status="free", model_id="MiMo"),
        _amd_ep(pricing_status="paid", model_id="DeepSeek"),
        {**_amd_ep(pricing_status=None)},  # no pricing key → unknown
    ]
    out = qualify_amd(endpoints)
    assert [ep["model_id"] for ep in out] == ["MiMo", "DeepSeek", "x/1"]
    assert out[2]["pricing_status"] == "unknown"


def test_qualify_amd_empty_input():
    assert qualify_amd([]) == []


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------


def test_qualify_huggingface_keeps_all_and_classifies():
    """HF qualify keeps all endpoints; classifies missing pricing_status."""
    endpoints = [
        _hf_ep(pricing_status="free", model_id="m1"),
        _hf_ep(pricing_status="paid", model_id="m2"),
        {**_hf_ep(pricing_status=None, model_id="m3"), "pricing": {"input": 0, "output": 0}},
    ]
    out = qualify_huggingface(endpoints)
    assert [ep["model_id"] for ep in out] == ["m1", "m2", "m3"]
    assert out[2]["pricing_status"] == "free"


def test_qualify_huggingface_empty_input():
    assert qualify_huggingface([]) == []


# ---------------------------------------------------------------------------
# OpenRouter / Kilo
# ---------------------------------------------------------------------------


def test_qualify_openrouter_classifies_missing_as_unknown():
    endpoints = [
        {"provider": "openrouter", "model_id": "m1", "free": True,
         "fetched_at": datetime.now(timezone.utc).isoformat()},  # no pricing → unknown
        {"provider": "openrouter", "model_id": "m2", "free": False,
         "fetched_at": datetime.now(timezone.utc).isoformat(),
         "pricing": {"input": 0, "output": 0}},  # free
        {"provider": "openrouter", "model_id": "m3", "free": False,
         "fetched_at": datetime.now(timezone.utc).isoformat(),
         "pricing": {"input": "1.0", "output": "2.0"}},  # paid
    ]
    out = qualify_openrouter(endpoints)
    statuses = {ep["model_id"]: ep["pricing_status"] for ep in out}
    assert statuses == {"m1": "unknown", "m2": "free", "m3": "paid"}


def test_qualify_kilo_classifies_missing_as_unknown():
    endpoints = [
        {"provider": "kilo", "model_id": "m1", "free": True,
         "fetched_at": datetime.now(timezone.utc).isoformat()},  # no pricing → unknown
        {"provider": "kilo", "model_id": "m2", "free": False,
         "fetched_at": datetime.now(timezone.utc).isoformat(),
         "pricing": {"input": "0.000000000000", "output": "0"}},  # free
    ]
    out = qualify_kilo(endpoints)
    statuses = {ep["model_id"]: ep["pricing_status"] for ep in out}
    assert statuses == {"m1": "unknown", "m2": "free"}


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


def test_qualify_ollama_keeps_all():
    endpoints = [
        _ep("ollama", free=True, pricing_status="free", model_id="free-model"),
        _ep("ollama", free=False, pricing_status="unknown", model_id="paid-model"),
    ]
    out = qualify_ollama(endpoints)
    assert [ep.model_id for ep in out] == ["free-model", "paid-model"]


# ---------------------------------------------------------------------------
# Dispatch / registry
# ---------------------------------------------------------------------------


def test_filter_free_dispatches_by_provider():
    hf = [_hf_ep(pricing_status="free")]
    assert [ep["model_id"] for ep in filter_free(hf, "huggingface")] == ["x/1"]
    nvidia = [_ep("nvidia", free=True, pricing_status="free")]
    assert [ep.model_id for ep in filter_free(nvidia, "nvidia")] == ["x/1"]


def test_filter_free_unknown_provider_passthrough():
    endpoints = [_ep("weird", free=True, pricing_status="unknown")]
    out = filter_free(endpoints, "weird")
    assert out is endpoints or out == endpoints


def test_provider_free_filters_registry():
    assert set(PROVIDER_FREE_FILTERS) == {
        "nvidia",
        "amd",
        "huggingface",
        "models_dev",
        "openrouter",
        "kilo",
        "ollama",
    }


def test_filter_free_handles_empty_input():
    for provider in ("nvidia", "amd", "huggingface", "openrouter", "kilo", "ollama"):
        assert filter_free([], provider) == []
