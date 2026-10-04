"""NormalizeStage — convert provider-specific parsed output into ModelEndpoint.

NVIDIA provider already returns ``ModelEndpoint`` objects; this stage
passes them through unchanged. AMD/HF return raw ``dict`` shaped like
``{provider, model_id, free, ...}`` and are mapped via
``data.process.normalize.normalize_endpoints``.

Option A (docs/tfi_provenance_enrichment_architecture.md): before
normalizing each batch, this stage indexes the OpenRouter raw
observations (keyed by alias-normalized canonical model_id via the
identity matcher) so each endpoint's normalize pass can fuse its
primary source's signals with the matching OR signals. The result is
a single normalize pass per endpoint, so capabilities derived partly
from OR end up with ``method=native`` provenance at the enrich stage.

NVIDIA batches get the same treatment — OR signals still feed into
``architecture`` and ``capabilities`` for NVIDIA endpoints, applied
in-place via :func:`_apply_openrouter_signals_to_nvidia_endpoint`.
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

    The identity matcher's normalization (owner-alias + version-separator
    unification + slug fallback) is applied on the key side so callers
    can do a single ``index[ep.model_id]`` lookup regardless of how the
    primary source spells its id — e.g. NVIDIA ``z-ai/glm-5-3-flash``
    matches OR ``z-ai/glm-5.3-flash`` via the version-separator pass.

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


def _apply_openrouter_signals_to_nvidia_endpoint(
    ep: ModelEndpoint,
    or_obs: dict,
) -> ModelEndpoint:
    """Merge OpenRouter raw signals into a NVIDIA ModelEndpoint in-place.

    NVIDIA's provider constructs ``ModelEndpoint`` objects directly
    with ``architecture`` derived from labels (often empty input) and
    ``capabilities`` derived from the legacy ``attributes`` block
    (often empty for live RSC payloads). When a matching OR
    observation exists, we:

    * Union the input/output modality lists into ``architecture``.
    * Add capability keys OR exposes but NVIDIA doesn't (``vision``,
      ``speech``, ``embedding``, ``tool_calling``, ``reasoning``).
    * Surface the OR ``supported_parameters`` and
      ``reasoning.default_enabled`` signals the same way the AMD/HF
      path does.

    ``ModelEndpoint`` is a frozen dataclass, so we mutate via
    ``object.__setattr__`` and return the same instance.
    """
    or_arch = or_obs.get("architecture") if isinstance(or_obs.get("architecture"), dict) else {}
    or_input = list(or_arch.get("input") or []) if isinstance(or_arch.get("input"), list) else []
    or_output = list(or_arch.get("output") or []) if isinstance(or_arch.get("output"), list) else []
    or_meta = or_obs.get("metadata") if isinstance(or_obs.get("metadata"), dict) else {}
    or_params = or_meta.get("supported_parameters") if isinstance(or_meta.get("supported_parameters"), list) else []
    or_reasoning = or_meta.get("reasoning") if isinstance(or_meta.get("reasoning"), dict) else {}

    # --- architecture ---
    existing_input = list(ep.architecture.get("input") or []) if isinstance(ep.architecture, dict) else []
    existing_output = list(ep.architecture.get("output") or []) if isinstance(ep.architecture, dict) else []
    merged_input = list(dict.fromkeys([*existing_input, *or_input]))
    merged_output = list(dict.fromkeys([*existing_output, *or_output]))
    if merged_input or merged_output:
        object.__setattr__(
            ep,
            "architecture",
            {"input": merged_input, "output": merged_output},
        )

    # --- capabilities (additive, never subtract) ---
    caps = dict(ep.capabilities or {})

    if "image" in merged_input or "image" in merged_output:
        caps["vision"] = True
    if any(m in merged_output for m in ("audio",)):
        caps["speech"] = True
    if "embedding" in merged_output:
        caps["embedding"] = True
    # Chat is implied if NVIDIA already set it (legacy attributes or
    # the chat-modal label), but OR's text output also confirms it.
    if "text" in merged_output and "embedding" not in merged_output:
        caps["chat"] = True

    if not caps.get("tool_calling"):
        if "tools" in or_params or "tool_choice" in or_params:
            caps["tool_calling"] = True

    if not caps.get("reasoning"):
        if "reasoning" in or_params:
            caps["reasoning"] = True
        elif or_reasoning.get("mandatory") or or_reasoning.get("default_enabled"):
            caps["reasoning"] = True

    object.__setattr__(ep, "capabilities", caps)
    return ep


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
                # bypassing normalize_endpoints. We still need OR's
                # architecture + supported_parameters to feed the
                # canonical 7-key capabilities shape, so look up the
                # OR observation and merge in-place.
                for ep in items:
                    if not isinstance(ep, ModelEndpoint):
                        # Defensive: NVIDIA provider should always yield
                        # ModelEndpoint, but tolerate legacy list inputs.
                        continue
                    key = _normalize_id(ep.model_id)
                    or_obs = or_index.get(key)
                    if or_obs is not None:
                        _apply_openrouter_signals_to_nvidia_endpoint(ep, or_obs)
                    endpoints.append(ep)
                continue
            for ep in normalize_endpoints(items, cross_source_index=or_index):
                endpoints.append(ep)
        context.data["endpoints"] = endpoints
        return context
