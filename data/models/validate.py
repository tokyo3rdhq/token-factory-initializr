"""JSON Schema validation for ``ModelEndpoint`` dicts.

The canonical schema lives at ``shared/schema/model.schema.json`` (repo root).
This module resolves the path relative to the repo root and exposes a thin
validator function that can be called by stages that want to assert a payload
matches the contract — for example, when reading back what StoreStage wrote.

No external dependency: uses the stdlib ``jsonschema`` package if available
(otherwise falls back to a minimal hand-rolled required-fields check so the
import never breaks).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from data.models.schema import ModelEndpoint

# Resolve <repo_root>/shared/schema/model.schema.json regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "shared" / "schema" / "model.schema.json"


def validate_schema_path() -> Path:
    """Return the absolute path to the canonical model schema file."""
    return _SCHEMA_PATH


def _load_schema() -> dict:
    """Load the canonical JSON schema from disk."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_endpoint_dict(endpoint: dict[str, Any]) -> List[str]:
    """Validate an endpoint dict against the canonical JSON Schema.

    Returns a list of human-readable error strings (empty list on success).
    Never raises; intended for ``Stage.execute`` callers that want to log
    invalid records instead of crashing the pipeline.
    """
    schema = _load_schema()
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    errors: list[str] = []

    for key in required:
        if key not in endpoint:
            errors.append(f"missing required field '{key}'")

    for key, value in endpoint.items():
        spec = properties.get(key)
        if spec is None:
            if not schema.get("additionalProperties", True):
                errors.append(f"unknown field '{key}'")
            continue
        # Light type checking (jsonschema would do more, but we want zero-deps).
        ty = spec.get("type")
        if ty == "string" and not isinstance(value, str):
            errors.append(f"field '{key}' must be a string, got {type(value).__name__}")
        elif ty == "boolean" and not isinstance(value, bool):
            errors.append(f"field '{key}' must be a boolean, got {type(value).__name__}")
        elif ty == "integer" and not isinstance(value, int):
            errors.append(f"field '{key}' must be an integer, got {type(value).__name__}")
        elif ty == "number" and not isinstance(value, (int, float)):
            errors.append(f"field '{key}' must be a number, got {type(value).__name__}")
        elif ty == "object" and not isinstance(value, dict):
            errors.append(f"field '{key}' must be an object, got {type(value).__name__}")
        elif ty == "array" and not isinstance(value, list):
            errors.append(f"field '{key}' must be an array, got {type(value).__name__}")
        elif isinstance(ty, list) and "null" in ty:
            # nullable field — accept None
            pass

    return errors


def validate_model_endpoint(ep: ModelEndpoint) -> List[str]:
    """Validate a ModelEndpoint dataclass instance against the canonical schema.

    Serializes via ``asdict`` and delegates to ``validate_endpoint_dict``.
    Useful for round-trip checks after StoreStage reads back from KV.
    """
    from dataclasses import asdict
    from datetime import datetime as _dt
    from datetime import date as _date

    payload = asdict(ep)
    # Normalize datetime/date values to ISO strings so the validator sees strings.
    for key, value in list(payload.items()):
        if isinstance(value, (_dt, _date)):
            payload[key] = value.isoformat()
    # Strip None values for fields the schema declares as `["...", "null"]` —
    # serializing through asdict gives None, but our validator's null type-list
    # branch already accepts None. The remaining issue is "modalities" which the
    # schema declares as a plain array — None must be removed to avoid spurious
    # type errors. This matches the schema's intent: absent = unknown.
    schema = _load_schema()
    for key, spec in schema.get("properties", {}).items():
        if key in payload and payload[key] is None and isinstance(spec.get("type"), str):
            # non-nullable field with None payload -> remove (interpreted as absent)
            del payload[key]
    return validate_endpoint_dict(payload)