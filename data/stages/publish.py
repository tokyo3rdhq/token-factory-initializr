"""PublishStage — apply the reconciliation plan to Cloudflare KV.

Per docs/data_source_provider_refactor.md §10 / §11 / §20 / §21:

    Publish order for each data source:

      1. PUT model catalogs for added providers
      2. PUT model catalogs for updated providers (idempotent overwrite)
      3. DELETE model catalogs for removed providers
      4. PUT the provider manifest LAST

    Why this order matters:
      The provider manifest acts as the discovery index. Until it is
      updated, consumers can only see the OLD set of providers. By
      writing model catalogs first, we narrow the window in which a
      consumer could discover a provider whose catalog has not yet
      been published.

Safety guards
    §20 — Incomplete source data must not trigger destructive deletion.
    §21 — Empty desired set is dangerous (could be a real zero OR a
    broken fetch). The publisher refuses to plan a full removal of
    all providers for a source unless the source's last fetch was
    marked ``validated=True`` in ``context.artifacts``.

    The flag ``context.artifacts[\"source_validated\"]`` is a per-
    source dict (``{\"huggingface\": True, \"amd\": True, ...}``).
    ValidateStage sets this to ``True`` when it accepts the fetch
    and ``False`` when it does not. The publisher consults it
    before issuing DELETEs.

Cloudflare KV is not transactional
    §11 — KV provides no multi-key atomicity. The publisher must
    therefore be:
      - deterministic (same plan → same KV state)
      - idempotent (running it twice converges)
      - retryable (transient backend errors are retried by the
        underlying KVStorage._request_with_retry)
      - safe (guards above prevent the worst-class bug: a failed
        fetch erasing the entire provider catalog)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.storage.cloudflare_kv import (
    KNOWN_DATA_SOURCES,
    KVStorage,
)

logger = logging.getLogger(__name__)


def _validated_sources(context: PipelineContext) -> dict[str, bool]:
    """Read the per-source validation flag set by ``ValidateStage``.

    Missing flag ⇒ assume not validated. This is conservative — the
    publisher will refuse destructive operations on unvalidated
    sources, which is the safer default.
    """
    raw = context.artifacts.get("source_validated") or {}
    out: dict[str, bool] = {}
    for ds in KNOWN_DATA_SOURCES:
        out[ds] = bool(raw.get(ds, False))
    return out


def _emit_manifest(
    desired_bucket: dict[str, Any],
) -> dict[str, Any]:
    """Build the per-data-source provider manifest payload."""
    return {
        "data_source": desired_bucket["data_source"],
        "providers": list(desired_bucket["provider_order"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def publish_plan(
    kv: KVStorage,
    plan: dict[str, Any],
    desired: dict[str, Any],
    validated: dict[str, bool],
    *,
    fail_on_unsafe: bool = True,
) -> dict[str, Any]:
    """Apply the plan to KV. Returns a result summary.

    Args:
        kv: The KV backend.
        plan: Output of :func:`data.stages.reconcile.build_plan`.
        desired: Output of :func:`data.stages.snapshot.build_desired_state`.
        validated: Per-data-source validation flag. Missing
            sources are treated as not validated (refuse DELETE).
        fail_on_unsafe: When True (default), an attempted destructive
            delete against an unvalidated source raises ``RuntimeError``
            instead of silently skipping. The Stage wraps this so the
            error surfaces to ``context.errors`` and the notify stage
            can alert.

    The summary dict gains a ``per_data_source_timestamps`` field
    (``{data_source: iso_timestamp}``) that records when the per-ds
    provider manifest was actually PUT to KV. The summarize stage
    surfaces this as ``providers.{ds}.generated_at`` in the
    aggregated manifest so consumers can tell exactly when each ds
    was last written without re-running the pipeline.
    """
    summary = {
        "added": 0,
        "updated": 0,
        "removed": 0,
        "manifests_written": 0,
        "skipped_unsafe": [],
        "per_data_source_timestamps": {},
    }

    for ds, bucket in plan["by_data_source"].items():
        desired_bucket = desired["data_sources"].get(ds) or {
            "data_source": ds,
            "providers": {},
            "provider_order": [],
        }

        # Step 1: PUT added provider catalogs.
        for provider in bucket["added"]:
            models = desired_bucket["providers"].get(provider, [])
            kv.put_provider_models(ds, provider, models)
            summary["added"] += 1
            logger.info("publish: PUT models:%s:%s (%d models)", ds, provider, len(models))

        # Step 2: PUT updated provider catalogs (idempotent overwrite).
        for provider in bucket["updated"]:
            models = desired_bucket["providers"].get(provider, [])
            kv.put_provider_models(ds, provider, models)
            summary["updated"] += 1
            logger.info(
                "publish: PUT models:%s:%s (updated, %d models)",
                ds,
                provider,
                len(models),
            )

        # Step 3: DELETE removed provider catalogs — guarded.
        for provider in bucket["removed"]:
            if not validated.get(ds, False):
                msg = (
                    f"refusing DELETE models:{ds}:{provider}: "
                    f"source not validated (artifacts.source_validated[{ds}]"
                    f"=False). Possible cause: upstream fetch was "
                    f"empty/incomplete/paginated-failed."
                )
                if fail_on_unsafe:
                    raise RuntimeError(msg)
                logger.warning("publish: %s", msg)
                summary["skipped_unsafe"].append(f"{ds}:{provider}")
                continue
            kv.delete_provider_models(ds, provider)
            summary["removed"] += 1
            logger.info("publish: DELETE models:%s:%s", ds, provider)

        # Step 4: PUT provider manifest LAST — record the actual
        # write time so the aggregated manifest can surface it as
        # ``providers.{ds}.generated_at``.
        try:
            kv.put_provider_manifest(ds, _emit_manifest(desired_bucket))
            summary["manifests_written"] += 1
            summary["per_data_source_timestamps"][ds] = (
                datetime.now(timezone.utc).isoformat()
            )
            logger.info(
                "publish: PUT providers:%s (%d providers) at %s",
                ds,
                len(desired_bucket["provider_order"]),
                summary["per_data_source_timestamps"][ds],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "publish: failed to write manifest for %s: %r", ds, exc
            )
            raise

    return summary


class PublishStage(Stage):
    """Apply the reconciliation plan to Cloudflare KV."""

    name = "publish"

    def __init__(self, kv: Optional[KVStorage] = None) -> None:
        self.kv = kv

    def execute(self, context: PipelineContext) -> PipelineContext:
        desired = context.artifacts.get("desired_state")
        plan = context.artifacts.get("reconciliation_plan")
        if desired is None or plan is None:
            context.errors.append(
                {
                    "stage": self.name,
                    "error": "missing desired_state or reconciliation_plan",
                }
            )
            return context

        kv = self.kv
        if kv is None:
            try:
                kv = KVStorage.from_env()
            except Exception as exc:  # noqa: BLE001
                msg = f"PublishStage: KV init failed: {exc!r}"
                logger.error(msg)
                context.errors.append({"stage": self.name, "error": msg})
                return context

        validated = _validated_sources(context)
        try:
            summary = publish_plan(kv, plan, desired, validated)
        except Exception as exc:  # noqa: BLE001
            msg = f"PublishStage: publish failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})
            return context

        context.artifacts["publish_summary"] = summary
        context.metrics["publish"] = {
            "added": summary["added"],
            "updated": summary["updated"],
            "removed": summary["removed"],
            "skipped_unsafe": len(summary["skipped_unsafe"]),
        }
        logger.info("PublishStage: %s", summary)
        return context


__all__ = ["PublishStage", "publish_plan"]