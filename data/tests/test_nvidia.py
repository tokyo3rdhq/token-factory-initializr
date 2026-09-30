"""Unit tests for NVIDIA provider."""

from __future__ import annotations
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from unittest.mock import Mock, patch

from data.providers.nvidia import (
    BASE_URL,
    _build_headers,
    _extract_rsc_payload,
    _find_json_end,
    _normalize_model,
    _parse_objects,
    fetch_catalog_page,
    fetch_with_cooldown,
    parse_html,
)


# ---------------------------------------------------------------------------
# _find_json_end (brace-matching)
# ---------------------------------------------------------------------------


def test_base_url_targets_free_models_view():
    """The fetch URL must match the web UI's free-models filter.

    Uses ``pageSize=96`` so the entire free catalog fits in a single
    response — the scraper no longer needs to paginate.

    The upstream server appears to ignore the ``filters`` query
    parameter at the RSC layer (full catalog is returned regardless),
    but the URL documents intent and matches what the web UI sends
    when "Free models" is selected. Pinning this prevents accidental
    regression to the unfiltered URL.
    """
    assert BASE_URL == (
        "https://build.nvidia.com/models"
        "?pageSize=96&filters=nimType%3Anim_type_preview"
    )


def test_find_json_end_simple_object():
    text = '{"a": 1}'
    assert _find_json_end(text, 0) == 7


def test_find_json_end_nested():
    text = '{"a": {"b": 2}}'
    # Match for outer '{' at index 0 ends at the final '}'
    assert _find_json_end(text, 0) == len(text) - 1


def test_find_json_end_with_escaped_quote():
    text = '{"a": "say \\"hi\\""}'
    assert _find_json_end(text, 0) == len(text) - 1


def test_find_json_end_unmatched_returns_minus_one():
    text = '{"a": 1'
    assert _find_json_end(text, 0) == -1


# ---------------------------------------------------------------------------
# _extract_rsc_payload
# ---------------------------------------------------------------------------


def test_extract_rsc_payload_concatenates_chunks_in_order():
    """Chunks must be sorted by their index before concatenation.

    Real build.nvidia.com format uses [N,"payload"] with no space after comma.
    """
    html = (
        '<script>self.__next_f.push([2,"second"])</script>'
        '<script>self.__next_f.push([1,"first"])</script>'
    )
    assert _extract_rsc_payload(html) == "firstsecond"


def test_extract_rsc_payload_decodes_json_strings():
    """Each chunk is a JSON-encoded string; embedded quotes are unescaped."""
    html = '<script>self.__next_f.push([1,"{\\"k\\": 1}"])</script>'
    assert _extract_rsc_payload(html) == '{"k": 1}'


def test_extract_rsc_payload_returns_empty_when_no_scripts():
    assert _extract_rsc_payload("<html><body>no scripts</body></html>") == ""


def test_extract_rsc_payload_ignores_non_push_scripts():
    """Only `self.__next_f.push(...)` is captured; other <script> content is ignored."""
    html = (
        "<script>console.log('hi')</script>"
        '<script>self.__next_f.push([1,"x"])</script>'
    )
    assert _extract_rsc_payload(html) == "x"


# ---------------------------------------------------------------------------
# _parse_objects
# ---------------------------------------------------------------------------


def test_parse_objects_extracts_endpoint_objects():
    rsc = (
        '{"resourceType":"ENDPOINT","resourceId":"a/1"}'
        '{"resourceType":"OTHER","x":1}'
        '{"resourceType":"ENDPOINT","resourceId":"b/2"}'
    )
    objs = _parse_objects(rsc)
    assert len(objs) == 2
    assert [o["resourceId"] for o in objs] == ["a/1", "b/2"]


def test_parse_objects_skips_unmatched_braces():
    """An ENDPOINT tag with an unterminated JSON body is dropped, not crashed on."""
    rsc = '{"resourceType":"ENDPOINT","resourceId":"x/1"'  # no closing brace
    assert _parse_objects(rsc) == []


def test_parse_objects_skips_json_decode_errors():
    """Malformed JSON inside an ENDPOINT block is skipped, not crashed on."""
    rsc = '{"resourceType":"ENDPOINT",BROKEN_JSON}'
    assert _parse_objects(rsc) == []


def test_parse_objects_empty_input():
    assert _parse_objects("") == []


# ---------------------------------------------------------------------------
# _normalize_model: dual-shape labels / attributes
# ---------------------------------------------------------------------------


def _ep(obj):
    return _normalize_model(obj)


def test_normalize_model_free_via_list_labels_real_api_shape():
    """Real NVIDIA API: labels is a list of {key, values, unresolvedValues}.

    When the publisher label is present, model_id is derived from
    ``labels.publisher.values[0] / displayName`` — NOT from
    ``resourceId`` (which is the NIM internal namespace
    ``qc69jvmznzxy/<slug>`` on the live API).
    """
    obj = {
        "resourceId": "qc69jvmznzxy/deepseek-v4.1-flash",
        "displayName": "DeepSeek V4.1 Flash",
        "labels": [
            {"key": "nimType", "values": ["Free Endpoint"], "unresolvedValues": []},
            {"key": "publisher", "values": ["deepseek-ai"], "unresolvedValues": []},
            {"key": "general", "values": ["chat"], "unresolvedValues": []},
        ],
        "attributes": [
            {"key": "AVAILABLE", "value": "true"},
        ],
    }
    ep = _ep(obj)
    assert ep.free is True
    assert ep.model_id == "deepseek-ai/DeepSeek V4.1 Flash"
    assert ep.name == "DeepSeek V4.1 Flash"
    # metadata.labels is normalized to dict keyed by label name
    assert "nimType" in ep.metadata["labels"]
    assert ep.metadata["labels"]["nimType"]["values"] == ["Free Endpoint"]


def test_normalize_model_uses_publisher_label_for_model_id():
    """``labels.publisher.values[0]`` is the canonical org for model_id."""
    obj = {
        "resourceId": "qc69jvmznzxy/some-slug",
        "displayName": "Some Model",
        "labels": [
            {"key": "publisher", "values": ["anthropic"], "unresolvedValues": []},
            {"key": "nimType", "values": ["Free Endpoint"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).model_id == "anthropic/Some Model"


def test_normalize_model_model_id_falls_back_when_no_publisher_label():
    """No publisher label + non-slash resourceId → legacy synthesis.

    When the live payload omits the publisher label AND resourceId
    has no slash, we fall back to the NIM namespace prefix to keep
    the model_id distinguishable (matches the pre-fix behavior).
    """
    obj = {
        "resourceId": "bare-slug",
        "displayName": "Bare Slug",
        "labels": [],
        "attributes": [],
    }
    assert _ep(obj).model_id == "qc69jvmznzxy/Bare Slug"


def test_normalize_model_model_id_uses_resource_id_when_no_publisher():
    """ResourceId has slash but no publisher label → fall back to resourceId."""
    obj = {
        "resourceId": "legacy-org/legacy-slug",
        "displayName": "Legacy Slug",
        "labels": [],
        "attributes": [],
    }
    assert _ep(obj).model_id == "legacy-org/legacy-slug"


def test_normalize_model_free_via_dict_labels_legacy_shape():
    """Legacy / fixture shape: labels is a dict keyed by label name."""
    obj = {
        "resourceId": "google/gemma-4-31b-it",
        "displayName": "Gemma 4",
        "labels": {
            "nimType": {"values": ["Free Endpoint"], "unresolvedValues": []},
        },
        "attributes": {"CHAT_MODALITY": "text2textDiffusion", "TOOL_CALLING": "true"},
    }
    ep = _ep(obj)
    assert ep.free is True
    assert ep.capabilities["chat"] is True
    assert ep.capabilities["tool_calling"] is True


def test_normalize_model_not_free_partner_endpoint():
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [{"key": "nimType", "values": ["Partner Endpoint"], "unresolvedValues": []}],
        "attributes": [],
    }
    assert _ep(obj).free is False


def test_normalize_model_unknown_labels_shape_degrades_safely():
    """A label payload we don't recognize yields free=False (no crash)."""
    obj = {
        "resourceId": "a/b",
        "displayName": "A",
        "labels": "definitely not a list or dict",
        "attributes": "also wrong",
    }
    ep = _ep(obj)
    assert ep.free is False
    assert ep.capabilities == {}


def test_normalize_model_resource_id_without_slash_falls_back():
    """When resourceId has no '/', model_id is synthesized as 'qc69jvmznzxy/{name}'."""
    obj = {
        "resourceId": "bare-slug",
        "displayName": "Bare Slug",
        "labels": [],
        "attributes": [],
    }
    assert _ep(obj).model_id == "qc69jvmznzxy/Bare Slug"


def test_normalize_model_sets_fetched_at_to_datetime():
    """NVIDIA parser yields ModelEndpoint directly from parse_html — fetched_at
    must be stamped here, otherwise ValidateStage rejects every NVIDIA endpoint.

    Regression test for the bug that caused tfi:models:nvidia:latest to be
    empty in production (validate_all returned 99 invalid records, all
    flagged 'fetched_at is not a datetime').
    """
    from datetime import datetime, timezone
    before = datetime.now(timezone.utc)
    ep = _ep({"resourceId": "x/y", "displayName": "X", "labels": [], "attributes": []})
    after = datetime.now(timezone.utc)
    assert isinstance(ep.fetched_at, datetime), (
        f"expected datetime, got {type(ep.fetched_at).__name__}"
    )
    assert before <= ep.fetched_at <= after, "fetched_at should be UTC now"


def test_normalize_model_attributes_list_chat_modality():
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [{"key": "CHAT_MODALITY", "value": "text2textDiffusion"}],
    }
    assert _ep(obj).capabilities == {"chat": True}


def test_normalize_model_attributes_list_tool_calling():
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [{"key": "TOOL_CALLING", "value": "true"}],
    }
    assert _ep(obj).capabilities == {"tool_calling": True}


def test_normalize_model_derives_architecture_from_chat():
    """NVIDIA doesn't expose input_modalities; chat capability implies
    output_modalities=['text']."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [{"key": "CHAT_MODALITY", "value": "text2textDiffusion"}],
    }
    ep = _ep(obj)
    assert ep.architecture == {"input": [], "output": ["text"]}


def test_normalize_model_derives_architecture_from_tool_calling():
    """tool_calling capability implies output_modalities=['text', 'tool_calls']."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [{"key": "TOOL_CALLING", "value": "true"}],
    }
    ep = _ep(obj)
    assert ep.architecture == {"input": [], "output": ["text", "tool_calls"]}


def test_normalize_model_architecture_is_none_when_no_capabilities():
    """When neither chat nor tool_calling is set, architecture stays None."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [],
    }
    assert _ep(obj).architecture is None


def test_normalize_model_architecture_from_labels_playground_chat():
    """``labels.playgroundType == "chat"`` → chat → text output."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [
            {"key": "playgroundType", "values": ["chat"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": [], "output": ["text"]}


def test_normalize_model_architecture_from_labels_usecase_text_to_embedding():
    """``labels.usecase == "Text-to-Embedding"`` → embedding output."""
    obj = {
        "resourceId": "x/y-emb",
        "displayName": "X Emb",
        "labels": [
            {"key": "usecase", "values": ["Text-to-Embedding"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["text"], "output": ["embedding"]}


def test_normalize_model_architecture_from_labels_usecase_image_generation():
    """``labels.usecase == "Image Generation"`` → text in, image out."""
    obj = {
        "resourceId": "x/y-img",
        "displayName": "X Img",
        "labels": [
            {"key": "usecase", "values": ["Image Generation"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["text"], "output": ["image"]}


def test_normalize_model_architecture_from_labels_usecase_text_to_speech():
    """``labels.usecase == "Text-to-Speech"`` → audio output."""
    obj = {
        "resourceId": "x/y-tts",
        "displayName": "X TTS",
        "labels": [
            {"key": "usecase", "values": ["Text-to-Speech"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["text"], "output": ["audio"]}


def test_normalize_model_architecture_from_labels_general_vision():
    """``labels.general`` containing "Vision Language Model" → image input."""
    obj = {
        "resourceId": "x/y-vlm",
        "displayName": "X VLM",
        "labels": [
            {"key": "general", "values": ["Vision Language Model"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["image"], "output": []}


def test_normalize_model_architecture_from_labels_multimodal_moe():
    """``labels.general`` containing "Multimodal MOE" → image input."""
    obj = {
        "resourceId": "x/y-moe",
        "displayName": "X MoE",
        "labels": [
            {"key": "general", "values": ["Multimodal MOE"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["image"], "output": []}


def test_normalize_model_architecture_chat_plus_vision():
    """Chat playgroundType + Vision Language Model → text output + image input."""
    obj = {
        "resourceId": "x/y-vlm",
        "displayName": "X VLM",
        "labels": [
            {"key": "playgroundType", "values": ["chat"], "unresolvedValues": []},
            {"key": "general", "values": ["Vision Language Model"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture == {"input": ["image"], "output": ["text"]}


def test_normalize_model_architecture_no_label_signals():
    """No playgroundType / usecase / general signals → architecture stays None."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [
            {"key": "nimType", "values": ["Free Endpoint"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).architecture is None


def test_normalize_model_pricing_and_context_length_remain_none():
    """NVIDIA's RSC payload does not expose pricing or context_length.

    Documenting the contract: these fields are intentionally left as
    ``None`` because the upstream ``build.nvidia.com/models`` RSC
    payload does not carry per-token prices or context window size.
    Downstream code must treat ``None`` as "unknown", not as "free".
    """
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [
            {"key": "publisher", "values": ["x"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    ep = _ep(obj)
    assert ep.context_length is None
    assert ep.pricing is None


def test_normalize_model_skips_non_dict_label_entries():
    """Label list may contain junk entries — they must be skipped, not crashed on."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [
            "string-instead-of-dict",
            {"key": "nimType", "values": ["Free Endpoint"], "unresolvedValues": []},
        ],
        "attributes": [],
    }
    assert _ep(obj).free is True


def test_normalize_model_description_defaults_to_empty_string():
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [],
    }
    assert _ep(obj).description == ""


def test_normalize_model_preserves_self_in_metadata_when_raw_obj_key_present():
    """The presence of a 'raw_obj' key in the input triggers metadata['raw_obj']
    to be the input object itself (so downstream stages can keep the raw payload)."""
    obj = {
        "resourceId": "x/y",
        "displayName": "X",
        "labels": [],
        "attributes": [],
        "raw_obj": {"placeholder": 1},
    }
    assert _ep(obj).metadata["raw_obj"] is obj


# ---------------------------------------------------------------------------
# parse_html (high-level)
# ---------------------------------------------------------------------------


def test_parse_html():
    with open(str(FIXTURES / "nvidia_html.html"), encoding="utf-8") as f:
        html = f.read()

    endpoints = parse_html(html)
    assert len(endpoints) == 3  # gemma + llama + mistral (deduplicated - no duplicate mistral)
    model_ids = {ep.model_id for ep in endpoints}
    assert model_ids == {
        "google/gemma-4-31b-it",
        "meta-llama/Llama-3.1-8B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
    }

    # Check free status from nimType values
    gemma = next(ep for ep in endpoints if ep.model_id == "google/gemma-4-31b-it")
    assert gemma.free is True  # "Free Endpoint" in nimType values
    mistral = next(ep for ep in endpoints if ep.model_id == "mistralai/Mistral-7B-Instruct-v0.3")
    assert mistral.free is False  # "Run Anywhere" not "Free Endpoint"


def test_parse_html_deduplication():
    """Duplicate entries (same resourceId) should be deduplicated."""
    with open(str(FIXTURES / "nvidia_html.html"), encoding="utf-8") as f:
        html = f.read()

    endpoints = parse_html(html)
    mistral_count = sum(1 for ep in endpoints if ep.model_id == "mistralai/Mistral-7B-Instruct-v0.3")
    assert mistral_count == 1  # deduped


def test_parse_html_free_detection():
    with open(str(FIXTURES / "nvidia_html.html"), encoding="utf-8") as f:
        html = f.read()

    endpoints = parse_html(html)
    gemma = next(ep for ep in endpoints if ep.model_id == "google/gemma-4-31b-it")
    mistral = next(ep for ep in endpoints if ep.model_id == "mistralai/Mistral-7B-Instruct-v0.3")
    # gemma has "Free Endpoint" in nimType values
    assert gemma.free is True
    # mistral has "Run Anywhere" (not "Free Endpoint")
    assert mistral.free is False


def test_parse_html_empty_html():
    """Empty input yields an empty endpoint list, not a crash."""
    assert parse_html("") == []


# ---------------------------------------------------------------------------
# _build_headers (WAF compatibility)
# ---------------------------------------------------------------------------


def test_build_headers():
    headers = _build_headers()
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "Chrome/153" in headers["User-Agent"]
    assert "Accept-Language" in headers
    assert "Sec-Fetch-Dest" in headers


def test_build_headers_accept_includes_html():
    headers = _build_headers()
    assert "text/html" in headers["Accept"]


def test_build_headers_sec_fetch_headers_present():
    """WAF checks Sec-Fetch-* headers — verify they are set."""
    headers = _build_headers()
    assert headers["Sec-Fetch-Mode"] == "navigate"
    assert headers["Sec-Fetch-Site"] == "none"
    assert headers["Upgrade-Insecure-Requests"] == "1"


# ---------------------------------------------------------------------------
# fetch_with_cooldown
# ---------------------------------------------------------------------------


def _resp(status: int, text: str = "") -> Mock:
    """Build a Mock that mimics a requests.Response."""
    r = Mock()
    r.status_code = status
    r.text = text
    return r


def test_fetch_with_cooldown_returns_on_first_200():
    session = Mock()
    session.get.return_value = _resp(200, "<html>ok</html>")
    out = fetch_with_cooldown(session, params={"page": "1"}, wait=0)
    assert out == "<html>ok</html>"
    # One HTTP call; no sleeping required.
    assert session.get.call_count == 1


def test_fetch_with_cooldown_retries_202_then_returns_200():
    session = Mock()
    session.get.side_effect = [_resp(202), _resp(202), _resp(200, "<html>ok</html>")]
    with patch("data.providers.nvidia.time.sleep") as mock_sleep:
        out = fetch_with_cooldown(session, params={"page": "1"}, wait=1)
    assert out == "<html>ok</html>"
    assert session.get.call_count == 3
    assert mock_sleep.call_count == 2  # slept after each 202


def test_fetch_with_cooldown_retries_403_then_returns_200():
    session = Mock()
    session.get.side_effect = [_resp(403), _resp(200, "<html>ok</html>")]
    with patch("data.providers.nvidia.time.sleep") as mock_sleep:
        out = fetch_with_cooldown(session, params={"page": "1"}, wait=1)
    assert out == "<html>ok</html>"
    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_fetch_with_cooldown_gives_up_after_5_attempts():
    """5 non-200 responses exhaust retries → empty string."""
    session = Mock()
    session.get.return_value = _resp(202)
    with patch("data.providers.nvidia.time.sleep"):
        out = fetch_with_cooldown(session, params={"page": "1"}, wait=0)
    assert out == ""
    assert session.get.call_count == 5


def test_fetch_with_cooldown_breaks_on_unhandled_status():
    """A 4xx other than 403 breaks the loop immediately (no retry)."""
    session = Mock()
    session.get.return_value = _resp(404)
    with patch("data.providers.nvidia.time.sleep") as mock_sleep:
        out = fetch_with_cooldown(session, params={"page": "1"}, wait=1)
    assert out == ""
    assert session.get.call_count == 1
    mock_sleep.assert_not_called()


def test_fetch_with_cooldown_passes_base_url_and_params():
    session = Mock()
    session.get.return_value = _resp(200, "ok")
    fetch_with_cooldown(session, params={"page": "2", "nimType": "preview"}, wait=0)
    args, kwargs = session.get.call_args
    assert args[0] == BASE_URL
    assert kwargs["params"] == {"page": "2", "nimType": "preview"}
    assert kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# fetch_catalog_page (high-level)
# ---------------------------------------------------------------------------


def test_fetch_catalog_page():
    """fetch_catalog_page composes fetch → parse → free-filter.

    Mocks fetch_all_pages to return raw HTML and asserts the full
    convenience pipeline: parse all endpoints (4 fixture entries →
    3 unique after dedup), then drop the "Run Anywhere" mistral row
    via ``filter_nvidia_free`` → 2 free endpoints.
    """
    with open(str(FIXTURES / "nvidia_html.html"), encoding="utf-8") as f:
        html = f.read()

    with patch(
        "data.providers.nvidia.NvidiaCatalogParser.fetch_all_pages"
    ) as mock_fetch:
        mock_fetch.return_value = [html]
        result = fetch_catalog_page()
        # Fixture: gemma (free) + llama (free) + mistral×2 (Run Anywhere, not free)
        # Dedup → 3 unique → filter → 2 free endpoints.
        assert len(result) == 2
        assert all(ep.provider == "nvidia" for ep in result)
        assert all(ep.free for ep in result)


def test_fetch_catalog_page_passes_filters_through():
    """filters kwarg must be forwarded to the parser unchanged."""
    with patch("data.providers.nvidia.NvidiaCatalogParser.fetch_all_pages") as mock_fetch:
        mock_fetch.return_value = []
        fetch_catalog_page(filters={"nimType": "nim_type_preview"})
        mock_fetch.assert_called_once_with({"nimType": "nim_type_preview"})


# ---------------------------------------------------------------------------
# NvidiaCatalogParser
# ---------------------------------------------------------------------------


def test_parser_get_all_models_uses_preview_filter():
    """get_all_models must compose get_all_pages + parse_nvidia_pages."""
    from data.providers.nvidia import NvidiaCatalogParser

    parser = NvidiaCatalogParser()
    with patch.object(parser, "get_all_pages", return_value=[]) as mock_pages, \
         patch(
             "data.providers.nvidia.parse_nvidia_pages", return_value=[]
         ) as mock_parse:
        parser.get_all_models()
        mock_pages.assert_called_once_with()
        mock_parse.assert_called_once_with([])


def test_parser_fetch_all_pages_stops_on_empty_html():
    """If the page comes back empty, the loop must break — not continue to page 2."""
    from data.providers.nvidia import NvidiaCatalogParser

    parser = NvidiaCatalogParser()
    with patch("data.providers.nvidia.fetch_with_cooldown", return_value="") as mock_cooldown, \
         patch("data.providers.nvidia.time.sleep"):
        result = parser.fetch_all_pages()
    assert result == []
    assert mock_cooldown.call_count == 1  # only page 1 attempted before break


def test_parser_fetch_all_pages_collects_across_pages():
    """Multiple non-empty pages extend the result list of raw HTML.

    ``fetch_all_pages`` is now a pure downloader: it returns the HTML
    strings, NOT parsed endpoints. The parse side has moved to
    :func:`parse_nvidia_pages`, which is tested separately.
    """
    from data.providers.nvidia import NvidiaCatalogParser

    def fake_cooldown(session, params, **kwargs):
        # page 1 → "page1", page 2 → "page2", page 3+ → empty (stops)
        page = int(params.get("page", "1"))
        if page == 1:
            return "page1"
        if page == 2:
            return "page2"
        return ""

    parser = NvidiaCatalogParser()
    with patch("data.providers.nvidia.fetch_with_cooldown", side_effect=fake_cooldown), \
         patch("data.providers.nvidia.time.sleep"):
        result = parser.fetch_all_pages(max_pages=5)

    assert result == ["page1", "page2"]


def test_parse_nvidia_pages_returns_all_endpoints_including_non_free():
    """Pure parse: must return every recognized endpoint, free or not.

    After the free-filter refactor, ``parse_nvidia_pages`` does NOT
    apply any filter — that's the :func:`filter_nvidia_free` job.
    The fixture's "Run Anywhere" mistral endpoint comes through here,
    with ``free=False`` set by :func:`_normalize_model`.
    """
    from data.providers.nvidia import parse_nvidia_pages

    with open(str(FIXTURES / "nvidia_html.html"), encoding="utf-8") as f:
        html = f.read()

    result = parse_nvidia_pages([html])
    model_ids = {ep.model_id for ep in result}
    # The non-free "Run Anywhere" partner endpoint IS present — the
    # filter stage is responsible for dropping it downstream.
    assert "mistralai/Mistral-7B-Instruct-v0.3" in model_ids
    assert "google/gemma-4-31b-it" in model_ids
    assert "meta-llama/Llama-3.1-8B-Instruct" in model_ids
    # And the free flag is correctly set on each row.
    by_id = {ep.model_id: ep.free for ep in result}
    assert by_id["google/gemma-4-31b-it"] is True
    assert by_id["mistralai/Mistral-7B-Instruct-v0.3"] is False


def test_parser_fetch_returns_text_for_filters():
    """fetch() must invoke fetch_with_cooldown when filters/page are supplied."""
    from data.providers.nvidia import NvidiaCatalogParser

    parser = NvidiaCatalogParser()
    # First call (cookie bootstrap) returns 200; second (filtered) returns 200.
    bootstrap = Mock(status_code=200, text="<html/>")
    filtered = Mock(status_code=200, text="<filtered/>")
    parser.session = Mock()
    parser.session.get.side_effect = [bootstrap, filtered]
    with patch("data.providers.nvidia.fetch_with_cooldown") as mock_cooldown:
        mock_cooldown.return_value = filtered
        out = parser.fetch(filters={"nimType": "preview"}, page=2)
    assert out == "<filtered/>"
    mock_cooldown.assert_called_once()


def test_parser_fetch_returns_empty_when_bootstrap_fails():
    """fetch() returns '' immediately if the WAF cookie bootstrap is non-200."""
    from data.providers.nvidia import NvidiaCatalogParser

    parser = NvidiaCatalogParser()
    parser.session = Mock()
    parser.session.get.return_value = Mock(status_code=403, text="")
    with patch("data.providers.nvidia.fetch_with_cooldown") as mock_cooldown:
        out = parser.fetch(filters={"nimType": "preview"})
    assert out == ""
    mock_cooldown.assert_not_called()


def test_parser_fetch_unfiltered_returns_first_response():
    """fetch() without filters returns the bootstrap response text directly."""
    from data.providers.nvidia import NvidiaCatalogParser

    parser = NvidiaCatalogParser()
    parser.session = Mock()
    parser.session.get.return_value = Mock(status_code=200, text="<bootstrap/>")
    out = parser.fetch()
    assert out == "<bootstrap/>"

# ---------------------------------------------------------------------------
# data_source stamping — refactor doc §14 / §16
# ---------------------------------------------------------------------------


def test_normalize_model_stamps_data_source_nvidia():
    """_normalize_model sets ``data_source="nvidia"`` on every endpoint.

    Refactor §16 — NVIDIA uses ``data_source="nvidia"`` /
    ``provider="nvidia"``.
    """
    obj = {
        "id": "google/gemma-3n-e2b-it",
        "name": "Gemma 3N E2B IT",
        "labels": [
            {"key": "nimType", "values": [{"value": "PUBLIC", "subType": "FREE"}]},
        ],
    }
    ep = _normalize_model(obj)
    assert ep.data_source == "nvidia"
    assert ep.provider == "nvidia"
