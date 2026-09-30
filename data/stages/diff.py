"""DiffStage — compare current published state against the desired snapshot.

Per docs/data_source_provider_refactor.md §8:

    The diff stage lists, per data source, which providers are:
      - added       (in desired, not in current)
      - updated     (in both, but model set differs)
      - removed     (in current, not in desired)

Provider membership is taken from the per-source provider manifest
(``tfi:providers:{data_source}:latest``), not from model-level
differences — per §8 \"do not infer provider removal from model-level
differences alone\".

For each data source the stage reads the current provider manifest
from KV (if any), then computes three sets relative to the desired
snapshot. The diff is deterministic and idempotent — running it
twice on the same inputs produces the same plan.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.storage.cloudflare_kv import KVStorage

logger = logging.getLogger(__name__)


def _current_provider_set(manifest: Optional[dict[str, Any]]) -> set[str]:
    """Extract the active provider set from a current provider manifest.

    Tolerates the legacy top-level ``providers: { name: {count, status} }``
    shape (what /api/manifest returns) and the simpler
    ``{\"providers\": [\"novita\", \"together\"]}`` array shape. The
    publisher writes the latter; readers / consumers that echo the
    manifest in /api/manifest may enrich it.
    """
    if not manifest:
        return set()
    raw = manifest.get("providers")
    if isinstance(raw, list):
        return {str(p) for p in raw}
    if isinstance(raw, dict):
        return set(raw.keys())
    return set()


def build_diff(
    desired: dict[str, Any],
    current_manifests: dict[str, Optional[dict[str, Any]]],
) -> dict[str, dict[str, list[str]]]:
    """Compute added / updated / removed provider sets per data source.

    Args:
        desired: Output of :func:`data.stages.snapshot.build_desired_state`.
        current_manifests: Mapping ``{data_source: current_manifest_or_None}``
            — the per-source provider manifests as currently stored in KV.

    Returns:
        ``{data_source: {\"added\": [...], \"updated\": [...], \"removed\": [...]}}``

    \"updated\" includes any provider that is present in both current
    and desired (its model set may or may not have changed — the
    publisher is responsible for the actual content PUT).
    """
    diff: dict[str, dict[str, list[str]]] = {}
    for ds in desired["data_source_order"]:
        desired_bucket = desired["data_sources"].get(ds) or {
            "provider_order": [],
            "providers": {},
        }
        wanted = set(desired_bucket["provider_order"])

        current = current_manifests.get(ds)
        existing = _current_provider_set(current)

        added = sorted(wanted - existing)
        removed = sorted(existing - wanted)
        # Anything present in both is \"updated\" — the publisher
        # re-PUTs the model catalog (idempotent write) so the
        # content reflects the desired state.
        updated = sorted(wanted & existing)

        diff[ds] = {
            "added": added,
            "updated": updated,
            "removed": removed,
        }
    return diff


class DiffStage(Stage):
    """Compute per-data-source provider diff against the current KV state."""

    name = "diff"

    def __init__(self, kv: Optional[KVStorage] = None) -> None:
        self.kv = kv  # None ⇒ read from env at execute time

    def execute(self, context: PipelineContext) -> PipelineContext:
        desired = context.artifacts.get("desired_state")
        if desired is None:
            context.errors.append(
                {"stage": self.name, "error": "missing desired_state"}
            )
            return context

        kv = self.kv
        if kv is None:
            try:
                kv = KVStorage.from_env()
            except Exception as exc:  # noqa: BLE001
                logger.warning("DiffStage: KV init failed: %r", exc)
                kv = None

        current_manifests: dict[str, Optional[dict[str, Any]]] = {}
        for ds in desired["data_source_order"]:
            if kv is None:
                current_manifests[ds] = None
            else:
                try:
                    current_manifests[ds] = kv.get_provider_manifest(ds)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "DiffStage: get_provider_manifest(%s) failed: %r",
                        ds,
                        exc,
                    )
                    current_manifests[ds] = None

        context.artifacts["provider_diff"] = build_diff(
            desired, current_manifests
        )
        logger.info(
            "DiffStage: %s",
            {
                ds: {k: len(v) for k, v in plan.items()}
                for ds, plan in context.artifacts["provider_diff"].items()
            },
        )
        return context


__all__ = ["DiffStage", "build_diff"]