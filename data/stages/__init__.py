"""Stages package — thin adapters binding business capabilities to the pipeline.

Each Stage here delegates to a concrete module (providers/, storage/, data/
notify/, data/process/) and writes/reads only ``PipelineContext`` slots.

The actual order is composed in :func:`build_default_pipeline` — the
Pipeline package itself must not import these Stage classes (one-way
dependency: main → pipeline → stages → ...).
"""

from data.stages.diff import DiffStage
from data.stages.enrich import EnrichStage
from data.stages.fetch import FetchStage, PROVIDER_FETCHERS
from data.stages.filter_free import FilterFreeStage
from data.stages.normalize import NormalizeStage
from data.stages.notify import NotifyStage
from data.stages.parse import ParseStage
from data.stages.publish import PublishStage
from data.stages.reconcile import ReconcileStage
from data.stages.snapshot import SnapshotStage
from data.stages.summarize import SummarizeStage
from data.stages.validate import ValidateStage


def build_default_pipeline() -> "Pipeline":
    """Compose the canonical data pipeline.

    Per docs/data_source_provider_refactor.md §6:

        fetch → parse → filter_free → normalize → validate → enrich
        → snapshot → diff → reconcile → publish → summarize → notify

    The ``store`` stage has been replaced by the four-stage
    snapshot/diff/reconcile/publish sequence, which writes through
    the new (data_source, provider) KV namespace and reconciles
    provider lifecycle explicitly.

    ``SummarizeStage`` runs AFTER publish so the Feishu manifest
    can report the actual provider changes (added/updated/removed)
    that the publish stage just committed.

    ``ValidateStage`` populates
    ``context.artifacts[\"source_validated\"]`` — a per-source flag
    that ``PublishStage`` consults before issuing any DELETE
    (refactor §20 / §21 empty-snapshot safety).
    """
    from data.pipeline.pipeline import Pipeline

    return (
        Pipeline()
        .then(FetchStage())
        .then(ParseStage())
        .then(FilterFreeStage())
        .then(NormalizeStage())
        .then(ValidateStage())
        .then(EnrichStage())
        .then(SnapshotStage())
        .then(DiffStage())
        .then(ReconcileStage())
        .then(PublishStage())
        .then(SummarizeStage())
        .then(NotifyStage())
        .end()
    )


__all__ = [
    "FetchStage",
    "ParseStage",
    "FilterFreeStage",
    "NormalizeStage",
    "ValidateStage",
    "EnrichStage",
    "SnapshotStage",
    "DiffStage",
    "ReconcileStage",
    "PublishStage",
    "SummarizeStage",
    "NotifyStage",
    "PROVIDER_FETCHERS",
    "build_default_pipeline",
]