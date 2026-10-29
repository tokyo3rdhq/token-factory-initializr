"""Unit tests for pricing_status classification in normalize_endpoints.

These tests were migrated from ``data/providers/free_filter.py``
(qualify_nvidia, qualify_amd, qualify_ollama, qualify_huggingface,
qualify_openrouter, qualify_kilo) after the pricing_status logic was
moved into :func:`data.process.normalize.normalize_endpoints`.

Each provider's pricing_status is now computed in the normalize stage
from provider metadata / normalized pricing, not in filter_free.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data.process.normalize import normalize_endpoints

_NOW = datetime.now(timezone.utc)


def _nvidia_item(model_id: str, nim_values: list[str]) -> dict:
    return {
        "provider": "nvidia",
        "data_source": "nvidia",
        "model_id": model_id,
        "free": True,
        "name": model_id.split("/")[-1],
        "description": None,
        "metadata": {
            "labels": {
                "nimType": {"values": nim_values},
            },
        },
    }


def _amd_item(model_id: str, free_status: str | None) -> dict:
    return {
        "provider": "amd",
        "data_source": "amd",
        "model_id": model_id,
        "free": free_status == "free_endpoint",
        "metadata": {"free_status": free_status},
    }


def _ollama_item(model_id: str, free_until: str | None) -> dict:
    return {
        "provider": "ollama",
        "data_source": "ollama",
        "model_id": model_id,
        "free": bool(free_until),
        "metadata": {"free_until": free_until} if free_until else {},
    }


def _hf_item(model_id: str, pricing: dict | None) -> dict:
    return {
        "provider": "huggingface",
        "data_source": "huggingface",
        "model_id": model_id,
        "free": False,
        "pricing": pricing,
        "metadata": {},
    }


def _openrouter_item(model_id: str, pricing: dict | None) -> dict:
    return {
        "provider": "openrouter",
        "data_source": "openrouter",
        "model_id": model_id,
        "free": False,
        "pricing": pricing,
        "metadata": {},
    }


def _kilo_item(model_id: str, pricing: dict | None) -> dict:
    return {
        "provider": "kilo",
        "data_source": "kilo",
        "model_id": model_id,
        "free": False,
        "pricing": pricing,
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------


def test_normalize_nvidia_pricing_status_free_endpoint():
    endpoints = normalize_endpoints([
        _nvidia_item("free/a", ["Free Endpoint"]),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_nvidia_pricing_status_priced():
    endpoints = normalize_endpoints([
        _nvidia_item("paid/b", ["Run Anywhere"]),
    ])
    assert endpoints[0].pricing_status == "priced"


def test_normalize_nvidia_pricing_status_unknown():
    endpoints = normalize_endpoints([
        _nvidia_item("unknown/c", []),
    ])
    assert endpoints[0].pricing_status == "unknown"


def test_normalize_nvidia_pricing_status_no_labels():
    endpoints = normalize_endpoints([
        {
            "provider": "nvidia",
            "data_source": "nvidia",
            "model_id": "no-labels",
            "free": True,
            "metadata": {},
        },
    ])
    assert endpoints[0].pricing_status == "unknown"


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


def test_normalize_amd_pricing_status_free_endpoint():
    endpoints = normalize_endpoints([
        _amd_item("MiMo", "free_endpoint"),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_amd_pricing_status_paid():
    endpoints = normalize_endpoints([
        _amd_item("DeepSeek", "paid"),
    ])
    assert endpoints[0].pricing_status == "priced"


def test_normalize_amd_pricing_status_unknown():
    endpoints = normalize_endpoints([
        _amd_item("x/1", None),
    ])
    assert endpoints[0].pricing_status == "unknown"


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


def test_normalize_ollama_pricing_status_free_with_free_until():
    endpoints = normalize_endpoints([
        _ollama_item("free-model", "2026-12-31T23:59:59+00:00"),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_ollama_pricing_status_unknown_without_free_until():
    endpoints = normalize_endpoints([
        _ollama_item("paid-model", None),
    ])
    assert endpoints[0].pricing_status == "unknown"


# ---------------------------------------------------------------------------
# Hugging Face / OpenRouter / Kilo (normalized pricing based)
# ---------------------------------------------------------------------------


def test_normalize_hf_pricing_status_all_zero_free():
    endpoints = normalize_endpoints([
        _hf_item("m1", {"input": 0, "output": 0}),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_hf_pricing_status_nonzero_priced():
    endpoints = normalize_endpoints([
        _hf_item("m2", {"input": "1.4e-7", "output": "2.8e-7"}),
    ])
    assert endpoints[0].pricing_status == "priced"


def test_normalize_hf_pricing_status_no_pricing_unknown():
    endpoints = normalize_endpoints([
        _hf_item("m4", None),
    ])
    assert endpoints[0].pricing_status == "unknown"


def test_normalize_openrouter_pricing_status_all_zero_free():
    endpoints = normalize_endpoints([
        _openrouter_item("m2", {"input": 0, "output": 0}),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_openrouter_pricing_status_nonzero_priced():
    endpoints = normalize_endpoints([
        _openrouter_item("m3", {"input": "1.0", "output": "2.0"}),
    ])
    assert endpoints[0].pricing_status == "priced"


def test_normalize_openrouter_pricing_status_no_pricing_unknown():
    endpoints = normalize_endpoints([
        _openrouter_item("m1", None),
    ])
    assert endpoints[0].pricing_status == "unknown"


def test_normalize_kilo_pricing_status_all_zero_free():
    endpoints = normalize_endpoints([
        _kilo_item("m2", {"input": "0.000000000000", "output": "0"}),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_kilo_pricing_status_no_pricing_unknown():
    endpoints = normalize_endpoints([
        _kilo_item("m1", None),
    ])
    assert endpoints[0].pricing_status == "unknown"


# ---------------------------------------------------------------------------
# Unknown provider
# ---------------------------------------------------------------------------


def test_normalize_unknown_provider_no_pricing_status():
    endpoints = normalize_endpoints([
        {
            "provider": "weird",
            "data_source": "weird",
            "model_id": "x/1",
            "free": True,
            "metadata": {},
        },
    ])
    assert endpoints[0].pricing_status is None
