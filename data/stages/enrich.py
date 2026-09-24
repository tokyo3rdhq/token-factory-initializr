"""EnrichStage — placeholder for future enrichment logic.

Per docs/arch_models_intelligence_layer_evo.md §6, enrichment combines
multiple external references (models.dev, OpenRouter, Hugging Face, etc.)
to build richer knowledge about each model. The MVP pipeline keeps the
slot so downstream Stages can rely on ``context.data["enriched"]``, but
per the current iteration scope no enrichers are wired up yet — the Stage
is a pass-through that copies the validated list into the ``enriched``
slot and records an empty facts list.

Future work:
  - ModelsDevEnricher
  - OpenRouterEnricher
  - HuggingFaceEnricher
  - ProviderEnricher
  - evidence + source authority engine (see doc §8–§10)
"""

from __future__ import annotations

import logging

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


class EnrichStage(Stage):
    """Forward ``valid`` endpoints to the ``enriched`` slot.

    No transformation applied yet. The Stage exists so the canonical DSL
    has a stable ``enrich`` step between ``validate`` and ``store``.
    """

    name = "enrich"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = list(context.data.get("valid", []))
        context.data["enriched"] = endpoints
        # Future: each enricher appends to context.artifacts["enrich_facts"].
        context.artifacts.setdefault("enrich_facts", [])
        return context