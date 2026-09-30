"""SnapshotStage — build the DesiredState for the current pipeline run.

Per docs/data_source_provider_refactor.md §7 / §15:

    fetch → parse → filter_free → normalize → validate → enrich
    → snapshot → diff → reconcile → publish → summarize → notify

``SnapshotStage`` consumes the validated, enriched endpoints and
groups them by ``(data_source, provider)``. The result is a
deterministic, in-memory snapshot of what the catalog SHOULD look
like in KV once this run finishes.

The DesiredState shape mirrors the KV namespace:

  DesiredState
    data_sources: dict[str, DataSourceSnapshot]
      DataSourceSnapshot
        data_source: str
        providers: dict[str, list[dict]]  # provider → endpoint dicts
        provider_order: list[str]         # deterministic ordering

The deterministic ordering matters because diff/reconcile must
produce a stable plan regardless of dict iteration order — which
in Python 3.7+ is insertion order, but in earlier points in the
pipeline the endpoint list may have come back from async tasks in
non-deterministic order. Sorting by provider name at the snapshot
level guarantees the rest of the pipeline is reproducible.

``SnapshotStage`` is a thin Stage: the only side effect on
``PipelineContext`` is ``context.artifacts[\"desired_state\"]``,
a fully-serializable dict.
"""

from __future__ import annotations

import logging
from typing import Any

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.normalize import endpoint_to_dict
from data.storage.cloudflare_kv import KNOWN_DATA_SOURCES

logger = logging.getLogger(__name__)


def build_desired_state(endpoints: list[Any]) -> dict[str, Any]:
    """Group validated endpoints by ``(data_source, provider)``.

    Returns a dict shaped like::

        {
            "data_sources": {
                "nvidia": {
                    "data_source": "nvidia",
                    "providers": {"nvidia": [<endpoint dict>, ...]},
                    "provider_order": ["nvidia"],
                },
                "huggingface": {
                    "data_source": "huggingface",
                    "providers": {
                        "novita":   [...],
                        "together": [...],
                    },
                    "provider_order": ["novita", "together"],
                },
                ...
            },
            "data_source_order": ["nvidia", "amd", "huggingface"],
        }

    Every known data source appears in the output even if it has
    zero providers this run — so consumers (and the publish stage)
    can distinguish \"no providers\" from \"no data yet\" by
    reading the manifest.
    """
    data_sources: dict[str, dict[str, Any]] = {}

    for ds in KNOWN_DATA_SOURCES:
        data_sources[ds] = {
            "data_source": ds,
            "providers": {},
            "provider_order": [],
        }

    for ep in endpoints:
        d = ep.__dict__ if hasattr(ep, "__dict__") else dict(ep)
        ds = d.get("data_source") or ""
        provider = d.get("provider") or ""
        if not ds or not provider:
            # ValidateStage should have caught this, but be defensive:
            # a record with no (data_source, provider) cannot be
            # reconciled. Drop and log.
            logger.warning(
                "SnapshotStage: dropping endpoint without "
                "(data_source, provider): %s",
                d.get("model_id"),
            )
            continue
        bucket = data_sources.setdefault(
            ds,
            {"data_source": ds, "providers": {}, "provider_order": []},
        )
        if provider not in bucket["providers"]:
            bucket["providers"][provider] = []
            bucket["provider_order"].append(provider)
        bucket["providers"][provider].append(d)

    # Stable sort so reconcile/publish are reproducible.
    for ds in data_sources.values():
        ds["provider_order"].sort()

    return {
        "data_sources": data_sources,
        "data_source_order": sorted(data_sources.keys()),
    }


class SnapshotStage(Stage):
    """Build the desired-state snapshot from validated endpoints."""

    name = "snapshot"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("enriched") or context.data.get("validated") or []
        context.artifacts["desired_state"] = build_desired_state(endpoints)
        logger.info(
            "SnapshotStage: built desired state for %d endpoints across %d sources",
            len(endpoints),
            len(context.artifacts["desired_state"]["data_sources"]),
        )
        return context


__all__ = ["SnapshotStage", "build_desired_state"]