"""SummarizeStage — build the manifest dict and persist it to KV.

Writes ``context.artifacts[\"manifest\"]``. The summary itself is computed by
``data.process.summarize.summarize_all``; this Stage is just an adapter.

Reads endpoints from ``context.data[\"enriched\"]`` (post-enrich), which is
the canonical slot since the deduplicate step was removed.

Per refactor §24 the manifest now includes per-data-source provider
lifecycle (``added`` / ``updated`` / ``removed``) so the Feishu notify
card surfaces removals like ``zai-org removed``.

The Stage ALSO writes the manifest to KV at ``tfi:manifest:latest`` (plus
a dated copy at ``tfi:manifest:<YYYY-MM-DD>``) — the aggregated manifest
is the source of truth for the daily Feishu card and the GitHub
Actions \"Validate results\" step that confirms a successful run. In
the pre-refactor pipeline, ``StoreStage`` owned this write. After the
split into ``Snapshot/Diff/Reconcile/Publish``, the per-(data_source,
provider) catalogs are written by ``PublishStage`` and the aggregated
manifest moves here.
"""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from typing import Optional

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.summarize import summarize_all
from data.storage.cloudflare_kv import KVStorage, manifest_key

logger = logging.getLogger(__name__)


def _today_key() -> str:
    """Return the dated manifest key for the current UTC day."""
    return manifest_key(_dt.utcnow().strftime("%Y-%m-%d"))


class SummarizeStage(Stage):
    """Compute the pipeline run manifest and persist it to KV."""

    name = "summarize"

    def __init__(self, kv: Optional[KVStorage] = None) -> None:
        self.kv = kv  # If None, will construct from env at execute time.

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("enriched", [])
        errors = context.state.get("fetch_errors", {})
        plan = context.artifacts.get("reconciliation_plan")
        manifest = summarize_all(endpoints, errors, reconciliation_plan=plan)
        context.artifacts["manifest"] = manifest

        kv = self.kv
        if kv is None:
            try:
                kv = KVStorage.from_env()
            except Exception as exc:  # noqa: BLE001
                msg = f"SummarizeStage: KV init failed: {exc!r}"
                logger.error(msg)
                context.errors.append({"stage": self.name, "error": msg})
                return context

        # tfi:manifest:latest — overwrites previous run.
        try:
            kv.put(manifest_key(), manifest)
        except Exception as exc:  # noqa: BLE001
            msg = f"SummarizeStage: put({manifest_key()}) failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})

        # tfi:manifest:<YYYY-MM-DD> — dated snapshot retained per run.
        # The \"Validate results\" CI step GETs this dated key to confirm
        # the pipeline actually committed today's manifest (immune to a
        # previous-day artifact still at tfi:manifest:latest).
        dated_key = _today_key()
        try:
            kv.put(dated_key, manifest)
            logger.info("Wrote dated manifest snapshot to %s", dated_key)
        except Exception as exc:  # noqa: BLE001
            msg = f"SummarizeStage: put({dated_key}) failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})

        return context