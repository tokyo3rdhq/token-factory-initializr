"""Validate canonical ModelEndpoint records against the schema contract.

This is a transform/pipeline stage — it lives under `data.process/`.

Unlike normalize (shape conversion), validate
checks *content sanity*: required fields non-empty, types correct, known
enums respected.  Invalid records are returned separately, never dropped
silently.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from data.models.schema import ModelEndpoint

KNOWN_PROVIDERS = {"nvidia", "amd", "huggingface"}
# model_id must look like "<org>/<name>" or an opaque AMD gateway id
_MODEL_ID_RE = re.compile(r"^\S+$")


class ValidationError(ValueError):
    """Raised when a record fails schema validation."""


def validate_endpoint(ep: ModelEndpoint) -> list[str]:
    """Validate a single endpoint.

    Returns a list of issues; empty list means the record is valid.
    """
    issues: list[str] = []

    if not ep.provider or not ep.provider.strip():
        issues.append("provider is empty")
    elif ep.provider not in KNOWN_PROVIDERS:
        issues.append(f"unknown provider '{ep.provider}'")

    if not ep.model_id or not ep.model_id.strip():
        issues.append("model_id is empty")
    elif not _MODEL_ID_RE.match(ep.model_id):
        issues.append(f"model_id has whitespace: '{ep.model_id}'")

    if not isinstance(ep.free, bool):
        issues.append(f"free must be bool, got {type(ep.free).__name__}")

    if not isinstance(ep.fetched_at, datetime):
        issues.append("fetched_at is not a datetime")

    if not isinstance(ep.capabilities, dict):
        issues.append("capabilities is not a dict")
    if not isinstance(ep.metadata, dict):
        issues.append("metadata is not a dict")

    ctx = ep.metadata.get("context_length") if isinstance(ep.metadata, dict) else None
    if ctx is not None and not isinstance(ctx, int):
        issues.append(f"metadata.context_length is not int: {type(ctx).__name__}")

    return issues


def validate_all(endpoints: list[ModelEndpoint]) -> tuple[list[ModelEndpoint], list[dict[str, Any]]]:
    """Split endpoints into (valid, invalid) tuples.

    Returns:
        (valid_endpoints, invalid_records) where invalid_records is a list of
        ``{"endpoint": dict, "issues": [str]}`` for diagnostics/manifest.
    """
    valid: list[ModelEndpoint] = []
    invalid: list[dict[str, Any]] = []
    for ep in endpoints:
        issues = validate_endpoint(ep)
        if issues:
            invalid.append({
                "endpoint": {
                    "provider": ep.provider,
                    "model_id": ep.model_id,
                },
                "issues": issues,
            })
        else:
            valid.append(ep)
    return valid, invalid