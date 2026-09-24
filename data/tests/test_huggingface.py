"""Unit tests for Hugging Face provider."""

from __future__ import annotations
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

if str(Path(__file__).parent.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import json
import urllib.error
from unittest.mock import Mock, patch

from data.providers import huggingface as hf
from data.providers.huggingface import (
    ROUTER_URL,
    SOCKS_PROXY_ENV,
    UA,
    _apply_socks_proxy,
    fetch_huggingface_models,
    fetch_router_json,
    filter_free_providers,
    to_endpoint_dicts,
)


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_router_url_points_to_v1_models():
    assert ROUTER_URL == "https://router.huggingface.co/v1/models"


def test_user_agent_is_chrome_153():
    """UA must be the pinned Chrome 153 stable (otherwise WAF may reject)."""
    assert "Chrome/153" in UA


# ---------------------------------------------------------------------------
# _apply_socks_proxy (local dev proxy)
# ---------------------------------------------------------------------------


def test_apply_socks_proxy_noop_when_env_unset(monkeypatch):
    """No SOCKS5_PROXY env → no proxy installed."""
    monkeypatch.delenv(SOCKS_PROXY_ENV, raising=False)
    # Reset any prior install
    _apply_socks_proxy._installed = False
    with patch.object(hf.socket, "socket") as mock_socket:
        _apply_socks_proxy()
        # socket.socket must NOT be replaced
        mock_socket.assert_not_called()
    assert getattr(_apply_socks_proxy, "_installed", False) is False


def test_apply_socks_proxy_installs_socket_once(monkeypatch):
    """SOCKS5_PROXY set + PySocks available -> socket.socket gets replaced."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "socks5h://127.0.0.1:7897")
    _apply_socks_proxy._installed = False

    # Patch socks module into sys.modules so the import inside _apply_socks_proxy resolves.
    fake_socks = Mock()
    fake_socks.SOCKS5 = 5
    original_socket = hf.socket.socket  # save to restore later

    try:
        with patch.dict(sys.modules, {"socks": fake_socks}):
            _apply_socks_proxy()
        assert hf.socket.socket is fake_socks.socksocket, "socket.socket should be replaced"
        assert _apply_socks_proxy._installed is True
        # socks.set_default_proxy must be called with parsed host/port + SOCKS5
        fake_socks.set_default_proxy.assert_called_once_with(
            fake_socks.SOCKS5, "127.0.0.1", 7897, rdns=True,
        )
    finally:
        # Restore socket.socket to avoid leaking into other tests.
        hf.socket.socket = original_socket
        _apply_socks_proxy._installed = False


def test_apply_socks_proxy_is_idempotent(monkeypatch):
    """Calling twice does not re-install the socket attribute."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "socks5h://127.0.0.1:7897")
    fake_socks = Mock()
    fake_socks.SOCKS5 = 5
    with patch.dict(sys.modules, {"socks": fake_socks}):
        with patch.object(hf.socket, "socket", create=True) as mock_socket_attr:
            _apply_socks_proxy()
            first_attr = mock_socket_attr
            # Reset mock to see if 2nd call touches it
            mock_socket_attr.reset_mock()
            _apply_socks_proxy()
            # 2nd call should NOT call mock_socket_attr (= attr setter)
            mock_socket_attr.assert_not_called()


def test_apply_socks_proxy_warns_when_pysocks_missing(monkeypatch, caplog):
    """SOCKS5_PROXY set + PySocks missing -> warn and fall back to direct."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "socks5h://127.0.0.1:7897")
    # Reset the install guard so this test actually runs the install path.
    _apply_socks_proxy._installed = False
    # Make socks import fail by injecting None into sys.modules.
    with patch.dict(sys.modules, {"socks": None}):
        with caplog.at_level("WARNING"):
            _apply_socks_proxy()
    # Verify warning was emitted with the expected message text.
    messages = [r.getMessage() for r in caplog.records]
    assert any("PySocks is not installed" in m for m in messages)


def test_apply_socks_proxy_handles_invalid_url(monkeypatch, caplog):
    """Malformed SOCKS5_PROXY must not crash — just warn and fall back."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "not-a-url")
    _apply_socks_proxy._installed = False
    fake_socks = Mock()
    fake_socks.SOCKS5 = 5
    with patch.dict(sys.modules, {"socks": fake_socks}):
        with caplog.at_level("WARNING"):
            _apply_socks_proxy()
    messages = [r.getMessage() for r in caplog.records]
    assert any("Invalid SOCKS5_PROXY" in m for m in messages)


# ---------------------------------------------------------------------------
# fetch_router_json (HTTP transport)
# ---------------------------------------------------------------------------


def test_fetch_router_json():
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)

    with patch("data.providers.huggingface.urllib.request.urlopen") as mock_urlopen, \
         patch("data.providers.huggingface.urllib.request.Request") as mock_request:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = fetch_router_json(timeout=5)
        assert "data" in result
        assert len(result["data"]) == 4


def test_fetch_router_json_applies_socks_proxy_before_request(monkeypatch):
    """Every fetch_router_json call must trigger proxy setup (idempotent)."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "socks5h://127.0.0.1:7897")
    _apply_socks_proxy._installed = False

    with patch("data.providers.huggingface.urllib.request.urlopen") as mock_urlopen, \
         patch("data.providers.huggingface._apply_socks_proxy") as mock_apply:
        mock_resp = Mock()
        mock_resp.read.return_value = b'{"data": []}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        fetch_router_json(timeout=5)
    mock_apply.assert_called_once()


def test_fetch_router_json_raises_runtimeerror_on_network_failure():
    """URLError must be wrapped in RuntimeError so callers can detect network issues."""
    with patch("data.providers.huggingface.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        try:
            fetch_router_json(timeout=5)
        except RuntimeError as exc:
            assert "Network error" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_fetch_router_json_sends_correct_headers():
    """Verify URL and Accept/User-Agent headers are set as expected."""
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)

    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url if hasattr(req, "full_url") else str(req)
        captured["headers"] = dict(req.header_items())
        resp = Mock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        # urlopen returns a context manager
        resp.__enter__ = Mock(return_value=resp)
        resp.__exit__ = Mock(return_value=False)
        return resp

    with patch("data.providers.huggingface.urllib.request.urlopen", side_effect=fake_urlopen):
        fetch_router_json(timeout=5)

    assert captured["url"] == ROUTER_URL
    headers_lower = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers_lower.get("user-agent") == UA
    assert "application/json" in headers_lower.get("accept", "")


# ---------------------------------------------------------------------------
# filter_free_providers
# ---------------------------------------------------------------------------


def test_filter_free_providers_drops_paid_providers():
    """A provider with pricing != 0 must be filtered out."""
    payload = {
        "data": [
            {
                "id": "meta/paid-model",
                "owned_by": "meta",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [
                    {"provider": "huggingface", "pricing": {"input": 0.001, "output": 0.002}, "status": "live"},
                ],
            }
        ]
    }
    assert filter_free_providers(payload) == []


def test_filter_free_providers_drops_non_live_status():
    """A provider with status != 'live' must be filtered out."""
    payload = {
        "data": [
            {
                "id": "meta/dead",
                "owned_by": "meta",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [
                    {"provider": "huggingface", "pricing": {"input": 0, "output": 0}, "status": "staging"},
                ],
            }
        ]
    }
    assert filter_free_providers(payload) == []


def test_filter_free_providers_drops_models_without_providers():
    """A model with no providers at all must be dropped."""
    payload = {
        "data": [
            {
                "id": "meta/lonely",
                "owned_by": "meta",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [],
            }
        ]
    }
    assert filter_free_providers(payload) == []


def test_filter_free_providers_keeps_model_with_at_least_one_free():
    """If ≥1 provider is free+live, the model survives (others dropped)."""
    payload = {
        "data": [
            {
                "id": "meta/mixed",
                "owned_by": "meta",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [
                    {"provider": "huggingface", "pricing": {"input": 0, "output": 0}, "status": "live"},
                    {"provider": "paidco", "pricing": {"input": 0.5, "output": 0.5}, "status": "live"},
                ],
            }
        ]
    }
    out = filter_free_providers(payload)
    assert len(out) == 1
    assert len(out[0]["free_providers"]) == 1
    assert out[0]["free_providers"][0]["provider"] == "huggingface"


def test_filter_free_providers_owned_by_defaults_to_first_path_segment():
    """If 'owned_by' is missing, owned_by defaults to the org segment of model_id."""
    payload = {
        "data": [
            {
                "id": "fallback-org/some-model",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [
                    {"provider": "huggingface", "pricing": {"input": 0, "output": 0}, "status": "live"},
                ],
            }
        ]
    }
    out = filter_free_providers(payload)
    assert out[0]["owned_by"] == "fallback-org"


def test_filter_free_providers_handles_missing_pricing_field():
    """Provider entry with no 'pricing' key is treated as paid (drop)."""
    payload = {
        "data": [
            {
                "id": "meta/x",
                "owned_by": "meta",
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "providers": [{"provider": "huggingface", "status": "live"}],
            }
        ]
    }
    assert filter_free_providers(payload) == []


def test_filter_free_providers_handles_empty_data():
    """Missing 'data' key → empty result (no crash)."""
    assert filter_free_providers({"data": []}) == []
    assert filter_free_providers({}) == []


def test_filter_free_providers():
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)
    free_groups = filter_free_providers(payload)
    assert len(free_groups) == 3
    model_ids = {g["model_id"] for g in free_groups}
    assert model_ids == {
        "meta-llama/Llama-3.2-3B-Instruct",
        "google/gemma-2-9b-it",
        "stabilityai/stable-diffusion-3-medium",
    }


# ---------------------------------------------------------------------------
# to_endpoint_dicts
# ---------------------------------------------------------------------------


def test_to_endpoint_dicts_single_model():
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)
    free_groups = filter_free_providers(payload)
    llama_group = next(g for g in free_groups if g["model_id"] == "meta-llama/Llama-3.2-3B-Instruct")
    endpoints = to_endpoint_dicts(llama_group)
    assert len(endpoints) == 2
    for ep in endpoints:
        assert ep["provider"] == "huggingface"
        assert ep["free"] is True
        assert ep["model_id"] == "meta-llama/Llama-3.2-3B-Instruct"
        assert "chat" in ep["capabilities"]


def test_to_endpoint_dicts_image_model():
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)
    free_groups = filter_free_providers(payload)
    sd_group = next(g for g in free_groups if g["model_id"] == "stabilityai/stable-diffusion-3-medium")
    endpoints = to_endpoint_dicts(sd_group)
    assert len(endpoints) == 1
    assert "vision" in endpoints[0]["capabilities"]


def _fp(provider: str = "huggingface", **overrides) -> dict:
    """Build a minimal free_providers dict that satisfies to_endpoint_dicts."""
    base = {
        "provider": provider,
        "context_length": 1024,
        "supports_tools": False,
        "supports_structured_output": False,
        "first_token_latency_ms": None,
        "throughput": None,
    }
    base.update(overrides)
    return base


def test_to_endpoint_dicts_embedding_model():
    """Output modalities contains 'embedding' -> capabilities.embedding = true."""
    group = {
        "model_id": "x/y-emb",
        "owned_by": "x",
        "input_modalities": ["text"],
        "output_modalities": ["embedding"],
        "free_providers": [_fp()],
    }
    eps = to_endpoint_dicts(group)
    assert eps[0]["capabilities"] == {"embedding": True}


def test_to_endpoint_dicts_audio_output_sets_speech():
    """Output modalities containing 'audio' -> capabilities.speech = true."""
    group = {
        "model_id": "x/tts",
        "owned_by": "x",
        "input_modalities": ["text"],
        "output_modalities": ["audio"],
        "free_providers": [_fp()],
    }
    eps = to_endpoint_dicts(group)
    assert eps[0]["capabilities"].get("speech") is True


def test_to_endpoint_dicts_name_is_last_segment_of_model_id():
    """The endpoint 'name' is the segment after the first '/'."""
    group = {
        "model_id": "owner/cool-model-v2",
        "owned_by": "owner",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "free_providers": [_fp()],
    }
    eps = to_endpoint_dicts(group)
    assert eps[0]["name"] == "cool-model-v2"


def test_to_endpoint_dicts_name_defaults_to_full_model_id_without_slash():
    """A model_id without '/' uses the full string as name."""
    group = {
        "model_id": "no-slash",
        "owned_by": "owner",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "free_providers": [_fp()],
    }
    eps = to_endpoint_dicts(group)
    assert eps[0]["name"] == "no-slash"


def test_to_endpoint_dicts_provider_metadata_forwarded():
    """Per-provider metadata (context_length, supports_tools, etc.) must be preserved."""
    group = {
        "model_id": "x/y",
        "owned_by": "x",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "free_providers": [
            {
                "provider": "huggingface",
                "context_length": 8192,
                "supports_tools": True,
                "supports_structured_output": False,
                "first_token_latency_ms": 123.0,
                "throughput": 45.0,
            }
        ],
    }
    eps = to_endpoint_dicts(group)
    meta = eps[0]["metadata"]
    assert meta["context_length"] == 8192
    assert meta["supports_tools"] is True
    assert meta["first_token_latency_ms"] == 123.0


def test_to_endpoint_dicts_emits_structured_modalities():
    """Modalities go in the top-level 'modalities' field as {input, output}."""
    group = {
        "model_id": "owner/vision",
        "owned_by": "owner",
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "free_providers": [_fp()],
    }
    eps = to_endpoint_dicts(group)
    assert eps[0]["modalities"] == {"input": ["text", "image"], "output": ["text"]}
    # Old flat fields must NOT leak into metadata anymore.
    assert "input_modalities" not in eps[0]["metadata"]
    assert "output_modalities" not in eps[0]["metadata"]


# ---------------------------------------------------------------------------
# fetch_huggingface_models (high-level)
# ---------------------------------------------------------------------------


def test_fetch_huggingface_models():
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)

    with patch("data.providers.huggingface.fetch_router_json") as mock_router:
        mock_router.return_value = payload
        result = fetch_huggingface_models()
        assert len(result) == 4
        model_ids = {ep["model_id"] for ep in result}
        assert model_ids == {
            "meta-llama/Llama-3.2-3B-Instruct",
            "google/gemma-2-9b-it",
            "stabilityai/stable-diffusion-3-medium",
        }
        for ep in result:
            assert ep["provider"] == "huggingface"
            assert ep["free"] is True


def test_fetch_huggingface_models_applies_socks_proxy(monkeypatch):
    """fetch_huggingface_models must call _apply_socks_proxy at entry."""
    monkeypatch.setenv(SOCKS_PROXY_ENV, "socks5h://127.0.0.1:7897")
    _apply_socks_proxy._installed = False

    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)

    with patch("data.providers.huggingface.fetch_router_json", return_value=payload), \
         patch("data.providers.huggingface._apply_socks_proxy") as mock_apply:
        fetch_huggingface_models()
    mock_apply.assert_called_once()


def test_fetch_huggingface_models_empty_payload_returns_empty():
    """Empty router payload → no endpoints."""
    with patch("data.providers.huggingface.fetch_router_json", return_value={"data": []}):
        assert fetch_huggingface_models() == []