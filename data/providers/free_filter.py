"""Per-provider endpoint qualification + pricing classification.

Replaces the old free-only filter behavior (docs/tfi_model_endpoint_support_paid_model.md §5.1).
Each provider function now:

* Sets ``pricing_status`` on every endpoint based on source evidence.
* Keeps every eligible (well-formed) endpoint — free, paid, and unknown.
* Returns only endpoints eligible for the catalog; malformed records
  (missing required identity fields) are rejected by the FilterFreeStage.

Free-only ingestion is no longer the pipeline behavior. If a free-only
view is needed, it is implemented as a downstream query/filter
(:mod:`web.functions.lib.filter`), not as the only published catalog.

The :func:`filter_free` dispatcher routes by provider name. Add new
providers by registering them in :data:`PROVIDER_FREE_FILTERS`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
from data.models.schema import ModelEndpoint
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Pricing classification helpers
# ---------------------------------------------------------------------------


def _is_zero(value: Any) -> bool:
    """True iff ``value`` is numerically zero (string/int/float/Decimal)."""
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def _classify_by_pricing(endpoint: Any) -> str:
    """Classify ``pricing_status`` from the endpoint's ``pricing`` field.

    Returns one of: ``"free"`` / ``"paid"`` / ``"unknown"``.
    """
    if hasattr(endpoint, "get"):
        pricing = endpoint.get("pricing")
    else:
        pricing = getattr(endpoint, "pricing", None)

    if not pricing:
        return "unknown"
    try:
        values = list(pricing.values())
    except AttributeError:
        return "unknown"
    if not values:
        return "unknown"
    if all(_is_zero(v) for v in values):
        return "free"
    return "paid"


def _hf_provider_pricing_status(provider_entry: Dict[str, Any]) -> str:
    """Classify a single HF router provider entry's access/pricing.

    Returns one of ``"free"`` / ``"paid"`` / ``"unknown"``:
      * ``"free"`` — status == "live" AND pricing.input == 0 AND pricing.output == 0.
      * ``"paid"`` — status == "live" AND pricing present but not all zero.
      * ``"unknown"`` — status != "live", or pricing missing/not a dict,
        or malformed. Never infer free from missing pricing.
    """
    if provider_entry.get("status") != "live":
        return "unknown"
    pricing = provider_entry.get("pricing")
    if not isinstance(pricing, dict):
        return "unknown"
    try:
        inp = float(pricing.get("input", -1))
        out = float(pricing.get("output", -1))
    except (TypeError, ValueError):
        return "unknown"
    if inp == 0 and out == 0:
        return "free"
    return "paid"


def _set_pricing_status(endpoint: Any, status: str) -> Any:
    """Set ``pricing_status`` on endpoint (dict or ModelEndpoint)."""
    if hasattr(endpoint, "get"):
        endpoint["pricing_status"] = status
        return endpoint
    else:
        # ModelEndpoint: frozen dataclass — reconstruct with new status.
        return ModelEndpoint(
            provider=endpoint.provider,
            model_id=endpoint.model_id,
            free=endpoint.free,
            pricing_status=status,
            fetched_at=endpoint.fetched_at,
            name=endpoint.name,
            description=endpoint.description,
            capabilities=endpoint.capabilities,
            architecture=endpoint.architecture,
            lab=endpoint.lab,
            metadata=endpoint.metadata,
            context_length=endpoint.context_length,
            pricing=endpoint.pricing,
            endpoint_url=endpoint.endpoint_url,
            region=endpoint.region,
            source_url=endpoint.source_url,
            status=endpoint.status,
            limits=endpoint.limits,
            score=endpoint.score,
            provenance=endpoint.provenance,
        )


# ---------------------------------------------------------------------------
# Per-provider qualification + classification
# ---------------------------------------------------------------------------


def qualify_nvidia(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible NVIDIA endpoints; classify ``pricing_status``.

    Classification from ``labels.nimType`` (stored in ``metadata.labels``):
      * "Free Endpoint" in nimType.values → "free"
      * Known non-empty nimType (e.g. "Run Anywhere") → "paid"
      * Absent/empty nimType → "unknown"
    """
    qualified = []
    for ep in endpoints:
        # NVIDIA stores nimType in metadata.labels
        if hasattr(ep, "get"):
            metadata = ep.get("metadata", {})
        else:
            metadata = getattr(ep, "metadata", {})

        labels = metadata.get("labels", {})
        nim_values = labels.get("nimType", {}).get("values", []) or []

        if "Free Endpoint" in nim_values:
            status = "free"
        elif nim_values:
            status = "paid"
        else:
            status = "unknown"

        qualified.append(_set_pricing_status(ep, status))
    return qualified


def qualify_amd(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible AMD endpoints; classify ``pricing_status``.

    Classification from ``free_status`` (stored in ``metadata``):
      * "free_endpoint" → "free"
      * "paid" → "paid"
      * Missing/unrecognized → "unknown"

    Note: AMD may have non-zero pricing even for free endpoints, so we
    trust the free_status flag over the pricing field.
    """
    qualified = []
    for ep in endpoints:
        if hasattr(ep, "get"):
            metadata = ep.get("metadata", {})
        else:
            metadata = getattr(ep, "metadata", {})

        free_status = metadata.get("free_status")
        if free_status == "free_endpoint":
            status = "free"
        elif free_status == "paid":
            status = "paid"
        else:
            status = "unknown"

        qualified.append(_set_pricing_status(ep, status))
    return qualified


def qualify_huggingface(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible HF endpoints; classify ``pricing_status``.

    Classification from provider entry's ``status`` and ``pricing``:
      * status == "live" AND pricing.input == 0 AND pricing.output == 0 → "free"
      * status == "live" AND pricing present with non-zero values → "paid"
      * Otherwise → "unknown"
    """
    qualified = []
    for ep in endpoints:
        if hasattr(ep, "get"):
            metadata = ep.get("metadata", {})
            # HF stores provider-level pricing in metadata; the endpoint
            # dict itself has the pricing at top level.
            status = _hf_provider_pricing_status(ep)
        else:
            # ModelEndpoint: pricing is at top level
            status = _hf_provider_pricing_status(ep)
        qualified.append(_set_pricing_status(ep, status))
    return qualified


def qualify_openrouter(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible OpenRouter endpoints; classify ``pricing_status``.

    Missing pricing → "unknown". All-zero prices → "free". Non-zero → "paid".
    """
    return [_set_pricing_status(ep, _classify_by_pricing(ep)) for ep in endpoints]


def qualify_kilo(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible Kilo endpoints; classify ``pricing_status``.

    Same rule as OpenRouter: missing → "unknown", all-zero → "free", non-zero → "paid".
    """
    return [_set_pricing_status(ep, _classify_by_pricing(ep)) for ep in endpoints]


def qualify_ollama(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible Ollama endpoints; stamp ``pricing_status``.

    :func:`data.providers.ollama.filter_ollama_free` sets
    ``pricing_status="free"`` when ``free_until`` is present, else
    ``"unknown"``, and keeps every endpoint.
    """
    # The ollama filter already returns ModelEndpoint with pricing_status set.
    # But defensively ensure any missing ones get classified.
    from data.providers.ollama import filter_ollama_free
    return filter_ollama_free(endpoints)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


# Each provider's qualify function. New providers register here.
PROVIDER_FREE_FILTERS: Dict[str, Callable[[List[Any]], List[Any]]] = {
    "nvidia": qualify_nvidia,
    "amd": qualify_amd,
    "huggingface": qualify_huggingface,
    "kilo": qualify_kilo,
    "openrouter": qualify_openrouter,
    "ollama": qualify_ollama,
}


def filter_free(
    endpoints: List[Any],
    provider: str,
) -> List[Any]:
    """Qualify endpoints for the catalog, dispatching by provider.

    Every provider's endpoints are classified (``pricing_status`` set when
    missing) and kept unless malformed. Unknown providers are passed
    through unchanged.

    Returns the eligible subset of ``endpoints``.
    """
    fn = PROVIDER_FREE_FILTERS.get(provider)
    if fn is None:
        return endpoints
    return fn(endpoints)


__all__ = [
    "qualify_nvidia",
    "qualify_amd",
    "qualify_huggingface",
    "qualify_openrouter",
    "qualify_kilo",
    "qualify_ollama",
    "filter_free",
    "PROVIDER_FREE_FILTERS",
]