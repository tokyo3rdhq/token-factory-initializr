"""Unit tests for Ollama provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

FIXTURES = Path(__file__).parent / "fixtures"

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.providers.ollama import (
    BASE_URL,
    MODELS_ENDPOINT,
    SHOW_ENDPOINT,
    LIBRARY_BASE_URL,
    _fetch_json,
    _fetch_library_html,
    _parse_library_html,
    _normalize_capabilities,
    _parse_free_until,
    fetch_model_list,
    fetch_model_detail,
    fetch_ollama_models,
    filter_ollama_free,
    build_model_endpoint,
    OllamaModelDetail,
)


# ---------------------------------------------------------------------------
# _fetch_json (HTTP transport)
# ---------------------------------------------------------------------------


def test_fetch_json_get_returns_decoded_body():
    payload = {"object": "list", "data": [{"id": "test-model"}]}
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        out = _fetch_json(f"{BASE_URL}{MODELS_ENDPOINT}")
    assert out == payload
    req = mock_urlopen.call_args[0][0]
    assert req.method == "GET"
    assert req.headers["Accept"] == "application/json"


def test_fetch_json_post_serializes_body():
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        _fetch_json(f"{BASE_URL}{SHOW_ENDPOINT}", method="POST", body={"model": "test", "verbose": True})
    req = mock_urlopen.call_args[0][0]
    assert req.method == "POST"
    assert req.headers["Content-type"] == "application/json"
    assert req.data == json.dumps({"model": "test", "verbose": True}).encode("utf-8")


def test_fetch_json_includes_auth_header():
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        import os
        os.environ["OLLAMA_API_KEY"] = "test-key"
        try:
            _fetch_json(f"{BASE_URL}{MODELS_ENDPOINT}")
        finally:
            del os.environ["OLLAMA_API_KEY"]
    req = mock_urlopen.call_args[0][0]
    assert req.headers["Authorization"] == "Bearer test-key"


# ---------------------------------------------------------------------------
# fetch_model_list (high-level)
# ---------------------------------------------------------------------------


def test_fetch_model_list_hits_models_endpoint():
    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
        result = fetch_model_list()
        args = mock_fetch.call_args[0]
    assert args[0] == f"{BASE_URL}{MODELS_ENDPOINT}"
    assert len(result) == 2
    assert result[0]["id"] == "model-1"


def test_fetch_model_list_uses_live_fixture():
    with open(FIXTURES / "ollama_models_live.json", encoding="utf-8") as f:
        payload = json.load(f)
    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = payload
        result = fetch_model_list()
    assert len(result) == 23
    assert any(m["id"] == "minimax-m3.1-flash" for m in result)


# ---------------------------------------------------------------------------
# fetch_model_detail (high-level)
# ---------------------------------------------------------------------------


def test_fetch_model_detail_hits_show_endpoint():
    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = {"capabilities": ["completion"], "details": {}}
        fetch_model_detail("test-model")
        args, kwargs = mock_fetch.call_args
    assert args[0] == f"{BASE_URL}{SHOW_ENDPOINT}"
    assert kwargs["method"] == "POST"
    assert kwargs["body"]["model"] == "test-model"
    assert kwargs["body"]["verbose"] is True


def test_fetch_model_detail_parses_capabilities():
    with open(FIXTURES / "ollama_detail_minimax-m3.1-flash_live.json", encoding="utf-8") as f:
        payload = json.load(f)
    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = payload
        detail = fetch_model_detail("minimax-m3.1-flash")
    assert isinstance(detail, OllamaModelDetail)
    assert detail.capabilities == ["completion", "tools", "thinking", "vision"]
    assert detail.context_length == 1000000
    assert detail.parameter_size == 428000000000
    assert detail.architecture == "minimax-m3"


def test_fetch_model_detail_parses_nemotron():
    with open(FIXTURES / "ollama_detail_nemotron-3-ultra_live.json", encoding="utf-8") as f:
        payload = json.load(f)
    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = payload
        detail = fetch_model_detail("nemotron-3-ultra")
    assert isinstance(detail, OllamaModelDetail)
    assert detail.capabilities == ["completion", "thinking", "tools"]
    assert detail.context_length == 262144
    assert detail.parameter_size == 550000000000


# ---------------------------------------------------------------------------
# _fetch_library_html (HTML transport)
# ---------------------------------------------------------------------------


def test_fetch_library_html_hits_library_url():
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = b"<html>test</html>"
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        html = _fetch_library_html("test-model")
    assert html == "<html>test</html>"
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == f"{LIBRARY_BASE_URL}/test-model"


def test_fetch_library_html_returns_none_on_404():
    import urllib.error
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        exc = urllib.error.HTTPError(
            url=f"{LIBRARY_BASE_URL}/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = exc
        result = _fetch_library_html("missing")
    assert result is None


def test_fetch_library_html_uses_live_fixture():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    with patch("data.providers.ollama.urllib.request.urlopen") as mock_urlopen:
        mock_resp = Mock()
        mock_resp.read.return_value = html.encode("utf-8")
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = _fetch_library_html("minimax-m3.1-flash")
    assert result is not None
    assert "minimax-m3.1-flash" in result or "minimax-m3" in result


# ---------------------------------------------------------------------------
# _parse_library_html (HTML parser)
# ---------------------------------------------------------------------------


def test_parse_library_html_extracts_description():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    result = _parse_library_html(html, "minimax-m3.1-flash")
    assert result["description"]
    assert "next-generation Flash model" in result["description"]


def test_parse_library_html_extracts_capabilities():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    result = _parse_library_html(html, "minimax-m3.1-flash")
    assert "vision" in result["capabilities"]
    assert "tools" in result["capabilities"]
    assert "thinking" in result["capabilities"]
    assert "cloud" in result["capabilities"]


def test_parse_library_html_extracts_free_until():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    result = _parse_library_html(html, "minimax-m3.1-flash")
    assert result["free_until"] is not None
    assert "Oct 22, 2026" in result["free_until"]


def test_parse_library_html_extracts_pricing():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    result = _parse_library_html(html, "minimax-m3.1-flash")
    assert "input" in result["pricing"]
    assert "output" in result["pricing"]
    assert "$0.15" in result["pricing"]["input"]


def test_parse_library_html_extracts_metadata():
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()
    result = _parse_library_html(html, "minimax-m3.1-flash")
    assert result["metadata"]["context_window"] == "976K"
    assert result["metadata"]["parameters"] == "428B"
    assert "K" in result["metadata"]["downloads"]
    assert result["metadata"]["updated"] == "yesterday"


def test_parse_library_html_404_returns_empty():
    html = "<!-- 404 Not Found -->"
    result = _parse_library_html(html, "missing-model")
    assert result["description"] == ""
    assert result["capabilities"] == []
    assert result["free_until"] is None
    assert result["pricing"] == {}
    assert result["metadata"]["context_window"] is None


# ---------------------------------------------------------------------------
# _normalize_capabilities
# ---------------------------------------------------------------------------


def test_normalize_capabilities_maps_completion_to_chat():
    assert _normalize_capabilities(["completion"]) == ["chat"]


def test_normalize_capabilities_maps_thinking_to_reasoning():
    assert _normalize_capabilities(["thinking"]) == ["reasoning"]


def test_normalize_capabilities_maps_tools_to_tool_calling():
    assert _normalize_capabilities(["tools"]) == ["tool_calling"]


def test_normalize_capabilities_maps_vision_to_vision():
    assert _normalize_capabilities(["vision"]) == ["vision"]


def test_normalize_capabilities_deduplicates_and_sorts():
    result = _normalize_capabilities(["tools", "completion", "tools", "vision"])
    assert result == ["chat", "tool_calling", "vision"]


def test_normalize_capabilities_ignores_unknown():
    result = _normalize_capabilities(["unknown", "completion"])
    assert result == ["chat"]


# ---------------------------------------------------------------------------
# _parse_free_until
# ---------------------------------------------------------------------------


def test_parse_free_until_parses_utc_format():
    result = _parse_free_until("Oct 22, 2026 11:59 PM UTC")
    assert result is not None
    assert result.year == 2026
    assert result.month == 10
    assert result.day == 22
    assert result.hour == 23
    assert result.minute == 59
    assert result.tzinfo is not None


def test_parse_free_until_returns_none_for_empty():
    assert _parse_free_until("") is None
    assert _parse_free_until(None) is None


def test_parse_free_until_returns_none_for_unparseable():
    assert _parse_free_until("not a date") is None


# ---------------------------------------------------------------------------
# build_model_endpoint
# ---------------------------------------------------------------------------


def test_build_model_endpoint_populates_all_fields():
    with open(FIXTURES / "ollama_detail_minimax-m3.1-flash_live.json", encoding="utf-8") as f:
        detail_data = json.load(f)
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html = f.read()

    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = detail_data
        detail = fetch_model_detail("minimax-m3.1-flash")
    library_enrichment = _parse_library_html(html, "minimax-m3.1-flash")
    endpoint = build_model_endpoint("minimax-m3.1-flash", detail, library_enrichment)

    # Required fields
    assert endpoint.provider == "ollama"
    assert endpoint.model_id == "minimax-m3.1-flash"
    assert endpoint.data_source == "ollama"
    assert endpoint.pricing_status == "free"
    assert endpoint.fetched_at is not None

    # Enriched fields
    assert endpoint.description is not None
    assert "next-generation Flash model" in endpoint.description
    assert endpoint.capabilities["input_modalities"] == ["text", "image"]
    assert endpoint.capabilities["output_modalities"] == ["text"]
    assert endpoint.architecture == {"input": ["text", "image"], "output": ["text"]}
    assert endpoint.context_length == 1000000
    assert endpoint.pricing is not None
    assert "input" in endpoint.pricing
    assert endpoint.source_url == "https://ollama.com/library/minimax-m3.1-flash"
    assert endpoint.endpoint_url == "https://ollama.com/"
    assert endpoint.supported_parameters == ["tool_calling", "reasoning", "streaming"]
    assert endpoint.lab == "ollama"
    assert endpoint.metadata["free_until"] is not None
    assert "2026-10-22T23:59:00" in endpoint.metadata["free_until"]


def test_build_model_endpoint_without_library_page():
    with open(FIXTURES / "ollama_detail_nemotron-3-ultra_live.json", encoding="utf-8") as f:
        detail_data = json.load(f)

    with patch("data.providers.ollama._fetch_json") as mock_fetch:
        mock_fetch.return_value = detail_data
        detail = fetch_model_detail("nemotron-3-ultra")
    library_enrichment = {"description": None, "capabilities": [], "free_until": None, "pricing": {}, "metadata": {}}
    endpoint = build_model_endpoint("nemotron-3-ultra", detail, library_enrichment)

    assert endpoint.provider == "ollama"
    assert endpoint.model_id == "nemotron-3-ultra"
    assert endpoint.pricing_status != "free"  # No free_until
    assert endpoint.capabilities["input_modalities"] == ["text"]
    assert endpoint.capabilities["output_modalities"] == ["text"]
    assert endpoint.architecture == {"input": ["text"], "output": ["text"]}
    assert endpoint.context_length == 262144
    assert endpoint.pricing is None
    assert endpoint.source_url == "https://ollama.com/library/nemotron-3-ultra"




# ---------------------------------------------------------------------------
# filter_ollama_free
# ---------------------------------------------------------------------------


def test_filter_ollama_free_keeps_models_with_free_until():
    from data.models.schema import ModelEndpoint
    from datetime import datetime, timezone

    endpoints = [
        ModelEndpoint(
            provider="ollama", model_id="free-model", free=True, fetched_at=datetime.now(timezone.utc),
            data_source="ollama", name="free-model", description=None,
            capabilities={}, metadata={"free_until": "2026-12-31T23:59:59+00:00"},
            architecture=None, supported_parameters=[], lab="ollama",
            context_length=None, pricing=None, endpoint_url=None, region=None,
            source_url=None, status=None, limits=None, score=None,
        ),
        ModelEndpoint(
            provider="ollama", model_id="paid-model", free=False, fetched_at=datetime.now(timezone.utc),
            data_source="ollama", name="paid-model", description=None,
            capabilities={}, metadata={"free_until": None},
            architecture=None, supported_parameters=[], lab="ollama",
            context_length=None, pricing=None, endpoint_url=None, region=None,
            source_url=None, status=None, limits=None, score=None,
        ),
    ]
    result = filter_ollama_free(endpoints)
    assert len(result) == 2
    assert result[0].model_id == "free-model"
    assert result[0].pricing_status == "free"
    assert result[1].model_id == "paid-model"
    assert result[1].pricing_status == "unknown"


def test_filter_ollama_free_drops_models_without_free_until():
    from data.models.schema import ModelEndpoint
    from datetime import datetime, timezone

    endpoints = [
        ModelEndpoint(
            provider="ollama", model_id="paid-model", free=False, fetched_at=datetime.now(timezone.utc),
            data_source="ollama", name="paid-model", description=None,
            capabilities={}, metadata={},  # No free_until key
            architecture=None, supported_parameters=[], lab="ollama",
            context_length=None, pricing=None, endpoint_url=None, region=None,
            source_url=None, status=None, limits=None, score=None,
        ),
    ]
    result = filter_ollama_free(endpoints)
    assert len(result) == 1
    assert result[0].model_id == "paid-model"
    assert result[0].pricing_status == "unknown"


# ---------------------------------------------------------------------------
# fetch_ollama_models (end-to-end, mocked)
# ---------------------------------------------------------------------------

def test_fetch_ollama_models_integration_mocked():
    with open(FIXTURES / "ollama_models_live.json", encoding="utf-8") as f:
        model_list = json.load(f)
    with open(FIXTURES / "ollama_detail_minimax-m3.1-flash_live.json", encoding="utf-8") as f:
        detail_minimax = json.load(f)
    with open(FIXTURES / "ollama_library_minimax-m3.1-flash_live.html", encoding="utf-8") as f:
        html_minimax = f.read()
    with open(FIXTURES / "ollama_library_deepseek-v4-pro-0813_live.html", encoding="utf-8") as f:
        html_404 = f.read()

    # Minimal detail for other models
    detail_other = {
        "capabilities": ["completion"],
        "context_length": 4096,
        "parameter_size": 1000000000,
        "architecture": None,
        "modified_at": "2026-01-01T00:00:00Z",
        "thinking_config": None,
    }

    with patch("data.providers.ollama.fetch_model_list") as mock_list:
        mock_list.return_value = model_list["data"]
        with patch("data.providers.ollama.fetch_model_detail") as mock_detail:
            def detail_side_effect(model_id):
                with patch("data.providers.ollama._fetch_json") as mock_fetch:
                    if model_id == "minimax-m3.1-flash":
                        mock_fetch.return_value = detail_minimax
                    else:
                        mock_fetch.return_value = detail_other
                    return fetch_model_detail(model_id)
            mock_detail.side_effect = detail_side_effect
            with patch("data.providers.ollama._fetch_library_html") as mock_html:
                def html_side_effect(model_id):
                    if model_id == "minimax-m3.1-flash":
                        return html_minimax
                    return html_404  # 404 for others
                mock_html.side_effect = html_side_effect
                endpoints = fetch_ollama_models()

    # All models should produce endpoints
    assert len(endpoints) == 23
    # Only minimax-m3.1-flash has free_until in our mock
    free_endpoints = [e for e in endpoints if e.pricing_status == "free"]
    assert len(free_endpoints) == 1
    assert free_endpoints[0].model_id == "minimax-m3.1-flash"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])