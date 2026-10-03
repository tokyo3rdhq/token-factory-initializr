"""AMD use_case → canonical capabilities integration.

The AMD provider builds an endpoint dict with ``metadata.use_case``
as the raw signal for the normalize stage. After normalize, the
canonical ``capabilities.chat`` (or vision / embedding / speech) must
be True. This regression test pins the wiring — without it, AMD's
``use_case = "chat"`` would be silently dropped at the consumer
(bug observed when AMD models showed ``vision + free`` but NOT
``chat`` on the Browse tag row).

Per the user-confirmed normalization plan: AMD stores its raw
``use_case`` string in ``metadata`` so the normalize stage can
fuse it into the canonical 7-key boolean shape.
"""

from __future__ import annotations

from data.process.normalize import normalize_endpoints
from data.providers.amd import build_endpoint_dict, derive_use_case


def _amd_fixture(capability: str = "chat", output: list[str] | None = None):
    """Wrap a model detail in the ``{"model": {...}}`` shape AMD's
    ``build_endpoint_dict`` expects.
    """
    if output is None:
        output = ["text"]
    return {
        "model": {
            "id": "model_gateway:test-model",
            "model": "test-model",
            "label": "Test Model",
            "description": "",
            "output": output,
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "publisher": {"name": "Test Lab"},
                "capability": {"key": capability},
            },
            "provider_pricing": [{"pricing": {"prompt": "0", "completion": "0"}}],
            "context_length": 4096,
        }
    }


def test_amd_chat_use_case_normalizes_to_canonical_chat():
    detail = _amd_fixture(capability="chat")
    raw = [build_endpoint_dict(detail)]
    eps = normalize_endpoints(raw)
    assert len(eps) == 1
    cap = eps[0].capabilities
    # Canonical shape — chat is True, others are False.
    assert cap["chat"] is True
    assert cap["tool_calling"] is False
    assert cap["vision"] is False
    # Every key present.
    assert set(cap.keys()) == {
        "chat", "vision", "speech", "embedding",
        "tool_calling", "structured_output", "reasoning",
    }


def test_amd_vision_use_case_normalizes_to_canonical_vision():
    detail = _amd_fixture(capability="vision", output=["text", "image"])
    raw = [build_endpoint_dict(detail)]
    eps = normalize_endpoints(raw)
    assert eps[0].capabilities["vision"] is True


def test_amd_embedding_use_case_normalizes_to_canonical_embedding():
    detail = _amd_fixture(capability="embedding", output=["embedding"])
    raw = [build_endpoint_dict(detail)]
    eps = normalize_endpoints(raw)
    assert eps[0].capabilities["embedding"] is True
    assert eps[0].capabilities["chat"] is False


def test_amd_transcription_use_case_normalizes_to_canonical_speech():
    detail = _amd_fixture(capability="transcription", output=["text"])
    raw = [build_endpoint_dict(detail)]
    eps = normalize_endpoints(raw)
    assert eps[0].capabilities["speech"] is True


def test_amd_no_use_case_metadata_yields_all_false_canonical():
    """If AMD's metadata loses the use_case field (regression), the
    normalize stage must still emit the canonical 7-key shape with
    everything False — not crash, not silently empty. Architecture
    modalities with text output still set chat=True via the shared
    architecture path, so this fixture uses an output that has no
    text (and no other modality) so chat stays False."""
    detail = _amd_fixture(capability="transcription", output=["nontext"])
    ep = build_endpoint_dict(detail)
    # The legacy AMD dict still carries ``capabilities.use_case`` —
    # pop that too so neither signal reaches the normalize stage.
    ep["capabilities"].pop("use_case", None)
    ep["metadata"].pop("use_case", None)
    eps = normalize_endpoints([ep])
    assert set(eps[0].capabilities.keys()) == {
        "chat", "vision", "speech", "embedding",
        "tool_calling", "structured_output", "reasoning",
    }
    # Every key is False — no chat (no text modality), no vision /
    # speech / embedding either.
    assert all(v is False for v in eps[0].capabilities.values())