"""Summarize a pipeline run into a manifest-friendly aggregate.

This is a transform/pipeline stage — it lives under `data.process/`.

The summary is what gets stored as `tfi:manifest:latest` in KV (plus a
dated copy at ``tfi:manifest:<YYYY-MM-DD>``) and what the notify layer
consumes when alerting on failures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from data.models.schema import ModelEndpoint

# Provider status model — same as AGENTS.md §24
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_PARTIAL = "partial"


def summarize_all(
    endpoints: list[ModelEndpoint],
    fetch_errors: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Aggregate per-provider counts + status into a manifest dict.

    Args:
        endpoints: Valid, enriched endpoints after all transforms.
        fetch_errors: Mapping of provider → error message for providers
            whose fetcher raised. Providers not in this dict are assumed OK.

    Returns:
        Manifest dict ready for JSON serialization::

            {
              "version": "2026-09-24",
              "generated_at": "...",
              "total": 152,
              "providers": {
                "nvidia": {"count": 37, "status": "success"},
                "amd": {"count": 21, "status": "success"},
                "huggingface": {"count": 0, "status": "failed",
                                "error": "Network error ..."}
              }
            }
    """
    fetch_errors = fetch_errors or {}
    provider_counts: dict[str, int] = {}
    for ep in endpoints:
        provider_counts[ep.provider] = provider_counts.get(ep.provider, 0) + 1

    providers: dict[str, dict[str, Any]] = {}
    # Every known provider appears; missing fetcher entirely = 0 models OK
    known = set(fetch_errors) | set(provider_counts) | {"nvidia", "amd", "huggingface"}
    for name in sorted(known):
        entry: dict[str, Any] = {"count": provider_counts.get(name, 0)}
        if name in fetch_errors:
            entry["status"] = STATUS_FAILED
            entry["error"] = fetch_errors[name]
        else:
            entry["status"] = STATUS_SUCCESS
        providers[name] = entry

    return {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(endpoints),
        "providers": providers,
    }