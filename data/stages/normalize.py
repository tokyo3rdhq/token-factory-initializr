"""NormalizeStage — convert provider-specific parsed output into ModelEndpoint.

NVIDIA provider already returns ``ModelEndpoint`` objects; this stage
passes them through unchanged. AMD/HF return raw ``dict`` shaped like
``{provider, model_id, free, ...}`` and are mapped via
``data.process.normalize.normalize_endpoints``.
"""

from __future__ import annotations

from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.normalize import normalize_endpoints


class NormalizeStage(Stage):
    """Normalize provider outputs into the canonical ModelEndpoint schema."""

    name = "normalize"

    def execute(self, context: PipelineContext) -> PipelineContext:
        parsed = context.data.get("parsed", {})
        endpoints: list[ModelEndpoint] = []
        for provider, items in parsed.items():
            if provider == "nvidia":
                # NVIDIA provider yields ModelEndpoint objects directly.
                endpoints.extend(items)
            else:
                endpoints.extend(normalize_endpoints(items))
        context.data["endpoints"] = endpoints
        return context