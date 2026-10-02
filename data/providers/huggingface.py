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

# Local dev may route HF traffic through a SOCKS5 proxy
# (router.huggingface.co is unreachable from some networks). Set
# SOCKS5_PROXY=socks5h://host:port. GitHub Actions runs direct (no proxy).
#
# Implementation note: we use ``requests`` with native SOCKS5h proxy
# support instead of monkey-patching ``socket.socket``. The
# monkey-patching approach breaks TLS handshakes on Python 3.10+
# because the ssl module's internal socket-type checks reject the
# patched class. ``requests`` (already a hard dep) routes through the
# proxy cleanly via urllib3 + PySocks.
SOCKS_PROXY_ENV = "SOCKS5_PROXY"


def fetch_router_json(timeout: int = TIMEOUT) -> dict:
    """GET the Hugging Face Inference Router model list.

    Local dev may route HF traffic through a SOCKS5 proxy via the
    ``SOCKS5_PROXY`` environment variable. GitHub Actions runs direct
    (no proxy).

    Two code paths:
      * **With SOCKS5_PROXY**: use ``requests`` with native SOCKS5h
        proxy support. urllib + global ``socket`` monkey-patching
        (``_apply_socks_proxy``) breaks TLS handshakes on Python 3.10+
        because the patched ``socksocket`` doesn't survive the ssl
        module's internal socket-type checks.
      * **Without proxy**: use stdlib ``urllib`` (zero extra deps; same
        path GitHub Actions uses).

    Returns the decoded JSON payload as a dict. Raises ``RuntimeError``
    on network failure so callers can distinguish it from parse errors.
    """
    proxy_url = os.getenv(SOCKS_PROXY_ENV, "").strip()
    if proxy_url:
        body = _fetch_via_requests(proxy_url, timeout=timeout)
    else:
        body = _fetch_via_urllib(timeout=timeout)
    return json.loads(body)


def _fetch_via_urllib(timeout: int) -> str:
    """Direct HTTP fetch via stdlib urllib (no proxy)."""
    req = urllib.request.Request(ROUTER_URL, headers={
        "User-Agent": UA,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        logger.error("Failed to fetch HF router: %s", exc)
        raise RuntimeError(f"Network error fetching HF models: {exc}") from exc


def _fetch_via_requests(proxy_url: str, timeout: int) -> str:
    """HTTP fetch through a SOCKS5 proxy using ``requests``.

    ``requests`` is already a hard dependency (NVIDIA provider uses
    it), so no new packages are required. SOCKS5h gives us remote DNS
    resolution through the proxy — matching the previous urllib path's
    behaviour exactly.
    """
    try:
        import requests  # noqa: WPS433 — local import; requests is a hard dep
    except ImportError as exc:
        raise RuntimeError(
            "SOCKS5_PROXY is set but 'requests' is not installed; "
            "pip install requests"
        ) from exc

    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {"User-Agent": UA, "Accept": "application/json"}
    try:
        resp = requests.get(ROUTER_URL, proxies=proxies, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch HF router via proxy: %s", exc)
        raise RuntimeError(f"Network error fetching HF models: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"HF router returned HTTP {resp.status_code}: {resp.text[:200]}"
        )
    return resp.text


def _is_free_provider(provider_entry: Dict[str, Any]) -> bool:
    """Decide whether a single HF router provider entry is free.

    The HF router API surfaces per-token prices at
    ``provider.pricing.{input, output}`` and a status flag at
    ``provider.status``. A provider is "free" iff:

      * ``status == "live"``, AND
      * ``pricing`` is present (not null / not missing), AND
      * ``pricing.input == 0`` AND ``pricing.output == 0``

    Note on missing pricing. The HF router carries ``is_free`` on
    every provider entry, and the recent observed pattern is
    ``is_free=False`` paired with ``pricing=null`` for almost every
    provider (cohere, featherless-ai, fireworks-ai, groq, scaleway,
    zai-org — collectively ~112 entries). Treating missing pricing
    as ``0/0`` would mark all of those as free, which is wildly
    wrong — those providers are paid services whose price field
    just hasn't been filled in yet. ``pricing=null`` therefore means
    *unknown / not confirmed free* and the model is excluded.

    The upstream ``is_free`` flag itself is sometimes missing (e.g.
    older entries) and is not consulted here; the price rule above
    is the authoritative signal we control. ``is_free``, when
    present, is preserved in metadata but does not affect this
    decision — same as before.
    """
    if provider_entry.get("status") != "live":
        return False
    pricing = provider_entry.get("pricing")
    if not isinstance(pricing, dict):
        # None / not a dict — unknown price ⇒ cannot confirm free.
        return False
    try:
        return float(pricing.get("input", -1)) == 0 and float(pricing.get("output", -1)) == 0
    except (TypeError, ValueError):
        return False


def to_endpoint_dicts(model_group: Dict[str, Any]) -> List[dict[str, Any]]:
    """Expand a single model+providers group into per-provider endpoint dicts.

    Pure expansion: emits one canonical endpoint dict per provider in
    ``model_group["providers"]``, regardless of free/paid status. The
    ``free`` flag is computed per-provider via the HF pricing rule;
    :func:`data.providers.free_filter.filter_huggingface_free` (i.e.
    the pipeline FilterFreeStage) drops the non-free ones.

    Each emitted endpoint carries the real provider name at the
    top-level ``provider`` field (was previously hidden in
    ``metadata.router_provider``). The actual upstream price values
    are also lifted to the top-level ``pricing`` field — the previous
    implementation hardcoded ``{"input": 0.0, "output": 0.0}`` and
    lost per-token prices entirely.
    """
    model_id = model_group["model_id"]
    name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    input_modalities = model_group["input_modalities"]
    output_modalities = model_group["output_modalities"]
    # Legacy 4-key capabilities shape — derived from the upstream
    # architecture block (modalities). The normalize stage
    # (``data.process.normalize.normalize_capabilities``) replaces
    # this with the canonical 7-key boolean shape on its way
    # through. Provider adapters that bypass the normalize stage
    # still see this legacy shape; downstream code reading
    # ``ep.capabilities`` via ``normalize_endpoints`` always sees the
    # canonical shape.
    capabilities: Dict[str, Any] = {}
    if "image" in input_modalities or "image" in output_modalities:
        capabilities["vision"] = True
    if any(m in output_modalities for m in ("audio",)):
        capabilities["speech"] = True
    if "text" in output_modalities and "embedding" not in output_modalities:
        capabilities["chat"] = True
    if "embedding" in output_modalities:
        capabilities["embedding"] = True

    architecture = {
        "input": list(input_modalities),
        "output": list(output_modalities),
    }

    endpoints: List[dict[str, Any]] = []
    for p in model_group["providers"]:
        provider_name = p.get("provider", "") or ""
        if not provider_name:
            continue  # malformed entry — drop silently

        # Per-provider context_length with fallback to model-level.
        provider_ctx = p.get("context_length")
        model_level_ctx = model_group.get("model_level_context_length")
        effective_ctx = provider_ctx if provider_ctx is not None else model_level_ctx

        # Per-provider pricing — preserved as raw values from upstream
        # (typically floats). Empty / missing treated as None.
        raw_pricing = p.get("pricing") or {}
        pricing: Optional[Dict[str, Any]] = None
        if raw_pricing:
            pricing = {
                k: v for k, v in raw_pricing.items()
                if isinstance(v, (str, int, float))
            } or None

        # Free flag derived from price + status (single source of
        # truth — see _is_free_provider docstring).
        free = _is_free_provider(p)

        endpoints.append({
            # The actual provider name (was hardcoded to "huggingface"
            # in the old design — bug fixed: see roadmap discussion).
            "data_source": "huggingface",
            "provider": provider_name,
            "model_id": model_id,
            "free": free,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "description": None,
            # Legacy 4-key capabilities shape — derived from
            # ``architecture.{input,output}_modalities`` above. The
            # normalize stage replaces this with the canonical 7-key
            # boolean shape on its way through.
            "capabilities": capabilities,
            # HF's router API exposes modalities under ``architecture``;
            # we keep the same key in our canonical schema so consumers can
            # read the field name verbatim.
            "architecture": architecture,
            "lab": model_group["owned_by"],
            # Real per-token pricing lifted from upstream. ``None`` when
            # the provider entry doesn't carry a pricing block.
            "pricing": pricing,
            "context_length": effective_ctx,
            "metadata": {
                # Per-provider metrics that don't fit any top-level
                # field. ``router_provider`` was removed — the provider
                # name is at the top-level ``provider`` field now.
                "supports_tools": bool(p.get("supports_tools", False)),
                "supports_structured_output": bool(p.get("supports_structured_output", False)),
                "first_token_latency_ms": p.get("first_token_latency_ms"),
                "throughput": p.get("throughput"),
                "is_model_author": bool(p.get("is_model_author", False)),
            },
        })
    return endpoints


def parse_huggingface_models(payload: dict) -> List[dict[str, Any]]:
    """Parse the raw HF router payload into per-provider endpoint dicts.

    Pure parser — takes the raw router JSON and returns a flat list of
    canonical endpoint dicts, **one per (model, provider) pair**. All
    providers are emitted (free and paid); the free-only filter is
    the FilterFreeStage's job. The router-level per-provider price
    rule (``pricing.input == 0 AND pricing.output == 0 AND
    status == "live"``) is what determines ``ep.free`` per endpoint.

    Args:
        payload: the dict returned by :func:`fetch_router_json`.

    Returns:
        List of endpoint dicts ready for
        ``data.models.normalize.normalize_endpoints``. Each entry has
        the actual upstream provider name at the top-level ``provider``
        field (e.g. ``"novita"`` / ``"cloudflare"`` / ``"huggingface"``),
        not a hardcoded ``"huggingface"``.
    """
    by_model = _group_models_by_id(payload)
    logger.info("Models with ≥1 provider: %d", len(by_model))

    all_endpoints: List[dict[str, Any]] = []
    for group in by_model:
        all_endpoints.extend(to_endpoint_dicts(group))

    logger.info("Expanded into %d provider endpoints", len(all_endpoints))
    return all_endpoints


def _group_models_by_id(payload: dict) -> List[Dict[str, Any]]:
    """Group the raw HF router ``data[]`` items by model id.

    Returns a list of per-model dicts shaped as
    ``{model_id, owned_by, input_modalities, output_modalities,
    model_level_context_length, providers: [...]}`` — the input
    contract of :func:`to_endpoint_dicts`. Model-level fields
    (``architecture``, ``context_length``, ``owned_by``) are flattened
    onto each group so the per-provider expander doesn't need to know
    about the outer model structure.
    """
    groups: List[Dict[str, Any]] = []
    for m in payload.get("data", []):
        model_id = m.get("id", "")
        if not model_id:
            continue
        owned_by = m.get("owned_by", model_id.split("/", 1)[0])
        arch = m.get("architecture", {})
        input_modalities: List[str] = arch.get("input_modalities", [])
        output_modalities: List[str] = arch.get("output_modalities", [])
        providers = m.get("providers") or []
        if not providers:
            continue
        groups.append({
            "model_id": model_id,
            "owned_by": owned_by,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
            "model_level_context_length": m.get("context_length"),
            "providers": providers,
        })
    return groups


def fetch_huggingface_models() -> List[dict[str, Any]]:
    """Fetch and return free Hugging Face inference model endpoints.

    Thin wrapper: fetches the raw router payload via
    :func:`fetch_router_json` (which applies the optional ``SOCKS5_PROXY``)
    and delegates parsing to :func:`parse_huggingface_models`. Keeping
    fetch and parse separate lets callers download the raw payload once
    and parse it under multiple policies (e.g. free-only vs. all), and
    lets unit tests exercise the parser without hitting the network.

    GitHub Actions runs direct (no proxy).
    """
    logger.info("Fetching Hugging Face router catalog: %s", ROUTER_URL)
    payload = fetch_router_json()
    total_models = len(payload.get("data", []))
    logger.info("Total models in HF router: %d", total_models)
    return parse_huggingface_models(payload)


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