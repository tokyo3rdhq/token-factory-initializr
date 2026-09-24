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

import pytest

from data.providers import huggingface as hf
from data.providers.huggingface import (
    ROUTER_URL,
    SOCKS_PROXY_ENV,
    _group_models_by_id,
    _is_free_provider,
    UA,
    fetch_huggingface_models,
    fetch_router_json,
    parse_huggingface_models,
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


# ---------------------------------------------------------------------------
# fetch_router_json (HTTP transport)
# ---------------------------------------------------------------------------


def test_fetch_router_json(monkeypatch):
    """Load the curated fixture JSON via the urllib fallback path."""
    # Force the urllib path even when a previous test left SOCKS5_PROXY set.
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
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


def test_fetch_router_json_raises_runtimeerror_on_network_failure(monkeypatch):
    """URLError must be wrapped in RuntimeError so callers can detect network issues."""
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
    with patch("data.providers.huggingface.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        try:
            fetch_router_json(timeout=5)
        except RuntimeError as exc:
            assert "Network error" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_fetch_router_json_sends_correct_headers(monkeypatch):
    """Verify URL and Accept/User-Agent headers are set as expected."""
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
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
# fetch_router_json via SOCKS5 proxy (uses requests)
# ---------------------------------------------------------------------------


def test_fetch_router_json_uses_requests_when_proxy_set(monkeypatch):
    """When ``SOCKS5_PROXY`` is set, ``fetch_router_json`` must use
    ``requests`` (not urllib) and pass the proxy URL through."""
    monkeypatch.setenv("SOCKS5_PROXY", "socks5h://127.0.0.1:7897")

    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = json.dumps({"object": "list", "data": []})

        def __init__(self):
            self.content = self.text.encode()

    def fake_get(*args, **kwargs):
        captured["url"] = args[0] if args else kwargs.get("url")
        captured["proxies"] = kwargs.get("proxies")
        captured["headers"] = kwargs.get("headers")
        captured["timeout"] = kwargs.get("timeout")
        return FakeResponse()

    fake_requests = type("FakeRequests", (), {"get": staticmethod(fake_get)})
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    result = fetch_router_json(timeout=42)
    assert result == {"object": "list", "data": []}
    assert captured["url"] == ROUTER_URL
    assert captured["proxies"] == {
        "http": "socks5h://127.0.0.1:7897",
        "https": "socks5h://127.0.0.1:7897",
    }
    assert captured["headers"]["User-Agent"] == UA
    assert captured["timeout"] == 42


def test_fetch_router_json_proxy_path_raises_runtimeerror_on_requests_failure(monkeypatch):
    """A ``requests.exceptions.RequestException`` from the proxy path
    must be wrapped in ``RuntimeError`` like the urllib path."""
    import requests as real_requests

    monkeypatch.setenv("SOCKS5_PROXY", "socks5h://127.0.0.1:7897")

    def fake_get(*_args, **_kwargs):
        raise real_requests.exceptions.ConnectionError("proxy unreachable")

    monkeypatch.setattr(real_requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="Network error fetching HF models"):
        fetch_router_json(timeout=5)


def test_fetch_router_json_proxy_path_raises_on_non_200(monkeypatch):
    """A non-200 HTTP response via the proxy must surface as
    ``RuntimeError`` carrying the status code (not silently return [])."""
    import requests as real_requests

    monkeypatch.setenv("SOCKS5_PROXY", "socks5h://127.0.0.1:7897")

    class FakeResponse:
        status_code = 503
        text = "Service Unavailable"
        content = b"Service Unavailable"

    monkeypatch.setattr(
        real_requests, "get", lambda *_a, **_kw: FakeResponse()
    )

    with pytest.raises(RuntimeError, match="HTTP 503"):
        fetch_router_json(timeout=5)


def test_fetch_router_json_proxy_empty_string_falls_back_to_urllib(monkeypatch):
    """An empty ``SOCKS5_PROXY`` is treated as unset (falls back to urllib)."""
    monkeypatch.setenv("SOCKS5_PROXY", "   ")

    urlopen_called = {"v": False}

    def fake_urlopen(req, timeout=None):
        urlopen_called["v"] = True
        resp = Mock()
        resp.read.return_value = b'{"object":"list","data":[]}'
        resp.__enter__ = Mock(return_value=resp)
        resp.__exit__ = Mock(return_value=False)
        return resp

    with patch("data.providers.huggingface.urllib.request.urlopen", side_effect=fake_urlopen):
        fetch_router_json(timeout=5)

    assert urlopen_called["v"], "empty SOCKS5_PROXY should fall back to urllib"


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# to_endpoint_dicts
# ---------------------------------------------------------------------------


def _provider(provider: str = "huggingface", **overrides) -> dict:
    """Build a minimal HF router provider entry for to_endpoint_dicts.

    The new contract accepts a ``providers`` list of upstream-shaped
    provider dicts (not a ``free_providers`` list of pre-filtered dicts).
    Pricing is preserved verbatim; ``status`` defaults to ``"live"``.
    """
    base = {
        "provider": provider,
        "status": "live",
        "pricing": {"input": 0.0, "output": 0.0},
        "context_length": 1024,
        "supports_tools": False,
        "supports_structured_output": False,
        "first_token_latency_ms": None,
        "throughput": None,
    }
    base.update(overrides)
    return base


def _group(
    providers: list,
    model_id: str = "owner/y",
    input_modalities=None,
    output_modalities=None,
    model_level_context_length=None,
    owned_by: str = "owner",
) -> dict:
    """Build a minimal ``_group_models_by_id``-shaped dict."""
    return {
        "model_id": model_id,
        "owned_by": owned_by,
        "input_modalities": input_modalities or ["text"],
        "output_modalities": output_modalities or ["text"],
        "model_level_context_length": model_level_context_length,
        "providers": providers,
    }


def test_to_endpoint_dicts_emits_one_endpoint_per_provider():
    """One canonical endpoint dict per provider in the group (free + paid)."""
    group = _group([
        _provider(provider="novita"),
        _provider(provider="cloudflare"),
    ])
    eps = to_endpoint_dicts(group)
    assert len(eps) == 2
    assert [ep["provider"] for ep in eps] == ["novita", "cloudflare"]


def test_to_endpoint_dicts_provider_field_uses_real_name_not_huggingface():
    """The top-level ``provider`` must be the upstream router name, not
    a hardcoded ``"huggingface"``.

    Regression: previously ``to_endpoint_dicts`` hardcoded
    ``"huggingface"`` for every emitted endpoint regardless of
    upstream, hiding the real router provider under
    ``metadata.router_provider``.
    """
    eps = to_endpoint_dicts(_group([
        _provider(provider="novita"),
        _provider(provider="fireworks-ai"),
        _provider(provider="together"),
    ]))
    assert {ep["provider"] for ep in eps} == {"novita", "fireworks-ai", "together"}


def test_to_endpoint_dicts_pricing_lifted_per_provider():
    """Real per-token prices from upstream end up in the top-level
    ``pricing`` field. Old behavior hardcoded ``{input: 0, output: 0}``.
    """
    eps = to_endpoint_dicts(_group([
        _provider(provider="novita", pricing={"input": 0.3, "output": 1.2}),
        _provider(provider="together", pricing={"input": 0.5, "output": 2.0}),
    ]))
    by_provider = {ep["provider"]: ep["pricing"] for ep in eps}
    assert by_provider["novita"] == {"input": 0.3, "output": 1.2}
    assert by_provider["together"] == {"input": 0.5, "output": 2.0}


def test_to_endpoint_dicts_context_length_per_provider():
    """Per-provider context_length is honored (no fallback to model-level)."""
    eps = to_endpoint_dicts(_group(
        [_provider(provider="a", context_length=4096),
         _provider(provider="b", context_length=8192)],
        model_level_context_length=131072,
    ))
    by_provider = {ep["provider"]: ep["context_length"] for ep in eps}
    assert by_provider["a"] == 4096
    assert by_provider["b"] == 8192


def test_to_endpoint_dicts_falls_back_to_model_level_context_length():
    """When per-provider context_length is None, fall back to model-level."""
    eps = to_endpoint_dicts(_group(
        [_provider(provider="a", context_length=None)],
        model_level_context_length=131072,
    ))
    assert eps[0]["context_length"] == 131072


def test_to_endpoint_dicts_context_length_none_when_neither_set():
    """No per-provider and no model-level context_length - stays None."""
    eps = to_endpoint_dicts(_group(
        [_provider(provider="a", context_length=None)],
        model_level_context_length=None,
    ))
    assert eps[0]["context_length"] is None


def test_to_endpoint_dicts_free_flag_per_provider():
    """``free`` is computed per-provider via the price+status rule."""
    eps = to_endpoint_dicts(_group([
        _provider(provider="free", pricing={"input": 0, "output": 0}),
        _provider(provider="paid", pricing={"input": 0.3, "output": 1.2}),
    ]))
    by_provider = {ep["provider"]: ep["free"] for ep in eps}
    assert by_provider["free"] is True
    assert by_provider["paid"] is False


def test_to_endpoint_dicts_non_live_status_is_not_free():
    """``status != "live"`` makes the endpoint non-free even with price=0."""
    eps = to_endpoint_dicts(_group([
        _provider(provider="offline", pricing={"input": 0, "output": 0}, status="offline"),
    ]))
    assert eps[0]["free"] is False


def test_to_endpoint_dicts_drops_providers_without_name():
    """A provider entry with empty/missing ``provider`` is silently dropped."""
    eps = to_endpoint_dicts(_group([
        _provider(provider="real"),
        {"provider": "", "status": "live", "pricing": {"input": 0, "output": 0}},
        {"status": "live", "pricing": {"input": 0, "output": 0}},  # no provider key
    ]))
    assert [ep["provider"] for ep in eps] == ["real"]


def test_to_endpoint_dicts_capabilities_chat_for_text_output():
    group = _group([_provider()], output_modalities=["text"])
    eps = to_endpoint_dicts(group)
    assert "chat" in eps[0]["capabilities"]


def test_to_endpoint_dicts_capabilities_embedding_for_embedding_output():
    group = _group([_provider()], output_modalities=["embedding"])
    eps = to_endpoint_dicts(group)
    assert eps[0]["capabilities"] == {"embedding": True}


def test_to_endpoint_dicts_capabilities_audio_for_audio_output():
    group = _group([_provider()], output_modalities=["audio"])
    eps = to_endpoint_dicts(group)
    assert eps[0]["capabilities"].get("speech") is True


def test_to_endpoint_dicts_capabilities_vision_for_image_input():
    group = _group([_provider()], input_modalities=["text", "image"])
    eps = to_endpoint_dicts(group)
    assert "vision" in eps[0]["capabilities"]


def test_to_endpoint_dicts_name_is_last_segment_of_model_id():
    group = _group([_provider()], model_id="owner/cool-model-v2")
    eps = to_endpoint_dicts(group)
    assert eps[0]["name"] == "cool-model-v2"


def test_to_endpoint_dicts_name_defaults_to_full_model_id_without_slash():
    group = _group([_provider()], model_id="no-slash")
    eps = to_endpoint_dicts(group)
    assert eps[0]["name"] == "no-slash"


def test_to_endpoint_dicts_emits_structured_architecture():
    """Modalities go in the top-level 'architecture' field as {input, output}."""
    group = _group(
        [_provider()],
        input_modalities=["text", "image"],
        output_modalities=["text"],
    )
    eps = to_endpoint_dicts(group)
    assert eps[0]["architecture"] == {"input": ["text", "image"], "output": ["text"]}


def test_to_endpoint_dicts_metadata_preserves_per_provider_metrics():
    """supports_tools / throughput / latency flow into metadata."""
    eps = to_endpoint_dicts(_group([
        _provider(
            provider="novita",
            supports_tools=True,
            first_token_latency_ms=1371.4,
            throughput=80.5,
        ),
    ]))
    meta = eps[0]["metadata"]
    assert meta["supports_tools"] is True
    assert meta["first_token_latency_ms"] == 1371.4
    assert meta["throughput"] == 80.5
    # router_provider must NOT be in metadata - it's now the top-level
    # ``provider`` field.
    assert "router_provider" not in meta


def test_to_endpoint_dicts_metadata_keeps_is_model_author():
    """The HF-specific is_model_author flag survives into metadata."""
    eps = to_endpoint_dicts(_group([
        _provider(provider="author", is_model_author=True),
    ]))
    assert eps[0]["metadata"]["is_model_author"] is True


def test_to_endpoint_dicts_on_curated_fixture():
    """End-to-end: real curated fixture - per-provider expansion with
    correct provider names, free flags, and pricing.
    """
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)
    endpoints = parse_huggingface_models(payload)
    # The fixture has 4 models / 5 providers -> 5 endpoints (paid openai
    # endpoint still emitted, marked free=False).
    assert len(endpoints) == 5
    by_id_provider = {(ep["model_id"], ep["provider"]): ep for ep in endpoints}
    # Llama has 2 providers: huggingface + cloudflare (both free).
    llama_hf = by_id_provider[("meta-llama/Llama-3.2-3B-Instruct", "huggingface")]
    assert llama_hf["free"] is True
    assert llama_hf["provider"] == "huggingface"
    assert "router_provider" not in llama_hf["metadata"]
    # gpt-4-turbo is paid (pricing != 0).
    gpt = by_id_provider[("openai/gpt-4-turbo", "huggingface")]
    assert gpt["free"] is False
    assert gpt["pricing"] == {"input": 0.01, "output": 0.03}


# fetch_huggingface_models (high-level)
# ---------------------------------------------------------------------------


def test_fetch_huggingface_models():
    """fetch_huggingface_models now emits ALL (model, provider) pairs.

    The free-only filter has moved to FilterFreeStage. The
    high-level wrapper still emits everything (paid endpoints
    included); ``free`` is computed per-provider.
    """
    with open(str(FIXTURES / "huggingface_router.json"), encoding="utf-8") as f:
        payload = json.load(f)

    with patch("data.providers.huggingface.fetch_router_json") as mock_router:
        mock_router.return_value = payload
        result = fetch_huggingface_models()
        # 4 models, 5 providers (Llama has 2) -> 5 endpoints.
        assert len(result) == 5
        # Providers are no longer hardcoded to "huggingface".
        providers = {ep["provider"] for ep in result}
        assert providers == {"huggingface", "cloudflare"}
        # gpt-4-turbo (paid) survives — the filter stage drops it.
        assert any(ep["free"] is False for ep in result)
        # Free providers carry pricing lifted verbatim.
        free_endpoints = [ep for ep in result if ep["free"]]
        for ep in free_endpoints:
            assert ep["pricing"] is not None


def test_fetch_huggingface_models_empty_payload_returns_empty():
    """Empty router payload → no endpoints."""
    with patch("data.providers.huggingface.fetch_router_json", return_value={"data": []}):
        assert fetch_huggingface_models() == []