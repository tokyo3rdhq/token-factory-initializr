"""Unit tests for Ollama pricing_status fix and web pricing cached field."""

from __future__ import annotations

from data.process.normalize import normalize_endpoints


def _ollama_item(model_id: str, free_until: str | None = None, pricing: dict | None = None) -> dict:
    """Build a minimal Ollama endpoint item dict.

    ``pricing=None`` means "no pricing dict at all"; pass an explicit dict
    to include one.
    """
    return {
        "provider": "ollama",
        "data_source": "ollama",
        "model_id": model_id,
        "free": bool(free_until),
        "metadata": {"free_until": free_until} if free_until else {},
        **({"pricing": pricing} if pricing is not None else {}),
    }


def test_normalize_ollama_pricing_status_free_with_free_until():
    """Ollama with free_until should still get pricing_status=free."""
    endpoints = normalize_endpoints([
        _ollama_item("free-model", free_until="2026-12-31T23:59:59+00:00"),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_ollama_pricing_status_unknown_without_free_until_and_no_pricing():
    """Ollama without free_until and without pricing should get unknown."""
    endpoints = normalize_endpoints([
        _ollama_item("no-free-model", free_until=None, pricing=None),
    ])
    assert endpoints[0].pricing_status == "unknown"


def test_normalize_ollama_pricing_status_priced_with_normalized_pricing():
    """Ollama with normalized pricing dict should get priced."""
    endpoints = normalize_endpoints([
        _ollama_item("paid-model", free_until=None, pricing={"input": "0.30", "cached": "0.006", "output": "1.20"}),
    ])
    # Any positive normalized value should result in "priced"
    assert endpoints[0].pricing_status == "priced"


def test_normalize_ollama_pricing_status_free_all_zero_pricing():
    """Ollama with all-zero pricing should get free."""
    endpoints = normalize_endpoints([
        _ollama_item("zero-priced-model", free_until=None, pricing={"input": "0", "cached": "0", "output": "0"}),
    ])
    assert endpoints[0].pricing_status == "free"


def test_normalize_ollama_pricing_status_unknown_with_negative():
    """Ollama with negative sentinel should get unknown."""
    endpoints = normalize_endpoints([
        _ollama_item("neg-model", free_until=None, pricing={"input": "-1"}),
    ])
    assert endpoints[0].pricing_status == "unknown"