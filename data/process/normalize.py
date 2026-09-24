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
    """Convert a list of provider dicts into a list of ModelEndpoint records.

    Side effects on ``item``:

    * Lifts ``metadata.context_length`` (if present and int) to the
      top-level ``ModelEndpoint.context_length`` field. The metadata
      copy is left in place for back-compat with readers that look at
      ``metadata.context_length`` directly.
    * Falls back to top-level ``item["context_length"]`` when
      ``metadata.context_length`` is absent — supports providers that
      emit the field at the top level instead.
    * Lifts ``item["architecture"]`` (if a ``{input: list[str],
      output: list[str]}`` dict) to ``ModelEndpoint.architecture``.
      AMD puts the structured modalities at top level of its parsed
      dict; HF puts them under ``architecture`` at the model level
      (then ``to_endpoint_dicts`` re-emits them per provider); both
      land at the top level of the endpoint dict and need to be
      copied onto the dataclass field of the same name.
    * Lifts ``item["pricing"]`` (if a non-empty dict) to
      ``ModelEndpoint.pricing``. AMD stamps per-token prices at
      ``model.provider_pricing[0].pricing`` (``{"prompt": ...,
      "completion": ..., "input_cache_read": ...}``) and
      ``build_endpoint_dict`` exposes them as a top-level ``pricing``
      key on the endpoint dict. HF and other providers don't emit
      per-token prices today; for them ``ModelEndpoint.pricing``
      stays ``None``.

    The lifts happen via ``object.__setattr__`` because
    ``ModelEndpoint`` is a frozen dataclass; we build the endpoint
    with the dataclass defaults and overwrite them after construction.
    """
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
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(
                f"Provider record missing required field '{missing}': {item}"
            ) from exc

        # Lift context_length: prefer metadata (where AMD/HF put it),
        # fall back to top-level (where future providers might emit it).
        # ``ModelEndpoint.context_length`` defaults to None, so we only
        # overwrite when a real int is found.
        metadata = ep.metadata
        candidate = None
        if isinstance(metadata, dict):
            candidate = metadata.get("context_length")
        if not isinstance(candidate, int):
            candidate = item.get("context_length")
        if isinstance(candidate, int):
            object.__setattr__(ep, "context_length", candidate)

        # Lift architecture: AMD/HF parsed dicts carry the structured
        # modalities at top level (``architecture: {input: [...],
        # output: [...]}``). Validate the shape before assigning so a
        # malformed payload fails loudly instead of silently storing a
        # bad value. NVIDIA goes through ``ModelEndpoint`` directly and
        # doesn't reach this code path.
        arch = item.get("architecture")
        if _is_valid_architecture(arch):
            object.__setattr__(ep, "architecture", arch)

        # Lift pricing: AMD stamps per-token prices at the top level of
        # its parsed endpoint dict. Validate it's a non-empty dict
        # before assigning — empty dicts are treated as "no data" so
        # downstream readers can rely on truthiness.
        pricing = item.get("pricing")
        if isinstance(pricing, dict) and pricing:
            object.__setattr__(ep, "pricing", pricing)

        endpoints.append(ep)
    return endpoints


def _is_valid_architecture(value: Any) -> bool:
    """True iff ``value`` is a ``{input: list[str], output: list[str]}`` dict.

    Anything else (``None``, plain dict, dict with wrong keys, dict
    whose values aren't list[str]) is treated as "no architecture" and
    left as ``None`` on the endpoint. Loud failures belong in
    ``validate.py``; here we just decide whether to lift at all.
    """
    if not isinstance(value, dict):
        return False
    if set(value.keys()) != {"input", "output"}:
        return False
    for key in ("input", "output"):
        items = value[key]
        if not isinstance(items, list):
            return False
        if not all(isinstance(s, str) for s in items):
            return False
    return True


def endpoint_to_dict(endpoint: ModelEndpoint) -> dict[str, Any]:
    """Serialize a ModelEndpoint to a plain dict for JSON storage."""
    data = asdict(endpoint)
    data["fetched_at"] = data["fetched_at"].isoformat()
    return data