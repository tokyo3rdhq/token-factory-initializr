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


# ---------------------------------------------------------------------------
# Canonical capabilities shape — the single source of truth across all
# data sources. The web-side `matchesRequirement()` / `format.ts` helpers
# and the Browse filter taxonomy (`BrowsePage.hasTag`) both read this
# exact key set. Adding a new capability = add a key here + handle it
# in `normalize_capabilities()` below. Everything else (nvidia/HF/AMD
# provider code, web matcher, tag chips) then sees the same shape.
# ---------------------------------------------------------------------------
CANONICAL_CAPABILITY_KEYS: tuple[str, ...] = (
    "chat",              # text conversation output
    "vision",            # accepts image inputs
    "speech",            # accepts or produces audio
    "embedding",         # produces embedding vectors
    "tool_calling",      # tool / function calling
    "structured_output", # JSON / schema-constrained output
    "reasoning",         # reasoning / chain-of-thought
)


def normalize_capabilities(
    data_source: str,
    raw_metadata: dict[str, Any] | None,
    architecture: dict[str, Any] | None,
) -> dict[str, bool]:
    """Provider-specific raw signals → canonical 7-key boolean flags.

    The returned dict always contains all ``CANONICAL_CAPABILITY_KEYS``
    keys (True or False) so consumer-side code can read ``ep.capabilities[
    key]`` without worrying about missing keys.

    Provider raw signals:

    * **nvidia** — read ``raw_metadata["attributes"]`` (the legacy
      attribute shape with ``CHAT_MODALITY`` / ``TOOL_CALLING``)
      plus ``architecture.{input,output}`` for vision / speech /
      embedding detection (the modern labels path also produces a
      structured architecture block).
    * **huggingface** — read ``architecture.{input,output}`` (HF's
      router API surfaces modalities here).
    * **amd** — read ``raw_metadata["use_case"]`` (single string
      emitted by TFI's own ``derive_use_case`` helper) plus the
      architecture block for vision fallback.

    Adding a new provider = add a new ``elif data_source == ...`` branch
    with the same shape; no other code needs to change.
    """
    out: dict[str, bool] = {k: False for k in CANONICAL_CAPABILITY_KEYS}
    # Architecture may be a malformed value (legacy RSC payloads,
    # fixture inputs, etc.) — ``data.process.normalize`` already
    # rejects non-dict architectures before they get here, but the
    # unit tests pass raw dicts straight in. Guard explicitly so
    # this function is safe regardless of caller hygiene.
    arch = architecture if isinstance(architecture, dict) else {}
    raw_meta = raw_metadata if isinstance(raw_metadata, dict) else {}
    input_modes = set(arch.get("input") or [])
    output_modes = set(arch.get("output") or [])
    attrs = raw_meta

    # Architecture-derived flags — common to every provider that
    # exposes ``architecture.{input,output}`` as modality lists.
    if "image" in input_modes or "image" in output_modes:
        out["vision"] = True
    if any(m in output_modes for m in ("audio",)):
        out["speech"] = True
    if "embedding" in output_modes:
        out["embedding"] = True
    if "text" in output_modes and "embedding" not in output_modes:
        out["chat"] = True

    if data_source == "nvidia":
        # Legacy attributes shape (legacy RSC payloads still carry
        # these inside ``raw_metadata["attributes"]`` — TFI's nvidia
        # adapter stashes the upstream ``attributes`` block there for
        # back-compat with consumers that read metadata directly).
        # Modern labels-driven paths produce architecture + capabilities
        # via the architecture block above, so this branch only fills
        # what the architecture can't infer.
        attrs = attrs.get("attributes") if isinstance(attrs, dict) else None
        if isinstance(attrs, dict):
            if attrs.get("CHAT_MODALITY") == "text2textDiffusion":
                out["chat"] = True
            if attrs.get("TOOL_CALLING") == "true":
                out["tool_calling"] = True
        elif isinstance(attrs, list):
            for a in attrs:
                if not isinstance(a, dict):
                    continue
                if a.get("key") == "CHAT_MODALITY" and a.get("value") == "text2textDiffusion":
                    out["chat"] = True
                if a.get("key") == "TOOL_CALLING" and a.get("value") == "true":
                    out["tool_calling"] = True

    elif data_source == "huggingface":
        # All HF capability signals come from the architecture block —
        # the legacy chat-only / tool-only boolean flags that the HF
        # provider used to emit are folded into the architecture
        # derivation above. New HF providers that surface structured
        # output / reasoning should set the corresponding boolean
        # here when their API exposes those signals.
        pass

    elif data_source == "amd":
        # AMD's TFI-authored ``derive_use_case`` returns one of:
        # "chat", "vision", "embedding", "speech", "transcription"
        # — a single string that we map to the canonical bool axis.
        use_case = attrs.get("use_case") if isinstance(attrs, dict) else None
        if use_case == "chat":
            out["chat"] = True
        elif use_case in ("vision", "vlm"):
            out["vision"] = True
        elif use_case == "embedding":
            out["embedding"] = True
        elif use_case in ("speech",):
            out["speech"] = True
        elif use_case in ("transcription", "asr"):
            out["speech"] = True

    # structured_output / reasoning: no provider currently emits raw
    # signals for these. Future providers can extend normalize() with
    # detection rules. Default-False here is the safe answer for the
    # consumer — the matcher reads ep.capabilities.structured_output
    # and only filters when the user explicitly asked for it.

    return out


def normalize_endpoints(raw: list[dict[str, Any]]) -> list[ModelEndpoint]:
    """Convert a list of provider dicts into a list of ModelEndpoint records.

    Side effects on ``item``:

    * **Capabilities** are normalized from each provider's raw
      signals (see :func:`normalize_capabilities`) into the canonical
      7-key boolean shape defined by ``CANONICAL_CAPABILITY_KEYS``.
      Provider adapters no longer construct the final ``capabilities``
      shape themselves — they only fill in raw signals (architecture
      modalities, AMD use-case string, NVIDIA legacy attributes) and
      the normalize stage does the rest.
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
                data_source=str(item.get("data_source") or item.get("provider", "")),
                model_id=str(item["model_id"]),
                free=bool(item.get("free", False)),
                fetched_at=fetched_at,
                name=item.get("name"),
                description=item.get("description"),
                # Constructor default — the canonical shape is written
                # below via ``object.__setattr__`` regardless of what
                # the provider adapter stamped (nvidia = {chat,
                # tool_calling}, HF = {vision, speech, chat, embedding},
                # AMD = {use_case: <str>}). The normalize stage is the
                # single source of truth for the canonical 7-key boolean
                # shape; provider adapters keep building their own raw
                # signals for back-compat with any consumer that
                # bypasses the normalize stage (e.g. unit tests).
                capabilities={},
                metadata=item.get("metadata") or {},
                lab=item.get("lab"),
            )
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(
                f"Provider record missing required field '{missing}': {item}"
            ) from exc

        # Lift capabilities — single canonical shape for the whole
        # catalog. Provider-specific raw signals live in ``metadata`` and
        # ``architecture``; this call fuses them into the 7-key
        # canonical bool dict. See normalize_capabilities() above.
        object.__setattr__(
            ep,
            "capabilities",
            normalize_capabilities(
                ep.data_source,
                ep.metadata,
                item.get("architecture"),
            ),
        )

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