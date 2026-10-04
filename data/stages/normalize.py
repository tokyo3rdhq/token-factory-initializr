"""NormalizeStage — convert provider-specific parsed output into ModelEndpoint.

NVIDIA provider already returns ``ModelEndpoint`` objects; this stage
passes them through unchanged. AMD/HF return raw ``dict`` shaped like
``{provider, model_id, free, ...}`` and are mapped via
``data.process.normalize.normalize_endpoints``.

Option A (docs/tfi_provenance_enrichment_architecture.md): before
normalizing each non-NVIDIA batch, this stage indexes the OpenRouter
raw observations (keyed by canonical model_id via the identity matcher)
so each endpoint's normalize pass can fuse its primary source's
signals with the matching OR signals. The result is a single
normalize pass per endpoint, so capabilities derived partly from OR
end up with ``method=native`` provenance at the enrich stage.
"""

from __future__ import annotations

import logging

from data.identity_matcher import DefaultIdentityMatcher, _normalize_id
from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.normalize import normalize_endpoints

logger = logging.getLogger(__name__)


def _build_openrouter_index(
    or_models: list[dict],
) -> dict[str, dict]:
    """Index OpenRouter raw observations by normalized canonical model_id.

    The identity matcher's normalization (owner-alias + slug fallback)
    is applied on the key side so callers can do a single
    ``index[ep.model_id]`` lookup regardless of how the primary source
    spells its id (e.g. NVIDIA ``deepseek-ai/deepseek-v4.1-flash``
    matches OR ``deepseek/deepseek-v4.1-flash`` via the alias table).

    When two OR observations collide on the same normalized key, the
    first one wins (deterministic for a given fetch); collisions are
    rare because OR's own id space is unique.
    """
    index: dict[str, dict] = {}
    for obs in or_models:
        or_id = obs.get("model_id") or obs.get("id") or ""
        if not or_id:
            continue
        key = _normalize_id(or_id)
        if key and key not in index:
            index[key] = obs
    return index


class NormalizeStage(Stage):
    """Normalize provider outputs into the canonical ModelEndpoint schema."""

    name = "normalize"

    def execute(self, context: PipelineContext) -> PipelineContext:
        parsed = context.data.get("parsed", {}) or {}
        or_models_raw: list[dict] = context.data.get("openrouter_models", []) or []
        # Pre-index OR observations once per run; lookup is O(1).
        or_index = _build_openrouter_index(or_models_raw)
        if or_index:
            logger.info(
                "NormalizeStage: indexed %d OpenRouter observations for cross-source normalization",
                len(or_index),
            )

        endpoints: list[ModelEndpoint] = []
        for provider, items in parsed.items():
            if provider == "nvidia":
                # NVIDIA provider yields ModelEndpoint objects directly,
                # bypassing normalize_endpoints. We still want OR's
                # architecture to inform NVIDIA's normalize-stage output
                # when present — but the existing ``ModelEndpoint`` route
                # already preserves whatever raw_modalities NVIDIA
                # carried. Re-running normalize_capabilities here would
                # require re-lifting architecture onto the frozen
                # dataclass; out of scope for option A's first pass.
                endpoints.extend(items)
                continue
            for ep in normalize_endpoints(items, cross_source_index=or_index):
                endpoints.append(ep)
        context.data["endpoints"] = endpoints
        return context
