"""Deterministic field-level conflict resolution for provenance.

Per docs/tfi_provenance_enrichment_architecture.md §12, conflict resolution
between competing field-level facts MUST be deterministic. The first-stage
rule is::

    native > trusted enrichment > inferred > derived

The resolver works in two modes:

  1. **Initial stamping** — when a provider first contributes a fact, the
     resolver decides whether the fact should be recorded at all (e.g. do
     NOT overwrite an existing native fact — Rule 1).

  2. **Conflict resolution** — when two facts compete for the same canonical
     field path, the resolver picks the higher-ranked one.

The ranking is a tuple ``(method_rank, source_rank, confidence, observed_at)``
where lower tuple values are preferred. ``method_rank`` is the primary key
(native = 0 wins over derived = 4); ``source_rank`` is the secondary key
when two providers contribute the same method (OpenRouter is treated as a
trusted enrichment source but NOT hard-coded to the highest rank); the
remaining keys break ties deterministically by freshness and confidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from data.models.schema import FieldProvenance

# Method precedence: lower rank = higher precedence.
METHOD_RANK: dict[str, int] = {
    "native": 0,
    "normalized": 1,
    "enriched": 2,
    "inferred": 3,
    "derived": 4,
}

# Source precedence — only used as a tie-breaker when two candidates have
# the same method. Lower rank wins. Sources not in this table get the
# default rank below.
SOURCE_RANK: dict[str, int] = {
    "nvidia": 0,
    "amd": 1,
    "huggingface": 2,
    "openrouter": 3,
    "models_dev": 4,
    "modelparams": 5,
    "provider_api": 6,
    "unknown": 99,
}

_DEFAULT_SOURCE_RANK = 50


def _rank(provenance: FieldProvenance) -> tuple:
    """Return a deterministic ranking tuple (lower wins)."""
    method_rank = METHOD_RANK.get(provenance.method, 99)
    source_rank = SOURCE_RANK.get(provenance.source, _DEFAULT_SOURCE_RANK)
    # Negative confidence: higher confidence wins.
    # Negative timestamp: more recent wins.
    return (
        method_rank,
        source_rank,
        -provenance.confidence,
        -provenance.observed_at.timestamp(),
    )


def resolve(
    existing: Optional[FieldProvenance],
    candidate: FieldProvenance,
) -> FieldProvenance:
    """Decide which provenance record wins for a single canonical field.

    Rule 1 (doc §11): native facts are never overwritten by enrichment.
    Rule 3 (doc §11): enrichment is ``method="enriched"`` or ``"inferred"``
                      — it can NEVER become ``native``.
    """
    if existing is None:
        return candidate
    return candidate if _rank(candidate) < _rank(existing) else existing


def should_overwrite(
    existing: Optional[FieldProvenance],
    candidate: FieldProvenance,
) -> bool:
    """Return True if ``candidate`` should replace ``existing`` for the same field."""
    if existing is None:
        return True
    return _rank(candidate) < _rank(existing)


def is_native(provenance: Optional[FieldProvenance]) -> bool:
    """True if the field is a native fact from its own provider."""
    return provenance is not None and provenance.method == "native"


__all__ = [
    "METHOD_RANK",
    "SOURCE_RANK",
    "resolve",
    "should_overwrite",
    "is_native",
]
