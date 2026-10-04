"""EnrichStage — populate field-level provenance via cross-source matching.

Per docs/tfi_provenance_enrichment_architecture.md §8-§12:

  1. Match canonical endpoints to cross-source observations by
     model_id (OpenRouter and models.dev currently).
  2. For each match, enrich ``description`` and ``context_length`` and
     stamp provenance (method=enriched, source=openrouter|models_dev).
  3. Stamp provenance for capabilities that derive (partly) from a
     cross-source observation.
  4. Never overwrite a native provenance stamp (Rule 1).

The observation shape is uniform across providers — see
:mod:`data.providers.openrouter` and :mod:`data.providers.models_dev`.
The enrich stage consumes ``context.data["openrouter_models"]`` and
``context.data["models_dev_models"]`` and treats each entry as a
``ModelIdentityMatcher`` observation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

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


def _source_label(obs: dict) -> str:
    """Return a stable provenance ``source`` label for an observation.

    Reads ``data_source`` first (always set by providers); falls back
    to ``provider`` for legacy inputs.
    """
    return obs.get("data_source") or obs.get("provider") or "unknown"


def _find_best_match(
    ep: ModelEndpoint,
    observations: Iterable[dict],
) -> tuple[dict | None, float]:
    """Return the highest-confidence identity match for an endpoint.

    Iterates the candidate observations once and keeps the best
    match. Returns ``(observation, confidence)`` — the confidence
    is the matcher's confidence (1.0 for exact, 0.8 for slug fallback).
    """
    matcher = DefaultIdentityMatcher()
    best_obs: dict | None = None
    best_conf = 0.0
    for m in observations:
        obs_id = m.get("model_id") or m.get("id") or ""
        if not obs_id:
            continue
        r = matcher.match(ep.model_id, [{"id": obs_id, "source": _source_label(m)}])
        if r is not None and r.confidence > best_conf:
            best_obs = m
            best_conf = r.confidence
    return best_obs, best_conf


def _apply_capability_provenance(
    ep: ModelEndpoint,
    obs: dict,
    obs_id: str,
    now: datetime,
    match_conf: float,
) -> ModelEndpoint:
    """Stamp provenance for capability keys that the observation informed.

    We don't know post-hoc which key came from the cross-source vs the
    primary source, so we conservatively stamp every capability that is
    True and that the observation declares a modality /
    supported_parameter for. These all get ``method=native`` (not
    ``enriched``) because the canonical normalize pass that produced the
    True already accepted the cross-source signal as part of the
    primary-source view per option A in the doc.
    """
    source = _source_label(obs)
    params = obs.get("metadata", {}).get("supported_parameters") if isinstance(obs.get("metadata"), dict) else None
    if not isinstance(params, list):
        params = []
    arch = obs.get("architecture") if isinstance(obs.get("architecture"), dict) else {}
    input_mods = arch.get("input") or []
    output_mods = arch.get("output") or []

    new_prov = dict(ep.provenance)
    source_field_map = {
        "chat": "architecture.output",
        "vision": "architecture.input",
        "speech": "architecture.input",
        "embedding": "architecture.output",
        "tool_calling": "supported_parameters",
        "reasoning": (
            "supported_parameters"
            if "reasoning" in params
            else "reasoning.default_enabled"
        ),
        "structured_output": "supported_parameters",
    }

    for key, source_field in source_field_map.items():
        if not ep.capabilities.get(key):
            continue
        prov_key = f"capabilities.{key}"
        existing = new_prov.get(prov_key)
        candidate = _make_provenance_record(
            source=source,
            source_id=obs_id,
            source_field=source_field,
            method="native",
            confidence=match_conf,
            observed_at=now,
        )
        if existing is None or should_overwrite(existing, candidate):
            new_prov[prov_key] = candidate

    return _make_endpoint(ep, {"provenance": new_prov})


def _apply_description_enrichment(
    ep: ModelEndpoint,
    obs: dict,
    obs_id: str,
    now: datetime,
    match_conf: float,
    source_label: str,
) -> tuple[ModelEndpoint, bool]:
    """Replace ``ep.description`` with the observation's value if eligible.

    Per doc §11 Rule 1, native facts are never overwritten. A non-null
    description with no explicit provenance is treated as inherited
    (often an upstream boilerplate like AMD's "Dynamic sglang-router
    service managed by Model Ops") and is therefore eligible for
    enrichment — the resolver still gates on the candidate's rank.

    Returns ``(new_ep, applied)`` where ``applied`` is True iff the
    description was replaced AND provenance was stamped.
    """
    desc_value = obs.get("description")
    if not desc_value:
        return ep, False
    candidate = _make_provenance_record(
        source=source_label,
        source_id=obs_id,
        source_field="description",
        method="enriched",
        confidence=0.99 * match_conf,
        observed_at=now,
    )
    existing = ep.provenance.get("description")
    if not should_overwrite(existing, candidate):
        return ep, False
    new_prov = dict(ep.provenance)
    new_prov["description"] = candidate
    return _make_endpoint(ep, {
        "description": desc_value,
        "provenance": new_prov,
    }), True


def _apply_context_length_enrichment(
    ep: ModelEndpoint,
    obs: dict,
    obs_id: str,
    now: datetime,
    match_conf: float,
    source_label: str,
) -> tuple[ModelEndpoint, bool]:
    """Set ``ep.context_length`` from the observation if eligible."""
    cl_value = obs.get("context_length")
    if not isinstance(cl_value, int) or cl_value <= 0:
        return ep, False
    candidate = _make_provenance_record(
        source=source_label,
        source_id=obs_id,
        source_field="context_length",
        method="enriched",
        confidence=0.95 * match_conf,
        observed_at=now,
    )
    existing = ep.provenance.get("context_length")
    if not should_overwrite(existing, candidate):
        return ep, False
    new_prov = dict(ep.provenance)
    new_prov["context_length"] = candidate
    return _make_endpoint(ep, {
        "context_length": cl_value,
        "provenance": new_prov,
    }), True


def _match_and_enrich(
    ep: ModelEndpoint,
    observations_by_source: dict[str, list[dict]],
) -> tuple[ModelEndpoint, list[dict]]:
    """Match an endpoint against every cross-source provider and enrich."""
    additions: list[dict] = []
    now = datetime.now(timezone.utc)

    for source_label, observations in observations_by_source.items():
        obs, match_conf = _find_best_match(ep, observations)
        if obs is None:
            continue
        obs_id = obs.get("model_id") or obs.get("id") or ""

        ep, applied = _apply_description_enrichment(
            ep, obs, obs_id, now, match_conf, source_label,
        )
        if applied:
            additions.append({"field": "description", "method": "enriched", "source": source_label})

        ep, applied = _apply_context_length_enrichment(
            ep, obs, obs_id, now, match_conf, source_label,
        )
        if applied:
            additions.append({"field": "context_length", "method": "enriched", "source": source_label})

        before_keys = set(ep.provenance.keys())
        ep = _apply_capability_provenance(ep, obs, obs_id, now, match_conf)
        for k in ep.provenance.keys() - before_keys:
            additions.append({"field": k, "method": "native", "source": source_label})

    return ep, additions


class EnrichStage(Stage):
    """Match endpoints against cross-source providers and populate provenance."""

    name = "enrich"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = list(context.data.get("valid", []))
        observations_by_source: dict[str, list[dict]] = {
            "openrouter": list(context.data.get("openrouter_models", []) or []),
            "models_dev": list(context.data.get("models_dev_models", []) or []),
        }

        enriched: list[ModelEndpoint] = []
        total_additions = 0
        match_count = 0

        for ep in endpoints:
            ep, additions = _match_and_enrich(ep, observations_by_source)
            if additions:
                match_count += 1
            total_additions += len(additions)
            enriched.append(ep)

        context.data["enriched"] = enriched
        context.artifacts["enrich_facts"] = {
            "total_endpoints": len(endpoints),
            "total_provenance_additions": total_additions,
            "openrouter_matches": len(observations_by_source["openrouter"]),
            "models_dev_matches": len(observations_by_source["models_dev"]),
            "endpoints_with_provenance": match_count,
        }
        logger.info(
            "EnrichStage: %d endpoints, %d with provenance (%d total additions)",
            len(endpoints),
            match_count,
            total_additions,
        )
        return context
