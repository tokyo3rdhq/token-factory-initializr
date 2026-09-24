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

    # Future fields (optional, may be added via enrichment):
    canonical_model_id: Optional[str] = None
    model_family: Optional[str] = None
    organization: Optional[str] = None
    version: Optional[str] = None
    context_length: Optional[int] = None
    modalities: Optional[list[str]] = None
    license: Optional[str] = None
    quantization: Optional[str] = None
    pricing: Optional[dict] = None
    endpoint_url: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    limits: Optional[dict] = None
    score: Optional[float] = None