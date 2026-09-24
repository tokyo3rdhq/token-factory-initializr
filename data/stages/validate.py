"""ValidateStage — split endpoints into (valid, invalid).

Keeps both lists: ``valid`` proceeds to dedup → store → summarize, and
``invalid`` is preserved for the Feishu notify card.
"""

from __future__ import annotations

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.validate import validate_all


class ValidateStage(Stage):
    """Split endpoints into valid (proceeds) and invalid (logged)."""

    name = "validate"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("endpoints", [])
        valid, invalid = validate_all(endpoints)
        context.data["valid"] = valid
        context.data["invalid"] = invalid
        return context