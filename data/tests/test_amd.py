"""Unit tests for AMD provider."""

from __future__ import annotations
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from unittest.mock import Mock, patch

from data.providers.amd import (
    BASE,
    DEFAULT_UA,
    TIMEOUT,
    _get_json,
    _parse_bootstrap,
    _post_json,
    _strip_gateway_prefix,
    build_endpoint_dict,
    derive_use_case,
    fetch_amd_models,
    fetch_bootstrap,
    fetch_detail,
)


# ---------------------------------------------------------------------------
# _post_json (HTTP transport)
# ---------------------------------------------------------------------------


def test_post_json_returns_decoded_body():
    payload = {"x": 1}
    with patch("data.providers.amd.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        out = _post_json("https://example.test/api", {"k": "v"}, "test-ua", "https://example.test/", timeout=10)
    assert out == payload
    # Verify request method/headers
    req = mock_urlopen.call_args[0][0]
    assert req.method == "POST"
    assert req.headers["Content-type"] == "application/json"
    assert req.headers["User-agent"] == "test-ua"
    assert req.headers["Origin"] == "https://developer.amd.com.cn"
    assert req.headers["Referer"] == "https://example.test/"


def test_post_json_serializes_body_as_json_bytes():
    with patch("data.providers.amd.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = b'{"ok": 1}'
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        _post_json("https://x", {"k": "v"}, "ua", "ref", timeout=10)
    req = mock_urlopen.call_args[0][0]
    assert req.data == json.dumps({"k": "v"}).encode("utf-8")


# ---------------------------------------------------------------------------
# _get_json (HTTP transport)
# ---------------------------------------------------------------------------


def test_get_json_returns_decoded_body():
    payload = {"y": 2}
    with patch("data.providers.amd.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        out = _get_json("https://example.test/api", "test-ua", timeout=10)
    assert out == payload
    req = mock_urlopen.call_args[0][0]
    assert req.headers["User-agent"] == "test-ua"


# ---------------------------------------------------------------------------
# fetch_bootstrap (high-level)
# ---------------------------------------------------------------------------


def test_fetch_bootstrap_uses_directory_endpoint():
    """fetch_bootstrap must hit /radeon/api/tokenfactory/bootstrap?directory=true."""
    with patch("data.providers.amd._post_json") as mock_post:
        mock_post.return_value = {"cards": []}
        fetch_bootstrap("ua", timeout=10)
        args = mock_post.call_args[0]
    assert args[0] == f"{BASE}/radeon/api/tokenfactory/bootstrap?directory=true"
    assert args[1] == {}
    assert args[2] == "ua"
    assert args[3] == f"{BASE}/radeon/tokenfactory"
    assert args[4] == 10


def test_fetch_bootstrap_returns_full_dict_not_just_cards():
    """fetch_bootstrap returns the raw bootstrap dict — callers extract cards."""
    with patch("data.providers.amd._post_json") as mock_post:
        mock_post.return_value = {"object": "list", "data": [], "extra": "stuff"}
        out = fetch_bootstrap("ua", timeout=10)
    assert out == {"object": "list", "data": [], "extra": "stuff"}


def test_fetch_bootstrap():
    with open(str(FIXTURES / "amd_bootstrap.json"), encoding="utf-8") as f:
        bootstrap = json.load(f)

    with patch("data.providers.amd._post_json") as mock_post:
        mock_post.return_value = bootstrap
        result = fetch_bootstrap("test-ua", timeout=5)
        assert "cards" in result
        assert len(result["cards"]) == 2
        ids = {item["id"] for item in result["cards"]}
        assert ids == {"model_gateway:MiMo-V2.6-Flash", "model_gateway:DeepSeek-V4-Flash"}


# ---------------------------------------------------------------------------
# fetch_detail (high-level)
# ---------------------------------------------------------------------------


def test_fetch_detail_url_encodes_model_id():
    """Colons and slashes in model_id must be URL-encoded."""
    with patch("data.providers.amd._get_json") as mock_get:
        mock_get.return_value = {"model": {"id": "x/y:z"}}
        fetch_detail("x/y:z", "ua", timeout=10)
        args = mock_get.call_args[0]
    assert args[0] == f"{BASE}/radeon/api/tokenfactory/model?id=x%2Fy%3Az"
    assert args[1] == "ua"
    assert args[2] == 10


def test_fetch_detail():
    with open(str(FIXTURES / "amd_detail_ragdoll.json"), encoding="utf-8") as f:
        detail = json.load(f)

    with patch("data.providers.amd._get_json") as mock_get:
        mock_get.return_value = detail
        result = fetch_detail("model_gateway:MiMo-V2.6-Flash", "test-ua", timeout=5)
        assert result == detail


# ---------------------------------------------------------------------------
# _parse_bootstrap
# ---------------------------------------------------------------------------


def test_parse_bootstrap_flattens_to_id_section():
    """Cards are normalized to {id, section} pairs."""
    cards = [
        {"id": "model_gateway:A", "section": "public_free", "extra": "ignored"},
        {"id": "model_gateway:B", "section": "premium"},
    ]
    out = _parse_bootstrap(cards)
    assert out == [
        {"id": "model_gateway:A", "section": "public_free"},
        {"id": "model_gateway:B", "section": "premium"},
    ]


def test_parse_bootstrap_empty():
    assert _parse_bootstrap([]) == []


# ---------------------------------------------------------------------------
# derive_use_case
# ---------------------------------------------------------------------------


def _model(capability=None, output=None):
    return {
        "token_factory": {"capability": {"key": capability}},
        "output": output or [],
    }


def test_derive_use_case_chat_capability():
    assert derive_use_case(_model(capability="chat")) == "chat"


def test_derive_use_case_text_capability():
    assert derive_use_case(_model(capability="text")) == "chat"


def test_derive_use_case_vision_capability():
    assert derive_use_case(_model(capability="vision")) == "vision"


def test_derive_use_case_vlm_capability():
    assert derive_use_case(_model(capability="vlm")) == "vision"


def test_derive_use_case_embedding_capability():
    assert derive_use_case(_model(capability="embedding")) == "embedding"


def test_derive_use_case_speech_capability():
    assert derive_use_case(_model(capability="speech")) == "speech"


def test_derive_use_case_transcription_capability():
    assert derive_use_case(_model(capability="transcription")) == "transcription"


def test_derive_use_case_asr_capability():
    assert derive_use_case(_model(capability="asr")) == "transcription"


def test_derive_use_case_falls_back_to_embedding_output():
    assert derive_use_case(_model(capability=None, output=["embedding"])) == "embedding"


def test_derive_use_case_falls_back_to_text_output():
    assert derive_use_case(_model(capability=None, output=["text"])) == "chat"


def test_derive_use_case_unknown_returns_none_to_drop():
    """Unknown capability + non-matching output → None (drop from registry)."""
    assert derive_use_case(_model(capability="alien-tech", output=["quantum"])) is None


def test_derive_use_case_no_token_factory_returns_none():
    """Missing token_factory.capability.key is treated as unknown."""
    assert derive_use_case({"output": []}) is None


# ---------------------------------------------------------------------------
# _strip_gateway_prefix
# ---------------------------------------------------------------------------


def test_strip_gateway_prefix_strips_model_gateway():
    from data.providers.amd import _strip_gateway_prefix

    assert _strip_gateway_prefix("model_gateway:MiMo-V2.6-Flash") == "MiMo-V2.6-Flash"


def test_strip_gateway_prefix_strips_any_gateway_suffix():
    """Any *_gateway prefix should be stripped, not just model_gateway."""
    from data.providers.amd import _strip_gateway_prefix

    assert _strip_gateway_prefix("router_gateway:Foo") == "Foo"
    assert _strip_gateway_prefix("chat_gateway:Bar") == "Bar"


def test_strip_gateway_prefix_leaves_unknown_prefixes():
    """Don't strip colons that aren't a known gateway prefix."""
    from data.providers.amd import _strip_gateway_prefix

    assert _strip_gateway_prefix("owner:Foo") == "owner:Foo"
    assert _strip_gateway_prefix("no-prefix-here") == "no-prefix-here"


# ---------------------------------------------------------------------------
# build_endpoint_dict
# ---------------------------------------------------------------------------


def test_build_endpoint_dict():
    with open(str(FIXTURES / "amd_detail_ragdoll.json"), encoding="utf-8") as f:
        detail = json.load(f)

    result = build_endpoint_dict(detail)
    assert result["provider"] == "amd"
    # model_id strips AMD's "model_gateway:" prefix to stay consistent with
    # other providers (NVIDIA/HF use org/name without a gateway prefix).
    assert result["model_id"] == "MiMo-V2.6-Flash"
    assert result["free"] is True
    assert result["name"] == "MiMo-V2.6-Flash"
    assert result["metadata"]["context_length"] == 1048576
    # Description comes from the AMD detail response (not hardcoded None).
    assert result["description"] == "Dynamic sglang-router service managed by Model Ops"
    # Original AMD id (with prefix) is kept in metadata for traceability.
    assert result["metadata"]["original_id"] == "model_gateway:MiMo-V2.6-Flash"


def test_build_endpoint_dict_includes_use_case_in_capabilities():
    with open(str(FIXTURES / "amd_detail_ragdoll.json"), encoding="utf-8") as f:
        detail = json.load(f)
    result = build_endpoint_dict(detail)
    assert "use_case" in result["capabilities"]


def test_build_endpoint_dict_strips_other_gateway_prefixes():
    """Any *_gateway: prefix should be stripped, not just model_gateway:."""
    detail = {
        "model": {
            "id": "router_gateway:Some-Model",
            "label": "Some Model",
            "model": "Some-Model",
            "output": ["text"],
            "description": "Test",
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["model_id"] == "Some-Model"
    assert result["metadata"]["original_id"] == "router_gateway:Some-Model"


def test_build_endpoint_dict_keeps_id_without_known_prefix():
    """An id without a recognized gateway prefix is preserved as-is."""
    detail = {
        "model": {
            "id": "no-prefix-here",
            "label": "Plain",
            "output": ["text"],
            "description": "Test",
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["model_id"] == "no-prefix-here"


def test_build_endpoint_dict_pulls_description_from_model():
    """description should come from model.description, not be hardcoded None."""
    detail = {
        "model": {
            "id": "model_gateway:X",
            "label": "X",
            "output": ["text"],
            "description": "A custom description from AMD's API",
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["description"] == "A custom description from AMD's API"


def test_build_endpoint_dict_description_is_none_when_missing():
    detail = {
        "model": {
            "id": "model_gateway:X",
            "label": "X",
            "output": ["text"],
            # no description field
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["description"] is None


def test_build_endpoint_dict_free_false_when_status_not_free_endpoint():
    detail = {
        "model": {
            "id": "model_gateway:Paid",
            "label": "Paid Model",
            "model": "paid",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "paid"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["free"] is False
    assert result["metadata"]["free_status"] == "paid"


def test_build_endpoint_dict_adds_image_input_for_vision_pricing():
    detail = {
        "model": {
            "id": "model_gateway:VL",
            "label": "VL",
            "model": "vl",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "vision"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{"vision": True}],
            "context_length": 8192,
        }
    }
    result = build_endpoint_dict(detail)
    assert "image" in result["metadata"]["input_modalities"]


def test_build_endpoint_dict_adds_image_input_for_ocr_pricing():
    detail = {
        "model": {
            "id": "model_gateway:OCR",
            "label": "OCR",
            "model": "ocr",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "vision"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{"ocr": True}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert "image" in result["metadata"]["input_modalities"]


def test_build_endpoint_dict_input_modalities_always_includes_text():
    detail = {
        "model": {
            "id": "model_gateway:T",
            "label": "T",
            "model": "t",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert "text" in result["metadata"]["input_modalities"]


def test_build_endpoint_dict_falls_back_to_model_id_for_name():
    """When label and model are missing, the stripped model_id is used as the name."""
    detail = {
        "model": {
            "id": "model_gateway:OnlyId",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["name"] == "OnlyId"


def test_build_endpoint_dict_uses_label_when_present():
    """label takes priority over model field for the name."""
    detail = {
        "model": {
            "id": "model_gateway:X",
            "label": "The Label",
            "model": "the-model",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "provider_pricing": [{}],
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert result["name"] == "The Label"


def test_build_endpoint_dict_handles_missing_provider_pricing():
    detail = {
        "model": {
            "id": "model_gateway:NP",
            "label": "NP",
            "model": "np",
            "output": ["text"],
            "token_factory": {
                "status": {"key": "free_endpoint"},
                "capability": {"key": "chat"},
                "publisher": {"name": "AMD"},
            },
            "context_length": 4096,
        }
    }
    result = build_endpoint_dict(detail)
    assert "text" in result["metadata"]["input_modalities"]


# ---------------------------------------------------------------------------
# fetch_amd_models (high-level)
# ---------------------------------------------------------------------------


def test_fetch_amd_models():
    with open(str(FIXTURES / "amd_bootstrap.json"), encoding="utf-8") as f:
        bootstrap = json.load(f)
    with open(str(FIXTURES / "amd_detail_ragdoll.json"), encoding="utf-8") as f:
        detail_ragdoll = json.load(f)
    with open(str(FIXTURES / "amd_detail_mistral.json"), encoding="utf-8") as f:
        detail_mistral = json.load(f)

    with patch("data.providers.amd.fetch_bootstrap") as mock_bootstrap, \
         patch("data.providers.amd.fetch_detail") as mock_detail:
        mock_bootstrap.return_value = bootstrap
        mock_detail.side_effect = [detail_ragdoll, detail_mistral]
        result = fetch_amd_models()
        assert len(result) == 2
        model_ids = {ep["model_id"] for ep in result}
        # model_id has the gateway prefix stripped (consistent with NVIDIA/HF).
        assert model_ids == {
            "MiMo-V2.6-Flash",
            "DeepSeek-V4-Flash",
        }
        # Original id is preserved in metadata.
        for ep in result:
            assert ep["metadata"]["original_id"].startswith("model_gateway:")
        for ep in result:
            assert ep["provider"] == "amd"
            assert ep["free"] is True


def test_fetch_amd_models_empty_cards_returns_empty_list():
    """No cards in bootstrap → no endpoints, no detail fetches."""
    with patch("data.providers.amd.fetch_bootstrap") as mock_bootstrap, \
         patch("data.providers.amd.fetch_detail") as mock_detail:
        mock_bootstrap.return_value = {"cards": []}
        result = fetch_amd_models()
    assert result == []
    mock_detail.assert_not_called()


def test_fetch_amd_models_propagates_bootstrap_failure():
    """If fetch_bootstrap raises, fetch_amd_models does not swallow it."""
    with patch("data.providers.amd.fetch_bootstrap") as mock_bootstrap:
        mock_bootstrap.side_effect = RuntimeError("network down")
        try:
            fetch_amd_models()
        except RuntimeError as exc:
            assert "network down" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_fetch_amd_models_uses_default_ua():
    """fetch_amd_models must call bootstrap/detail with DEFAULT_UA."""
    with open(str(FIXTURES / "amd_bootstrap.json"), encoding="utf-8") as f:
        bootstrap = json.load(f)
    with open(str(FIXTURES / "amd_detail_ragdoll.json"), encoding="utf-8") as f:
        detail = json.load(f)

    with patch("data.providers.amd.fetch_bootstrap") as mock_bootstrap, \
         patch("data.providers.amd.fetch_detail") as mock_detail:
        mock_bootstrap.return_value = bootstrap
        mock_detail.return_value = detail
        fetch_amd_models()
        # Both bootstrap and detail must be called with DEFAULT_UA
        assert mock_bootstrap.call_args[0][0] == DEFAULT_UA
        assert all(call.args[1] == DEFAULT_UA for call in mock_detail.call_args_list)