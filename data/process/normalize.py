"""Normalize provider-specific model data into canonical ModelEndpoint.

This is a transform/pipeline stage — it lives under `data.process/`
to keep concerns separate:
  data.models     → schema definitions (dataclasses, JSON contracts)
  data.process    → transforms (normalize, validate, summarize, …)
  data.providers  → ingestion
  data.storage    → persistence
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from data.models.schema import ModelEndpoint


def normalize_endpoints(raw: list[dict[str, Any]]) -> list[ModelEndpoint]:
    """Convert a list of provider dicts into a list of ModelEndpoint records."""
    fetched_at = datetime.now(timezone.utc)
    endpoints = []
    for item in raw:
        try:
            ep = ModelEndpoint(
                provider=str(item["provider"]),
                model_id=str(item["model_id"]),
                free=bool(item.get("free", False)),
                fetched_at=fetched_at,
                name=item.get("name"),
                description=item.get("description"),
                capabilities=item.get("capabilities") or {},
                metadata=item.get("metadata") or {},
                lab=item.get("lab"),
            )
            endpoints.append(ep)
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(
                f"Provider record missing required field '{missing}': {item}"
            ) from exc
    return endpoints


def endpoint_to_dict(endpoint: ModelEndpoint) -> dict[str, Any]:
    """Serialize a ModelEndpoint to a plain dict for JSON storage."""
    data = asdict(endpoint)
    data["fetched_at"] = data["fetched_at"].isoformat()
    return data