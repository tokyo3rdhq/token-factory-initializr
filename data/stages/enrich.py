"""EnrichStage — populate field-level provenance via OpenRouter matching.

Per docs/tfi_provenance_enrichment_architecture.md §8-§12:

  1. Fetch OpenRouter models (now a first-class provider)
  2. Match canonical endpoints to OpenRouter observations by model_id
  3. For each match, enrich missing fields and record provenance
  4. Never overwrite native fields (Rule 1)
  5. Empty fields are eligible for enrichment (Rule 2)

Provenance is recorded on ``ep.provenance[field_path]`` as a
:class:`FieldProvenance` object. The canonical endpoint object is
returned with all fields intact — provenance lives alongside them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from data.identity_matcher import DefaultIdentityMatcher
from data.field_resolver import should_overwrite
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


def _match_openrouter(
    ep: ModelEndpoint,
    or_models: list[dict],
) -> tuple[ModelEndpoint, list[dict]]:
    """Match endpoint to an OpenRouter observation and apply enrichment.

    Matching delegates to :class:`DefaultIdentityMatcher` so the same
    owner-alias + slug-fallback rules used elsewhere in the pipeline
    apply (e.g. AMD ``MiMo-V2.6-Flash`` → OR ``xiaomi/mimo-v2.6-flash``).
    """
    from data.identity_matcher import DefaultIdentityMatcher

    matcher = DefaultIdentityMatcher()
    obs = None
    match_result = None
    for m in or_models:
        # OpenRouter provider normalizes the raw "id" to "model_id".
        or_id = m.get("model_id") or m.get("id") or ""
        r = matcher.match(ep.model_id, [{"id": or_id, "source": "openrouter"}])
        if r is not None:
            obs = m
            match_result = r
            break

    if obs is None:
        return ep, []

    additions: list[dict] = []
    now = datetime.now(timezone.utc)
    obs_id = obs.get("model_id") or obs.get("id") or ""

    # --- description ---
    # Slug-fallback matches (confidence 0.8) carry more identity uncertainty
    # than exact matches (1.0); lower the recorded confidence proportionally
    # so consumers can tell which enrichments are tentative.
    match_conf = match_result.confidence if match_result else 1.0
    candidate_desc = _make_provenance_record(
        source="openrouter",
        source_id=obs_id,
        source_field="description",
        method="enriched",
        confidence=0.99 * match_conf,
        observed_at=now,
    )
    existing_desc = ep.provenance.get("description")

    # Per doc §11 Rule 1, native facts are never overwritten. A non-null
    # description with no explicit provenance is treated as inherited
    # (often an upstream boilerplate like AMD's "Dynamic sglang-router
    # service managed by Model Ops") and is therefore eligible for
    # enrichment — the resolver still gates on the candidate's rank.
    desc_value = obs.get("description")
    if desc_value and should_overwrite(existing_desc, candidate_desc):
        new_prov = dict(ep.provenance)
        new_prov["description"] = candidate_desc
        ep = _make_endpoint(ep, {
            "description": desc_value,
            "provenance": new_prov,
        })
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
        ep = _make_endpoint(ep, {
            "context_length": cl_value,
            "provenance": new_prov,
        })
        additions.append({"field": "context_length", "method": "enriched", "source": "openrouter"})

    return ep, additions


def _enrich_capabilities(
    ep: ModelEndpoint,
    obs: dict,
    match_conf: float = 1.0,
) -> tuple[ModelEndpoint, list[dict]]:
    """Enrich capabilities from OpenRouter data if missing.

    Each capability key gets its own FieldProvenance record so conflict
    resolution can be applied per-key (doc §12).

    ``match_conf`` scales the recorded confidence for slug-fallback
    identity matches (typically 0.8) so consumers can tell which
    capabilities were inferred from a tentative identity match.
    """
    additions: list[dict] = []
    now = datetime.now(timezone.utc)
    obs_id = obs.get("model_id") or obs.get("id") or ""

    arch = obs.get("architecture") or {}
    params = obs.get("supported_parameters") or []
    input_mods = set(arch.get("input") or arch.get("input_modalities") or [])
    output_mods = set(arch.get("output") or arch.get("output_modalities") or [])

    signals: dict[str, tuple[bool, str, str]] = {
        # key:               (value_predicate, source_field, method)
        "vision":            ("image" in input_mods or "image" in output_mods,
                              "architecture.input_modalities", "inferred"),
        "speech":            ("audio" in input_mods or "audio" in output_mods,
                              "architecture.input_modalities", "inferred"),
        "embedding":         ("embedding" in output_mods,
                              "architecture.output_modalities", "inferred"),
        "chat":              ("text" in output_mods,
                              "architecture.output_modalities", "inferred"),
        "tool_calling":      ("tools" in params or "tool_choice" in params,
                              "supported_parameters", "enriched"),
        "reasoning":         (
            "reasoning" in params
            or (obs.get("reasoning") or {}).get("default_enabled", False),
            "supported_parameters" if "reasoning" in params else "reasoning",
            "enriched",
        ),
    }

    merged = dict(ep.capabilities)
    changed = False
    new_prov = dict(ep.provenance)

    for k, (v, source_field, method) in signals.items():
        if not v:
            continue
        candidate = _make_provenance_record(
            source="openrouter",
            source_id=obs_id,
            source_field=source_field,
            method=method,
            confidence=(0.85 if method == "inferred" else 0.95) * match_conf,
            observed_at=now,
        )
        existing = new_prov.get(f"capabilities.{k}")
        if (k not in merged or not merged[k]) and should_overwrite(existing, candidate):
            merged[k] = v
            new_prov[f"capabilities.{k}"] = candidate
            changed = True

    if changed:
        ep = _make_endpoint(ep, {
            "capabilities": merged,
            "provenance": new_prov,
        })
        additions.append({"field": "capabilities.*", "method": "inferred", "source": "openrouter"})

    return ep, additions


class EnrichStage(Stage):
    """Match endpoints against OpenRouter and populate provenance."""

    name = "enrich"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = list(context.data.get("valid", []))
        or_models_raw: list[dict] = context.data.get("openrouter_models", [])

        from data.identity_matcher import DefaultIdentityMatcher

        matcher = DefaultIdentityMatcher()
        enriched: list[ModelEndpoint] = []
        total_additions = 0
        match_count = 0

        for ep in endpoints:
            # Find best OR observation for this endpoint via the canonical
            # matcher (owner aliases + slug fallback).
            obs = None
            obs_conf = 1.0
            for m in or_models_raw:
                or_id = m.get("model_id") or m.get("id") or ""
                r = matcher.match(
                    ep.model_id, [{"id": or_id, "source": "openrouter"}],
                )
                if r is not None:
                    obs = m
                    obs_conf = r.confidence
                    match_count += 1
                    break

            ep, additions = _match_openrouter(ep, or_models_raw)
            if obs is not None and additions:
                ep, cap_additions = _enrich_capabilities(ep, obs, obs_conf)
                total_additions += len(additions) + len(cap_additions)
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