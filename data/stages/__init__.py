"""Stages package — thin adapters binding business capabilities to the pipeline.

Each Stage here delegates to a concrete module (providers/, storage/, data/
notify/, data/process/) and writes/reads only ``PipelineContext`` slots.

The actual order is composed in :func:`build_default_pipeline` — the
Pipeline package itself must not import these Stage classes (one-way
dependency: main → pipeline → stages → ...).
"""

from data.stages.enrich import EnrichStage
from data.stages.fetch import FetchStage, PROVIDER_FETCHERS
from data.stages.normalize import NormalizeStage
from data.stages.notify import NotifyStage
from data.stages.parse import ParseStage
from data.stages.store import StoreStage
from data.stages.summarize import SummarizeStage
from data.stages.validate import ValidateStage


def build_default_pipeline() -> "Pipeline":
    """Compose the canonical data pipeline.

    Per docs/arch_models_intelligence_layer_evo.md §2:

        fetch → parse → normalize → validate → enrich
        → summarize → store → notify

    ``SummarizeStage`` runs before ``StoreStage`` so the manifest written
    to KV reflects the actual endpoints being persisted (rather than an
    empty placeholder computed before validation/enrichment).

    ``EnrichStage`` is a placeholder (no enrichers wired yet). The
    ``DeduplicateStage`` was removed per doc §12 — model identity and
    endpoint identity are kept distinct, and same-model-different-provider
    is preserved as separate endpoints.
    """
    from data.pipeline.pipeline import Pipeline

    return (
        Pipeline()
        .then(FetchStage())
        .then(ParseStage())
        .then(NormalizeStage())
        .then(ValidateStage())
        .then(EnrichStage())
        .then(SummarizeStage())
        .then(StoreStage())
        .then(NotifyStage())
        .end()
    )


__all__ = [
    "FetchStage",
    "ParseStage",
    "NormalizeStage",
    "ValidateStage",
    "EnrichStage",
    "StoreStage",
    "SummarizeStage",
    "NotifyStage",
    "PROVIDER_FETCHERS",
    "build_default_pipeline",
]