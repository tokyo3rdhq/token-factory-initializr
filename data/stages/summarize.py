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
        # Per-ds write timestamps from the publish stage. Falls back
        # to ``{}`` when publish didn't run (e.g. KV init failed);
        # ``summarize_all`` then defaults the per-ds ``generated_at``
        # to ``None`` and the top-level ``generated_at`` to
        # ``datetime.now()``.
        publish_summary = context.artifacts.get("publish_summary") or {}
        per_ds_ts = publish_summary.get("per_data_source_timestamps") or {}
        manifest = summarize_all(
            endpoints,
            errors,
            reconciliation_plan=plan,
            per_data_source_timestamps=per_ds_ts,
        )
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

        # Sanity guard: refuse to overwrite tfi:manifest:latest when the
        # new run's total endpoint count drops sharply vs. the previous
        # manifest. Defends against the failure mode where a local
        # ``python main.py`` run with stale / pre-refactor code clobbers
        # a healthy production manifest (commit history: this happened
        # 2026-10-08 and produced a 962 -> 1 regression that persisted
        # until the next CI run). The dated ``tfi:manifest:<YYYY-MM-DD>``
        # key is intentionally NOT guarded -- it's an append-only daily
        # journal, not a clobber target.
        #
        # Thresholds:
        #   old_total == 0            -> first run or KV is empty; skip guard.
        #   new_total >= old_total * 0.5  -> normal / acceptable shrink.
        #   new_total <  old_total * 0.5  -> abort the write; surface to
        #                                   context.errors + notify so a
        #                                   Feishu alert fires.
        MANIFEST_REGRESSION_RATIO = 0.5
        guard_msg = None
        try:
            previous = kv.get(manifest_key())
        except Exception as exc:  # noqa: BLE001
            # GET failure (network, 5xx) is non-fatal: we still write the
            # new manifest rather than risk skipping a healthy run. The
            # failure is logged so the regression is observable in CI.
            logger.warning(
                "SummarizeStage: guard GET failed (%r); proceeding with write",
                exc,
            )
            previous = None
        if previous:
            old_total = previous.get("total")
            if isinstance(old_total, int) and old_total > 0:
                threshold = old_total * MANIFEST_REGRESSION_RATIO
                if manifest["total"] < threshold:
                    guard_msg = (
                        f"manifest regression guard tripped: "
                        f"old_total={old_total} new_total={manifest['total']} "
                        f"threshold={threshold} ({MANIFEST_REGRESSION_RATIO:.0%} "
                        f"of old). Refusing to overwrite tfi:manifest:latest. "
                        f"Likely cause: stale code or partial fetch. "
                        f"The dated manifest for today "
                        f"({manifest_key(_dt.utcnow().strftime('%Y-%m-%d'))}) "
                        f"was still written so today's record is preserved."
                    )

        if guard_msg is not None:
            logger.error("SummarizeStage: %s", guard_msg)
            context.errors.append({
                "stage": self.name,
                "error": guard_msg,
                "old_total": previous.get("total") if previous else None,
                "new_total": manifest["total"],
            })
            # Skip the latest-key write; fall through to write the
            # dated daily snapshot below so today's record is preserved.
        else:
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