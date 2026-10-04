"""Match canonical model identifiers across data sources.

Different providers use different ID formats for the same underlying model:

  NVIDIA: deepseek-ai/deepseek-v4.1-flash
  AMD:           MiMo-V2.6-Flash
  HuggingFace:   deepseek-ai/DeepSeek-V3
  OpenRouter:    deepseek/deepseek-v4.1-flash

This module provides :class:`ModelIdentityMatcher` which matches a canonical
endpoint to a list of source observations and returns a :class:`MatchResult`
containing source_id and confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class MatchResult:
    """A single identity match between a canonical model and a source observation."""

    source: str
    source_id: str
    confidence: float


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

# Known owner aliases for cross-source matching.
_OWNER_ALIASES: dict[str, str] = {
    "deepseek-ai": "deepseek",
    "meta-llama": "meta",
}


def _normalize_owner(model_id: str) -> str:
    """Apply owner aliases so ``deepseek-ai/...`` and ``deepseek/...`` match."""
    for src, dst in _OWNER_ALIASES.items():
        if model_id.startswith(src + "/"):
            return dst + "/" + model_id[len(src) + 1:]
    return model_id


def _strip_model_version(model_id: str) -> str:
    """Strip common version suffixes like ``-20251022`` from a model id."""
    return re.sub(r"-\d{8}$", "", model_id)


def _normalize_version_separator(model_id: str) -> str:
    """Unify version-number separators.

    OpenRouter spells minor versions with a dot (``glm-5.3``) while
    NVIDIA spells the same model with a dash (``glm-5-3``). Without
    normalization these never collide even though they refer to the
    same release.

    This pass only rewrites ``<digit><sep><digit>`` patterns — i.e.
    sequences that look like version numbers. It does not touch
    dashes elsewhere in the slug, so ``qwen3-vl-plus`` stays put.
    """

    def _replace(match: re.Match[str]) -> str:
        return match.group(1) + "-" + match.group(2)

    return re.sub(r"(\d)[._](\d)", _replace, model_id)


def _normalize_id(model_id: str) -> str:
    """Return a comparable normalized form of an identifier.

    Order matters:
      1. ``lower().strip()`` — case + whitespace.
      2. ``_normalize_version_separator`` — ``5.3`` → ``5-3`` etc.
         Run BEFORE the date-suffix strip so a trailing ``-20251022``
         is still recognised as a date.
      3. ``_strip_model_version`` — drop trailing ``-YYYYMMDD``.
      4. ``_normalize_owner`` — collapse owner aliases
         (``deepseek-ai`` → ``deepseek``).
    """
    lowered = model_id.lower().strip()
    version_unified = _normalize_version_separator(lowered)
    return _normalize_owner(_strip_model_version(version_unified))


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


class ModelIdentityMatcher(Protocol):
    """Strategy interface for matching canonical models to source observations."""

    def match(
        self,
        canonical_model_id: str,
        source_observations: Iterable[dict],
    ) -> MatchResult | None:
        """Return the best match for ``canonical_model_id`` or ``None``."""
        ...


class DefaultIdentityMatcher:
    """Default matcher: exact normalized + owner-aliased + family/slug fallback.

    Strategy order (highest confidence first):
      1. Exact normalized match (canonical id == source id after normalization).
         confidence = 1.0
      2. Family/slug match (last segment matches after owner aliasing).
         confidence = 0.80
    """

    def match(
        self,
        canonical_model_id: str,
        source_observations: Iterable[dict],
    ) -> MatchResult | None:
        target = _normalize_id(canonical_model_id)
        target_slug = target.split("/")[-1] if "/" in target else target

        best: MatchResult | None = None
        for obs in source_observations:
            source = obs.get("source") or obs.get("data_source") or "unknown"
            source_id = obs.get("id") or obs.get("model_id") or ""
            if not source_id:
                continue

            normalized = _normalize_id(source_id)
            if normalized == target:
                return MatchResult(source=source, source_id=source_id, confidence=1.0)

            obs_slug = normalized.split("/")[-1] if "/" in normalized else normalized
            if obs_slug == target_slug:
                if best is None:
                    best = MatchResult(
                        source=source,
                        source_id=source_id,
                        confidence=0.80,
                    )

        return best


__all__ = [
    "MatchResult",
    "ModelIdentityMatcher",
    "DefaultIdentityMatcher",
    "_normalize_id",
]
