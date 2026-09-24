"""Unit tests for normalize + validate + summarize stages."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data.models.schema import ModelEndpoint
from data.process.normalize import normalize_endpoints, endpoint_to_dict
from data.process.validate import validate_all, validate_endpoint
from data.process.summarize import summarize_all


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def test_normalize_endpoints_basic():
    raw = [
        {
            "provider": "amd",
            "model_id": "amd/test-model",
            "free": True,
            "name": "Test Model",
            "capabilities": {"chat": True},
            "metadata": {"context_length": 4096},
        }
    ]
    eps = normalize_endpoints(raw)
    assert len(eps) == 1
    ep = eps[0]
    assert ep.provider == "amd"
    assert ep.model_id == "amd/test-model"
    assert ep.free is True
    assert isinstance(ep.fetched_at, datetime)
    assert ep.name == "Test Model"
    assert ep.capabilities == {"chat": True}
    assert ep.metadata == {"context_length": 4096}


def test_normalize_endpoints_missing_required_field():
    raw = [{"provider": "amd"}]  # no model_id
    with pytest.raises(ValueError, match="missing required field 'model_id'"):
        normalize_endpoints(raw)


def test_normalize_endpoints_defaults():
    raw = [{"provider": "nvidia", "model_id": "x/y"}]
    eps = normalize_endpoints(raw)
    assert eps[0].free is False
    assert eps[0].capabilities == {}
    assert eps[0].metadata == {}
    assert eps[0].name is None


def test_endpoint_to_dict():
    ep = ModelEndpoint(
        provider="amd",
        model_id="x/y",
        free=True,
        fetched_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    d = endpoint_to_dict(ep)
    assert d["provider"] == "amd"
    assert d["fetched_at"] == "2026-09-24T00:00:00+00:00"
    assert isinstance(d["capabilities"], dict)


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def _mk(provider: str, model_id: str, name: str | None = None) -> ModelEndpoint:
    return ModelEndpoint(
        provider=provider,
        model_id=model_id,
        free=True,
        fetched_at=datetime.now(timezone.utc),
        name=name,
    )


def test_validate_endpoint_valid():
    ep = _mk("amd", "x/y")
    assert validate_endpoint(ep) == []


def test_validate_endpoint_empty_provider():
    ep = _mk("", "x/y")
    issues = validate_endpoint(ep)
    assert any("provider is empty" in i for i in issues)


def test_validate_endpoint_unknown_provider():
    ep = _mk("openai", "x/y")
    issues = validate_endpoint(ep)
    assert any("unknown provider" in i for i in issues)


def test_validate_endpoint_empty_model_id():
    ep = _mk("amd", "  ")
    issues = validate_endpoint(ep)
    assert any("model_id" in i for i in issues)


def test_validate_endpoint_bad_context_length():
    ep = _mk("amd", "x/y")
    ep.metadata["context_length"] = "8192"  # type: ignore[assignment]
    issues = validate_endpoint(ep)
    assert any("context_length" in i for i in issues)


def test_validate_all_splits_valid_invalid():
    good = _mk("amd", "x/y")
    bad = _mk("openai", "z/w")
    valid, invalid = validate_all([good, bad])
    assert len(valid) == 1
    assert len(invalid) == 1
    assert invalid[0]["endpoint"]["provider"] == "openai"
    assert invalid[0]["issues"]


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------


def test_summarize_all_success():
    eps = [_mk("amd", "x/1"), _mk("amd", "x/2"), _mk("nvidia", "y/1")]
    manifest = summarize_all(eps, {})
    assert manifest["total"] == 3
    assert manifest["providers"]["amd"]["count"] == 2
    assert manifest["providers"]["amd"]["status"] == "success"
    assert manifest["providers"]["nvidia"]["count"] == 1


def test_summarize_all_failure_flag():
    eps = [_mk("amd", "x/1")]
    manifest = summarize_all(eps, {"huggingface": "Network error ..."})
    assert manifest["providers"]["huggingface"]["status"] == "failed"
    assert manifest["providers"]["huggingface"]["error"] == "Network error ..."
    assert manifest["providers"]["huggingface"]["count"] == 0
    assert manifest["providers"]["amd"]["status"] == "success"


def test_summarize_all_empty_is_not_success_for_failed_provider():
    """Zero endpoints for a provider that errored must NOT read as success (AGENTS.md §24)."""
    manifest = summarize_all([], {"nvidia": "parser failed"})
    assert manifest["providers"]["nvidia"]["status"] == "failed"


def test_summarize_all_zero_models_no_error_is_success():
    """Provider fetched successfully but returned zero models = success with count 0."""
    manifest = summarize_all([], {})
    assert manifest["providers"]["nvidia"]["status"] == "success"
    assert manifest["providers"]["nvidia"]["count"] == 0