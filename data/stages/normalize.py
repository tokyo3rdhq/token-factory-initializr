"""NormalizeStage — convert provider-specific parsed output into ModelEndpoint.

NVIDIA provider already returns ``ModelEndpoint`` objects; this stage
passes them through unchanged. AMD/HF return raw ``dict`` shaped like
``{provider, model_id, free, ...}`` and are mapped via
``data.process.normalize.normalize_endpoints``.

Option A (docs/tfi_provenance_enrichment_architecture.md): before
normalizing each batch, this stage indexes the cross-source raw
observations (currently OpenRouter and models.dev — keyed by
alias-normalized canonical model_id via the identity matcher) so each
endpoint's normalize pass can fuse its primary source's signals with
the matching observations. The result is a single normalize pass per
endpoint, so capabilities derived partly from cross-source signals end
up with ``method=native`` provenance at the enrich stage.

NVIDIA batches get the same treatment — cross-source signals still
feed into ``architecture`` and ``capabilities`` for NVIDIA endpoints,
applied in-place via :func:`_apply_cross_source_signals_to_nvidia_endpoint`.
"""

from __future__ import annotations

import logging

from data.identity_matcher import DefaultIdentityMatcher, _normalize_id
from data.models.schema import ModelEndpoint
from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.normalize import normalize_endpoints

logger = logging.getLogger(__name__)


def _build_cross_source_index(
    *source_lists: list[dict],
) -> dict[str, list[dict]]:
    """Index cross-source raw observations by normalized canonical model_id.

    Accepts one or more observation lists (OpenRouter, models.dev, …)
    and merges them under the same normalized key. The matching
    identity-matcher's normalization (owner-alias + version-separator
    unification + slug fallback) is applied on the key side so callers
    can do a single ``index[ep.model_id]`` lookup regardless of how
    the primary source spells its id.

    Additionally, when an observation carries an OpenRouter
    ``metadata.hugging_face_id`` (the upstream HF id the OR entry
    points to), the observation is also indexed under that HF id's
    normalized form. This lets a HF endpoint whose id differs from OR's
    ``id`` — e.g. ``prism-ml/Ternary-Bonsai-2-27B-gguf`` (HF) ↔
    ``prism-ml/ternary-bonsai-2-27b`` (OR) with ``hugging_face_id``
    pointing back to the HF id — still hit via a single observation
    lookup rather than the slug-fallback path.

    When two observations from the same provider collide on the same
    normalized key, the first one wins. When two observations from
    *different* providers collide (e.g. OR ``z-ai/glm-5.3-flash`` and
    models.dev ``z-ai/glm-5-3-flash`` after version normalization), the
    lists are merged into one dict so downstream code can iterate
    ``observations[key]`` as a list of observations.

    Returns a ``{normalized_key: [obs1, obs2, ...]}`` mapping.
    """
    index: dict[str, list[dict]] = {}
    for source_list in source_lists:
        if not source_list:
            continue
        for obs in source_list:
            obs_id = obs.get("model_id") or obs.get("id") or ""
            if obs_id:
                key = _normalize_id(obs_id)
                if key:
                    index.setdefault(key, []).append(obs)
            # OR entries carry metadata.hugging_face_id, which is the
            # upstream HF id. Index the same observation under that
            # HF id too so HF endpoints can find it directly.
            or_meta = obs.get("metadata") if isinstance(obs.get("metadata"), dict) else {}
            hf_id = or_meta.get("hugging_face_id")
            if hf_id and isinstance(hf_id, str) and hf_id != obs_id:
                hf_key = _normalize_id(hf_id)
                if hf_key and hf_key not in index:
                    index.setdefault(hf_key, []).append(obs)
    return index


def _apply_cross_source_signals_to_nvidia_endpoint(
    ep: ModelEndpoint,
    observations: list[dict],
) -> ModelEndpoint:
    """Merge cross-source raw signals into a NVIDIA ModelEndpoint in-place.

    NVIDIA's provider constructs ``ModelEndpoint`` objects directly
    with ``architecture`` derived from labels (often empty input) and
    ``capabilities`` derived from the legacy ``attributes`` block
    (often empty for live RSC payloads). When matching cross-source
    observations exist (OpenRouter, models.dev), we:

    * Union the input/output modality lists across every observation
      into ``architecture``.
    * Add capability keys that any observation exposes but NVIDIA
      doesn't (``vision``, ``speech``, ``embedding``, ``tool_calling``,
      ``reasoning``).
    * Surface the OR ``reasoning.default_enabled`` structured signal
      the same way the AMD/HF path does.

    ``ModelEndpoint`` is a frozen dataclass, so we mutate via
    ``object.__setattr__`` and return the same instance.
    """
    # --- collect signals across all observations ---
    cs_input: list[str] = []
    cs_output: list[str] = []
    cs_params: list[str] = []
    or_reasoning_default_enabled = False
    or_reasoning_mandatory = False

    for obs in observations:
        or_arch = obs.get("architecture") if isinstance(obs.get("architecture"), dict) else {}
        if isinstance(or_arch.get("input"), list):
            cs_input.extend(m for m in or_arch["input"] if isinstance(m, str))
        if isinstance(or_arch.get("output"), list):
            cs_output.extend(m for m in or_arch["output"] if isinstance(m, str))

        or_meta = obs.get("metadata") if isinstance(obs.get("metadata"), dict) else {}
        params = or_meta.get("supported_parameters")
        if isinstance(params, list):
            cs_params.extend(p for p in params if isinstance(p, str))
        reasoning = or_meta.get("reasoning")
        if isinstance(reasoning, dict):
            if reasoning.get("default_enabled"):
                or_reasoning_default_enabled = True
            if reasoning.get("mandatory"):
                or_reasoning_mandatory = True

    # --- architecture ---
    existing_input = list(ep.architecture.get("input") or []) if isinstance(ep.architecture, dict) else []
    existing_output = list(ep.architecture.get("output") or []) if isinstance(ep.architecture, dict) else []
    merged_input = list(dict.fromkeys([*existing_input, *cs_input]))
    merged_output = list(dict.fromkeys([*existing_output, *cs_output]))
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
    # the chat-modal label), but cross-source text output also
    # confirms it.
    if "text" in merged_output and "embedding" not in merged_output:
        caps["chat"] = True

    if not caps.get("tool_calling"):
        if "tools" in cs_params or "tool_choice" in cs_params:
            caps["tool_calling"] = True

    if not caps.get("reasoning"):
        if "reasoning" in cs_params:
            caps["reasoning"] = True
        elif or_reasoning_default_enabled or or_reasoning_mandatory:
            caps["reasoning"] = True

    object.__setattr__(ep, "capabilities", caps)
    return ep


class NormalizeStage(Stage):
    """Normalize provider outputs into the canonical ModelEndpoint schema."""

    name = "normalize"

    def execute(self, context: PipelineContext) -> PipelineContext:
        parsed = context.data.get("parsed", {}) or {}
        or_models_raw: list[dict] = context.data.get("openrouter_models", []) or []
        md_models_raw: list[dict] = context.data.get("models_dev_models", []) or []
        # Pre-index cross-source observations once per run; lookup is
        # O(1). Multiple sources share the same key space because the
        # identity matcher normalizes owner aliases + version
        # separators + slug forms the same way for every provider.
        cross_index = _build_cross_source_index(or_models_raw, md_models_raw)
        if cross_index:
            logger.info(
                "NormalizeStage: indexed %d cross-source observations "
                "(OR=%d, models_dev=%d) → %d unique keys",
                len(or_models_raw) + len(md_models_raw),
                len(or_models_raw),
                len(md_models_raw),
                len(cross_index),
            )

        endpoints: list[ModelEndpoint] = []
        # Build a single matcher instance — repeated construction is
        # cheap but it also keeps the alias/version/quantization state
        # consistent across both the NVIDIA and AMD/HF lookup paths.
        from data.identity_matcher import DefaultIdentityMatcher

        matcher = DefaultIdentityMatcher()
        for provider, items in parsed.items():
            if provider == "nvidia":
                # NVIDIA provider yields ModelEndpoint objects directly,
                # bypassing normalize_endpoints. We still need
                # cross-source architecture + supported_parameters to
                # feed the canonical 7-key capabilities shape, so walk
                # the cross-source index via the matcher (token-subset
                # fallback) instead of a literal normalized-key dict
                # lookup — owner-prefixed NVIDIA ids like
                # ``nvidia/nemotron-3.5-lightning-30b-a3b`` only
                # collide with OR's shorter base slug via the matcher.
                for ep in items:
                    if not isinstance(ep, ModelEndpoint):
                        continue
                    best_observations: list[dict] = []
                    best_conf = 0.0
                    for observations in cross_index.values():
                        if not observations:
                            continue
                        for obs in observations:
                            obs_id = obs.get("model_id") or obs.get("id") or ""
                            if not obs_id:
                                continue
                            r = matcher.match(
                                ep.model_id,
                                [
                                    {
                                        "id": obs_id,
                                        "source": obs.get("data_source") or "unknown",
                                    }
                                ],
                            )
                            if r is not None and r.confidence > best_conf:
                                best_conf = r.confidence
                                best_observations = observations
                    if best_observations:
                        _apply_cross_source_signals_to_nvidia_endpoint(ep, best_observations)
                    endpoints.append(ep)
                continue
            # AMD/HF path goes through normalize_endpoints which
            # already accepts cross_source_index. The index is a
            # ``{normalized_id: [obs1, obs2, ...]}`` map — every
            # cross-source observation contributes its signals to
            # the single normalize pass for the matching endpoint.
            for ep in normalize_endpoints(
                items,
                cross_source_index=cross_index,
            ):
                endpoints.append(ep)
        context.data["endpoints"] = endpoints
        return context
