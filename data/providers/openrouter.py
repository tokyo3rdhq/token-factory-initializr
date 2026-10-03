"""OpenRouter API provider for model enrichment.

Fetches models from https://openrouter.ai/api/v1/models and normalizes
them into TFI's canonical dict format for downstream consumption.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1/models"


def _fetch_models_page() -> list[dict[str, Any]]:
    """Fetch models from OpenRouter API."""
    if requests is None:
        raise ImportError("requests is required for OpenRouter provider")

    resp = requests.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def _normalize_capabilities(data: dict[str, Any]) -> dict[str, bool]:
    """Derive canonical capabilities from OpenRouter data.

    OpenRouter doesn't directly expose capability flags, so we infer them
    from architecture, supported_parameters, and description.
    """
    out: dict[str, bool] = {
        "chat": False,
        "vision": False,
        "speech": False,
        "embedding": False,
        "tool_calling": False,
        "structured_output": False,
        "reasoning": False,
    }

    arch = data.get("architecture") or {}
    input_mods = arch.get("input_modalities") or []
    output_mods = arch.get("output_modalities") or []
    modalities_str = arch.get("modality") or ""

    # Infer capabilities from modality strings
    if "image" in input_mods or "image" in output_mods:
        out["vision"] = True
    if "image" in modalities_str.lower():
        out["vision"] = True
    if "audio" in input_mods or "audio" in output_mods:
        out["speech"] = True
    if "embedding" in output_mods:
        out["embedding"] = True

    # Chat capability - text output modality
    if "text" in output_mods or "text" in modalities_str.lower():
        out["chat"] = True

    # Tool calling from supported_parameters
    params = data.get("supported_parameters") or []
    if isinstance(params, list):
        if "tools" in params:
            out["tool_calling"] = True
        if "tool_choice" in params:
            out["tool_calling"] = True

    # Reasoning from reasoning field
    reasoning = data.get("reasoning") or {}
    if isinstance(reasoning, dict):
        if reasoning.get("mandatory") or reasoning.get("default_enabled"):
            out["reasoning"] = True

    # Also check if "reasoning" is in supported_parameters
    if "reasoning" in params:
        out["reasoning"] = True

    return out


def _normalize_architecture(data: dict[str, Any]) -> dict[str, list[str]] | None:
    """Normalize architecture from OpenRouter format."""
    arch = data.get("architecture") or {}
    if not arch:
        return None

    input_mods = arch.get("input_modalities") or []
    output_mods = arch.get("output_modalities") or []

    if not input_mods and not output_mods:
        return None

    return {
        "input": input_mods,
        "output": output_mods,
    }


def _normalize_model(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenRouter model data to TFI canonical format."""
    model_id = data.get("id", "")
    if not model_id:
        logger.warning("OpenRouter model missing id, skipping")
        return {}

    pricing = data.get("pricing") or {}
    prompt_price = pricing.get("prompt", "0")
    completion_price = pricing.get("completion", "0")

    # Check if free (both prices are 0)
    is_free = (
        float(prompt_price) == 0 and float(completion_price) == 0
        if prompt_price and completion_price
        else False
    )

    return {
        "provider": "openrouter",
        "data_source": "openrouter",
        "model_id": model_id,
        "free": is_free,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": data.get("name"),
        "description": data.get("description"),
        "capabilities": _normalize_capabilities(data),
        "architecture": _normalize_architecture(data),
        "context_length": data.get("context_length"),
        "metadata": {
            "source_id": model_id,
            "canonical_slug": data.get("canonical_slug"),
            "hugging_face_id": data.get("hugging_face_id"),
            "supported_parameters": data.get("supported_parameters") or [],
            "reasoning": data.get("reasoning"),
            "top_provider": data.get("top_provider"),
        },
    }


def fetch_openrouter_models() -> list[dict[str, Any]]:
    """Fetch and normalize OpenRouter models.

    Returns list of canonical dicts suitable for pipeline processing.
    """
    try:
        raw_models = _fetch_models_page()
    except Exception as exc:
        logger.error("Failed to fetch OpenRouter models: %s", exc)
        return []

    endpoints = []
    for model in raw_models:
        try:
            endpoint = _normalize_model(model)
            if endpoint and endpoint.get("model_id"):
                endpoints.append(endpoint)
        except Exception as exc:
            logger.warning(
                "Failed to normalize OpenRouter model %s: %s",
                model.get("id", "unknown"),
                exc,
            )

    logger.info("Fetched %d OpenRouter models", len(endpoints))
    return endpoints


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    models = fetch_openrouter_models()
    print(f"Total models: {len(models)}", file=sys.stderr)
    for m in models[:5]:
        print(
            f"  {m['model_id']:<55} "
            f"desc={str(m.get('description', ''))[:40]}... "
            f"free={m['free']}"
        )
