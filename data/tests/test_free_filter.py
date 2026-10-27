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
    metadata: dict | None = None,
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
        metadata=metadata or {},
    )
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


def _amd_ep(free_status: str | None = None, pricing: dict | None = None, model_id: str = "x/1") -> dict:
    """Build a minimal AMD-style dict endpoint."""
    return {
        "data_source": "amd",
        "provider": "amd",
        "model_id": model_id,
        "free": free_status == "free_endpoint",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id,
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {
            "free_status": free_status,
        },
        "pricing": pricing,
    }


def _hf_ep(status: str = "live", pricing: dict | None = None, model_id: str = "x/1") -> dict:
    """Build a minimal HF-style dict endpoint (original format with top-level status)."""
    return {
        "data_source": "huggingface",
        "provider": "huggingface",
        "model_id": model_id,
        "free": False,  # will be overridden by qualify
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": model_id.split("/")[-1],
        "description": None,
        "capabilities": {},
        "architecture": {"input": ["text"], "output": ["text"]},
        "lab": "test",
        "metadata": {},
        "status": status,
        "pricing": pricing,
    }


def _hf_ep_canonical(provider_status: str = "live", pricing: dict | None = None, model_id: str = "x/1") -> dict:
    """Build a minimal HF-style dict endpoint (canonical format with metadata.provider_status)."""
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
        "metadata": {"provider_status": provider_status},
        "pricing": pricing,
    }


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------


def test_qualify_nvidia_classifies_by_nimtype():
    """NVIDIA qualify classifies by metadata.labels.nimType.values."""
    endpoints = [
        _ep("nvidia", free=True, model_id="free/a",
            metadata={"labels": {"nimType": {"values": ["Free Endpoint"]}}}),
        _ep("nvidia", free=False, model_id="paid/b",
            metadata={"labels": {"nimType": {"values": ["Run Anywhere"]}}}),
        _ep("nvidia", free=False, model_id="unknown/c",
            metadata={"labels": {}}),
    ]
    out = qualify_nvidia(endpoints)
    assert [ep.model_id for ep in out] == ["free/a", "paid/b", "unknown/c"]
    statuses = {ep.model_id: ep.pricing_status for ep in out}
    assert statuses == {"free/a": "free", "paid/b": "priced", "unknown/c": "unknown"}


def test_qualify_nvidia_empty_input():
    assert qualify_nvidia([]) == []


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


def test_qualify_amd_classifies_by_free_status():
    """AMD qualify classifies by metadata.free_status."""
    endpoints = [
        _amd_ep(free_status="free_endpoint", model_id="MiMo"),
        _amd_ep(free_status="paid", model_id="DeepSeek"),
        _amd_ep(free_status=None),  # default model_id "x/1"
    ]
    out = qualify_amd(endpoints)
    assert [ep["model_id"] for ep in out] == ["MiMo", "DeepSeek", "x/1"]
    statuses = {ep["model_id"]: ep["pricing_status"] for ep in out}
    assert statuses == {"MiMo": "free", "DeepSeek": "priced", "x/1": "unknown"}


def test_qualify_amd_empty_input():
    assert qualify_amd([]) == []


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------


def test_qualify_huggingface_classifies_by_status_and_pricing():
    """HF qualify classifies by status + pricing."""
    endpoints = [
        _hf_ep(status="live", pricing={"input": 0, "output": 0}, model_id="m1"),
        _hf_ep(status="live", pricing={"input": "1.4e-7", "output": "2.8e-7"}, model_id="m2"),
        _hf_ep(status="offline", pricing={"input": 0, "output": 0}, model_id="m3"),
        _hf_ep(status="live", pricing=None, model_id="m4"),
    ]
    out = qualify_huggingface(endpoints)
    assert [ep["model_id"] for ep in out] == ["m1", "m2", "m3", "m4"]
    statuses = {ep["model_id"]: ep["pricing_status"] for ep in out}
    assert statuses == {"m1": "free", "m2": "priced", "m3": "unknown", "m4": "unknown"}


def test_qualify_huggingface_canonical_format():
    """HF qualify classifies canonical format endpoints (metadata.provider_status)."""
    endpoints = [
        _hf_ep_canonical(provider_status="live", pricing={"input": 0, "output": 0}, model_id="m1"),
        _hf_ep_canonical(provider_status="live", pricing={"input": "1.4e-7", "output": "2.8e-7"}, model_id="m2"),
        _hf_ep_canonical(provider_status="offline", pricing={"input": 0, "output": 0}, model_id="m3"),
        _hf_ep_canonical(provider_status="live", pricing=None, model_id="m4"),
    ]
    out = qualify_huggingface(endpoints)
    assert [ep["model_id"] for ep in out] == ["m1", "m2", "m3", "m4"]
    statuses = {ep["model_id"]: ep["pricing_status"] for ep in out}
    assert statuses == {"m1": "free", "m2": "priced", "m3": "unknown", "m4": "unknown"}


def test_qualify_huggingface_empty_input():
    assert qualify_huggingface([]) == []


# ---------------------------------------------------------------------------
# OpenRouter / Kilo
# ---------------------------------------------------------------------------


def test_qualify_openrouter_classifies_by_pricing():
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
    assert statuses == {"m1": "unknown", "m2": "free", "m3": "priced"}


def test_qualify_kilo_classifies_by_pricing():
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
    hf = [_hf_ep(status="live", pricing={"input": 0, "output": 0})]
    assert [ep["model_id"] for ep in filter_free(hf, "huggingface")] == ["x/1"]
    nvidia = [_ep("nvidia", free=True, model_id="x/1",
                  metadata={"labels": {"nimType": {"values": ["Free Endpoint"]}}})]
    assert [ep.model_id for ep in filter_free(nvidia, "nvidia")] == ["x/1"]


def test_filter_free_unknown_provider_passthrough():
    endpoints = [_ep("weird", free=True, pricing_status="unknown")]
    out = filter_free(endpoints, "weird")
    assert out is endpoints or out == endpoints


    hf = [_hf_ep(status="live", pricing={"input": 0, "output": 0})]
    assert set(PROVIDER_FREE_FILTERS) == {
        "nvidia",
        "amd",
        "huggingface",
        "openrouter",
        "kilo",
        "ollama",
    }


def test_filter_free_handles_empty_input():
    for provider in ("nvidia", "amd", "huggingface", "openrouter", "kilo", "ollama"):
        assert filter_free([], provider) == []