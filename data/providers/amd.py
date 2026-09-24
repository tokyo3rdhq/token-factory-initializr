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
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data.models.schema import ModelEndpoint

logger = logging.getLogger(__name__)

BASE = "https://developer.amd.com.cn"
DEFAULT_UA = (
    # Chrome 153 stable on Linux x86_64 (released 2026-09-08)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)
TIMEOUT = 30


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

    input_modalities: list[str] = []
    output_modalities: list[str] = m.get("output", [])

    # Populate input_modalities from provider_pricing if available
    pp = (m.get("provider_pricing") or [{}])[0]
    if pp.get("vision"):
        input_modalities.append("image")
    if pp.get("ocr"):
        input_modalities.append("image")
    # Add text as minimum input modality
    if "text" not in input_modalities:
        input_modalities.insert(0, "text")

    free_status = tf.get("status", {}).get("key")
    is_free = free_status == "free_endpoint"

    raw_id = m["id"]
    clean_id = _strip_gateway_prefix(raw_id)

    return {
        "provider": "amd",
        "model_id": clean_id,
        "free": is_free,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "name": m.get("label") or m.get("model") or clean_id,
        "description": m.get("description"),
        "capabilities": {
            "use_case": derive_use_case(detail),
        },
        # Structured modalities matching the canonical schema. AMD's API
        # splits input vs output natively; we mirror that directly under
        # the ``architecture`` key (named for parity with HF's router
        # ``architecture`` block).
        "architecture": {
            "input": input_modalities,
            "output": output_modalities,
        },
        "lab": tf.get("publisher", {}).get("name"),
        "metadata": {
            "family": tf.get("publisher", {}).get("name") or m.get("family", "unknown"),
            "context_length": m.get("context_length", 0),
            "free_status": free_status,
            # Preserve the original AMD id (with gateway prefix) so callers can
            # disambiguate if AMD introduces new gateways later.
            "original_id": raw_id,
        },
    }


def fetch_amd_models() -> List[dict[str, Any]]:
    """Fetch and return free AMD Radeon model endpoints.

    Raises RuntimeError on network failure; returns empty list if no free
    models are found (not an error condition).
    """
    logger.info("Fetching AMD Radeon catalog: %s", BASE)
    bootstrap = fetch_bootstrap(DEFAULT_UA)
    cards = bootstrap.get("cards", [])
    available: List[dict] = []
    # Real shape: cards is a flat list of {key, id, detail_url} dicts — no section nesting.
    for card in cards:
        model_id = card["id"]
        logger.info("Fetching AMD detail for %s", model_id)
        detail = fetch_detail(model_id, DEFAULT_UA)
        ep = build_endpoint_dict(detail)
        available.append(ep)

    logger.info("Fetched %d AMD endpoints", len(available))
    return available


if __name__ == "__main__":
    import sys
    models = fetch_amd_models()
    print(f"Total: {len(models)}", file=sys.stderr)
    for m in models:
        print(f"  {m['model_id']} provider={m['provider']} free={m['free']} "
              f"ctx={m['metadata']['context_length']}", file=sys.stderr)