"""Canonical model endpoint schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ModelEndpoint:
    """Immutable canonical model endpoint record.

    Fields marked `None` are placeholders for future enrichment.
    Do not add complex fields unless the current provider data requires them.
    """

    provider: str
    model_id: str
    free: bool
    fetched_at: datetime

    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # ``architecture`` carries the input/output modalities in the same shape
    # HF's router API uses (``architecture.{input,output}_modalities``) and
    # AMD exposes via ``model.output`` + ``provider_pricing``. The name
    # matches the upstream convention so downstream consumers don't need
    # per-provider renaming. NVIDIA doesn't expose modalities natively; we
    # derive output_modalities from capabilities (``chat`` ->
    # ``["text"]``, ``tool_calling`` -> ``["text", "tool_calls"]``) and leave
    # input_modalities empty.
    architecture: Optional[dict[str, list[str]]] = None

    # Lab / organization the model is attributed to (HF: ``owned_by``,
    # AMD: ``token_factory.publisher.name``, NVIDIA: empty). Kept as a
    # distinct field so consumers can group / filter by lab without
    # reaching into metadata.
    lab: Optional[str] = None

    # Future fields (optional, may be added via enrichment):
    canonical_model_id: Optional[str] = None
    model_family: Optional[str] = None
    organization: Optional[str] = None
    version: Optional[str] = None
    context_length: Optional[int] = None
    license: Optional[str] = None
    quantization: Optional[str] = None
    pricing: Optional[dict] = None
    endpoint_url: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    limits: Optional[dict] = None
    score: Optional[float] = None