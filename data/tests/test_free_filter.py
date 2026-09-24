"""Unit tests for :mod:`data.providers.free_filter`.

The three per-provider rules are independently tested because the rule
shape itself differs (NVIDIA label set membership, AMD boolean field,
HF multi-key provider tuple). A single shared helper would either
conflate the three concepts or force a least-common-denominator
abstraction; testing them separately documents the differences.
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
    PROVIDER_FREE_FILTERS,
    filter_amd_free,
    filter_free,
    filter_huggingface_free,
    filter_nvidia_free,
)


def _ep(provider: str, free: bool, model_id: str = "x/1") -> ModelEndpoint:
    """Build a minimal NVIDIA-style ModelEndpoint for filter tests."""
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
    """Build a minimal AMD-style dict endpoint."""
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
    """Build a minimal HF-style dict endpoint."""
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


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------


def test_filter_nvidia_free_drops_non_free():
    """Run Anywhere partner endpoints (free=False) must be dropped."""
    endpoints = [
        _ep("nvidia", free=True, model_id="free/a"),
        _ep("nvidia", free=False, model_id="runanywhere/b"),
        _ep("nvidia", free=True, model_id="free/c"),
    ]
    out = filter_nvidia_free(endpoints)
    assert [ep.model_id for ep in out] == ["free/a", "free/c"]


def test_filter_nvidia_free_empty_input():
    """Empty input is a no-op (returns empty list)."""
    assert filter_nvidia_free([]) == []


def test_filter_nvidia_free_all_non_free_returns_empty():
    """All-non-free input collapses to empty."""
    endpoints = [_ep("nvidia", free=False) for _ in range(3)]
    assert filter_nvidia_free(endpoints) == []


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


def test_filter_amd_free_drops_paid_endpoints():
    """AMD endpoints with status.key != 'free_endpoint' must be dropped."""
    endpoints = [
        _amd_ep(free=True, model_id="MiMo"),
        _amd_ep(free=False, model_id="SomePaid"),
        _amd_ep(free=True, model_id="DeepSeek"),
    ]
    out = filter_amd_free(endpoints)
    assert [ep["model_id"] for ep in out] == ["MiMo", "DeepSeek"]


def test_filter_amd_free_handles_missing_free_key():
    """An AMD dict without a ``free`` key is treated as paid (drop).

    Defensive: AMD parser always sets ``free`` explicitly, but if the
    upstream schema ever drops the key, the filter must not crash.
    """
    endpoints = [_amd_ep(free=True), {"provider": "amd", "model_id": "no-flag"}]
    out = filter_amd_free(endpoints)
    assert [ep["model_id"] for ep in out] == ["x/1"]


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------


def test_filter_huggingface_free_is_passthrough():
    """HF parser already filters by price+status; this is defensive only.

    All HF endpoints reaching the filter should already have free=True
    (the upstream ``filter_free_providers`` drops paid providers per
    model). The filter must accept this without dropping anything.
    """
    endpoints = [_hf_ep(free=True), _hf_ep(free=True)]
    out = filter_huggingface_free(endpoints)
    assert len(out) == 2


def test_filter_huggingface_free_drops_unexpected_non_free():
    """Defensive: if a future parser emits free=False for HF, drop it."""
    endpoints = [_hf_ep(free=True), _hf_ep(free=False)]
    out = filter_huggingface_free(endpoints)
    assert [ep["model_id"] for ep in out] == ["x/1"]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_filter_free_dispatches_by_provider():
    """filter_free must route to the right per-provider implementation."""
    nvidia = [_ep("nvidia", free=True), _ep("nvidia", free=False)]
    amd = [_amd_ep(free=True), _amd_ep(free=False)]
    hf = [_hf_ep(free=True)]

    assert [ep.model_id for ep in filter_free(nvidia, "nvidia")] == ["x/1"]
    assert [ep["model_id"] for ep in filter_free(amd, "amd")] == ["x/1"]
    assert [ep["model_id"] for ep in filter_free(hf, "huggingface")] == ["x/1"]


def test_filter_free_unknown_provider_passthrough():
    """An unknown provider key returns the input unchanged (no crash)."""
    endpoints = [_ep("unknown", free=False)]
    out = filter_free(endpoints, "unknown")
    assert out is endpoints or out == endpoints


def test_provider_free_filters_registry():
    """All three expected providers must be registered."""
    assert set(PROVIDER_FREE_FILTERS) == {"nvidia", "amd", "huggingface"}


def test_filter_free_handles_empty_input():
    """Empty input is safe across all providers."""
    for provider in ("nvidia", "amd", "huggingface"):
        assert filter_free([], provider) == []