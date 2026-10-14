"""
AMD Radeon AI Platform provider — fetches free-tier models via two REST endpoints.

Adapted from cloudfolio/skills/amd-radeon-models/fetch.py:
  Step 1: POST bootstrap → lists all model cards in the public_free section
  Step 2: GET detail per card → full metadata (ctx, modalities, pricing, license)

Output: list[dict[str, Any]] → normalized via data.models.normalize
Output schema: ModelEndpoint from data.models.schema

Free model filter:
  - License key == "free_endpoint" (not "limited_free")
  - No explicit "at capacity" marker needed (per reference notes)
Network: developer.amd.com.cn is directly reachable from this machine."""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data.models.schema import ModelEndpoint
from data.models.source_url import normalize_source_url

logger = logging.getLogger(__name__)

BASE = "https://developer.amd.com.cn"
DEFAULT_UA = (
    # Chrome 153 stable on Linux x86_64 (released 2026-09-08)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)
TIMEOUT = 30

# Authenticated v1/models API token (Authorization: Bearer).
# Loaded from the AMD_API_TOKEN environment variable; see data/.env.example.
# Falls back to the built-in token so local runs work without extra setup —
# GitHub Actions injects the real value from the AMD_API_TOKEN secret.
AMD_API_TOKEN = os.environ.get("AMD_API_TOKEN", "")



def _post_json(url: str, body: dict, ua: str, referer: str, timeout: int = 30) -> dict:
    """POST with CORS headers to avoid 403 on bootstrap."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "User-Agent": ua,
            "Content-Type": "application/json",
            "Origin": "https://developer.amd.com.cn",
            "Referer": referer,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, ua: str, timeout: int = 30) -> dict:
    """GET model detail page."""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json_v1(url: str, timeout: int = TIMEOUT) -> dict:
    """GET an authenticated (Authorization: Bearer) v1 API endpoint.

    The ``/radeon/api/v1/models`` endpoint requires a bearer token —
    an unauthenticated request returns ``401 {"detail": "Login required"}``.
    The token is read from ``AMD_API_TOKEN`` at import time.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {AMD_API_TOKEN}",
            "User-Agent": DEFAULT_UA,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_v1_models(timeout: int = TIMEOUT) -> list[dict]:
    """Fetch the full model list from the authenticated v1/models API.

    This is the authoritative source for per-model capability booleans
    (``providers[0].vision`` / ``tools`` / ``reasoning``) and
    ``structured_output``. It does NOT expose free-tier status — the
    tokenfactory bootstrap/detail endpoints remain the source of truth
    for which endpoints are free.
    """
    return _get_json_v1(f"{BASE}/radeon/api/v1/models", timeout=timeout).get("data", [])


def fetch_bootstrap(ua: str, timeout: int = TIMEOUT) -> list[dict]:
    """Fetch the full bootstrap list of model cards."""
    url = f"{BASE}/radeon/api/tokenfactory/bootstrap?directory=true"
    return _post_json(url, {}, ua, f"{BASE}/radeon/tokenfactory", timeout)


def fetch_detail(model_id: str, ua: str, timeout: int = TIMEOUT) -> dict:
    """Fetch full per-model detail."""
    encoded = urllib.parse.quote(model_id, safe="")
    url = f"{BASE}/radeon/api/tokenfactory/model?id={encoded}"
    return _get_json(url, ua, timeout)


def derive_use_case(model: dict) -> str | None:
    """Map capability_key + modalities → canonical use-case. Returns None to drop."""
    tf = model.get("token_factory", {})
    cap = tf.get("capability", {}).get("key")
    out = model.get("output", [])

    if cap in ("chat", "text"):
        return "chat"
    if cap in ("vision", "vlm"):
        return "vision"
    if cap in ("embedding",):
        return "embedding"
    if cap in ("speech",):
        return "speech"
    if cap in ("transcription", "asr"):
        return "transcription"

    # Fallback to modalities
    if "embedding" in out:
        return "embedding"
    if "text" in out:
        return "chat"
    return None


def _strip_gateway_prefix(model_id: str) -> str:
    """Strip AMD's gateway namespace prefix from a model id.

    Real AMD ``model.id`` values look like ``"model_gateway:MiMo-V2.6-Flash"``
    — the ``model_gateway:`` part is AMD's gateway namespace, not part of the
    actual model identifier. Other consumers (NVIDIA uses ``org/name``, HF
    uses ``org/name``) don't have such a namespace prefix, so we strip it
    here to keep model_ids consistent across providers.

    If the id doesn't contain a colon, return as-is.
    """
    if ":" in model_id:
        head, _, tail = model_id.partition(":")
        # Only strip known gateway namespaces; otherwise leave the id alone.
        if head.endswith("_gateway") or head == "model_gateway":
            return tail
    return model_id


def build_endpoint_dict(detail: dict) -> dict[str, Any]:
    """Build a dict suitable for data.models.normalize.normalize_endpoints().

    Maps the reference emit.py output shape to ModelEndpoint fields.

    Reference emit output:
      {
        "id": "<owner>/<model>",
        "owned_by": "<owner>",
        "input_modalities": [...],
        "output_modalities": [...],
        "free_providers": [...]
      }

    But AMD's detail response is richer — we flatten it into a single
    ModelEndpoint per model with capabilities derived from capabilities_key.

    The raw AMD id includes a gateway namespace prefix (e.g.
    ``"model_gateway:MiMo-V2.6-Flash"``). We strip it here so model_ids
    are consistent across providers; the original id is kept in
    ``metadata.original_id`` for traceability.
    """
    m = detail["model"]
    tf = m.get("token_factory", {})
    capability_key = tf.get("capability", {}).get("key")

    # Per-model capability booleans from the authenticated v1/models API.
    # ``fetch_amd_models`` merges ``providers`` (and ``structured_output``)
    # from ``/radeon/api/v1/models`` onto the detail payload before calling
    # this function, so these fields are present when the v1 fetch
    # succeeded and absent (→ False) otherwise.
    #   providers[0].vision     → capabilities.vision
    #   providers[0].tools      → capabilities.tool_calling (canonical key)
    #   providers[0].reasoning  → capabilities.reasoning
    #   model.structured_output → capabilities.structured_output
    v1_providers = m.get("providers") or []
    v1_provider = v1_providers[0] if v1_providers and isinstance(v1_providers[0], dict) else {}
    v1_vision = bool(v1_provider.get("vision"))
    v1_tools = bool(v1_provider.get("tools"))
    v1_reasoning = bool(v1_provider.get("reasoning"))
    v1_structured = bool(m.get("structured_output"))
    v1_context_length = m.get("context_length")

    input_modalities: list[str] = []
    output_modalities: list[str] = m.get("output", [])

    # Populate input_modalities from provider_pricing if available.
    # AMD's ``provider_pricing[0]`` block carries feature flags AND a
    # nested ``pricing`` sub-dict with per-token prices (e.g.
    # ``{"prompt": "1.4e-7", "completion": "2.8e-7",
    # "input_cache_read": "2.8e-9"}``). The feature flags are read for
    # ``architecture.input``; the per-token prices are lifted to the
    # top-level ``pricing`` field.
    pp = (m.get("provider_pricing") or [{}])[0]
    if pp.get("vision"):
        input_modalities.append("image")
    if pp.get("ocr"):
        input_modalities.append("image")
    # Add text as minimum input modality
    if "text" not in input_modalities:
        input_modalities.insert(0, "text")

    # Per-token prices (only set when AMD's payload actually carries
    # them — older fixtures may not). String values are kept verbatim
    # because AMD expresses very small magnitudes in scientific notation
    # (e.g. ``"1.4e-7"``) that ``float()`` would lose precision on.
    raw_pricing = pp.get("pricing")
    if isinstance(raw_pricing, dict) and raw_pricing:
        # Coerce to the union of string / float — most keys are strings
        # from the AMD API but tolerate floats too (defensive).
        pricing: dict[str, Any] = {}
        for key, value in raw_pricing.items():
            if isinstance(value, (str, int, float)):
                pricing[key] = value
    else:
        pricing = None

    free_status = tf.get("status", {}).get("key")
    is_free = free_status == "free_endpoint"

    raw_id = m["id"]
    clean_id = _strip_gateway_prefix(raw_id)

    # AMD does not expose a per-model detail URL on its public
    # developer site — the public Radeon catalog page lists every
    # free model in a single document. Per docs §4 we surface the
    # catalog-level URL verbatim rather than fabricating a per-
    # model path. Validation is belt-and-braces: the URL is
    # hardcoded, so the value is always safe.
    amd_source_url = normalize_source_url(
        "https://developer.amd.com.cn/radeon/tokenfactory"
    )
    return {
        "data_source": "amd",
        "provider": "amd",
        "model_id": clean_id,
        "free": is_free,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": m.get("label") or m.get("model") or clean_id,
        "description": m.get("description"),
        "source_url": amd_source_url,
        # Legacy capabilities shape — AMD's TFI-authored
        # ``derive_use_case`` produces a single string here. The
        # normalize stage (``data.process.normalize.normalize_capabilities``)
        # maps this string into the canonical 7-key boolean shape on
        # its way through. Provider adapters that bypass the normalize
        # stage still see this raw shape.
        "capabilities": {
            "use_case": derive_use_case(m),
        },
        # Structured modalities matching the canonical schema. AMD's API
        # splits input vs output natively; we mirror that directly under
        # the ``architecture`` key (named for parity with HF's router
        # ``architecture`` block). The normalize stage can also read
        # this to derive vision / speech flags.
        "architecture": {
            "input": input_modalities,
            "output": output_modalities,
        },
        "lab": tf.get("publisher", {}).get("name"),
        # Per-token prices lifted from
        # ``model.provider_pricing[0].pricing``. ``None`` when the
        # upstream payload doesn't carry the block (older fixtures,
        # or non-token-priced endpoints like free ones — AMD uses the
        # same ``provider_pricing`` shape for both paid and free, so
        # free endpoints may still have non-zero prices; the
        # ``free`` flag is the authoritative signal of cost, not
        # this field).
        "pricing": pricing,
        "metadata": {
            # TFI-authored raw signal that the normalize stage consumes
            # to map AMD into the canonical 7-key capabilities shape.
            # We store it under ``metadata`` rather than under
            # ``capabilities`` (which the normalize stage overwrites
            # with the canonical shape) so legacy consumers that read
            # ``ep.capabilities`` directly without going through
            # ``normalize_endpoints`` still see the AMD ``use_case``
            # string. ``derive_use_case`` reads from the model dict
            # (``m``), not the wrapper (``detail``), so we pass ``m``
            # here to avoid an off-by-one bug where the legacy
            # ``capabilities.use_case`` field silently came back as
            # ``None`` in production.
            "use_case": derive_use_case(m),
            # Raw per-model capability booleans from the authenticated
            # v1/models API. The normalize stage
            # (``data.process.normalize.normalize_capabilities``) reads
            # these to set the canonical 7-key boolean shape; they are
            # stored here (not under ``capabilities``, which normalize
            # overwrites) so direct consumers can still see the raw
            # upstream signals. Absent/false when the v1 fetch failed.
            "v1_vision": v1_vision,
            "v1_tools": v1_tools,
            "v1_reasoning": v1_reasoning,
            "v1_structured_output": v1_structured,
            "family": tf.get("publisher", {}).get("name") or m.get("family", "unknown"),
            "context_length": detail["model"].get("context_length", 0),
            "free_status": free_status,
            # Preserve the original AMD id (with gateway prefix) so callers can
            # disambiguate if AMD introduces new gateways later.
            "original_id": raw_id,
        },
    }


def fetch_amd_models() -> List[dict[str, Any]]:
    """Fetch and return free AMD Radeon model endpoints.

    This function integrates two data sources:
    1. The authenticated v1/models API for authoritative capability booleans
       (vision, tools, reasoning, structured_output).
    2. The tokenfactory bootstrap/detail flow for free-tier status and metadata.
    """
    ua = DEFAULT_UA
    try:
        v1_models_list = fetch_v1_models()
        v1_models_by_id = {m.get("id"): m for m in v1_models_list if m.get("id")}
        logger.info("Fetched %d models from v1/models API", len(v1_models_by_id))
    except Exception as e:
        logger.warning("Failed to fetch v1/models API: %s; continuing without enrichment", e)
        v1_models_by_id = {}

    bootstrap = fetch_bootstrap(ua)
    cards = bootstrap.get("cards", [])
    available: List[dict] = []

    for card in cards:
        model_id_raw = card["id"]
        model_id = _strip_gateway_prefix(model_id_raw)
        try:
            detail = fetch_detail(model_id_raw, ua)
            if not detail:
                continue

            # Enrich detail with v1 data if available
            if v1_models_by_id:
                v1_model = v1_models_by_id.get(model_id)
                if v1_model:
                    model_obj = detail["model"]
                    model_obj["name"] = v1_model.get("name", model_obj.get("name"))
                    model_obj["description"] = v1_model.get("description", model_obj.get("description"))
                    model_obj["family"] = v1_model.get("family", model_obj.get("family"))
                    model_obj["output"] = v1_model.get("output", model_obj.get("output"))
                    model_obj["architecture"] = v1_model.get("architecture", model_obj.get("architecture"))
                    model_obj["providers"] = v1_model.get("providers", model_obj.get("providers"))
                    model_obj["structured_output"] = v1_model.get("structured_output", model_obj.get("structured_output"))

            ep = build_endpoint_dict(detail)
            if ep.get("free", False):
                available.append(ep)
        except Exception as e:
            logger.warning("Failed to process model %s: %s", model_id_raw, e)
            continue

    logger.info("Fetched %d AMD endpoints", len(available))
    return available


if __name__ == "__main__":
    import sys
    models = fetch_amd_models()
    print(f"Total: {len(models)}", file=sys.stderr)
    for m in models:
        print(f"  {m['model_id']} provider={m['provider']} free={m['free']} "
              f"ctx={m['metadata']['context_length']}", file=sys.stderr)