"""Per-provider free-model filters.

Each provider exposes its own rule for what counts as "free":

* **NVIDIA** — ``labels.nimType.values contains "Free Endpoint"``. Stamped
  into ``ModelEndpoint.free`` by :func:`data.providers.nvidia.parse_html`,
  so the filter is a simple ``ep.free == True`` check.
* **AMD** — ``model.token_factory.status.key == "free_endpoint"``. Stamped
  into the endpoint dict by
  :func:`data.providers.amd.build_endpoint_dict`. Filter checks
  ``ep["free"] == True``.
* **Hugging Face** — ``provider.pricing.input == 0 AND
  provider.pricing.output == 0 AND provider.status == "live"`` per
  provider within a model. The HF parser
  (:func:`data.providers.huggingface.parse_huggingface_models`) already
  applies this rule via ``filter_free_providers``; the filter stage here
  is a pass-through safety net that drops anything whose ``free`` flag
  was unset (defensive against future parse changes).

The three rules are intentionally **separate functions**, not a single
predicate: the rule shape itself differs (label set membership vs.
boolean field vs. multi-key provider tuple). Sharing one helper would
either conflate three concepts or force a least-common-denominator
abstraction that hides provider-specific semantics.

The :func:`filter_free` dispatcher routes by provider name. Add new
providers by registering them in :data:`PROVIDER_FREE_FILTERS`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from data.models.schema import ModelEndpoint


# ---------------------------------------------------------------------------
# Per-provider rules
# ---------------------------------------------------------------------------


def filter_nvidia_free(endpoints: List[ModelEndpoint]) -> List[ModelEndpoint]:
    """Drop NVIDIA endpoints whose ``free`` flag is False.

    The NVIDIA parser (:func:`data.providers.nvidia.parse_html` →
    :func:`data.providers.nvidia._normalize_model`) sets ``free=True`` when
    ``labels.nimType.values contains "Free Endpoint"``; everything else
    ("Run Anywhere" partner endpoints, etc.) is ``free=False``. This
    filter drops the non-free rows.
    """
    return [ep for ep in endpoints if ep.free]


def filter_amd_free(endpoints: List[dict]) -> List[dict]:
    """Drop AMD endpoints whose ``free`` flag is False.

    The AMD parser (:func:`data.providers.amd.build_endpoint_dict`)
    sets ``free=True`` when ``model.token_factory.status.key ==
    "free_endpoint"``. AMD's API also returns some ``status ==
    "paid"`` endpoints in the same bootstrap listing; this filter drops
    them.
    """
    return [ep for ep in endpoints if ep.get("free") is True]


def filter_huggingface_free(endpoints: List[dict]) -> List[dict]:
    """Pass-through for Hugging Face endpoints.

    The HF parser (:func:`data.providers.huggingface.parse_huggingface_models`)
    already enforces the HF free rule
    (``provider.pricing.input == 0 AND provider.pricing.output == 0
    AND provider.status == "live"``) via ``filter_free_providers`` —
    only free providers survive to ``to_endpoint_dicts``. The resulting
    endpoint dicts all have ``free=True``, so this filter is a no-op
    in practice. Kept as a uniform contract across providers and as a
    defensive guard if the parser is ever refactored.
    """
    return [ep for ep in endpoints if ep.get("free") is True]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


# Each provider's filter. New providers register here.
PROVIDER_FREE_FILTERS: Dict[str, Callable[[List[Any]], List[Any]]] = {
    "nvidia": filter_nvidia_free,
    "amd": filter_amd_free,
    "huggingface": filter_huggingface_free,
}


def filter_free(
    endpoints: List[Any],
    provider: str,
) -> List[Any]:
    """Dispatch to the right per-provider filter.

    Args:
        endpoints: parsed endpoints for this provider (may be a mix of
            ``ModelEndpoint`` and ``dict`` depending on provider).
        provider: provider key — must match an entry in
            :data:`PROVIDER_FREE_FILTERS`.

    Returns:
        The free subset of ``endpoints``. If the provider is unknown,
        returns ``endpoints`` unchanged (logged via a caller-visible
        metrics counter downstream).
    """
    fn = PROVIDER_FREE_FILTERS.get(provider)
    if fn is None:
        return endpoints
    return fn(endpoints)


__all__ = [
    "filter_nvidia_free",
    "filter_amd_free",
    "filter_huggingface_free",
    "filter_free",
    "PROVIDER_FREE_FILTERS",
]