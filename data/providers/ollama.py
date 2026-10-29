"""Ollama provider for cloud-hosted models.

Discovers models via GET https://ollama.com/v1/models, enriches details
via POST https://ollama.com/api/show, and enriches metadata via the
Ollama library page parser.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from data.models.schema import FieldProvenance, ModelEndpoint

logger = logging.getLogger(__name__)

BASE_URL = "https://ollama.com"
MODELS_ENDPOINT = "/v1/models"
SHOW_ENDPOINT = "/api/show"
LIBRARY_BASE_URL = "https://ollama.com/library"

# Ollama API key from environment (Bearer token)
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# Request timeout
TIMEOUT = 30

# Concurrency for detail fetching
MAX_CONCURRENT_DETAILS = 5

# Retry configuration for transient failures
MAX_RETRIES = 3
BASE_DELAY = 2.0
MAX_DELAY = 30.0

# Capability keyword normalization
OLLAMA_CAPABILITY_MAP = {
    "completion": "chat",
    "thinking": "reasoning",
    "tools": "tool_calling",
    "vision": "vision",
}

# Free-until date parsing
FREE_UNTIL_PATTERN = re.compile(r"free until\s+([^<\$]+)", re.IGNORECASE)

@dataclasses.dataclass
class OllamaModelDetail:
    """Parsed detail from /api/show."""

    capabilities: List[str]
    context_length: Optional[int]
    parameter_size: Optional[int]
    architecture: Optional[str]
    modified_at: Optional[str]
    thinking_config: Optional[Dict[str, Any]]
    details: Optional[Dict[str, Any]] = None
    model_info: Optional[Dict[str, Any]] = None

def _fetch_json(url: str, method: str = "GET", body: Optional[Dict] = None, headers: Optional[Dict[str, str]] = None) -> Dict:
    """Fetch JSON from URL with optional POST body and headers."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TokenFactoryInitializr/1.0)",
        "Accept": "application/json",
        **(headers or {}),
    }
    # Read API key at request time so tests can override via environment
    api_key = os.environ.get("OLLAMA_API_KEY", "")
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

    last_exc: Optional[BaseException] = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning("Ollama API %s %s failed (%s), retrying in %.1fs", method, url, exc.code, delay)
                time.sleep(delay)
            else:
                raise
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning("Ollama API %s %s network error (%s), retrying in %.1fs", method, url, exc, delay)
                time.sleep(delay)
            else:
                raise
    raise last_exc


def fetch_model_list() -> List[Dict]:
    """Fetch model list from Ollama OpenAI-compatible endpoint."""
    url = f"{BASE_URL}{MODELS_ENDPOINT}"
    logger.info("Fetching Ollama model list from %s", url)
    payload = _fetch_json(url)
    models = payload.get("data", [])
    logger.info("Found %d models in Ollama catalog", len(models))
    return models


def fetch_model_detail(model_id: str) -> OllamaModelDetail:
    """Fetch detailed model info from /api/show."""
    url = f"{BASE_URL}{SHOW_ENDPOINT}"
    logger.debug("Fetching detail for %s", model_id)
    payload = _fetch_json(url, method="POST", body={"model": model_id, "verbose": True})

    # Parse capabilities
    capabilities = payload.get("capabilities", [])

    # Parse context length from model_info
    context_length = None
    model_info = payload.get("model_info", {})
    for key, value in model_info.items():
        if key.endswith(".context_length") and isinstance(value, (int, float)):
            context_length = int(value)
            break

    # Parse parameter size
    parameter_size = None
    details = payload.get("details", {})
    if "parameter_size" in details and details["parameter_size"]:
        try:
            parameter_size = int(details["parameter_size"])
        except (ValueError, TypeError):
            pass
    elif "general.parameter_count" in model_info and model_info["general.parameter_count"]:
        try:
            parameter_size = int(model_info["general.parameter_count"])
        except (ValueError, TypeError):
            pass

    # Parse architecture
    architecture = None
    if "general.architecture" in model_info and model_info["general.architecture"]:
        architecture = model_info["general.architecture"]

    modified_at = payload.get("modified_at")
    thinking_config = payload.get("thinking")

    return OllamaModelDetail(
        capabilities=capabilities,
        context_length=context_length,
        parameter_size=parameter_size,
        architecture=architecture,
        modified_at=modified_at,
        thinking_config=thinking_config,
    )


def _fetch_library_html(model_id: str) -> Optional[str]:
    """Fetch Ollama library page HTML for parser enrichment."""
    url = f"{LIBRARY_BASE_URL}/{model_id}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TokenFactoryInitializr/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to fetch library page for %s: %s", model_id, exc)
        return None


# --- Ollama library page parser (refactored from /tmp/ollama_parser.py) ---

CAPABILITY_KEYWORDS = ["vision", "tools", "thinking", "cloud"]


def _extract_description(html: str) -> str:
    match = re.search(r'<meta name="description" content="([^"]+)"', html)
    return match.group(1).strip() if match else ""


def _extract_capabilities(html: str) -> List[str]:
    caps = []
    for cap in CAPABILITY_KEYWORDS:
        if re.search(rf"\b{cap}\b", html, re.IGNORECASE):
            caps.append(cap)
    return caps


def _extract_pricing(html: str) -> tuple[Optional[str], Dict[str, str]]:
    free_until = None
    match = FREE_UNTIL_PATTERN.search(html)
    if match:
        free_until = match.group(1).strip()

    prices = {}
    price_matches = re.findall(
        r'data-rate="base"[^>]*>\$([\d.]+)</div>.*?(input|cached|output)</div>',
        html,
        re.DOTALL,
    )
    for price, label in price_matches:
        prices[label] = f"${price} / 1M tokens"

    return free_until, prices


def _extract_metadata(html: str) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {
        "context_window": None,
        "parameters": None,
        "downloads": None,
        "updated": None,
    }

    # Context window
    match = re.search(
        r"Context</div>.*?<span[^>]*>(\d+[KM])</span>.*?tokens",
        html,
        re.DOTALL,
    )
    if match:
        meta["context_window"] = match.group(1)

    # Parameters
    match = re.search(
        r"Size</div>.*?<span[^>]*>(\d+[KMGTB]?)</span>.*?parameters",
        html,
        re.DOTALL,
    )
    if match:
        meta["parameters"] = match.group(1)

    # Downloads
    match = re.search(
        r"</svg>\s*<span[^>]*>(\d+\.?\d*[KM]?)</span>\s*<span[^>]*>&nbsp;Downloads</span>",
        html,
    )
    if match:
        meta["downloads"] = match.group(1)

    # Updated
    match = re.search(
        r"Updated\s*&nbsp;</span>\s*<span[^>]*>([^<]+)</span>",
        html,
    )
    if match:
        meta["updated"] = match.group(1).strip()

    return meta


def _parse_library_html(html: str, model_id: str) -> Dict[str, Any]:
    """Parse Ollama library page HTML into enrichment dict."""
    description = _extract_description(html)
    capabilities = _extract_capabilities(html)
    free_until, prices = _extract_pricing(html)
    metadata = _extract_metadata(html)

    return {
        "description": description,
        "capabilities": capabilities,
        "free_until": free_until,
        "pricing": prices,
        "metadata": metadata,
    }


def _normalize_capabilities(raw_caps: List[str]) -> List[str]:
    """Map Ollama capabilities to TFI canonical vocabulary."""
    normalized = set()
    for cap in raw_caps:
        mapped = OLLAMA_CAPABILITY_MAP.get(cap.lower())
        if mapped:
            normalized.add(mapped)
    return sorted(normalized)


def _parse_free_until(free_until_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse free_until string to datetime (UTC)."""
    if not free_until_str:
        return None
    # Try common formats
    formats = [
        "%b %d, %Y %I:%M %p %Z",  # Oct 22, 2026 11:59 PM UTC
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(free_until_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning("Could not parse free_until: %s", free_until_str)
    return None


def build_model_endpoint(
    model_id: str,
    detail: OllamaModelDetail,
    library_enrichment: Dict[str, Any],
) -> ModelEndpoint:
    """Build a ModelEndpoint from Ollama data sources."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc)

    # Normalize capabilities
    api_caps = _normalize_capabilities(detail.capabilities)
    library_caps = library_enrichment.get("capabilities", [])
    # Merge: API is authoritative, library adds
    all_caps = sorted(set(api_caps + library_caps))

    # Description: prefer library (richer), fallback to API (none available)
    description = library_enrichment.get("description")

    # Pricing
    pricing = library_enrichment.get("pricing", {})

    # Free until
    free_until = _parse_free_until(library_enrichment.get("free_until"))

    # Context length: API is authoritative
    context_length = detail.context_length

    # Architecture input modalities
    # Ollama models are text-in, text-out by default
    # Vision capability means image input
    input_modalities = ["text"]
    if "vision" in all_caps:
        input_modalities.append("image")
    architecture = {"input": input_modalities, "output": ["text"]}

    # Metadata
    metadata = {
        "parameter_size": detail.parameter_size,
        "modified_at": detail.modified_at,
        "thinking_config": detail.thinking_config,
        "free_until": free_until.isoformat() if free_until else None,
        **library_enrichment.get("metadata", {}),
    }

    # Source URL
    source_url = f"{LIBRARY_BASE_URL}/{model_id}"

    # Free flag: true if free_until exists (regardless of expiry)
    free = free_until is not None

    # Lab/owner from model_id (Ollama uses 'ollama' as owner)
    lab = "ollama"

    # Capabilities dict (legacy format)
    capabilities_dict = {
        "input_modalities": architecture["input"] if architecture else ["text"],
        "output_modalities": architecture["output"] if architecture else ["text"],
    }

    # Supported parameters (endpoint-level interface params)
    supported_parameters = []
    if "tool_calling" in all_caps:
        supported_parameters.append("tool_calling")
    if "reasoning" in all_caps:
        supported_parameters.append("reasoning")
    # streaming is always supported for chat completions
    supported_parameters.append("streaming")

    return ModelEndpoint(
        provider="ollama",
        model_id=model_id,
        pricing_status="free" if free_until is not None else "unknown",
        fetched_at=fetched_at,
        data_source="ollama",
        name=model_id,
        description=description,
        capabilities=capabilities_dict,
        metadata=metadata,
        architecture=architecture,
        supported_parameters=supported_parameters,
        lab=lab,
        context_length=context_length,
        pricing=pricing if pricing else None,
        endpoint_url=f"{BASE_URL}/",
        region=None,
        source_url=source_url,
        status=None,
        limits=None,
        score=None,
    )


def filter_ollama_free(endpoints: List[ModelEndpoint]) -> List[ModelEndpoint]:
    """Keep only Ollama endpoints with valid free_until; set pricing_status."""
    kept = []
    for ep in endpoints:
        free_until = ep.metadata.get("free_until")
        if free_until:
            kept.append(ModelEndpoint(
                provider=ep.provider,
                model_id=ep.model_id,
                pricing_status="free",
                fetched_at=ep.fetched_at,
                name=ep.name,
                description=ep.description,
                capabilities=ep.capabilities,
                architecture=ep.architecture,
                lab=ep.lab,
                metadata=ep.metadata,
                context_length=ep.context_length,
                pricing=ep.pricing,
                endpoint_url=ep.endpoint_url,
                region=ep.region,
                source_url=ep.source_url,
                status=ep.status,
                limits=ep.limits,
                score=ep.score,
                provenance=ep.provenance,
            ))
        else:
            kept.append(ModelEndpoint(
                provider=ep.provider,
                model_id=ep.model_id,
                pricing_status="unknown",
                fetched_at=ep.fetched_at,
                name=ep.name,
                description=ep.description,
                capabilities=ep.capabilities,
                architecture=ep.architecture,
                lab=ep.lab,
                metadata=ep.metadata,
                context_length=ep.context_length,
                pricing=ep.pricing,
                endpoint_url=ep.endpoint_url,
                region=ep.region,
                source_url=ep.source_url,
                status=ep.status,
                limits=ep.limits,
                score=ep.score,
                provenance=ep.provenance,
            ))
    dropped = len(endpoints) - len(kept)
    if dropped:
        logger.info("filter_free[ollama]: dropped %d endpoints without free_until", dropped)
    return kept


def fetch_ollama_models() -> List[ModelEndpoint]:
    """Main entry: fetch, enrich, and return Ollama ModelEndpoints."""
    # Stage A: Discover
    model_list = fetch_model_list()
    if not model_list:
        logger.warning("No models discovered from Ollama")
        return []

    model_ids = [m.get("id") for m in model_list if m.get("id")]
    logger.info("Discovered %d model IDs", len(model_ids))

    # Stage B + C: Fetch details + library enrichment + build endpoints
    endpoints = []
    for model_id in model_ids:
        try:
            detail = fetch_model_detail(model_id)
        except Exception as exc:
            logger.error("Failed to fetch detail for %s: %s", model_id, exc)
            continue

        library_html = _fetch_library_html(model_id)
        library_enrichment = {}
        if library_html:
            library_enrichment = _parse_library_html(library_html, model_id)
        else:
            logger.warning("No library page for %s, using API-only enrichment", model_id)

        try:
            endpoint = build_model_endpoint(model_id, detail, library_enrichment)
            endpoints.append(endpoint)
        except Exception as exc:
            logger.error("Failed to build endpoint for %s: %s", model_id, exc)
            continue

    logger.info("Built %d Ollama endpoints", len(endpoints))
    return endpoints


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)

    models = fetch_ollama_models()
    for m in models:
        free_mark = "✓" if m.pricing_status == "free" else "✗"
        print(f"  {m.model_id:<40} free={free_mark} ctx={m.context_length} caps={m.capabilities}")