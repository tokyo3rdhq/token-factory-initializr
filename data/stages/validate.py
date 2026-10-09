"""ValidateStage — split endpoints into (valid, invalid) and flag source health.

Keeps both lists: ``valid`` proceeds to snapshot → diff → reconcile → publish,
and ``invalid`` is preserved for the Feishu notify card.

The Stage also populates ``context.artifacts["source_validated"]`` —
a per-data-source boolean flag consulted by ``PublishStage`` before
issuing any destructive DELETE on a provider catalog (refactor §20 /
§21). A source is considered validated iff it had at least one valid
endpoint this run OR it had zero endpoints AND no fetch error. An
incomplete fetch (zero endpoints + fetch error in context state) is
NOT validated, which causes ``PublishStage`` to refuse destructive
deletes.

Additionally, if ``FetchStage`` populated ``context.data["nvidia_canonical_ids"]``
(a set of model ids from ``https://integrate.api.nvidia.com/v1/models``),
this stage filters NVIDIA endpoints: any ``provider == "nvidia"`` endpoint
whose ``model_id`` is not in that canonical set is marked invalid with
the issue ``"model_id not in NIM API catalog"``. If the canonical set
is missing or empty (fetch failed / API returned nothing), the NIM
membership check is skipped — a transient NIM outage never wipes the
catalog.
"""

from __future__ import annotations

from typing import Optional

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.validate import validate_all
from data.storage.cloudflare_kv import KNOWN_DATA_SOURCES


class ValidateStage(Stage):
    """Split endpoints into valid (proceeds) and invalid (logged)."""

    name = "validate"

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("endpoints", [])

        # First: standard schema validation
        valid, invalid = validate_all(endpoints)

        # Second: NIM canonical membership check for NVIDIA endpoints
        nim_ids: Optional[list[str]] = context.data.get("nvidia_canonical_ids")
        if nim_ids is not None and nim_ids:
            nim_set = set(nim_ids)
            nvidia_valid: list = []
            for ep in valid:
                if ep.provider == "nvidia" and ep.model_id not in nim_set:
                    invalid.append({
                        "endpoint": {
                            "provider": ep.provider,
                            "model_id": ep.model_id,
                        },
                        "issues": [f"model_id '{ep.model_id}' not in NIM API catalog"],
                    })
                else:
                    nvidia_valid.append(ep)
            valid = nvidia_valid

        context.data["valid"] = valid
        context.data["invalid"] = invalid

        # Mark every known source validated iff it had any valid
        # endpoint OR it had no fetch error this run. A source that
        # produced zero valid endpoints AND has a fetch error is
        # treated as not validated.
        fetch_errors = context.state.get("fetch_errors") or {}
        per_source_counts: dict[str, int] = {}
        for ep in valid:
            ds = ep.data_source if hasattr(ep, "data_source") else ""
            if ds:
                per_source_counts[ds] = per_source_counts.get(ds, 0) + 1
        validated: dict[str, bool] = {}
        for ds in KNOWN_DATA_SOURCES:
            if per_source_counts.get(ds, 0) > 0:
                validated[ds] = True
            elif ds not in fetch_errors:
                validated[ds] = True  # zero valid + no error = legitimate empty
            else:
                validated[ds] = False
        context.artifacts["source_validated"] = validated
        return context