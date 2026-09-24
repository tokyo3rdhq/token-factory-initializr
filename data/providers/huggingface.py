"""
Hugging Face Inference Router provider — fetches free-tier models via REST API.

Sources:
  GET https://router.huggingface.co/v1/models
  (returns OpenAI-compatible model list with provider pricing/status)

Output: list[dict[str, Any]] suitable for data.models.normalize.normalize_endpoints()

Free model filter:
  pricing.input == 0  AND  pricing.output == 0  AND  status == "live"

No proxy needed for GitHub Actions runner.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

from data.models.schema import ModelEndpoint

logger = logging.getLogger(__name__)

ROUTER_URL = "https://router.huggingface.co/v1/models"
# Chrome 153 stable on Linux x86_64 (released 2026-09-08)
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
)

ACCEPT_LANGUAGE = "en-US,en;q=0.9"
ACCEPT_ENCODING = "gzip, deflate, br"
TIMEOUT = 30

# Local dev may route HF traffic through a SOCKS5 proxy (router.huggingface.co
# is unreachable from some networks). Set SOCKS5_PROXY=socks5h://host:port.
# GitHub Actions runs direct — leave unset there.
SOCKS_PROXY_ENV = "SOCKS5_PROXY"


def _apply_socks_proxy() -> None:
    """If SOCKS5_PROXY is set, route urllib/socket traffic through that proxy.

    Idempotent: installs PySocks' ``socksocket`` as the global socket only
    once via a module-level guard. Requires PySocks (optional dependency).

    Returns without error when the env var is unset or PySocks is missing —
    direct connection is the fallback.
    """
    proxy_url = os.getenv(SOCKS_PROXY_ENV)
    if not proxy_url:
        return
    if getattr(_apply_socks_proxy, "_installed", False):
        return
    try:
        import socks  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "SOCKS5_PROXY set but PySocks is not installed; using direct connection"
        )
        return
    try:
        cleaned = proxy_url.split("://", 1)[-1]
        host, _, port_s = cleaned.rpartition(":")
        port = int(port_s)
        socks.set_default_proxy(socks.SOCKS5, host, port, rdns=True)
        socket.socket = socks.socksocket  # type: ignore[assignment]
        _apply_socks_proxy._installed = True
        logger.info("Routing HF provider through SOCKS5 proxy %s", proxy_url)
    except (ValueError, OSError):
        logger.warning("Invalid SOCKS5_PROXY=%r; using direct connection", proxy_url)
def fetch_router_json(timeout: int = TIMEOUT) -> dict:
    """GET the Hugging Face Inference Router model list.

    Local dev may route HF traffic through a SOCKS5 proxy via the
    ``SOCKS5_PROXY`` environment variable. The proxy setup is idempotent.
    GitHub Actions runs direct (no proxy).
    """
    _apply_socks_proxy()
    req = urllib.request.Request(ROUTER_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        logger.error("Failed to fetch HF router: %s", exc)
        raise RuntimeError(f"Network error fetching HF models: {exc}") from exc
    return json.loads(body)


def filter_free_providers(payload: dict) -> List[Dict[str, Any]]:
    """Group free providers per model; keep only models with ≥1 free provider.

    Returns list of dicts keyed by model id; each entry's providers field is
    a flat list of one ModelEndpoint-worthy dict per free provider.
    """
    by_model: Dict[str, Dict[str, Any]] = {}

    for m in payload.get("data", []):
        model_id = m.get("id", "")
        owned_by = m.get("owned_by", model_id.split("/", 1)[0])
        arch = m.get("architecture", {})
        input_modalities: List[str] = arch.get("input_modalities", [])
        output_modalities: List[str] = arch.get("output_modalities", [])
        # Per-provider context_length is sometimes null even for live free
        # providers. Fall back to the model-level value when present; only
        # leave it None if neither is set (real data gap on HF side).
        model_level_ctx = m.get("context_length")
        free_providers: List[dict] = []
        for p in m.get("providers", []):
            pricing = p.get("pricing") or {}
            if pricing.get("input") != 0 or pricing.get("output") != 0:
                continue
            if p.get("status") != "live":
                continue
            provider_ctx = p.get("context_length")
            effective_ctx = provider_ctx if provider_ctx is not None else model_level_ctx
            free_providers.append({
                "provider": p.get("provider", ""),
                "context_length": effective_ctx,
                "supports_tools": bool(p.get("supports_tools", False)),
                "supports_structured_output": bool(p.get("supports_structured_output", False)),
                "first_token_latency_ms": p.get("first_token_latency_ms"),
                "throughput": p.get("throughput"),
                "pricing": {"input": 0.0, "output": 0.0},
                "status": "live",
            })
        if not free_providers:
            continue
        by_model[model_id] = {
            "model_id": model_id,
            "owned_by": owned_by,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
            "free_providers": free_providers,
        }

    return list(by_model.values())


def to_endpoint_dicts(model_group: Dict[str, Any]) -> List[dict[str, Any]]:
    """Expand a single model+providers group into per-provider endpoint dicts."""
    model_id = model_group["model_id"]
    name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    input_modalities = model_group["input_modalities"]
    output_modalities = model_group["output_modalities"]
    capabilities: Dict[str, Any] = {}
    if "image" in input_modalities or "image" in output_modalities:
        capabilities["vision"] = True
    if any(m in output_modalities for m in ("audio",)):
        capabilities["speech"] = True
    if "text" in output_modalities and "embedding" not in output_modalities:
        capabilities["chat"] = True
    if "embedding" in output_modalities:
        capabilities["embedding"] = True

    endpoints: List[dict[str, Any]] = []
    for fp in model_group["free_providers"]:
        endpoints.append({
            "provider": "huggingface",
            "model_id": model_id,
            "free": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "description": None,
            "capabilities": capabilities,
            # HF's router API exposes modalities under ``architecture``;
            # we keep the same key in our canonical schema so consumers can
            # read the field name verbatim.
            "architecture": {
                "input": list(input_modalities),
                "output": list(output_modalities),
            },
            "lab": model_group["owned_by"],
            "metadata": {
                "router_provider": fp["provider"],
                "context_length": fp["context_length"],
                "supports_tools": fp["supports_tools"],
                "first_token_latency_ms": fp["first_token_latency_ms"],
                "throughput": fp["throughput"],
            },
        })
    return endpoints


def fetch_huggingface_models() -> List[dict[str, Any]]:
    """Fetch and return free Hugging Face inference model endpoints.

    Local dev may route HF traffic through a SOCKS5 proxy via the
    ``SOCKS5_PROXY`` environment variable. The proxy setup is idempotent.
    GitHub Actions runs direct (no proxy).
    """
    _apply_socks_proxy()
    logger.info("Fetching Hugging Face router catalog: %s", ROUTER_URL)
    payload = fetch_router_json()
    total_models = len(payload.get("data", []))
    logger.info("Total models in HF router: %d", total_models)
    free_groups = filter_free_providers(payload)
    logger.info("Models with ≥1 free provider: %d", len(free_groups))

    all_endpoints: List[dict[str, Any]] = []
    for group in free_groups:
        all_endpoints.extend(to_endpoint_dicts(group))

    logger.info("Expanded into %d provider endpoints", len(all_endpoints))
    return all_endpoints


if __name__ == "__main__":
    import sys
    models = fetch_huggingface_models()
    print(f"Fetched {len(models)} endpoints")
    for m in models[:5]:
        print(
            f"  {m['model_id']} lab={m.get('lab')!r} "
            f"provider={m['provider']} ctx={m['metadata'].get('context_length')} "
            f"arch={m.get('architecture')}"
        )