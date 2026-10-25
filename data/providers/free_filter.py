"""Per-provider free-model filters.

Each provider exposes its own rule for what counts as "free":

* **NVIDIA** — ``labels.nimType.values contains "Free Endpoint"``. Stamped
  into ``ModelEndpoint.pricing_status="free"`` by
  :func:`data.providers.nvidia.parse_html`, so the filter checks
  ``ep.pricing_status == "free"``.
* **AMD** — ``model.token_factory.status.key == "free_endpoint"``. Stamped
  into the endpoint dict by
  :func:`data.providers.amd.build_endpoint_dict`. Filter checks
  ``ep["pricing_status"] == "free"``.
* **Hugging Face** — ``provider.pricing.input == 0 AND
  provider.pricing.output == 0 AND provider.status == "live"`` per
  provider within a model. The HF parser
  (:func:`data.providers.huggingface.parse_huggingface_models`) emits
  one endpoint per ``(model, provider)`` pair regardless of paid/free
  status, computing the ``pricing_status`` flag via the rule above.
  The filter drops endpoints where ``pricing_status != "free"``.

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
from data.providers.ollama import filter_ollama_free
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Per-provider rules
# ---------------------------------------------------------------------------


def filter_nvidia_free(endpoints: List[ModelEndpoint]) -> List[ModelEndpoint]:
    """Drop NVIDIA endpoints whose ``pricing_status`` is not "free".

    The NVIDIA parser (:func:`data.providers.nvidia.parse_html` →
    :func:`data.providers.nvidia._normalize_model`) sets
    ``pricing_status="free"`` when ``labels.nimType.values`` contains
    "Free Endpoint"; everything else ("Run Anywhere" partner endpoints,
    etc.) gets ``pricing_status="paid"`` or ``"unknown"``. This filter
    drops the non-free rows.
    """
    return [ep for ep in endpoints if ep.pricing_status == "free"]


def filter_amd_free(endpoints: List[dict]) -> List[dict]:
    """Drop AMD endpoints whose ``pricing_status`` is not "free".

    The AMD parser (:func:`data.providers.amd.build_endpoint_dict`)
    sets ``pricing_status="free"`` when
    ``model.token_factory.status.key == "free_endpoint"``. AMD's API
    also returns some ``status == "paid"`` endpoints in the same
    bootstrap listing; this filter drops them.
    """
    return [ep for ep in endpoints if ep.get("pricing_status") == "free"]


def filter_huggingface_free(endpoints: List[dict]) -> List[dict]:
    """Drop Hugging Face endpoints whose ``pricing_status`` is not "free".

    After the parse-side refactor (per-provider expansion of all
    HF router providers, regardless of paid/free status), every
    endpoint already has a correct ``pricing_status`` flag computed
    via the HF pricing rule. The filter just enforces that contract —
    any endpoint with ``pricing_status != "free"`` is dropped. (The HF
    parser expands one endpoint per ``(model, provider)`` pair; a
    single model can therefore yield multiple endpoints where some are
    free and some are paid. The filter keeps only the free ones.)
    """
    return [ep for ep in endpoints if ep.get("pricing_status") == "free"]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def filter_openrouter_free(endpoints: List[dict]) -> List[dict]:
    """Drop OpenRouter endpoints whose pricing contains non-zero values.

    The rule: a model is considered free when **every** value in its
    ``pricing`` dict is numerically zero (string "0", int 0, float 0.0,
    or numeric-zero strings like "0.000000000000").
    """
    from decimal import Decimal, InvalidOperation

    def _is_zero(v):
        try:
            return Decimal(str(v)) == 0
        except InvalidOperation:
            return False

    kept = []
    for ep in endpoints:
        pricing = ep.get("pricing")
        if not pricing:
            # No pricing field → cannot confirm as free
            continue
        if all(_is_zero(v) for v in pricing.values()):
            ep["pricing_status"] = "free"
            kept.append(ep)
    return kept


def filter_kilo_free(endpoints: List[dict]) -> List[dict]:
    """Drop Kilo endpoints whose pricing contains non-zero values.

    The rule: a model is considered free when **every** value in its
    ``pricing`` dict is numerically zero (string "0", int 0, float 0.0,
    or numeric-zero strings like "0.000000000000").
    """
    from decimal import Decimal, InvalidOperation

    def _is_zero(v):
        try:
            return Decimal(str(v)) == 0
        except InvalidOperation:
            return False

    kept = []
    for ep in endpoints:
        pricing = ep.get("pricing")
        if not pricing:
            # No pricing field → cannot confirm as free (per spec)
            continue
        if all(_is_zero(v) for v in pricing.values()):
            # Stamp free flag so downstream stages can use it
            ep["pricing_status"] = "free"
            kept.append(ep)
    return kept


def filter_ollama_free(endpoints: List[dict]) -> List[dict]:
    """Filter Ollama endpoints based on pricing_status."""
    return [ep for ep in endpoints if ep.get("pricing_status") == "free"]


# Each provider's filter. New providers register here.
PROVIDER_FREE_FILTERS: Dict[str, Callable[[List[Any]], List[Any]]] = {
    "nvidia": filter_nvidia_free,
    "amd": filter_amd_free,
    "huggingface": filter_huggingface_free,
    "kilo": filter_kilo_free,
    "openrouter": filter_openrouter_free,
    "ollama": filter_ollama_free,
}


def filter_free(
    endpoints: List[Any],
    provider: str,
) -> List[Any]:
    """Dispatch to the right per-provider filter.

    If no filter is registered for the provider, pass through unchanged
    (log a warning on first occurrence).
    """
    fn = PROVIDER_FREE_FILTERS.get(provider)
    if fn is None:
        # Log only once per unknown provider
        if not hasattr(filter_free, "_warned"):
            filter_free._warned = set()
        if provider not in filter_free._warned:
            filter_free._warned.add(provider)
            # Cannot log here without context; caller should handle
        return endpoints
    return fn(endpoints)


__all__ = [
    "filter_nvidia_free",
    "filter_amd_free",
    "filter_huggingface_free",
    "filter_openrouter_free",
    "filter_kilo_free",
    "filter_ollama_free",
    "filter_free",
    "PROVIDER_FREE_FILTERS",
]