"""Unit tests for option A cross-source normalization.

The normalize stage now accepts a ``cross_source_index`` (keyed by
alias-normalized canonical model_id → OpenRouter raw observation) and
fuses OR's raw architecture + supported_parameters signals into the
primary source's normalize pass. Capabilities that ultimately come from
OR are stamped ``method=native`` at the enrich stage, because option A
makes them part of the primary-source view of the model.
"""

from __future__ import annotations

from data.process.normalize import normalize_capabilities


# ---------------------------------------------------------------------------
# Architecture fusion (modality lists)
# ---------------------------------------------------------------------------


def test_nvidia_no_architecture_fills_vision_from_or():
    """NVIDIA raw has no architecture; OR declares image in input.
    The fused normalize pass must surface vision=True."""
    nvidia_meta = {"attributes": {"CHAT_MODALITY": "text2textDiffusion"}}
    or_signals = {
        "architecture": {"input": ["text", "image"], "output": ["text"]},
        "metadata": {"supported_parameters": []},
    }
    out = normalize_capabilities("nvidia", nvidia_meta, None, cross_source_signals=or_signals)
    assert out["vision"] is True
    assert out["chat"] is True  # from NVIDIA CHAT_MODALITY


def test_nvidia_vision_modality_via_output():
    """OR declares image in output modality."""
    or_signals = {"architecture": {"input": ["text"], "output": ["text", "image"]}}
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["vision"] is True


def test_nvidia_speech_via_or_audio_modality():
    """OR declares audio output → speech=True on NVIDIA endpoint."""
    or_signals = {"architecture": {"input": ["text"], "output": ["audio"]}}
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["speech"] is True


def test_amd_use_case_chat_fused_with_or_vision():
    """AMD use_case=chat + OR declares image input → chat+vision both True."""
    or_signals = {"architecture": {"input": ["image"], "output": ["text"]}}
    out = normalize_capabilities("amd", {"use_case": "chat"}, None, cross_source_signals=or_signals)
    assert out["chat"] is True
    assert out["vision"] is True


# ---------------------------------------------------------------------------
# supported_parameters fusion (tool_calling, reasoning)
# ---------------------------------------------------------------------------


def test_nvidia_tool_calling_from_or_supported_parameters():
    """NVIDIA doesn't expose TOOL_CALLING attrs; OR does via supported_parameters."""
    or_signals = {
        "architecture": {"input": ["text"], "output": ["text"]},
        "metadata": {"supported_parameters": ["tools"]},
    }
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["tool_calling"] is True


def test_nvidia_tool_calling_from_tool_choice():
    or_signals = {
        "architecture": {"input": ["text"], "output": ["text"]},
        "metadata": {"supported_parameters": ["tool_choice"]},
    }
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["tool_calling"] is True


def test_nvidia_reasoning_from_or_default_enabled():
    or_signals = {
        "architecture": {"input": ["text"], "output": ["text"]},
        "metadata": {
            "supported_parameters": [],
            "reasoning": {"default_enabled": True},
        },
    }
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["reasoning"] is True


def test_nvidia_reasoning_from_or_supported_parameters():
    or_signals = {
        "architecture": {"input": ["text"], "output": ["text"]},
        "metadata": {"supported_parameters": ["reasoning"]},
    }
    out = normalize_capabilities("nvidia", {}, None, cross_source_signals=or_signals)
    assert out["reasoning"] is True


# ---------------------------------------------------------------------------
# Primary-source precedence
# ---------------------------------------------------------------------------


def test_primary_source_chat_wins_over_or_no_chat():
    """If NVIDIA declares chat but OR doesn't, chat=True regardless of OR."""
    or_signals = {"architecture": {"input": ["text"], "output": ["embedding"]}}
    nvidia_meta = {"attributes": {"CHAT_MODALITY": "text2textDiffusion"}}
    out = normalize_capabilities("nvidia", nvidia_meta, None, cross_source_signals=or_signals)
    assert out["chat"] is True
    assert out["embedding"] is True


def test_no_cross_source_signals_unchanged_behavior():
    """When cross_source_signals is None, behavior matches the legacy path."""
    out = normalize_capabilities("nvidia", {"attributes": {"CHAT_MODALITY": "text2textDiffusion"}}, None)
    assert out["chat"] is True
    assert out["tool_calling"] is False
    assert out["vision"] is False


def test_empty_cross_source_signals_unchanged_behavior():
    out = normalize_capabilities(
        "nvidia",
        {"attributes": {"CHAT_MODALITY": "text2textDiffusion"}},
        None,
        cross_source_signals={},
    )
    assert out["chat"] is True
    assert out["tool_calling"] is False
