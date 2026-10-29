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


# Quantization / format suffixes that Hugging Face appends to its
# model ids but other providers (OpenRouter, models.dev) omit. Strip
# them so the canonical id space collapses e.g.
# ``prism-ml/Ternary-Bonsai-2-27B-gguf`` (HF) and
# ``prism-ml/ternary-bonsai-2-27b`` (OR / models.dev).
_QUANTIZATION_SUFFIXES = (
    "-gguf",
    "-gptq",
    "-awq",
    "-safetensors",
    "-int4",
    "-int8",
    "-fp16",
    "-bf16",
    "-fp8",
    "-bin",
    "-exl2",
)


def _strip_quantization_suffix(model_id: str) -> str:
    """Remove a trailing HF quantization / file-format suffix.

    Only strips when the suffix is present at the very end of the
    string and is preceded by ``-`` — never inside the slug. This is a
    best-effort pass; identifiers without a known suffix pass through
    unchanged.
    """
    lowered = model_id.lower()
    for suf in _QUANTIZATION_SUFFIXES:
        if lowered.endswith(suf):
            return model_id[: -len(suf)]
    return model_id


def _normalize_id(model_id: str) -> str:
    """Return a comparable normalized form of an identifier.

    Order matters:
      1. ``lower().strip()`` — case + whitespace.
      2. ``_strip_quantization_suffix`` — drop trailing
         ``-gguf``/``-awq``/etc. so HF ids match OR / models.dev ids
         for the same release.
      3. ``_normalize_version_separator`` — ``5.3`` → ``5-3`` etc.
         Run BEFORE the date-suffix strip so a trailing ``-20251022``
         is still recognised as a date.
      4. ``_strip_model_version`` — drop trailing ``-YYYYMMDD``.
      5. ``_normalize_owner`` — collapse owner aliases
         (``deepseek-ai`` → ``deepseek``).
    """
    lowered = model_id.lower().strip()
    quant_stripped = _strip_quantization_suffix(lowered)
    version_unified = _normalize_version_separator(quant_stripped)
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
    """Default matcher: exact + owner-aliased + family/slug + token-subset fallback.

    Strategy order (highest confidence first):
      1. Exact normalized match (canonical id == source id after
         normalization). confidence = 1.0
      2. Family/slug match (last segment matches after owner aliasing).
         confidence = 0.80
      3. Token-subset match — the slug tokens of one side are a subset
         of the slug tokens of the other side. Used when a HF id like
         ``prism-ml/Ternary-Bonsai-27B-gguf`` (slug ``ternary-bonsai-27b``)
         refers to the same model as an OR / models.dev id
         ``prism-ml/ternary-bonsai-2-27b`` (slug
         ``ternary-bonsai-2-27b``). Both have 3 tokens; one set is the
         other minus an inserted ``2``. confidence = 0.75 (lower than
         the slug-equal path because it's a weaker signal).
    """

    @staticmethod
    def _token_subset_slug_match(slug_a: str, slug_b: str) -> bool:
        """True iff the dash-separated tokens of ``slug_a`` are a subset of
        ``slug_b``'s tokens (or vice versa) AND the two slugs share at
        least one alphabetic token beyond pure numeric / size tokens.

        Pure numeric tokens like ``2``, ``27``, ``27b``, ``7b`` are
        ignored when comparing overlap because they're noisy (the same
        model often appears as ``27b`` in one id and ``2-27b`` in
        another). At least one alphabetic token must match.
        """
        import re

        def _tokens(slug: str) -> set[str]:
            return {t for t in re.split(r"[-_.]+", slug) if t}

        a = _tokens(slug_a)
        b = _tokens(slug_b)
        if not a or not b:
            return False
        # Drop pure-digit tokens and tokens that are only digits + a
        # single trailing letter (``27b``, ``7b`` etc.) — they're the
        # noisy bits that drift between "Bonsai-27B" and "Bonsai-2-27B".
        def _non_noisy(tokens: set[str]) -> set[str]:
            return {
                t
                for t in tokens
                if any(ch.isalpha() for ch in t)
                and not all(ch.isdigit() for ch in t.rstrip("bBmMkK"))
            }

        an = _non_noisy(a)
        bn = _non_noisy(b)
        if not (an & bn):
            return False
        return a.issubset(b) or b.issubset(a)

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
                continue

            # Token-subset fallback: HF often drops a version token
            # (e.g. ``Bonsai-2-27B`` → ``Bonsai-27B``). When the slugs
            # are otherwise identical aside from such an inserted token,
            # treat as a tentative match.
            if self._token_subset_slug_match(target_slug, obs_slug):
                # Confidence 0.75, lower than 0.80 slug-equal because
                # the token-subset heuristic is structurally weaker
                # (it could in principle match unrelated slugs that share
                # a few alphabetic tokens). Same confidence for either
                # subset direction (a ⊃ b vs b ⊃ a).
                tentative = MatchResult(
                    source=source,
                    source_id=source_id,
                    confidence=0.75,
                )
                if best is None or tentative.confidence > best.confidence:
                    best = tentative

        return best


__all__ = [
    "MatchResult",
    "ModelIdentityMatcher",
    "DefaultIdentityMatcher",
    "_normalize_id",
]
