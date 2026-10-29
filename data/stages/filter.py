"""FilterStage — qualify endpoints for the catalog after parsing.

Per docs/tfi_model_endpoint_support_paid_model.md §5.1, ingestion no
longer drops paid/unknown-pricing endpoints. This stage now performs
*qualification*:

* Keeps every eligible endpoint — free, paid, and unknown.
* Rejects only *malformed* records: endpoints missing a required
  identity field (``provider``, ``model_id``, ``data_source``).
  ``fetched_at`` is intentionally NOT required here — it is filled in by
  the normalize stage which runs AFTER this stage.
* Writes ``context.data["filtered"]`` and mirrors it into
  ``context.data["parsed"]`` so downstream readers (NormalizeStage,
  legacy code) see the post-qualification data.
* Records per-provider metrics under ``context.metrics["filter"]``
  where ``dropped`` now counts malformed rejections only — not
  non-free endpoints.

Pipeline order::

    fetch → parse → filter → normalize → validate → enrich
    → snapshot → diff → reconcile → publish → summarize → notify
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)

# Required identity fields an endpoint must carry to be eligible for the
# catalog. Missing any of these ⇒ malformed ⇒ rejected.
#
# NOTE: ``fetched_at`` is intentionally NOT required here — it is filled
# in by the normalize stage (``normalize_endpoints``), which runs AFTER
# FilterStage. Requiring it here would wrongly reject every
# dict-shaped endpoint (Kilo, OpenRouter, models_dev, …) that hasn't
# been normalized yet.
_REQUIRED_IDENTITY_FIELDS = ("provider", "model_id", "data_source")


def _is_malformed(endpoint: Any) -> bool:
    """True iff ``endpoint`` is missing a required identity field.

    Tolerates both ``ModelEndpoint`` dataclass instances (constructor
    guarantees these fields) and plain dicts (provider adapters).
    """
    if isinstance(endpoint, dict):
        for field in _REQUIRED_IDENTITY_FIELDS:
            if endpoint.get(field) in (None, ""):
                return True
        return False
    # ModelEndpoint / dataclass: required fields are constructor-enforced.
    return False


class FilterStage(Stage):
    """Qualify endpoints for the catalog, dispatching by provider.

    Reads ``context.data["parsed"]`` (a dict ``{provider: [endpoints]}``),
    applies the per-provider qualify function (classify + keep all
    eligible), rejects malformed records, and writes the result to
    ``context.data["filtered"]``. Metrics are recorded under
    ``context.metrics["filter"]`` as::

        {
            "<provider>": {"in": N, "out": M, "dropped": N - M},
            ...
        }

    ``dropped`` counts malformed rejections only — paid/unknown endpoints
    are kept.
    """

    name = "filter"

    def execute(self, context: PipelineContext) -> PipelineContext:
        parsed = context.data.get("parsed", {}) or {}
        filtered: Dict[str, List[Any]] = {}
        metrics: Dict[str, Dict[str, int]] = {}

        for provider, endpoints in parsed.items():
            before = len(endpoints)
            kept: List[Any] = []
            dropped_malformed = 0
            for ep in endpoints:
                if _is_malformed(ep):
                    dropped_malformed += 1
                    logger.debug(
                        "filter[%s]: dropping malformed endpoint missing "
                        "identity field: %s",
                        provider,
                        getattr(ep, "get", lambda *_: None)("model_id")
                        if isinstance(ep, dict)
                        else ep,
                    )
                    continue
                kept.append(ep)
            # All eligible endpoints are kept; pricing_status is
            # computed later in the normalize stage.
            qualified = kept
            after = len(qualified)
            filtered[provider] = qualified
            metrics[provider] = {
                "in": before,
                "out": after,
                "dropped": before - after,
            }
            if before != after:
                logger.info(
                    "filter[%s]: kept %d / %d (dropped %d, malformed %d)",
                    provider,
                    after,
                    before,
                    before - after,
                    dropped_malformed,
                )

        context.data["filtered"] = filtered
        existing = context.metrics.get("filter", {})
        existing.update(metrics)
        context.metrics["filter"] = existing

        # Downstream stages read from ``endpoints`` (NormalizeStage) or
        # ``parsed`` (legacy code). Mirror the filtered result into
        # ``parsed`` too so NormalizeStage — which currently reads
        # ``parsed`` — sees the post-qualification data without a separate
        # code change.
        context.data["parsed"] = filtered

        return context


__all__ = ["FilterStage"]
