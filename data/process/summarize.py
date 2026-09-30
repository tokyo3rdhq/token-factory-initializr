"""Summarize a pipeline run into a manifest-friendly aggregate.

This is a transform/pipeline stage — it lives under `data.process/`.

The summary is what gets stored as ``tfi:manifest:latest`` in KV (plus a
dated copy at ``tfi:manifest:<YYYY-MM-DD>``) and what the notify layer
consumes when alerting on failures.

Per docs/data_source_provider_refactor.md §24 the summary also surfaces
the reconciliation outcome (added / updated / removed providers per
data source) so daily run reports can answer \"zai-org removed?\"
without re-running the diff.
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
    *,
    reconciliation_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate per-data-source counts + status into a manifest dict.

    Args:
        endpoints: Valid, enriched endpoints after all transforms.
        fetch_errors: Mapping of data_source → error message for sources
            whose fetcher raised. Sources not in this dict are assumed OK.
        reconciliation_plan: Optional output of
            :func:`data.stages.reconcile.build_plan`. When supplied, the
            manifest includes per-source ``added`` / ``updated`` /
            ``removed`` provider lists so daily reports surface provider
            lifecycle changes (refactor §24).

    Returns:
        Manifest dict ready for JSON serialization::

            {
              "version": "2026-09-24",
              "generated_at": "...",
              "total": 152,
              "providers": {
                "nvidia": {"data_source": "nvidia", "count": 37, "status": "success",
                           "added": [], "updated": ["nvidia"], "removed": []},
                "amd":    {"data_source": "amd", "count": 21, "status": "success",
                           "added": ["amd"], "updated": [], "removed": []},
                "huggingface": {"data_source": "huggingface", "count": 0,
                                "status": "failed", "error": "...",
                                "added": [], "updated": ["novita", "together"],
                                "removed": ["zai-org"]}
              }
            }
    """
    fetch_errors = fetch_errors or {}
    provider_counts: dict[str, int] = {}
    for ep in endpoints:
        ds = ep.data_source or ""
        if ds:
            provider_counts[ds] = provider_counts.get(ds, 0) + 1

    providers: dict[str, dict[str, Any]] = {}
    # Every known data source appears; missing fetcher entirely = 0 models OK
    known = set(fetch_errors) | set(provider_counts) | {"nvidia", "amd", "huggingface"}
    for name in sorted(known):
        entry: dict[str, Any] = {
            "data_source": name,
            "count": provider_counts.get(name, 0),
        }
        if name in fetch_errors:
            entry["status"] = STATUS_FAILED
            entry["error"] = fetch_errors[name]
        else:
            entry["status"] = STATUS_SUCCESS
        # Reconciliation lifecycle (refactor §24) — only attached when
        # the plan is available; older callers that compute the manifest
        # before the publish stage continue to work.
        if reconciliation_plan is not None:
            by_ds = (reconciliation_plan.get("by_data_source") or {}).get(name) or {}
            entry["added"] = by_ds.get("added", [])
            entry["updated"] = by_ds.get("updated", [])
            entry["removed"] = by_ds.get("removed", [])
        providers[name] = entry

    return {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(endpoints),
        "providers": providers,
    }