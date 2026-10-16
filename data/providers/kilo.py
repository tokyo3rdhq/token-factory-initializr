"""Kilo AI model data source.

Fetches models from https://api.kilo.ai/api/gateway/models and exposes them
as RAW observations — NOT pre-normalized.

Per docs/tfi_kiloai_integration_and_openrouter_promotion_implementation.md (option B),
Kilo records are processed by the production model-catalog pipeline (fetch → parse →
filter_free → normalize → validate → enrich → snapshot → diff → reconcile → publish).

The normalize stage indexes Kilo raw observations alongside other sources (OpenRouter,
models.dev) keyed by the identity matcher, so each endpoint's normalize pass can fuse
Kilo's raw architecture + supported_parameters signals before computing capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from data.models.source_url import normalize_source_url

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kilo.ai/api/gateway/models"


def _fetch_models_page() -> list[dict[str, Any]]:
    """Fetch raw models list from Kilo API."""
    if requests is None:
        raise ImportError("requests is required for Kilo provider")

    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def _build_raw_observation(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Kilo raw model into a TFI raw-signals observation.

    Kilo's response shape is:
    {
      "id": "...",
      "name": "...",
      "description": "...",
      "architecture": {"input": [...], "output": [...]},
      "context_length": 256000,
      "pricing": {"prompt": "0", "completion": "0", ...},
      "supported_parameters": ["max_tokens", "temperature"],
      "isFree": bool,
      "top_provider": {...}
    }

    We carry the raw architecture modalities, supported_parameters, and isFree
    into the metadata dict so normalize_capabilities and filter_free can use them.
    """
    model_id = data.get("id", "")
    if not model_id:
        return {}

    # Pre-normalize Kilo's OR-specific input/output naming into the canonical
    # ``input`` / ``output`` shape so normalize_capabilities can read it the same
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

    source_url = normalize_source_url(f"https://kilo.ai/models/{model_id}")

    return {
        "provider": "kilo",
        "data_source": "kilo",
        "model_id": model_id,
        "name": data.get("name"),
        "description": data.get("description"),
        "architecture": architecture,
        "context_length": data.get("context_length"),
        "pricing": data.get("pricing"),
        "metadata": {
            # Pass these through so normalize_capabilities can read them when this
            # observation is merged into an endpoint.
            "supported_parameters": supported_parameters,
            "isFree": data.get("isFree"),
            "source_id": model_id,
        },
        "source_url": source_url,
    }


def fetch_kilo_models() -> list[dict[str, Any]]:
    """Fetch raw Kilo observations.

    Returns a list of dicts shaped like the ``raw`` parameter of
    :func:`data.process.normalize.normalize_endpoints`.
    """
    try:
        raw_models = _fetch_models_page()
    except Exception as exc:
        logger.error("Failed to fetch Kilo models: %s", exc)
        return []

    observations: list[dict[str, Any]] = []
    for model in raw_models:
        try:
            obs = _build_raw_observation(model)
            if obs and obs.get("model_id"):
                observations.append(obs)
        except Exception as exc:
            logger.warning(
                "Failed to parse Kilo model %s: %s",
                model.get("id", "unknown"),
                exc,
            )

    logger.info("Fetched %d Kilo models", len(observations))
    return observations


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    models = fetch_kilo_models()
    print(f"Total models: {len(models)}", file=sys.stderr)
    for m in models[:5]:
        print(
            f"  {m['model_id']:<55} "
            f"arch={m.get('architecture')} "
            f"isFree={m['metadata'].get('isFree')}",
            file=sys.stderr,
        )