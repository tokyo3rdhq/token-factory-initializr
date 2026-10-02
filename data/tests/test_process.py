"""Unit tests for normalize + validate + summarize stages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.models.schema import ModelEndpoint
from data.process.normalize import normalize_endpoints, endpoint_to_dict
from data.process.validate import validate_all, validate_endpoint
from data.process.summarize import summarize_all


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------


def test_normalize_endpoints_basic():
    """End-to-end: capabilities are always emitted in the canonical
    7-key boolean shape regardless of what the input dict carried.
    AMD's ``use_case`` string + chat-adjacent raw signals get
    translated by ``normalize_capabilities``.
    """
    raw = [
        {
            "provider": "amd",
            "model_id": "amd/test-model",
            "data_source": "amd",
            "free": True,
            "name": "Test Model",
            "capabilities": {"chat": True},
            "metadata": {"context_length": 4096, "use_case": "chat"},
            "lab": "Test Lab",
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
    # Canonical 7-key shape — chat=True from both raw signal +
    # architecture derivation. Every key is present.
    assert ep.capabilities["chat"] is True
    assert set(ep.capabilities.keys()) == {
        "chat", "vision", "speech", "embedding",
        "tool_calling", "structured_output", "reasoning",
    }
    assert ep.metadata == {"context_length": 4096, "use_case": "chat"}
    assert ep.lab == "Test Lab"


def test_normalize_endpoints_lab_none_when_missing():
    raw = [
        {
            "provider": "amd",
            "model_id": "x/y",
            "free": True,
        }
    ]
    eps = normalize_endpoints(raw)
    assert len(eps) == 1
    ep = eps[0]
    assert ep.lab is None


def test_normalize_endpoints_missing_required_field():
    raw = [{"provider": "amd"}]  # no model_id
    with pytest.raises(ValueError, match="missing required field 'model_id'"):
        normalize_endpoints(raw)


def test_normalize_endpoints_defaults():
    """Empty raw signals → all-False canonical 7-key capabilities."""
    raw = [{"provider": "nvidia", "model_id": "x/y"}]
    eps = normalize_endpoints(raw)
    assert eps[0].free is False
    # Canonical shape is always emitted — every key present, all False.
    assert set(eps[0].capabilities.keys()) == {
        "chat", "vision", "speech", "embedding",
        "tool_calling", "structured_output", "reasoning",
    }
    assert all(v is False for v in eps[0].capabilities.values())
    assert eps[0].metadata == {}
    assert eps[0].name is None


def test_normalize_lifts_context_length_from_metadata():
    """``metadata.context_length`` must be lifted to the top-level field."""
    raw = [{
        "provider": "amd",
        "model_id": "x/y",
        "free": True,
        "metadata": {"context_length": 8192},
    }]
    ep = normalize_endpoints(raw)[0]
    assert ep.context_length == 8192
    # And the metadata copy stays put for back-compat.
    assert ep.metadata["context_length"] == 8192


def test_normalize_context_length_none_when_absent():
    """Missing context_length on both metadata and top-level → None."""
    raw = [{"provider": "amd", "model_id": "x/y", "free": True}]
    ep = normalize_endpoints(raw)[0]
    assert ep.context_length is None


def test_normalize_context_length_non_int_metadata_ignored():
    """A non-int metadata.context_length is ignored (top-level stays None)."""
    raw = [{
        "provider": "amd",
        "model_id": "x/y",
        "free": True,
        "metadata": {"context_length": "8192"},
    }]
    ep = normalize_endpoints(raw)[0]
    assert ep.context_length is None
    # But the metadata copy is preserved as-is (validator catches it).
    assert ep.metadata["context_length"] == "8192"


def test_normalize_lifts_architecture():
    """``item['architecture']`` is copied onto the dataclass field."""
    raw = [{
        "provider": "amd",
        "model_id": "x/y",
        "free": True,
        "architecture": {"input": ["text", "image"], "output": ["text"]},
    }]
    ep = normalize_endpoints(raw)[0]
    assert ep.architecture == {
        "input": ["text", "image"],
        "output": ["text"],
    }


def test_normalize_architecture_none_when_missing():
    """No architecture key in the raw dict → stays None."""
    raw = [{"provider": "amd", "model_id": "x/y", "free": True}]
    ep = normalize_endpoints(raw)[0]
    assert ep.architecture is None


def test_normalize_architecture_malformed_kept_as_none():
    """Wrong shape (extra key / wrong value type) is dropped, not stored."""
    bad_shapes = [
        {"input": ["text"], "output": ["text"], "extra": "x"},
        {"input": "text", "output": ["text"]},  # input not a list
        {"input": [1, 2], "output": ["text"]},   # input not list[str]
        {"outputs": ["text"]},                    # wrong key
        "not-a-dict",
    ]
    for bad in bad_shapes:
        raw = [{
            "provider": "amd",
            "model_id": "x/y",
            "free": True,
            "architecture": bad,
        }]
        ep = normalize_endpoints(raw)[0]
        assert ep.architecture is None, f"should drop malformed arch: {bad!r}"


def test_normalize_lifts_real_amd_fixture_architecture():
    """End-to-end: real AMD fixture → architecture populated, context_length set."""
    fixtures = Path(__file__).parent / "fixtures"
    with open(fixtures / "amd_detail_ragdoll.json", encoding="utf-8") as f:
        detail = json.load(f)

    from data.providers.amd import build_endpoint_dict

    raw = [build_endpoint_dict(detail)]
    ep = normalize_endpoints(raw)[0]
    # Fixture has model.output = ["text"]; build_endpoint_dict adds "text"
    # to input and image (provider_pricing.vision = true). Verify the
    # lifted dataclass field matches.
    assert ep.architecture is not None
    assert "text" in ep.architecture["input"]
    assert "image" in ep.architecture["input"]
    assert "text" in ep.architecture["output"]
    # And context_length (1048576 in the fixture) lifts correctly.
    assert ep.context_length == 1048576


def test_normalize_lifts_pricing():
    """``item['pricing']`` is copied onto the dataclass field."""
    raw = [{
        "provider": "amd",
        "model_id": "x/y",
        "free": True,
        "pricing": {"prompt": "1.4e-7", "completion": "2.8e-7"},
    }]
    ep = normalize_endpoints(raw)[0]
    assert ep.pricing == {"prompt": "1.4e-7", "completion": "2.8e-7"}


def test_normalize_pricing_none_when_missing():
    """No pricing key in the raw dict → stays None."""
    raw = [{"provider": "amd", "model_id": "x/y", "free": True}]
    ep = normalize_endpoints(raw)[0]
    assert ep.pricing is None


def test_normalize_pricing_empty_dict_stays_none():
    """An empty pricing dict is treated as "no data" → None."""
    raw = [{
        "provider": "amd",
        "model_id": "x/y",
        "free": True,
        "pricing": {},
    }]
    ep = normalize_endpoints(raw)[0]
    assert ep.pricing is None


def test_normalize_lifts_pricing_from_live_amd_fixture():
    """End-to-end: live AMD fixture (MiMo) carries real per-token prices."""
    fixtures = Path(__file__).parent / "fixtures"
    with open(fixtures / "amd_detail_MiMo-V2.6-Flash_live.json", encoding="utf-8") as f:
        detail = json.load(f)

    from data.providers.amd import build_endpoint_dict

    ep = normalize_endpoints([build_endpoint_dict(detail)])[0]
    assert ep.pricing is not None
    # Live AMD data has prompt / completion / input_cache_read keys.
    assert "prompt" in ep.pricing
    assert "completion" in ep.pricing
    # String values preserved verbatim (precision loss risk).
    assert isinstance(ep.pricing["prompt"], str)


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
        data_source=provider,
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


def test_validate_endpoint_unknown_provider_removed_opaque_string_accepted():
    """After the HF parse rewrite, ``provider`` is an opaque string.

    Real HF router provider names (``"novita"`` / ``"fireworks-ai"`` /
    ``"together"`` / ``"cloudflare"`` etc.) are valid; the validator
    only rejects empty / whitespace-only values. Historical test
    ``test_validate_endpoint_unknown_provider`` was removed because
    the allowlist (``{nvidia, amd, huggingface}``) was obsolete.
    """
    ep = _mk("fireworks-ai", "x/y")
    issues = validate_endpoint(ep)
    # No "unknown provider" or "provider is empty" issue should fire.
    assert not any("provider" in i for i in issues)


def test_validate_endpoint_empty_model_id():
    ep = _mk("amd", "  ")
    issues = validate_endpoint(ep)
    assert any("model_id" in i for i in issues)


def test_validate_endpoint_bad_context_length():
    ep = _mk("amd", "x/y")
    ep.metadata["context_length"] = "8192"  # type: ignore[assignment]
    issues = validate_endpoint(ep)
    assert any("context_length" in i for i in issues)


def test_validate_endpoint_architecture_valid():
    """A well-shaped architecture must produce no architecture-related issues."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "architecture", {"input": ["text"], "output": ["text"]})
    issues = validate_endpoint(ep)
    assert not any("architecture" in i for i in issues)


def test_validate_endpoint_architecture_wrong_type():
    """Non-dict architecture is rejected."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "architecture", "not-a-dict")  # type: ignore[arg-type]
    issues = validate_endpoint(ep)
    assert any("architecture must be dict or None" in i for i in issues)


def test_validate_endpoint_architecture_wrong_keys():
    """Extra / missing keys on architecture are rejected."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "architecture", {"input": ["text"], "output": ["text"], "extra": "x"})
    issues = validate_endpoint(ep)
    assert any("architecture keys must be exactly" in i for i in issues)


def test_validate_endpoint_architecture_non_list_values():
    """Non-list values inside architecture are rejected."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "architecture", {"input": "text", "output": ["text"]})
    issues = validate_endpoint(ep)
    assert any("architecture['input'] must be list" in i for i in issues)


def test_validate_endpoint_architecture_non_string_elements():
    """Non-string elements inside architecture lists are rejected."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "architecture", {"input": [1, 2], "output": ["text"]})
    issues = validate_endpoint(ep)
    assert any("architecture['input'] must be list[str]" in i for i in issues)


def test_validate_endpoint_architecture_none_is_ok():
    """architecture = None is the legitimate default for providers that
    don't expose modalities (NVIDIA today). Must not produce issues."""
    ep = _mk("nvidia", "x/y")
    # _mk does not set architecture, so it stays at the dataclass default.
    issues = validate_endpoint(ep)
    assert not any("architecture" in i for i in issues)


def test_validate_endpoint_pricing_valid():
    """A well-shaped pricing dict (string/int/float values) is accepted."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "pricing", {"prompt": "1.4e-7", "completion": 0.0})
    issues = validate_endpoint(ep)
    assert not any("pricing" in i for i in issues)


def test_validate_endpoint_pricing_none_is_ok():
    """pricing = None is the legitimate default for providers without
    per-token prices (HF, NVIDIA today). Must not produce issues."""
    ep = _mk("huggingface", "x/y")
    issues = validate_endpoint(ep)
    assert not any("pricing" in i for i in issues)


def test_validate_endpoint_pricing_wrong_type():
    """Non-dict pricing is rejected."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "pricing", "free")  # type: ignore[arg-type]
    issues = validate_endpoint(ep)
    assert any("pricing must be dict or None" in i for i in issues)


def test_validate_endpoint_pricing_empty_dict_rejected():
    """An empty pricing dict is rejected (must be None or non-empty)."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "pricing", {})
    issues = validate_endpoint(ep)
    assert any("pricing must not be an empty dict" in i for i in issues)


def test_validate_endpoint_pricing_nested_value_rejected():
    """Nested structures inside pricing are rejected (only scalars allowed)."""
    ep = _mk("amd", "x/y")
    object.__setattr__(ep, "pricing", {"prompt": {"min": 0}})
    issues = validate_endpoint(ep)
    assert any("pricing['prompt'] must be scalar" in i for i in issues)


def test_validate_all_splits_valid_invalid():
    good = _mk("amd", "x/y")
    bad = _mk("amd", "  ")  # whitespace-only model_id → invalid
    valid, invalid = validate_all([good, bad])
    assert len(valid) == 1
    assert len(invalid) == 1
    assert invalid[0]["endpoint"]["model_id"] == "  "
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

# ---------------------------------------------------------------------------
# Refactor §24 — manifest reports per-data-source lifecycle (added/updated/removed)
# ---------------------------------------------------------------------------


def test_summarize_all_attaches_reconciliation_plan_lifecycle():
    """When a reconciliation plan is provided, each provider entry
    carries added/updated/removed lists so the Feishu notify card can
    surface lifecycle changes."""
    plan = {
        "by_data_source": {
            "huggingface": {
                "added": ["deepinfra"],
                "updated": ["novita", "together"],
                "removed": ["zai-org"],
            },
            "nvidia": {"added": [], "updated": ["nvidia"], "removed": []},
            "amd": {"added": ["amd"], "updated": [], "removed": []},
        }
    }
    eps = [_mk("huggingface", "openai/gpt-oss-20b"), _mk("amd", "MiMo")]
    manifest = summarize_all(eps, {}, reconciliation_plan=plan)
    hf = manifest["providers"]["huggingface"]
    assert hf["added"] == ["deepinfra"]
    assert sorted(hf["updated"]) == ["novita", "together"]
    assert hf["removed"] == ["zai-org"]


def test_summarize_all_without_plan_omits_lifecycle_fields():
    """Older callers that compute the manifest before reconciliation
    continue to work without the lifecycle fields."""
    manifest = summarize_all([], {})
    assert "added" not in manifest["providers"]["nvidia"]
    assert "removed" not in manifest["providers"]["nvidia"]
