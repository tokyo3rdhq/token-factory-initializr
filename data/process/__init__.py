"""Pipeline processing stages: normalize, validate, summarize.

Each stage operates on canonical ModelEndpoint records.

Modules:
- ``normalize``  — normalize_endpoints + endpoint_to_dict
- ``validate``   — split into (valid, invalid) by schema contract
- ``summarize``  — build the run manifest (counts + failure flags)

Note: deduplicate was removed per
``docs/arch_models_intelligence_layer_evo.md`` §12. Same-model across
different providers is treated as distinct endpoints (model identity !=
endpoint identity != quota identity). Future evolution should introduce
a ResolveIdentityStage rather than the simplistic
DeduplicateStage.
"""

from data.process.normalize import normalize_endpoints, endpoint_to_dict
from data.process.validate import validate_all, validate_endpoint, ValidationError
from data.process.summarize import summarize_all


__all__ = [
    "normalize_endpoints",
    "endpoint_to_dict",
    "validate_all",
    "validate_endpoint",
    "ValidationError",
    "summarize_all",
]