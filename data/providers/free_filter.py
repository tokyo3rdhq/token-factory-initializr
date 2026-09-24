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
  (:func:`data.providers.huggingface.parse_huggingface_models`) emits
  one endpoint per ``(model, provider)`` pair regardless of paid/free
  status, computing the ``free`` flag via the rule above. The filter
  stage drops endpoints where ``free=False``.

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
    """Drop Hugging Face endpoints whose ``free`` flag is False.

    After the parse-side refactor (per-provider expansion of all
    HF router providers, regardless of paid/free status), every
    endpoint already has a correct ``free`` flag computed via the
    HF pricing rule. The filter just enforces that contract — any
    endpoint with ``free=False`` is dropped. (The HF parser
    expands one endpoint per ``(model, provider)`` pair; a single
    model can therefore yield multiple endpoints where some are
    free and some are paid. The filter keeps only the free ones.)
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