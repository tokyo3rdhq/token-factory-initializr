"""ParseStage — pass-through adapter between Fetch and Normalize.

Per docs/arch_pipeline.md §12, parsing is the Provider's responsibility,
not a Pipeline stage. This Stage exists to preserve the canonical DSL
ordering (fetch → parse → normalize → validate → enrich → store →
summarize → notify) and to hand the fetched data forward as
``context.data["parsed"]``.

The Stage is intentionally boring: it should be a no-op unless future
providers need an explicit parse/normalization step before NormalizeStage
runs.
"""

from __future__ import annotations

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage


class ParseStage(Stage):
    """Pass-through: forwarded parsed output = fetched output."""

    name = "parse"

    def execute(self, context: PipelineContext) -> PipelineContext:
        # Each provider already returns provider-specific parsed output.
        # We simply forward it; NormalizeStage will reconcile into ModelEndpoint.
        fetched = context.data.get("fetched", {})
        context.data["parsed"] = {name: list(models) for name, models in fetched.items()}
        return context