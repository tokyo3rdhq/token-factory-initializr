"""Canonical data contracts for the Free Model Aggregator.

Modules:
- ``schema``     — Python dataclass ``ModelEndpoint`` (runtime type).
- ``validate``  — JSON Schema validator against ``shared/schema/model.schema.json``.

The shared JSON Schema (in ``shared/schema/``) is the source of truth for both
Python and TypeScript runtimes; this package provides both a Python type
(ModelEndpoint) and an optional validator entry point.
"""

from data.models.schema import ModelEndpoint
from data.models.validate import validate_endpoint_dict, validate_schema_path


__all__ = [
    "ModelEndpoint",
    "validate_endpoint_dict",
    "validate_schema_path",
]