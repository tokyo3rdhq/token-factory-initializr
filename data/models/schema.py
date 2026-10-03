"""Canonical model endpoint schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class FieldProvenance:
    """A single provenance record for one canonical field.

    Provenance keys are canonical field paths:
      - ``description``
      - ``capabilities.input_modalities``
      - ``capabilities.output_modalities``
      - ``context_length``
      - ``architecture.input_modalities``

    Attributes:
        source: Data source name (``nvidia``, ``amd``, ``huggingface``,
            ``openrouter``, ``models_dev``, ``modelparams``, ``provider_api``).
        source_id: Source-specific model identifier (e.g. ``deepseek/deepseek-v4.1-flash``).
        source_field: Field path in the source payload (e.g. ``description``,
            ``architecture.input_modalities``).
        method: How the canonical value was formed.
            One of: ``native``, ``enriched``, ``normalized``, ``inferred``, ``derived``.
        confidence: Confidence score 0.0–1.0.
        observed_at: ISO timestamp when this value was observed.
    """

    source: str
    source_id: str
    source_field: str
    method: str
    confidence: float
    observed_at: datetime


@dataclass(frozen=True)
class ModelEndpoint:
    """Immutable canonical model endpoint record.

    Fields marked ``None`` are placeholders for future enrichment.
    Do not add complex fields unless the current provider data requires them.
    """

    provider: str
    model_id: str
    free: bool
    fetched_at: datetime

    # The platform/source the endpoint was discovered through. Always
    # set explicitly by the source adapter; never derived from
    # ``provider`` after the fact (e.g. ``data_source="huggingface"``
    # with ``provider="novita"``). Required so consumers can address
    # endpoints in the (data_source, provider) namespace.
    data_source: str = ""

    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: dict = field(default_factory=dict)

    # ``metadata`` is a per-provider context dictionary for fields that
    # do not yet warrant their own top-level field on the canonical
    # schema. The fields are NOT shared across providers — each
    # provider stamps a different shape:
    #
    #   * AMD: ``{family, context_length, free_status, original_id}``.
    #   ``family`` is the publisher name; ``context_length`` is also
    #   lifted to the top-level ``context_length`` field (the
    #   metadata copy stays for back-compat); ``free_status`` is the
    #   raw ``tf.status.key`` value (e.g. ``"free_endpoint"`` /
    #   ``"paid"``); ``original_id`` preserves AMD's gateway-prefixed
    #   id (e.g. ``"model_gateway:MiMo-V2.6-Flash"``) so the stripped
    #   ``model_id`` can be disambiguated.
    #   * Hugging Face: ``{router_provider, context_length,
    #   supports_tools, first_token_latency_ms, throughput}``.
    #   ``router_provider`` is the specific HF router provider
    #   (e.g. ``"huggingface"`` / ``"cloudflare"``) — one model may
    #   appear under multiple providers as separate endpoints; ``context_length``
    #   is also lifted to the top-level field.
    #   * NVIDIA: ``{raw_obj?, attributes?, labels?}``. All three keys
    #   are optional and only present when the upstream RSC payload
    #   carries them. ``raw_obj`` is the full RSC object (debug /
    #   enrichment use; can be large — keep an eye on KV size);
    #   ``attributes`` and ``labels`` are the normalized NVIDIA
    #   catalog labels/attributes (each label value is shaped as
    #   ``{"values": [...], "unresolved": [...]}``).
    #
    # Because the three providers stamp different shapes, any
    # consumer that wants a specific metadata key MUST branch on
    # ``ep.provider`` first. There is currently no production
    # consumer of these keys outside of the normalize / validate
    # stages; the metadata dict exists primarily so per-provider
    # debug data survives the KV round-trip via
    # :func:`endpoint_to_dict`.
    metadata: dict = field(default_factory=dict)

    # ``architecture`` carries the input/output modalities in the same shape
    # HF's router API uses (``architecture.{input,output}_modalities``) and
    # AMD exposes via ``model.output`` + ``provider_pricing``. The name
    # matches the upstream convention so downstream consumers don't need
    # per-provider renaming. NVIDIA doesn't expose modalities natively; we
    # derive output_modalities from capabilities (``chat`` -> ``["text"]``,
    # ``tool_calling`` -> ``["text", "tool_calls"]``) and leave input_modalities
    # empty.
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

    # Per-token prices lifted from the upstream provider payload.
    # AMD stamps these at ``model.provider_pricing[0].pricing`` with
    # keys like ``prompt``, ``completion``, ``input_cache_read``
    # (string-encoded scientific notation, e.g. ``"1.4e-7"`` — kept
    # verbatim because float() would lose precision at that scale).
    # HF and NVIDIA do not emit per-token prices today; for them
    # this stays ``None``. The ``free`` flag is the authoritative
    # signal of cost — a non-None ``pricing`` field does NOT imply
    # the endpoint is paid.
    pricing: Optional[dict] = None
    endpoint_url: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None
    limits: Optional[dict] = None
    score: Optional[float] = None

    # Provenance: per-canonical-field provenance records.
    # Keyed by dotted field path (e.g. ``description``, ``capabilities.input_modalities``).
    # Values are ``FieldProvenance`` objects with: source, source_id, source_field,
    # method (native|enriched|normalized|inferred|derived), confidence, observed_at.
    provenance: dict[str, FieldProvenance] = field(default_factory=dict)
