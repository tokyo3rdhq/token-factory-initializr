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
from data.models.schema import legacy_free_compatible

# ---------------------------------------------------------------------------
# Canonical capabilities shape — the single source of truth across all
# data sources. The web-side `matchesRequirement()` / `format.ts` helpers
# and the Browse filter taxonomy (`BrowsePage.hasTag`) both read this
# exact key set. Adding a new capability = add a key here + handle it
# in `normalize_capabilities()` below. Everything else (nvidia/HF/AMD
# provider code, web matcher, tag chips) then sees the same shape.
#
# MIGRATION (user directive, 2026-10-19): ``tool_calling`` /
# ``reasoning`` / ``structured_output`` moved from capabilities to
# ``CANONICAL_SUPPORTED_PARAMETER_KEYS`` — they are interface/runtime
# parameters, not model-task capabilities. Their detection rules live
# in :func:`normalize_capability_signals` and the resulting booleans
# are stamped onto ``supported_parameters`` by
# :func:`normalize_supported_parameters`. Filters and the Browse UI
# keep exposing all three (gray styling preserved).
# ---------------------------------------------------------------------------
CANONICAL_CAPABILITY_KEYS: tuple[str, ...] = (
    "chat",              # text conversation output
    "vision",            # accepts image inputs
    "speech",            # accepts or produces audio
    "embedding",         # produces embedding vectors
    "translation",       # accepts or produces text translation
    "decision",          # decision-task / decision-output models
)


def normalize_capability_signals(
    data_source: str,
    raw_metadata: dict[str, Any] | None,
    architecture: dict[str, Any] | None,
    cross_source_signals: list[dict[str, Any]] | None = None,
) -> dict[str, bool]:
    """Provider-specific raw signals → every canonical boolean axis.

    Internal: computes ALL nine signals — the six capability keys
    (``CANONICAL_CAPABILITY_KEYS``) plus the three interface/runtime
    parameter keys migrated to ``supported_parameters`` on 2026-10-19
    (``tool_calling`` / ``reasoning`` / ``structured_output``).
    Detection rules for every key live HERE so provider branches
    stay in one place; the public
    :func:`normalize_capabilities` / :func:`normalize_supported_parameters`
    split this result into their respective fields.

    The returned dict always contains all nine keys (True or False)
    so consumers never see a missing key.

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
      architecture block for vision fallback, and the
      ``v1_tools`` / ``v1_reasoning`` / ``v1_structured_output``
      raw booleans from the authenticated v1 API.

    Cross-source enrichment (option A in
    docs/tfi_provenance_enrichment_architecture.md): when ``data_source``
    is one of the canonical providers (nvidia/amd/huggingface), the
    caller may pass ``cross_source_signals`` — a list of raw OpenRouter
    / models.dev / other-provider observations for the same canonical
    model. Each observation carries ``architecture: {input, output}``
    + ``metadata: {supported_parameters, reasoning}``. Signals from
    every observation are unioned into the primary source's working
    raw_signals before the canonical bool shape is computed, so the
    final capabilities are produced by exactly ONE normalize pass
    even when multiple cross-source providers contribute.

    Adding a new provider = add a new ``elif data_source == ...`` branch
    with the same shape; no other code needs to change.
    """
    out: dict[str, bool] = {k: False for k in CANONICAL_CAPABILITY_KEYS}
    for migrated in MIGRATED_PARAMETER_KEYS:
        out[migrated] = False
    # Architecture may be a malformed value (legacy RSC payloads,
    # fixture inputs, etc.) — ``data.process.normalize`` already
    # rejects non-dict architectures before they get here, but the
    # unit tests pass raw dicts straight in. Guard explicitly so
    # this function is safe regardless of caller hygiene.
    arch = architecture if isinstance(architecture, dict) else {}
    raw_meta = raw_metadata if isinstance(raw_metadata, dict) else {}

    # Merge cross-source signals (OpenRouter / models.dev / etc.) into
    # the working raw_signals. The primary source's signals win when
    # both sources disagree — cross-source only fills gaps. Concretely:
    #   * Each observation's architecture modalities extend the primary
    #     arch's input/output sets (union, never subtraction).
    #   * Each observation's metadata.supported_parameters is checked
    #     for tool/reasoning flags only if the primary source didn't
    #     already set them.
    if isinstance(cross_source_signals, dict):
        # Backward-compat: a single dict was the historical shape;
        # treat it as a one-element list so the merge loop below
        # works the same way for old callers.
        cross_source_signals = [cross_source_signals]
    elif not isinstance(cross_source_signals, list):
        cross_source_signals = []

    input_modes = set(arch.get("input") or [])
    output_modes = set(arch.get("output") or [])
    cs_params: list[str] = []
    cs_reasoning_default_enabled = False
    cs_reasoning_mandatory = False

    for cs in cross_source_signals:
        if not isinstance(cs, dict):
            continue
        cs_arch = cs.get("architecture") if isinstance(cs.get("architecture"), dict) else {}
        cs_meta = cs.get("metadata") if isinstance(cs.get("metadata"), dict) else {}
        if isinstance(cs_arch.get("input"), list):
            input_modes |= set(m for m in cs_arch["input"] if isinstance(m, str))
        if isinstance(cs_arch.get("output"), list):
            output_modes |= set(m for m in cs_arch["output"] if isinstance(m, str))
        params = cs_meta.get("supported_parameters") if isinstance(cs_meta, dict) else None
        if isinstance(params, list):
            cs_params.extend(p for p in params if isinstance(p, str))
        cs_reasoning = cs_meta.get("reasoning") if isinstance(cs_meta, dict) else None
        if isinstance(cs_reasoning, dict):
            if cs_reasoning.get("default_enabled"):
                cs_reasoning_default_enabled = True
            if cs_reasoning.get("mandatory"):
                cs_reasoning_mandatory = True

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

        # Modern labels-driven path: usecase includes "Text Translation"
        # (e.g. nvidia/riva-translate-4b-instruct-v2) → set translation flag.
        # Labels live under raw_meta["labels"], not top-level keys.
        labels_block = raw_meta.get("labels") if isinstance(raw_meta, dict) else {}
        for key in ("usecase", "general"):
            if not isinstance(labels_block, dict):
                continue
            vals = labels_block.get(key)
            if not isinstance(vals, dict):
                continue
            for v in vals.get("values", []):
                if not isinstance(v, str):
                    continue
                if "translation" in v.lower() or "translate" in v.lower():
                    out["translation"] = True
                    break
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
        # HF capability signals come from the architecture block.
        # The per-provider interface booleans (``supports_tools`` /
        # ``supports_structured_output``, stamped by the HF adapter
        # from the router's ``providers[]`` entries) map to the
        # MIGRATED parameter keys — they live in
        # ``supported_parameters`` now, not capabilities.
        out["tool_calling"] = bool(attrs.get("supports_tools"))
        out["structured_output"] = bool(attrs.get("supports_structured_output"))

    elif data_source == "amd":
        # AMD's TFI-authored ``derive_use_case`` returns one of:
        # "chat", "vision", "embedding", "speech", "transcription",
        # "decision" — a single string that we map to the canonical
        # bool axis. ``decision`` is set only when AMD's
        # ``token_factory.capability.key`` explicitly declared it
        # (docs/tfi_add_supported_parameters.md §3.1 — never inferred
        # from the model id).
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
        elif use_case == "decision":
            out["decision"] = True

        # Override/augment with authoritative raw boolean flags from the
        # authenticated v1/models API.
        out["vision"] = out["vision"] or bool(attrs.get("v1_vision"))
        out["tool_calling"] = out["tool_calling"] or bool(attrs.get("v1_tools"))
        out["reasoning"] = out["reasoning"] or bool(attrs.get("v1_reasoning"))
        out["structured_output"] = out["structured_output"] or bool(attrs.get("v1_structured_output"))
    # Cross-source signal promotion: every observation's
    # ``supported_parameters`` is checked for tool/reasoning flags, plus
    # OR's ``reasoning.default_enabled`` / ``reasoning.mandatory``
    # booleans. Apply these ONLY if the primary source didn't already
    # set the flag — cross-source is the fallback.
    if not out.get("tool_calling"):
        if "tools" in cs_params or "tool_choice" in cs_params:
            out["tool_calling"] = True

    if not out.get("reasoning"):
        if "reasoning" in cs_params:
            out["reasoning"] = True
        elif cs_reasoning_default_enabled or cs_reasoning_mandatory:
            out["reasoning"] = True

    # structured_output: explicit token in the cross-source
    # ``supported_parameters`` list (OpenRouter uses
    # ``structured_outputs``, models.dev / AMD v1 use
    # ``response_format``). Explicit signals only — never inferred.
    if not out.get("structured_output"):
        if "structured_outputs" in cs_params or "response_format" in cs_params:
            out["structured_output"] = True

    return out


# ---------------------------------------------------------------------------
# Hugging Face pricing normalization
# ---------------------------------------------------------------------------
#
# HF router exposes prices as per-token rates in raw form (e.g., 0.285 means
# $0.285 per token). For display and comparison, we normalize to USD per
# 1M tokens by dividing all values by 1,000,000. This function mutates the
# pricing dict in place and returns the normalized dict.
# ---------------------------------------------------------------------------

HF_PRICING_DIVISOR = 1_000_000


def normalize_hf_pricing(pricing: dict[str, Any] | None) -> dict[str, float] | None:
    """Normalize HF pricing values to USD per 1M tokens.

    HF router exposes prices as raw per-token values (e.g., 0.285 per token).
    This function divides all numeric values by 1,000,000 to convert to
    USD per 1M tokens, which is the standard display unit.

    Non-numeric values are preserved as-is (e.g., sentinel -1 values).

    Returns a new dict with normalized values, or None if input is None/empty.
    """
    if not pricing:
        return None

    normalized = {}
    for key, value in pricing.items():
        if isinstance(value, (int, float)):
            # -1 is a sentinel for "unknown" — preserve as-is
            if value < 0:
                normalized[key] = value
            else:
                # Divide by 1M to convert from per-token to per-million-tokens,
                # then round to eliminate floating-point artifacts and trailing zeros.
                normalized[key] = round(value / HF_PRICING_DIVISOR, 10)
        else:
            normalized[key] = value
    return normalized


def normalize_capabilities(
    data_source: str,
    raw_metadata: dict[str, Any] | None,
    architecture: dict[str, Any] | None,
    cross_source_signals: list[dict[str, Any]] | None = None,
) -> dict[str, bool]:
    """Public capabilities projection — the six ``CANONICAL_CAPABILITY_KEYS``
    booleans only.

    The three interface/runtime parameter booleans (``tool_calling`` /
    ``reasoning`` / ``structured_output``) are computed by the same
    signal pass but are surfaced through
    :func:`normalize_supported_parameters` instead (migration of
    2026-10-19) — reading them from ``capabilities`` is a bug.
    """
    signals = normalize_capability_signals(
        data_source, raw_metadata, architecture, cross_source_signals
    )
    return {k: signals[k] for k in CANONICAL_CAPABILITY_KEYS}

# ---------------------------------------------------------------------------
# Canonical supported_parameters vocabulary — the single source of truth
# across all data sources. Mirrors ``CANONICAL_CAPABILITY_KEYS``: the
# web-side projection and Browse filter read this exact vocabulary.
# Adding a new parameter = add a key here + a detection rule in
# normalize_supported_parameters().
#
# MIGRATION (user directive, 2026-10-19): the field is named
# ``supported_parameters`` to match the upstream sources (AMD v1 /
# OpenRouter / HF router all use this exact name). The values are
# TFI-canonical tokens, not raw upstream tokens: ``tool_calling`` /
# ``reasoning`` / ``structured_output`` moved here from
# ``CANONICAL_CAPABILITY_KEYS`` — they describe the endpoint's
# interface, not the model's task capabilities. The Browse UI keeps
# all of them as filter chips (gray styling) and model-row badges.
# ---------------------------------------------------------------------------
CANONICAL_SUPPORTED_PARAMETER_KEYS: tuple[str, ...] = (
    "tool_calling",      # tool / function calling interface
    "reasoning",         # reasoning / chain-of-thought interface
    "structured_output", # JSON / schema-constrained output interface
    "streaming",         # endpoint streams tokens incrementally
)

# The three keys migrated from capabilities on 2026-10-19.
MIGRATED_PARAMETER_KEYS: tuple[str, ...] = (
    "tool_calling",
    "reasoning",
    "structured_output",
)

# Raw upstream parameter tokens → canonical tokens. OpenRouter uses
# ``tools`` / ``tool_choice`` / ``structured_outputs`` / ``reasoning``
# / ``stream``; AMD v1 uses the same list with ``response_format``
# for structured output. These token rules apply ONLY to explicit
# ``supported_parameters`` lists — presence of the parameter means
# the endpoint implements the interface.
RAW_PARAMETER_TOKENS: dict[str, tuple[str, ...]] = {
    "tool_calling": ("tools", "tool_choice"),
    "reasoning": ("reasoning",),
    "structured_output": ("structured_outputs", "response_format"),
    "streaming": ("stream",),
}


def normalize_supported_parameters(
    data_source: str,
    raw_metadata: dict[str, Any] | None,
    architecture: dict[str, Any] | None = None,
    cross_source_signals: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Provider raw signals → canonical supported-parameter tokens.

    Source-mapping rules (explicit signals ONLY — missing/ambiguous
    data never becomes confirmed support):

    * **tool_calling / reasoning / structured_output** — computed by
      :func:`normalize_capability_signals` (provider v1 booleans,
      HF ``supports_tools`` / ``supports_structured_output``,
      NVIDIA legacy attributes, cross-source parameter tokens,
      OpenRouter ``reasoning`` flags). Migrated from capabilities
      on 2026-10-19; detection rules unchanged.
    * **streaming** — explicit signals ONLY:

      * **amd** — ``raw_metadata["streaming"]`` boolean, stamped by
        the AMD adapter from ``model.provider_pricing[0].streaming``.
      * **cross-source** (OpenRouter / models.dev / Kilo) — an
        explicit ``"stream"`` token in
        ``metadata.supported_parameters``. Applied only when the
        primary source emitted no streaming signal, same
        primary-source-wins semantics as capability promotion.

    The primary source's own ``supported_parameters`` token list
    (AMD v1 emits it for live endpoints) is consulted for streaming
    when the adapter passed no explicit streaming boolean.
    """
    out: list[str] = []
    raw_meta = raw_metadata if isinstance(raw_metadata, dict) else {}

    # Migrated interface parameters — reuse the exact same detection
    # pass that used to fill capabilities, so no signal is lost or
    # reinterpreted during the migration.
    signals = normalize_capability_signals(
        data_source, raw_metadata, architecture, cross_source_signals
    )
    # The guard/safety id heuristic runs later at the
    # normalize_endpoints level (it needs the full endpoint record for
    # the model_id) and is purely additive, so explicit signals are
    # emitted here — real source data (HF
    # ``supports_structured_output``, AMD v1 ``structured_output``,
    # OR ``structured_outputs`` tokens) never gets dropped.
    for migrated in MIGRATED_PARAMETER_KEYS:
        if signals.get(migrated):
            out.append(migrated)

    primary_streaming = raw_meta.get("streaming")
    primary_params = raw_meta.get("supported_parameters")
    primary_decided = isinstance(primary_streaming, bool)

    if primary_decided:
        if primary_streaming is True:
            out.append("streaming")
    elif isinstance(primary_params, list) and any(
        tok in primary_params for tok in RAW_PARAMETER_TOKENS["streaming"]
    ):
        out.append("streaming")

    # Cross-source fallback for streaming — only when the primary
    # source gave no streaming signal at all.
    if "streaming" not in out and not primary_decided:
        if not isinstance(cross_source_signals, list):
            cross_source_signals = []
        for cs in cross_source_signals:
            if not isinstance(cs, dict):
                continue
            cs_meta = cs.get("metadata") if isinstance(cs.get("metadata"), dict) else {}
            params = cs_meta.get("supported_parameters") if isinstance(cs_meta, dict) else None
            if isinstance(params, list) and any(
                tok in params for tok in RAW_PARAMETER_TOKENS["streaming"]
            ):
                out.append("streaming")
                break

    # Dedup while preserving the canonical vocabulary order.
    ordered: list[str] = []
    for key in CANONICAL_SUPPORTED_PARAMETER_KEYS:
        if key in out:
            ordered.append(key)
    return ordered


def normalize_endpoints(
    raw: list[dict[str, Any]],
    cross_source_index: dict[str, list[dict[str, Any]]] | None = None,
) -> list[ModelEndpoint]:
    """Convert a list of provider dicts into a list of ModelEndpoint records.

    Side effects on ``item``:

    * **Capabilities** are normalized from each provider's raw
      signals (see :func:`normalize_capabilities`) into the canonical
      7-key boolean shape defined by ``CANONICAL_CAPABILITY_KEYS``.
      Provider adapters no longer construct the final ``capabilities``
      shape themselves — they only fill in raw signals (architecture
      modalities, AMD use-case string, NVIDIA legacy attributes) and
      the normalize stage does the rest.

      When ``cross_source_index`` is provided, OpenRouter / models.dev
      raw observations for the same canonical model are fused into the
      primary source's signals before this pass runs (option A from
      docs/tfi_provenance_enrichment_architecture.md). The result is a
      single normalize pass per endpoint — capabilities end up with
      provenance ``method=native`` regardless of which underlying
      signal fed them. The index maps each canonical model_id to the
      full list of observations (OR + models.dev + future providers)
      so every cross-source signal contributes.
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
      copied onto the dataclass field of the same name. The merged
      cross-source modalities (from ``cross_source_index``) take
      precedence here so the canonical ``architecture`` field on the
      endpoint reflects what the normalize stage saw.
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
                # TFI source URL (per docs/tfi_model_source_url.md §4).
                # The source adapter has already validated the URL
                # through ``normalize_source_url``; the normalize
                # stage just passes the canonical value through.
                # ``item`` may be a dict or a ModelEndpoint (older
                # callers / unit tests); handle both.
                source_url=getattr(item, "source_url", None)
                if hasattr(item, "source_url")
                else item.get("source_url"),
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

        # Look up the matching cross-source raw observations (if any)
        # for this endpoint's canonical model_id. The stage precomputes
        # ``cross_source_index`` keyed by the alias-normalized id
        # (so ``deepseek-ai/...`` and ``deepseek/...`` collapse to one
        # entry), but owner-less endpoint ids (e.g. AMD's
        # ``MiniCPM5-2B``) only collide with the ``openbmb/minicpm5-2b``
        # entry via slug fallback, not via a literal normalized key
        # match. Walk the index and use the identity matcher to resolve
        # — that keeps normalize_endpoints consistent with how
        # EnrichStage does its matching and ensures slug-fallback hits
        # actually contribute signals.
        cross_source_signals_for_endpoint: list[dict] | None = None
        if cross_source_index:
            from data.identity_matcher import DefaultIdentityMatcher

            matcher = DefaultIdentityMatcher()
            best_obs: list[dict] | None = None
            best_conf = 0.0
            for key, observations in cross_source_index.items():
                for obs in observations:
                    obs_id = obs.get("model_id") or obs.get("id") or ""
                    if not obs_id:
                        continue
                    r = matcher.match(
                        ep.model_id,
                        [{"id": obs_id, "source": obs.get("data_source") or "unknown"}],
                    )
                    if r is not None and r.confidence > best_conf:
                        best_conf = r.confidence
                        best_obs = observations
            cross_source_signals_for_endpoint = best_obs

        # Lift capabilities — single canonical shape for the whole
        # catalog. Provider-specific raw signals live in ``metadata`` and
        # ``architecture``; this call fuses them with cross-source
        # OpenRouter / models.dev signals (if any) into the 6-key
        # canonical bool dict. See normalize_capabilities() above.
        object.__setattr__(
            ep,
            "capabilities",
            normalize_capabilities(
                ep.data_source,
                ep.metadata,
                item.get("architecture"),
                cross_source_signals=cross_source_signals_for_endpoint,
            ),
        )
        # (The guard/safety structured-output heuristic runs after the
        # supported_parameters lift below — it stamps
        # ``supported_parameters`` now, not capabilities.)
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
            # --- Prove provenance as native ---
            # When the value comes from the provider's metadata attribute,
            # we consider it a native fact.  This prevents EnrichStage
            # from overwriting it with a cross-source observation.
            if isinstance(metadata, dict) \
                    and "context_length" in metadata:
                # Build a native provenance record.
                from data.stages.enrich import _make_provenance_record

                record = _make_provenance_record(
                    source="amd",
                    source_id=ep.model_id,
                    source_field="context_length",
                    method="native",
                    confidence=1.0,
                    observed_at=ep.fetched_at,
                )
                ep.provenance["context_length"] = record

        # Now actually set the top-level field.
        object.__setattr__(ep, "context_length", candidate)

        # Lift architecture: AMD/HF parsed dicts carry the structured
        # modalities at top level (``architecture: {input: [...],
        # output: [...]}``). When cross-source signals were merged
        # into capabilities, surface the merged modalities here too so
        # the canonical ``architecture`` field agrees with what the
        # normalize stage saw.
        arch = item.get("architecture")
        if cross_source_signals_for_endpoint:
            base_input = list(arch.get("input") or []) if isinstance(arch, dict) else []
            base_output = list(arch.get("output") or []) if isinstance(arch, dict) else []
            cs_input: list[str] = []
            cs_output: list[str] = []
            for cs_obs in cross_source_signals_for_endpoint:
                if not isinstance(cs_obs, dict):
                    continue
                cs_arch = cs_obs.get("architecture") if isinstance(cs_obs.get("architecture"), dict) else {}
                if isinstance(cs_arch.get("input"), list):
                    cs_input.extend(m for m in cs_arch["input"] if isinstance(m, str))
                if isinstance(cs_arch.get("output"), list):
                    cs_output.extend(m for m in cs_arch["output"] if isinstance(m, str))
            # Only merge cross-source architecture when the provider
            # did not already supply an architecture dict.  This
            # preserves provider-native modality lists (e.g. AMD's
            # ``input_modalities`` / ``output_modalities`` from the
            # v1 API) and prevents cross-source signals from injecting
            # extra modalities such as ``video`` or ``audio``.
            if not arch:
                merged_input = list(dict.fromkeys([*base_input, *cs_input]))
                merged_output = list(dict.fromkeys([*base_output, *cs_output]))
                arch = {"input": merged_input, "output": merged_output}
        if _is_valid_architecture(arch):
            object.__setattr__(ep, "architecture", arch)

        # Lift pricing: AMD stamps per-token prices at the top level of
        # its parsed endpoint dict. Validate it's a non-empty dict
        # before assigning — empty dicts are treated as "no data" so
        # downstream readers can rely on truthiness.
        # For Hugging Face, normalize pricing to USD per 1M tokens first.
        pricing = item.get("pricing")
        if isinstance(pricing, dict) and pricing:
            if item.get("data_source") == "huggingface":
                pricing = normalize_hf_pricing(pricing)
            object.__setattr__(ep, "pricing", pricing)
        # Lift pricing_status from the parsed dict — the validate stage
        # computed this per-provider (free/priced/unknown). Preserve it
        # so downstream consumers (web UI badge, filter, etc.) can rely
        # on it instead of re-deriving from scratch.
        pricing_status = item.get("pricing_status")
        if pricing_status is not None:
            object.__setattr__(ep, "pricing_status", pricing_status)

        # Lift supported_parameters — endpoint-level interface/runtime
        # parameters (docs/tfi_add_supported_parameters.md §3.2/§4.1).
        # Populated ONLY from explicit source signals; missing data
        # stays ``[]``. Cross-source observations may contribute the
        # explicit ``stream`` token, but only when the primary
        # source didn't already decide the value — same
        # primary-source-wins semantics as capability promotion.
        object.__setattr__(
            ep,
            "supported_parameters",
            normalize_supported_parameters(
                ep.data_source,
                ep.metadata,
                item.get("architecture"),
                cross_source_signals=cross_source_signals_for_endpoint,
            ),
        )
        # Safety/guardrail models emit JSON-schema-constrained verdicts
        # by design (e.g. ``meta/llama-guard-4-12b``,
        # ``nvidia/nemotron-3.5-content-safety``). No upstream provider
        # currently exposes an explicit ``structured_output`` signal for
        # them, so the parameter is inferred from the model id keyword
        # and stamped onto ``supported_parameters``. MVP heuristic —
        # replace with a real signal when a provider starts surfacing
        # one. Additive: never removes a confirmed parameter.
        apply_guard_safety_structured_output(ep)

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


GUARD_SAFETY_KEYWORDS: tuple[str, ...] = ("guard", "safety")


def apply_guard_safety_structured_output(endpoint: ModelEndpoint) -> None:
    """Infer ``structured_output`` for safety/guardrail models by id keyword.

    Guardrail models (``*guard*`` / ``*safety*`` in ``model_id`` — e.g.
    ``meta/llama-guard-4-12b``, ``nvidia/nemotron-3.5-content-safety``,
    ``nvidia/llama-3.1-nemotron-safety-guard-8b-v3``) emit
    JSON-schema-constrained verdicts by design. No upstream provider
    (NVIDIA labels / OpenRouter supported_parameters / models.dev)
    currently exposes an explicit ``structured_output`` signal for
    them, so the capability is inferred from the model id keyword.
    MVP heuristic — replace with a real signal when a provider starts
    surfacing one. Additive: never turns a True off.
    """
    model_id = (endpoint.model_id or "").lower()
    if not any(k in model_id for k in GUARD_SAFETY_KEYWORDS):
        return
    params = list(endpoint.supported_parameters or [])
    if "structured_output" in params:
        return
    params.append("structured_output")
    # Keep the canonical vocabulary order.
    ordered = [k for k in CANONICAL_SUPPORTED_PARAMETER_KEYS if k in params]
    object.__setattr__(endpoint, "supported_parameters", ordered)


def endpoint_to_dict(endpoint: ModelEndpoint) -> dict[str, Any]:
    """Serialize a ModelEndpoint to a plain dict for JSON storage.

    Handles two non-JSON-native types:

    * ``fetched_at`` (top-level ``datetime``) — ISO 8601 string.
    * ``provenance[<path>].observed_at`` (``datetime`` inside each
      :class:`FieldProvenance`) — also ISO 8601. Provenance was added
      after the original serializer was written and previously broke
      PublishStage with ``TypeError: Object of type datetime is not
      JSON serializable`` because ``asdict`` recurses but doesn't
      format datetime values.
    """
    data = asdict(endpoint)
    # Legacy ``free`` compatibility rule (§3.2): backfill ``pricing_status``
    # from the legacy ``free`` field when the record carries no explicit
    # classification, then derive ``free`` from ``pricing_status`` so both
    # fields stay consistent. Missing pricing is never treated as free for
    # new records — those always carry an explicit ``pricing_status``.
    pricing_status = data.get("pricing_status")
    if pricing_status is None:
        pricing_status = "free" if data.get("free") else "unknown"
        data["pricing_status"] = pricing_status
    data["free"] = legacy_free_compatible(pricing_status)
    data["fetched_at"] = data["fetched_at"].isoformat()
    prov = data.get("provenance")
    if isinstance(prov, dict):
        for key, fp in prov.items():
            if isinstance(fp, dict) and isinstance(fp.get("observed_at"), datetime):
                fp["observed_at"] = fp["observed_at"].isoformat()
    return data