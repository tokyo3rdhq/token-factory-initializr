"""SummarizeStage — build the manifest dict for the run.

Writes ``context.artifacts["manifest"]``. The summary itself is computed by
``data.process.summarize.summarize_all``; this Stage is just an adapter.

Reads endpoints from ``context.data["enriched"]`` (post-enrich), which is
the canonical slot since the deduplicate step was removed.

Per refactor §24 the manifest now includes per-data-source provider
lifecycle (``added`` / ``updated`` / ``removed``) so the Feishu notify
card surfaces removals like ``zai-org removed``.
"""

from __future__ import annotations

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.summarize import summarize_all


class SummarizeStage(Stage):
    """Compute the pipeline run manifest and attach to context."""

    name = "summarize"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("enriched", [])
        errors = context.state.get("fetch_errors", {})
        plan = context.artifacts.get("reconciliation_plan")
        manifest = summarize_all(endpoints, errors, reconciliation_plan=plan)
        context.artifacts["manifest"] = manifest
        return context