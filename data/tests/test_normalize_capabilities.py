"""Unit tests for normalize_capabilities() in data.process.normalize.

Per the user-confirmed normalization plan: every data source ends up
with the same canonical 7-key boolean shape. Adding a new provider =
one new branch in normalize_capabilities().

We test:
  * the canonical shape is always emitted (no missing keys).
  * nvidia: legacy attrs drive chat + tool_calling; architecture drives
    vision / speech / embedding when no legacy signal.
  * huggingface: architecture modalities drive everything.
  * amd: use_case string drives one canonical flag; architecture drives
    vision fallback.
  * boundary conditions: empty metadata, missing architecture, both.
"""

from __future__ import annotations

from data.process.normalize import (
    CANONICAL_CAPABILITY_KEYS,
    apply_guard_safety_structured_output,
    normalize_capabilities,
)


# ---------------------------------------------------------------------------
# Shape invariant
# ---------------------------------------------------------------------------

def test_normalize_capabilities_always_returns_canonical_keys():
    """Every provider path must emit all 7 canonical keys."""
    out = normalize_capabilities("nvidia", None, None)
    assert set(out.keys()) == set(CANONICAL_CAPABILITY_KEYS)
    # And every value is bool — no None, no missing.
    assert all(isinstance(v, bool) for v in out.values())


def test_normalize_capabilities_unknown_provider_returns_all_false():
    """A provider we don't recognize still emits the canonical shape,
    with every flag False — never silently drops a key."""
    out = normalize_capabilities("openrouter", None, None)
    assert set(out.keys()) == set(CANONICAL_CAPABILITY_KEYS)
    assert all(v is False for v in out.values())


# ---------------------------------------------------------------------------
# nvidia
# ---------------------------------------------------------------------------

def test_nvidia_legacy_attrs_drive_chat_and_tool_calling():
    attrs = {"CHAT_MODALITY": "text2textDiffusion", "TOOL_CALLING": "true"}
    out = normalize_capabilities("nvidia", {"attributes": attrs}, None)
    assert out["chat"] is True
    { id: "structured_output", variant: "neutral"  },
    assert out["vision"] is False
    assert out["speech"] is False


def test_nvidia_legacy_attrs_in_list_form():
    """Real RSC payloads sometimes wrap attrs in a list of {key, value}
    objects. The normalize stage must accept both shapes."""
    attrs = [
        {"key": "CHAT_MODALITY", "value": "text2textDiffusion"},
        {"key": "TOOL_CALLING", "value": "true"},
    ]
    out = normalize_capabilities("nvidia", {"attributes": attrs}, None)
    assert out["chat"] is True
    assert out["tool_calling"] is True


def test_nvidia_legacy_attrs_via_modern_architecture_path():
    """When the architecture block is present (live labels path),
    modality-based derivation takes precedence over legacy attrs."""
    arch = {"input": [], "output": ["text", "image"]}
    # Even with legacy chat attrs, the architecture wins for chat.
    attrs = {"CHAT_MODALITY": "text2textDiffusion"}
    out = normalize_capabilities("nvidia", {"attributes": attrs}, arch)
    assert out["chat"] is True  # from architecture: text in output, no embedding
    assert out["vision"] is True  # from architecture: image in output
    # tool_calling only comes from legacy attrs.
    assert out["tool_calling"] is False


def test_nvidia_with_no_signals():
    """No attrs, no architecture — all False, no crash."""
    out = normalize_capabilities("nvidia", None, None)
    assert all(v is False for v in out.values())


# ---------------------------------------------------------------------------
# huggingface
# ---------------------------------------------------------------------------

def test_huggingface_architecture_drives_capabilities():
    arch = {"input": ["text", "image"], "output": ["text"]}
    out = normalize_capabilities("huggingface", None, arch)
    assert out["chat"] is True  # text in output, no embedding
    assert out["vision"] is True  # image in input


def test_huggingface_embedding_only():
    """Embedding-only models get embedding=True and chat=False."""
    arch = {"input": ["text"], "output": ["embedding"]}
    out = normalize_capabilities("huggingface", None, arch)
    assert out["embedding"] is True
    assert out["chat"] is False


def test_huggingface_audio_in_output_drives_speech():
    arch = {"input": ["text"], "output": ["audio"]}
    out = normalize_capabilities("huggingface", None, arch)
    assert out["speech"] is True


# ---------------------------------------------------------------------------
# amd
# ---------------------------------------------------------------------------

def test_amd_use_case_string_drives_canonical_flag():
    """AMD's ``use_case`` is a single string — normalize maps it to
    one of the canonical 7 keys."""
    out = normalize_capabilities("amd", {"use_case": "chat"}, None)
    assert out["chat"] is True
    assert out["embedding"] is False


def test_amd_use_case_embedding():
    out = normalize_capabilities("amd", {"use_case": "embedding"}, None)
    assert out["embedding"] is True
    assert out["chat"] is False


def test_amd_use_case_transcription_drives_speech():
    out = normalize_capabilities("amd", {"use_case": "transcription"}, None)
    assert out["speech"] is True


def test_amd_use_case_asr_alias_drives_speech():
    """TFI's derive_use_case() emits 'transcription' or 'asr' — both
    should normalize to speech=True."""
    out = normalize_capabilities("amd", {"use_case": "asr"}, None)
    assert out["speech"] is True


def test_amd_use_case_unknown_drives_nothing():
    """If derive_use_case() returns None or an unknown string, no
    capability flag is set. The architecture fallback may still apply."""
    out = normalize_capabilities("amd", {"use_case": None}, None)
    assert all(v is False for v in out.values())
    out = normalize_capabilities("amd", {"use_case": "unknown-thing"}, None)
    assert all(v is False for v in out.values())


def test_amd_vision_via_architecture_fallback():
    """AMD's use_case doesn't carry vision — but the architecture
    block does. The normalize stage falls back to modalities."""
    arch = {"input": ["text", "image"], "output": ["text"]}
    out = normalize_capabilities("amd", {"use_case": "chat"}, arch)
    assert out["chat"] is True
    assert out["vision"] is True


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------

def test_empty_inputs_return_all_false():
    """No metadata, no architecture — must still emit the canonical
    shape, all False."""
    out = normalize_capabilities("huggingface", {}, {})
    assert all(v is False for v in out.values())


def test_none_inputs_return_all_false():
    out = normalize_capabilities("nvidia", None, None)
    assert all(v is False for v in out.values())


# ---------------------------------------------------------------------------
# Guard/safety model id heuristic (structured_output)
# ---------------------------------------------------------------------------

def _make_ep(model_id: str) -> "ModelEndpoint":
    from datetime import datetime, timezone

    from data.models.schema import ModelEndpoint

    return ModelEndpoint(
        provider="nvidia",
        model_id=model_id,
        data_source="nvidia",
        free=True,
        fetched_at=datetime.now(timezone.utc),
        name=None,
        description=None,
        source_url=None,
        capabilities={k: False for k in CANONICAL_CAPABILITY_KEYS},
        metadata={},
        lab="nvidia",
    )


def test_guard_model_id_infers_structured_output():
    """A model with ``guard`` in its id gets structured_output=True."""
    ep = _make_ep("meta/llama-guard-4-12b")
    apply_guard_safety_structured_output(ep)
    assert ep.capabilities["structured_output"] is True


def test_safety_model_id_infers_structured_output():
    """A model with ``safety`` in its id gets structured_output=True."""
    ep = _make_ep("nvidia/nemotron-3.5-content-safety")
    apply_guard_safety_structured_output(ep)
    so = ep.capabilities["structured_output"]
    assert so is True


def test_normal_model_id_stays_false():
    """Control: non-guard/safety ids never gain structured_output."""
    ep = _make_ep("meta/llama-3.3-70b-instruct")
    apply_guard_safety_structured_output(ep)
    assert ep.capabilities["structured_output"] is False


def test_guard_heuristic_is_case_insensitive():
    ep = _make_ep("Meta/Llama-GUARD-4-12B")
    apply_guard_safety_structured_output(ep)
    assert ep.capabilities["structured_output"] is True


def test_guard_heuristic_never_disables():
    """Additive only: an already-True structured_output stays True."""
    caps = {k: False for k in CANONICAL_CAPABILITY_KEYS}
    caps["structured_output"] = True

    from datetime import datetime, timezone

    from data.models.schema import ModelEndpoint

    ep = ModelEndpoint(
        provider="nvidia",
        model_id="meta/llama-guard-4-12b",
        data_source="nvidia",
        free=True,
        fetched_at="2026-10-10T00:00:00Z" if False else datetime.now(timezone.utc),
        name=None,
        description=None,
        source_url=None,
        capabilities=caps,
        metadata={},
        lab="nvidia",
    )
    apply_guard_safety_structured_output(ep)
    assert ep.capabilities["structured_output"] is True


def test_guard_heuristic_via_normalize_endpoints():
    """End-to-end through normalize_endpoints: a raw provider dict
    with a guard id comes out with structured_output=True."""
    from data.process.normalize import normalize_endpoints

    raw = [
        {
            "provider": "nvidia",
            "data_source": "nvidia",
            "model_id": "meta/llama-guard-4-12b",
            "free": True,
            "name": "Llama Guard 4 12B",
            "description": None,
            "capabilities": {},
            "metadata": {},
        },
        {
            "provider": "nvidia",
            "data_source": "nvidia",
            "model_id": "meta/llama-3.3-70b-instruct",
            "free": True,
            "name": "Llama 3.3 70B",
            "capabilities": {},
            "metadata": {},
        },
    ]
    endpoints = normalize_endpoints(raw)
    assert endpoints[0].capabilities["structured_output"] is True
    assert endpoints[1].capabilities["structured_output"] is False