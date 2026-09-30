"""ReconcileStage — turn the diff into an explicit reconciliation plan.

Per docs/data_source_provider_refactor.md §9:

    A ReconciliationPlan defines, per data source:
      - added providers       (PUT model catalog)
      - updated providers     (PUT model catalog, idempotent)
      - removed providers     (DELETE model catalog)

The plan is intentionally a plain dict so that ``PublishStage`` and
``SummarizeStage`` can both consume it without coupling to a custom
class. It also surfaces the invariants the publisher MUST honor:

    * Empty-snapshot safety (refactor §20 / §21):
      if the previous KV state had providers for a source but the
      current snapshot has none, refuse to plan a full removal
      unless ``context.artifacts[\"source_validated\"]`` is True.
      The intent is to prevent accidental deletion of an entire
      provider catalog because a source returned an empty /
      incomplete / paginated / partially-failed fetch.

    * Idempotency (refactor §12):
      the plan is a function of (desired_state, current_manifests).
      Running reconcile twice on the same inputs produces the same
      plan; running it after the publish stage already converged
      produces a no-op plan with empty added/updated/removed sets.
"""

from __future__ import annotations

import logging
from typing import Any

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


def build_plan(
    desired: dict[str, Any],
    diff: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    """Build the reconciliation plan from desired state + diff.

    Empty-snapshot safety (§20/§21) is NOT enforced here — that's a
    publisher concern (``PublishStage`` reads ``context.artifacts``
    flags). This stage only materializes the plan.
    """
    plan: dict[str, Any] = {"by_data_source": {}}
    total_added = total_updated = total_removed = 0

    for ds in desired["data_source_order"]:
        d = diff.get(ds) or {"added": [], "updated": [], "removed": []}
        bucket = desired["data_sources"].get(ds) or {
            "data_source": ds,
            "providers": {},
        }
        plan["by_data_source"][ds] = {
            "data_source": ds,
            "added": d["added"],
            "updated": d["updated"],
            "removed": d["removed"],
            # Provider manifests list every currently active provider,
            # sorted deterministically for downstream reproducibility.
            "manifest_providers": bucket.get("provider_order", []),
        }
        total_added += len(d["added"])
        total_updated += len(d["updated"])
        total_removed += len(d["removed"])

    plan["summary"] = {
        "added": total_added,
        "updated": total_updated,
        "removed": total_removed,
    }
    return plan


class ReconcileStage(Stage):
    """Materialize the explicit reconciliation plan from the diff."""

    name = "reconcile"

    def execute(self, context: PipelineContext) -> PipelineContext:
        desired = context.artifacts.get("desired_state")
        diff = context.artifacts.get("provider_diff")
        if desired is None or diff is None:
            context.errors.append(
                {
                    "stage": self.name,
                    "error": "missing desired_state or provider_diff",
                }
            )
            return context

        plan = build_plan(desired, diff)
        context.artifacts["reconciliation_plan"] = plan
        logger.info(
            "ReconcileStage: plan = added=%d updated=%d removed=%d",
            plan["summary"]["added"],
            plan["summary"]["updated"],
            plan["summary"]["removed"],
        )
        return context


__all__ = ["ReconcileStage", "build_plan"]