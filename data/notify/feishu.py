"""Feishu (Lark) webhook notification adapter.

Sends pipeline run summaries / alerts to a Feishu custom-bot webhook.
Webhooks are configured via the ``FEISHU_WEBHOOK_URL`` environment variable.

Network:  GitHub Actions runner can reach open.feishu.cn directly — no
proxy needed.

Usage:
    from data.notify.feishu import send_summary

    send_summary(manifest, invalid=[...])
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Iterable

logger = logging.getLogger(__name__)

DEFAULT_WEBHOOK_ENV = "FEISHU_WEBHOOK_URL"
TIMEOUT = 10


def _post_json(url: str, body: dict) -> bool:
    """POST JSON to a webhook URL. Returns True on success."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.error("Feishu webhook POST failed: %s", exc)
        return False


def _format_card(
    manifest: dict[str, Any],
    invalid: Iterable[dict],
    errors: Iterable[dict] | None = None,
) -> dict[str, Any]:
    """Build an interactive-card message body for Feishu."""
    provider_lines = []
    for name, info in sorted(manifest.get("providers", {}).items()):
        status = info.get("status", "unknown")
        count = info.get("count", 0)
        added = info.get("added") or []
        removed = info.get("removed") or []
        line = f"**{name}** — {count} endpoints ({status})"
        # Refactor §24: surface provider lifecycle changes (added/removed).
        if added or removed:
            parts = []
            if added:
                parts.append(f"added: {', '.join(added)}")
            if removed:
                parts.append(f"removed: {', '.join(removed)}")
            line += f"  ({'; '.join(parts)})"
        provider_lines.append(line)

    invalid_count = len(list(invalid)) if not isinstance(invalid, list) else len(invalid)
    body_text = "\n".join(provider_lines)
    body_text += f"\n\nTotal: {manifest.get('total', 0)} | Invalid: {invalid_count}"

    error_list = list(errors or [])
    if error_list:
        body_text += "\n\n**Stage errors:**\n"
        for e in error_list:
            stage = e.get("stage", "?")
            err = e.get("error", "?")
            if len(err) > 200:
                err = err[:200] + "..."
            body_text += f"- `{stage}`: {err}\n"

    header_template = "red" if error_list else "blue"
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "Token Factory Initializr — Pipeline Run",
                },
                "template": header_template,
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": body_text,
                },
            ],
        },
    }


def send_summary(
    manifest: dict[str, Any],
    invalid: list[dict[str, Any]] | None = None,
    webhook_url: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> bool:
    """Send a pipeline-run summary as a Feishu interactive card.

    Args:
        manifest: Pipeline manifest dict from data.process.summarize.
        invalid:  List of invalid-record diagnostics (optional).
        webhook_url: Override webhook URL; defaults to FEISHU_WEBHOOK_URL env var.
        errors:   Stage-level errors from PipelineContext.errors (optional).
            When non-empty, the card header is rendered red and the errors are
            surfaced inline.

    Returns:
        True if the webhook accepted the message (2xx); False otherwise.
    """
    url = webhook_url or os.environ.get(DEFAULT_WEBHOOK_ENV, "")
    if not url:
        logger.info("FEISHU_WEBHOOK_URL not set; skipping notification")
        return False

    card = _format_card(manifest, invalid or [], errors=errors or [])
    return _post_json(url, card)


def send_alert(
    message: str,
    webhook_url: str | None = None,
) -> bool:
    """Send a plain-text alert (used on hard pipeline failures).

    Args:
        message: Plain-text alert body.
        webhook_url: Override webhook URL; defaults to FEISHU_WEBHOOK_URL.

    Returns:
        True if the webhook accepted the message; False otherwise.
    """
    url = webhook_url or os.environ.get(DEFAULT_WEBHOOK_ENV, "")
    if not url:
        logger.info("FEISHU_WEBHOOK_URL not set; skipping alert")
        return False

    body = {"msg_type": "text", "content": {"text": message}}
    return _post_json(url, body)