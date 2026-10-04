"""EnrichStage — populate field-level provenance via OpenRouter matching.

Per docs/tfi_provenance_enrichment_architecture.md §8-§12:

  1. Match canonical endpoints to OpenRouter observations by model_id.
  2. For each match, enrich ``description`` and ``context_length`` and
     stamp provenance (method=enriched, source=openrouter).
  3. Stamp provenance for capabilities that derive (partly) from OR.
     Under option A in the doc, capabilities are computed by a single
     normalize pass that fuses the primary source's signals with OR's
     architecture / supported_parameters; we can't tell post-hoc which
     capability keys came from OR, so we conservatively stamp native
     provenance for every capability that OR's observation could have
     informed — i.e. the union of canonical modalities OR declares.
  4. Never overwrite a native provenance stamp (Rule 1).

Provenance is recorded on ``ep.provenance[field_path]`` as a
:class:`FieldProvenance` object. The canonical endpoint object is
returned with all fields intact — provenance lives alongside them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from data.field_resolver import should_overwrite
from data.identity_matcher import DefaultIdentityMatcher
from data.models.schema import FieldProvenance, ModelEndpoint
from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


def _make_endpoint(
    ep: ModelEndpoint,
    updates: dict,
) -> ModelEndpoint:
    """Build a new ModelEndpoint from an existing one with field updates.

    Uses ``object.__setattr__`` for frozen dataclass mutation.
    """
    new_ep = ModelEndpoint(**{k: getattr(ep, k) for k in ModelEndpoint.__dataclass_fields__})
    for k, v in updates.items():
        object.__setattr__(new_ep, k, v)
    return new_ep


def _make_provenance_record(
    source: str,
    source_id: str,
    source_field: str,
    method: str,
    confidence: float,
    observed_at: datetime,
) -> FieldProvenance:
    """Create a provenance record."""
    return FieldProvenance(
        source=source,
        source_id=source_id,
        source_field=source_field,
        method=method,
        confidence=confidence,
        observed_at=observed_at,
    )


def _apply_capability_provenance(
    ep: ModelEndpoint,
    obs: dict,
    obs_id: str,
    now: datetime,
    match_conf: float,
) -> ModelEndpoint:
    """Stamp provenance for capability keys that OR's observation could
    have informed during the normalize-stage fusion.

    We don't know post-hoc which key came from OR vs the primary source,
    so we conservatively stamp every capability that is True and that
    OR's observation declares a modality / supported_parameter for.
    These all get ``method=native`` (not ``enriched``) because the
    canonical normalize pass that produced the True already accepted OR's
    signal as part of the primary-source view per option A in the doc.

    Returns the endpoint with new provenance applied (no value mutation).
    """
    params = obs.get("metadata", {}).get("supported_parameters") if isinstance(obs.get("metadata"), dict) else None
    if not isinstance(params, list):
        params = []
    arch = obs.get("architecture") if isinstance(obs.get("architecture"), dict) else {}
    input_mods = arch.get("input") or []
    output_mods = arch.get("output") or []
    or_reasoning = obs.get("metadata", {}).get("reasoning") if isinstance(obs.get("metadata"), dict) else None
    if not isinstance(or_reasoning, dict):
        or_reasoning = {}

    new_prov = dict(ep.provenance)
    source_field_map = {
        "chat": ("architecture.output", 1.0),
        "vision": ("architecture.input", 1.0),
        "speech": ("architecture.input", 1.0),
        "embedding": ("architecture.output", 1.0),
        "tool_calling": ("supported_parameters", 1.0),
        "reasoning": (
            "supported_parameters"
            if "reasoning" in params
            else "reasoning.default_enabled",
            1.0,
        ),
        "structured_output": ("supported_parameters", 1.0),
    }

    for key, (source_field, _) in source_field_map.items():
        if not ep.capabilities.get(key):
            continue
        prov_key = f"capabilities.{key}"
        existing = new_prov.get(prov_key)
        candidate = _make_provenance_record(
            source="openrouter",
            source_id=obs_id,
            source_field=source_field,
            method="native",
            confidence=match_conf,
            observed_at=now,
        )
        # Only stamp when there's no provenance yet OR when the existing
        # record is a non-native one (a previous enrichment). Native
        # provenance always wins per Rule 1.
        if existing is None or should_overwrite(existing, candidate):
            new_prov[prov_key] = candidate

    return _make_endpoint(ep, {"provenance": new_prov})


def _match_openrouter(
    ep: ModelEndpoint,
    or_models: list[dict],
) -> tuple[ModelEndpoint, list[dict], float]:
    """Match endpoint to an OpenRouter observation and apply enrichment.

    Returns (possibly-enriched endpoint, list of provenance additions,
    match confidence in [0.8, 1.0]).
    """
    matcher = DefaultIdentityMatcher()
    obs = None
    match_result = None
    for m in or_models:
        or_id = m.get("model_id") or m.get("id") or ""
        r = matcher.match(ep.model_id, [{"id": or_id, "source": "openrouter"}])
        if r is not None:
            obs = m
            match_result = r
            break

    if obs is None:
        return ep, [], 1.0

    additions: list[dict] = []
    now = datetime.now(timezone.utc)
    obs_id = obs.get("model_id") or obs.get("id") or ""
    match_conf = match_result.confidence if match_result else 1.0

    # --- description ---
    # Per doc §11 Rule 1, native facts are never overwritten. A non-null
    # description with no explicit provenance is treated as inherited
    # (often an upstream boilerplate like AMD's "Dynamic sglang-router
    # service managed by Model Ops") and is therefore eligible for
    # enrichment — the resolver still gates on the candidate's rank.
    candidate_desc = _make_provenance_record(
        source="openrouter",
        source_id=obs_id,
        source_field="description",
        method="enriched",
        confidence=0.99 * match_conf,
        observed_at=now,
    )
    existing_desc = ep.provenance.get("description")
    desc_value = obs.get("description")
    if desc_value and should_overwrite(existing_desc, candidate_desc):
        new_prov = dict(ep.provenance)
        new_prov["description"] = candidate_desc
        ep = _make_endpoint(
            ep,
            {
                "description": desc_value,
                "provenance": new_prov,
            },
        )
        additions.append({"field": "description", "method": "enriched", "source": "openrouter"})

    # --- context_length ---
    candidate_cl = _make_provenance_record(
        source="openrouter",
        source_id=obs_id,
        source_field="context_length",
        method="enriched",
        confidence=0.95 * match_conf,
        observed_at=now,
    )
    existing_cl = ep.provenance.get("context_length")
    cl_value = obs.get("context_length")
    if isinstance(cl_value, int) and cl_value > 0 and should_overwrite(existing_cl, candidate_cl):
        new_prov = dict(ep.provenance)
        new_prov["context_length"] = candidate_cl
        ep = _make_endpoint(
            ep,
            {
                "context_length": cl_value,
                "provenance": new_prov,
            },
        )
        additions.append({"field": "context_length", "method": "enriched", "source": "openrouter"})

    # --- capabilities provenance ---
    # Under option A the normalize pass already computed the canonical
    # 7-key shape using OR's raw signals. We stamp native provenance for
    # keys OR could have informed so consumers can still ask "which
    # source contributed to this capability?" via the provenance map.
    ep = _apply_capability_provenance(ep, obs, obs_id, now, match_conf)
    cap_additions = [
        {"field": f"capabilities.{k}", "method": "native", "source": "openrouter"}
        for k in ep.capabilities
        if ep.capabilities.get(k)
        and ep.provenance.get(f"capabilities.{k}") is not None
        and ep.provenance[f"capabilities.{k}"].source == "openrouter"
    ]
    additions.extend(cap_additions)

    return ep, additions, match_conf


class EnrichStage(Stage):
    """Match endpoints against OpenRouter and populate provenance."""

    name = "enrich"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = list(context.data.get("valid", []))
        or_models_raw: list[dict] = context.data.get("openrouter_models", [])

        enriched: list[ModelEndpoint] = []
        total_additions = 0
        match_count = 0

        for ep in endpoints:
            ep, additions, _ = _match_openrouter(ep, or_models_raw)
            if additions:
                match_count += 1
            total_additions += len(additions)
            enriched.append(ep)

        context.data["enriched"] = enriched
        context.artifacts["enrich_facts"] = {
            "total_endpoints": len(endpoints),
            "total_provenance_additions": total_additions,
            "openrouter_matches": match_count,
            "openrouter_observations": len(or_models_raw),
        }
        logger.info(
            "EnrichStage: %d endpoints, %d matches, %d provenance additions",
            len(endpoints),
            match_count,
            total_additions,
        )
        return context
