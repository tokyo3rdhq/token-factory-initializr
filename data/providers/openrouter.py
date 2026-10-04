"""OpenRouter API provider.

Fetches models from https://openrouter.ai/api/v1/models and exposes them
as RAW observations — NOT pre-normalized.

Per docs/tfi_provenance_enrichment_architecture.md (option A in this
iteration), OpenRouter signals participate in the single normalize pass
that every other provider goes through:

    fetch → parse → filter_free → normalize → validate → enrich → ...

The normalize stage indexes OpenRouter observations by canonical
model_id (via the identity matcher) and merges their raw ``architecture``
+ ``supported_parameters`` signals into each endpoint's raw-signals
dict BEFORE :func:`normalize_capabilities` runs. That way the canonical
7-key capabilities shape is computed exactly once, and capabilities that
ultimately come from OpenRouter still get stamped ``method=native`` by
the enrich stage (because they're now part of the primary source's view
of the model).

This module therefore MUST NOT compute the 7-key boolean shape — doing
so would either lose the raw modality strings the normalize stage needs,
or force a second normalize pass downstream.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/models"


def _fetch_models_page() -> list[dict[str, Any]]:
    """Fetch raw models list from OpenRouter API."""
    if requests is None:
        raise ImportError("requests is required for OpenRouter provider")

    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def _build_raw_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenRouter raw model into a TFI raw-signals observation.

    The output is shaped like other providers' normalized records, but
    ``architecture`` carries the original modality lists (input /
    output_modalities) and ``metadata`` carries the explicit
    ``supported_parameters`` list — both consumed by
    :func:`data.process.normalize.normalize_capabilities` when merged
    into an endpoint's raw_signals dict.

    The 7-key boolean capabilities dict is deliberately omitted here.
    """
    model_id = data.get("id", "")
    if not model_id:
        return {}

    # Pre-normalize the OR-specific ``input_modalities`` /
    # ``output_modalities`` naming into the canonical ``input`` /
    # ``output`` shape so normalize_capabilities can read it the same
    # way it does for HF and AMD.
    raw_arch = data.get("architecture") or {}
    arch_input = raw_arch.get("input") or raw_arch.get("input_modalities") or []
    arch_output = raw_arch.get("output") or raw_arch.get("output_modalities") or []
    if isinstance(arch_input, list) and isinstance(arch_output, list):
        architecture = {"input": list(arch_input), "output": list(arch_output)}
    else:
        architecture = None

    supported_parameters = data.get("supported_parameters") or []
    if not isinstance(supported_parameters, list):
        supported_parameters = []

    reasoning = data.get("reasoning") or {}
    if not isinstance(reasoning, dict):
        reasoning = {}

    return {
        "provider": "openrouter",
        "data_source": "openrouter",
        "model_id": model_id,
        "name": data.get("name"),
        "description": data.get("description"),
        "architecture": architecture,
        "context_length": data.get("context_length"),
        "metadata": {
            # Pass these through so normalize_capabilities can read
            # them when this observation is merged into an endpoint.
            "supported_parameters": supported_parameters,
            "reasoning": reasoning,
            "source_id": model_id,
            "canonical_slug": data.get("canonical_slug"),
            "hugging_face_id": data.get("hugging_face_id"),
            "top_provider": data.get("top_provider"),
        },
    }


def fetch_openrouter_models() -> list[dict[str, Any]]:
    """Fetch raw OpenRouter observations.

    Returns a list of dicts shaped like the ``raw`` parameter of
    :func:`data.process.normalize.normalize_endpoints`. Each record
    carries raw ``architecture`` modalities + raw ``supported_parameters``
    / ``reasoning`` in ``metadata`` so the normalize stage can fuse
    them with the primary source's signals before computing capabilities.
    """
    try:
        raw_models = _fetch_models_page()
    except Exception as exc:
        logger.error("Failed to fetch OpenRouter models: %s", exc)
        return []

    observations: list[dict[str, Any]] = []
    for model in raw_models:
        try:
            obs = _build_raw_observation(model)
            if obs and obs.get("model_id"):
                observations.append(obs)
        except Exception as exc:
            logger.warning(
                "Failed to parse OpenRouter model %s: %s",
                model.get("id", "unknown"),
                exc,
            )

    logger.info("Fetched %d OpenRouter models", len(observations))
    return observations


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    models = fetch_openrouter_models()
    print(f"Total models: {len(models)}", file=sys.stderr)
    for m in models[:5]:
        print(
            f"  {m['model_id']:<55} "
            f"arch={m.get('architecture')} "
            f"params={m['metadata'].get('supported_parameters')}",
            file=sys.stderr,
        )
