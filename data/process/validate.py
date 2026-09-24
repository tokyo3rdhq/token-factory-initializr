"""Validate canonical ModelEndpoint records against the schema contract.

This is a transform/pipeline stage — it lives under `data.process/`.

Unlike normalize (shape conversion), validate
checks *content sanity*: required fields non-empty, types correct.
Invalid records are returned separately, never dropped silently.

Provider allowlist (historical):
    An earlier version of this module rejected ``provider`` values
    outside ``{nvidia, amd, huggingface}``. That allowlist became
    obsolete after the HF parse rewrite (which now emits one
    ``ModelEndpoint`` per upstream router provider, carrying names
    like ``"novita"`` / ``"fireworks-ai"`` / ``"together"`` /
    ``"cloudflare"`` at the top-level ``provider`` field). The
    field is now treated as opaque: any non-empty string is valid;
    the downstream consumer / filter decides what to do with it.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from data.models.schema import ModelEndpoint

# model_id must look like "<org>/<name>" or an opaque AMD gateway id
_MODEL_ID_RE = re.compile(r"^\S+$")


class ValidationError(ValueError):
    """Raised when a record fails schema validation."""


def validate_endpoint(ep: ModelEndpoint) -> list[str]:
    """Validate a single endpoint.

    Returns a list of issues; empty list means the record is valid.
    """
    issues: list[str] = []

    # Provider is now an opaque string. NVIDIA / AMD / HF carry
    # their own semantic ("nvidia" / "amd" / "huggingface"); HF's
    # per-provider expansion carries the actual upstream router name
    # ("novita" / "fireworks-ai" / etc.). Whitespace-only / empty
    # values are still rejected.
    if not ep.provider or not ep.provider.strip():
        issues.append("provider is empty")

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

    # context_length is a top-level optional[int] field. None means
    # "unknown / not provided"; any other non-int is an error.
    if ep.context_length is not None and not isinstance(ep.context_length, int):
        issues.append(
            f"context_length must be int or None, got {type(ep.context_length).__name__}"
        )

    # Back-compat: providers historically put context_length in
    # ``metadata`` (AMD/HF); some downstream code reads it from
    # there directly. Validate the metadata copy's type too so a
    # malformed payload surfaces as an issue here, not as a crash
    # in a downstream consumer.
    if isinstance(ep.metadata, dict):
        meta_ctx = ep.metadata.get("context_length")
        if meta_ctx is not None and not isinstance(meta_ctx, int):
            issues.append(
                f"metadata.context_length is not int: {type(meta_ctx).__name__}"
            )

    # architecture, if set, must be a {input: list[str], output: list[str]}
    # dict. AMD and HF providers populate this; NVIDIA leaves it None
    # (its modalities live under metadata-derived context). Mis-shaped
    # values are errors so downstream readers don't crash on iteration.
    arch = ep.architecture
    if arch is not None:
        if not isinstance(arch, dict):
            issues.append(
                f"architecture must be dict or None, got {type(arch).__name__}"
            )
        elif set(arch.keys()) != {"input", "output"}:
            issues.append(
                f"architecture keys must be exactly {{'input', 'output'}}, got {sorted(arch.keys())}"
            )
        else:
            for key in ("input", "output"):
                items = arch[key]
                if not isinstance(items, list):
                    issues.append(
                        f"architecture['{key}'] must be list, got {type(items).__name__}"
                    )
                elif not all(isinstance(s, str) for s in items):
                    issues.append(
                        f"architecture['{key}'] must be list[str]; found non-string element"
                    )

    # pricing, if set, must be a non-empty dict with scalar values
    # (AMD emits strings in scientific notation like ``"1.4e-7"``;
    # the contract is "scalar number-like" so float / int / str all
    # pass). Nested structures are an error.
    price = ep.pricing
    if price is not None:
        if not isinstance(price, dict):
            issues.append(
                f"pricing must be dict or None, got {type(price).__name__}"
            )
        elif not price:
            issues.append("pricing must not be an empty dict")
        else:
            for key, value in price.items():
                if not isinstance(key, str):
                    issues.append(
                        f"pricing keys must be str, got {type(key).__name__}"
                    )
                if not isinstance(value, (str, int, float)):
                    issues.append(
                        f"pricing['{key}'] must be scalar (str/int/float), "
                        f"got {type(value).__name__}"
                    )

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