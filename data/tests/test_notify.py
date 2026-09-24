"""Unit tests for Feishu webhook notification adapter."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from data.notify.feishu import _format_card, send_alert, send_summary


# ---------------------------------------------------------------------------
# _format_card payload structure
# ---------------------------------------------------------------------------


def test_format_card_builds_interactive_message():
    """_format_card returns msg_type=interactive with markdown body."""
    manifest = {
        "total": 42,
        "providers": {
            "amd": {"count": 21, "status": "success"},
            "nvidia": {"count": 21, "status": "success"},
        },
    }
    card = _format_card(manifest, [])
    assert card["msg_type"] == "interactive"
    assert "card" in card
    header = card["card"]["header"]
    assert header["title"]["tag"] == "plain_text"
    elements = card["card"]["elements"]
    assert len(elements) == 1
    body_md = elements[0]["content"]
    assert "amd" in body_md
    assert "nvidia" in body_md
    assert "Total: 42" in body_md
    assert "Invalid: 0" in body_md


def test_format_card_sorts_providers_alphabetically():
    """Providers appear in sorted order in the markdown body."""
    manifest = {
        "total": 0,
        "providers": {
            "nvidia": {"count": 1, "status": "success"},
            "amd": {"count": 2, "status": "success"},
            "huggingface": {"count": 3, "status": "success"},
        },
    }
    card = _format_card(manifest, [])
    body_md = card["card"]["elements"][0]["content"]
    amd_pos = body_md.index("amd")
    huggingface_pos = body_md.index("huggingface")
    nvidia_pos = body_md.index("nvidia")
    assert amd_pos < huggingface_pos < nvidia_pos


def test_format_card_includes_invalid_count():
    """Invalid count appears in the markdown body."""
    manifest = {"total": 10, "providers": {}}
    invalid = [
        {"reason": "missing provider", "model_id": "x"},
        {"reason": "empty model_id", "model_id": "y"},
    ]
    card = _format_card(manifest, invalid)
    body_md = card["card"]["elements"][0]["content"]
    assert "Invalid: 2" in body_md


def test_format_card_handles_missing_keys():
    """Missing 'providers' / 'total' falls back to empty / 0 without raising."""
    manifest = {}
    card = _format_card(manifest, [])
    body_md = card["card"]["elements"][0]["content"]
    assert "Total: 0" in body_md


def test_format_card_red_header_when_errors_present():
    """When stage errors are passed, the header uses the red template."""
    card = _format_card({}, [], errors=[{"stage": "store", "error": "KV init failed"}])
    assert card["card"]["header"]["template"] == "red"
    body_md = card["card"]["elements"][0]["content"]
    assert "Stage errors" in body_md
    assert "`store`: KV init failed" in body_md


def test_format_card_blue_header_when_no_errors():
    card = _format_card({}, [])
    assert card["card"]["header"]["template"] == "blue"


def test_send_summary_passes_errors_to_card():
    """send_summary forwards context.errors into the card payload."""
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = True
        send_summary(
            {"total": 0, "providers": {}},
            invalid=[],
            errors=[{"stage": "store", "error": "boom"}],
            webhook_url="https://example.test/webhook",
        )
        url, payload = mock_post.call_args[0]
    assert url == "https://example.test/webhook"
    assert payload["msg_type"] == "interactive"
    body_md = payload["card"]["elements"][0]["content"]
    assert "Stage errors" in body_md


# ---------------------------------------------------------------------------
# send_summary
# ---------------------------------------------------------------------------


def test_send_summary_returns_false_when_webhook_unset(monkeypatch):
    """send_summary returns False when FEISHU_WEBHOOK_URL is unset."""
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    manifest = {"total": 10, "providers": {}}
    result = send_summary(manifest)
    assert result is False


def test_send_summary_does_not_call_post_when_webhook_unset(monkeypatch):
    """send_summary does not POST when FEISHU_WEBHOOK_URL is unset."""
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    with patch("data.notify.feishu._post_json") as mock_post:
        send_summary({"total": 0, "providers": {}})
        mock_post.assert_not_called()


def test_send_summary_posts_card_to_webhook():
    """send_summary POSTs the formatted card to the webhook."""
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = True
        manifest = {
            "total": 5,
            "providers": {"amd": {"count": 5, "status": "success"}},
        }
        result = send_summary(manifest, webhook_url="https://example.test/webhook")
        assert result is True
        mock_post.assert_called_once()
        url, payload = mock_post.call_args[0]
        assert url == "https://example.test/webhook"
        assert payload["msg_type"] == "interactive"


def test_send_summary_prefers_explicit_webhook_over_env(monkeypatch):
    """send_summary uses the explicit webhook_url when both are set."""
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://env.test/webhook")
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = True
        send_summary({"total": 0, "providers": {}}, webhook_url="https://explicit.test/webhook")
        url = mock_post.call_args[0][0]
        assert url == "https://explicit.test/webhook"


def test_send_summary_returns_false_on_post_failure():
    """send_summary returns False when _post_json reports failure."""
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = False
        result = send_summary({"total": 0, "providers": {}}, webhook_url="https://example.test")
        assert result is False


# ---------------------------------------------------------------------------
# send_alert
# ---------------------------------------------------------------------------


def test_send_alert_returns_false_when_webhook_unset(monkeypatch):
    """send_alert returns False when FEISHU_WEBHOOK_URL is unset."""
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    result = send_alert("Pipeline crashed")
    assert result is False


def test_send_alert_posts_text_payload():
    """send_alert POSTs msg_type=text payload with the message."""
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = True
        result = send_alert("Critical failure", webhook_url="https://example.test/webhook")
        assert result is True
        url, payload = mock_post.call_args[0]
        assert url == "https://example.test/webhook"
        assert payload["msg_type"] == "text"
        assert payload["content"]["text"] == "Critical failure"


def test_send_alert_prefers_explicit_webhook_over_env(monkeypatch):
    """send_alert uses explicit webhook_url over env var."""
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://env.test/webhook")
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = True
        send_alert("test", webhook_url="https://explicit.test/webhook")
        url = mock_post.call_args[0][0]
        assert url == "https://explicit.test/webhook"


def test_send_alert_returns_false_on_post_failure():
    """send_alert returns False when _post_json reports failure."""
    with patch("data.notify.feishu._post_json") as mock_post:
        mock_post.return_value = False
        result = send_alert("test", webhook_url="https://example.test")
        assert result is False