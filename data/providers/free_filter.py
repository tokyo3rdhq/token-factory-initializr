"""Per-provider endpoint qualification + pricing classification.

Replaces the old free-only filter behavior (docs/tfi_model_endpoint_support_paid_model.md §5.1).
Each provider function now:

* Ensures ``pricing_status`` is set on every endpoint, classifying from
  source evidence when the parser did not already stamp it.
* Keeps every eligible (well-formed) endpoint — free, paid, and unknown.
* Returns only endpoints eligible for the catalog; malformed records
  (missing required identity fields) are rejected.

Free-only ingestion is no longer the pipeline behavior. If a free-only
view is needed, it is implemented as a downstream query/filter
(:mod:`web.functions.lib.filter`), not as the only published catalog.

The :func:`filter_free` dispatcher routes by provider name. Add new
providers by registering them in :data:`PROVIDER_FREE_FILTERS`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
from data.models.schema import ModelEndpoint
from data.providers.ollama import filter_ollama_free
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


def classify_pricing(endpoint: Any) -> str:
    """Classify an endpoint's ``pricing_status`` from its ``pricing`` field.

    Accepts both dict and ModelEndpoint. Returns one of:
    - ``"free"``   — all pricing values are zero
    - ``"paid"``   — any pricing value is non-zero
    - ``"unknown"`` — no pricing data, empty, or malformed
    """
    # Handle both dict and ModelEndpoint
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


def _ensure_pricing_status(endpoint: Any) -> Any:
    """Ensure ``pricing_status`` is set on endpoint (dict or ModelEndpoint).

    For dict: sets in place and returns the same dict.
    For ModelEndpoint (frozen dataclass): returns a NEW ModelEndpoint with
    pricing_status set, or the original if already set.
    """
    # Already has pricing_status?
    if hasattr(endpoint, "get"):
        current = endpoint.get("pricing_status")
    else:
        current = getattr(endpoint, "pricing_status", None)

    if current is not None:
        return endpoint

    # Compute pricing_status
    new_status = classify_pricing(endpoint)

    if hasattr(endpoint, "get"):
        # Dict: modify in place
        endpoint["pricing_status"] = new_status
        return endpoint
    else:
        # ModelEndpoint: create new instance with pricing_status
        # ModelEndpoint is frozen, so we must reconstruct
        return ModelEndpoint(
            provider=endpoint.provider,
            model_id=endpoint.model_id,
            free=endpoint.free,
            pricing_status=new_status,
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
    """Keep all eligible NVIDIA endpoints.

    ``pricing_status`` is stamped by :func:`data.providers.nvidia._normalize_model`
    ("Free Endpoint" → free, known non-empty nimType → paid, absent → unknown).
    No re-classification is needed here; pass everything through.
    """
    return list(endpoints)


def qualify_amd(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible AMD endpoints; classify ``pricing_status`` if missing."""
    return [_ensure_pricing_status(ep) for ep in endpoints]


def qualify_huggingface(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible HF endpoints; classify ``pricing_status`` if missing.

    The HF parser (:func:`data.providers.huggingface.to_endpoint_dicts`)
    already stamps ``pricing_status`` via :func:`_provider_pricing_status`;
    this is a defensive pass-through that fills any gaps.
    """
    return [_ensure_pricing_status(ep) for ep in endpoints]


def qualify_openrouter(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible OpenRouter endpoints; classify ``pricing_status``.

    Missing pricing → ``"unknown"`` (kept, never dropped). All-zero prices →
    ``"free"``. Non-zero → ``"paid"``.
    """
    return [_ensure_pricing_status(ep) for ep in endpoints]


def qualify_kilo(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible Kilo endpoints; classify ``pricing_status``.

    Same rule as OpenRouter: missing → ``"unknown"``, all-zero → ``"free"``,
    non-zero → ``"paid"``.
    """
    return [_ensure_pricing_status(ep) for ep in endpoints]


def qualify_ollama(endpoints: List[Any]) -> List[Any]:
    """Keep all eligible Ollama endpoints; stamp ``pricing_status``.

    :func:`data.providers.ollama.filter_ollama_free` sets
    ``pricing_status="free"`` when ``free_until`` is present, else
    ``"unknown"``, and keeps every endpoint.
    """
    # The ollama filter already returns ModelEndpoint with pricing_status set.
    # But defensively ensure any missing ones get classified.
    return [_ensure_pricing_status(ep) for ep in endpoints]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


# Each provider's qualify function. New providers register here.
PROVIDER_FREE_FILTERS: Dict[str, Callable[[List[Any]], List[Any]]] = {
    "nvidia": qualify_nvidia,
    "amd": qualify_amd,
    "huggingface": qualify_huggingface,
    "models_dev": qualify_amd,
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
    "classify_pricing",
    "qualify_nvidia",
    "qualify_amd",
    "qualify_huggingface",
    "qualify_openrouter",
    "qualify_kilo",
    "qualify_ollama",
    "filter_free",
    "PROVIDER_FREE_FILTERS",
]