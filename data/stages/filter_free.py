"""FilterFreeStage — drop non-free endpoints after parsing.

Per docs/arch_models_intelligence_layer_evo.md, the canonical pipeline
order is::

    fetch → parse → filter_free → normalize → validate → enrich
    → summarize → store → notify

The filter step is a single stage but the *rule* is provider-specific
(NVIDIA label-set membership, AMD boolean field, HF per-provider
pricing tuple — see :mod:`data.providers.free_filter` for the
asymmetry). The Stage dispatches to the right per-provider filter via
:func:`data.providers.free_filter.filter_free` and records metrics so
ops can see how many endpoints each provider dropped.

The Stage reads ``context.data["parsed"]`` (set by ``ParseStage``),
writes ``context.data["filtered"]``, and increments
``context.metrics["filter_free"]`` with per-provider counts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.providers.free_filter import filter_free

logger = logging.getLogger(__name__)


class FilterFreeStage(Stage):
    """Drop non-free endpoints, dispatching by provider.

    Reads ``context.data["parsed"]`` (a dict ``{provider: [endpoints]}``),
    applies the per-provider free filter, and writes the result to
    ``context.data["filtered"]``. Metrics are recorded under
    ``context.metrics["filter_free"]`` as::

        {
            "<provider>": {"in": N, "out": M, "dropped": N - M},
            ...
        }

    Unknown providers are passed through and recorded with the same
    ``in``/``out``/``dropped`` counts — they shouldn't appear in normal
    operation, but a forward-compatible pipeline shouldn't crash if
    one does.
    """

    name = "filter_free"

    def execute(self, context: PipelineContext) -> PipelineContext:
        parsed = context.data.get("parsed", {}) or {}
        filtered: Dict[str, List[Any]] = {}
        metrics: Dict[str, Dict[str, int]] = {}

        for provider, endpoints in parsed.items():
            before = len(endpoints)
            kept = filter_free(list(endpoints), provider)
            after = len(kept)
            filtered[provider] = kept
            metrics[provider] = {
                "in": before,
                "out": after,
                "dropped": before - after,
            }
            if before != after:
                logger.info(
                    "filter_free[%s]: kept %d / %d (dropped %d)",
                    provider,
                    after,
                    before,
                    before - after,
                )

        context.data["filtered"] = filtered
        existing = context.metrics.get("filter_free", {})
        existing.update(metrics)
        context.metrics["filter_free"] = existing

        # Downstream stages read from ``endpoints`` (NormalizeStage) or
        # ``parsed`` (legacy code). Mirror the filtered result into
        # ``parsed`` too so NormalizeStage — which currently reads
        # ``parsed`` — sees the post-filter data without a separate
        # code change. If the pipeline grows other readers, this
        # alias can be removed.
        context.data["parsed"] = filtered

        return context


__all__ = ["FilterFreeStage"]