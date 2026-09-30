"""ValidateStage — split endpoints into (valid, invalid) and flag source health.

Keeps both lists: ``valid`` proceeds to snapshot → diff → reconcile → publish,
and ``invalid`` is preserved for the Feishu notify card.

The Stage also populates ``context.artifacts[\"source_validated\"]`` —
a per-data-source boolean flag consulted by ``PublishStage`` before
issuing any destructive DELETE on a provider catalog (refactor §20 /
§21). A source is considered validated iff it had at least one valid
endpoint this run OR it had zero endpoints AND no fetch error. An
incomplete fetch (zero endpoints + fetch error in context state) is
NOT validated, which causes ``PublishStage`` to refuse destructive
deletes.
"""

from __future__ import annotations

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.validate import validate_all
from data.storage.cloudflare_kv import KNOWN_DATA_SOURCES


class ValidateStage(Stage):
    """Split endpoints into valid (proceeds) and invalid (logged)."""

    name = "validate"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("endpoints", [])
        valid, invalid = validate_all(endpoints)
        context.data["valid"] = valid
        context.data["invalid"] = invalid
        # Mark every known source validated iff it had any valid
        # endpoint OR it had no fetch error this run. A source that
        # produced zero valid endpoints AND has a fetch error is
        # treated as not validated.
        fetch_errors = context.state.get("fetch_errors") or {}
        per_source_counts: dict[str, int] = {}
        for ep in valid:
            ds = ep.data_source if hasattr(ep, "data_source") else ""
            if ds:
                per_source_counts[ds] = per_source_counts.get(ds, 0) + 1
        validated: dict[str, bool] = {}
        for ds in KNOWN_DATA_SOURCES:
            if per_source_counts.get(ds, 0) > 0:
                validated[ds] = True
            elif ds not in fetch_errors:
                validated[ds] = True  # zero valid + no error = legitimate empty
            else:
                validated[ds] = False
        context.artifacts["source_validated"] = validated
        return context