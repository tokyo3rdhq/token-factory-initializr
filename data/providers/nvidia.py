"""
NVIDIA NIM provider — parses build.nvidia.com model catalog (RSC payloads).

This module adapts the reference nvidia_parser.py logic into the current
project's data pipeline architecture:
  - output: list[dict[str, Any]] → normalized via data.models.normalize
  - output schema: ModelEndpoint from data.models.schema

Free model list uses nimType=nim_type_preview filter.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from data.models.schema import ModelEndpoint
from data.models.source_url import normalize_source_url
logger = logging.getLogger(__name__)

# Request headers for WAF compatibility
#
# Matches the URL the public web UI uses when "Free models" is
# selected, with ``pageSize=96`` so the full free catalog fits in
# a single fetch (free models rarely exceed 96 entries). The
# upstream server appears to ignore the ``filters`` query parameter
# at the RSC layer (we still get the full catalog back in the
# response), so we drop pagination in the parser — see
# ``fetch_all_pages`` below. Using this URL:
#
#   1. Documents intent — readers see we're hitting the
#      free-models view, not the unfiltered view.
#   2. Aligns the scraper URL with the web UI's URL bar for trace
#      correlation.
#
# Filtering of paid vs. free still happens locally via the
# ``free`` flag computed in ``_normalize_model`` (from
# ``labels.nimType.values``) and dropped by ``FilterFreeStage`` —
# see ``data/providers/free_filter.py``.
BASE_URL = (
    "https://build.nvidia.com/models"
    "?pageSize=96&filters=nimType%3Anim_type_preview"
)

# WAF cooldown: server returns 202 after first page, needs retry with delay
WAIT_AFTER_202 = 35  # seconds

# All RSC chunk types (RSC, Flight)
RSC_TYPES = {"nim_type_preview", "nim_type_run_anywhere"}

# ISO 8601 format for fetched_at
ISO_8601 = "%Y-%m-%dT%H:%M:%S.%fZ"


def _find_json_end(text: str, start: int) -> int:
    """Find the matching '}' for '{' at start, respecting string escapes."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        c = text[i]
        if escaped:
            escaped = False
        elif in_str:
            if c == '\\':
                escaped = True
            elif c == '"':
                in_str = False
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _extract_rsc_payload(html: str) -> str:
    """Extract and concatenate all RSC/Flight chunks from the HTML."""
    scripts = re.findall(r'<script>([^<]*self\.__next_f\.push.*?)</script>', html, re.DOTALL)
    chunks: List[tuple[int, str]] = []
    for s in scripts:
        for m in re.finditer(r'self\.__next_f\.push\(\[(\d+),("(?:[^"\\]|\\.)*")\]\)', s):
            chunks.append((int(m.group(1)), m.group(2)))
    chunks.sort(key=lambda x: x[0])
    return "".join(json.loads(c) for _, c in chunks)


def _parse_objects(rsc_payload: str) -> List[Dict]:
    """Parse all ENDPOINT resource objects from RSC payload."""
    objects: List[Dict] = []
    for m in re.finditer(r'\{"resourceType":"ENDPOINT"', rsc_payload):
        start = m.start()
        end_idx = _find_json_end(rsc_payload, start)
        if end_idx < 0:
            continue
        try:
            obj = json.loads(rsc_payload[start:end_idx + 1])
            objects.append(obj)
        except json.JSONDecodeError:
            pass
    return objects


def _extract_publisher(obj: Dict) -> Optional[str]:
    """Return the publisher name from ``labels.publisher.values[0]``.

    NVIDIA's live RSC payload carries the publisher at
    ``labels[].key == "publisher" -> values[0]`` (a list of strings like
    ``"deepseek-ai"`` / ``"nvidia"``). ``resourceId`` is a NIM namespace
    like ``"qc69jvmznzxy/<slug>"`` which is NOT useful as a public
    ``model_id`` — the publisher label is the canonical org.

    Returns ``None`` when the publisher label is absent or malformed;
    callers should fall back to legacy heuristics in that case.
    """
    labels = obj.get("labels")
    if not isinstance(labels, list):
        return None
    for lbl in labels:
        if not isinstance(lbl, dict):
            continue
        if lbl.get("key") != "publisher":
            continue
        values = lbl.get("values") or []
        if values:
            return str(values[0])
    return None


def _labels_to_dict(labels: Any) -> Dict[str, Dict[str, Any]]:
    """Normalize the labels payload to a ``{key: {"values": [...], "unresolved": [...]}}`` dict.

    Live RSC uses a list of ``{key, values, unresolvedValues}`` objects;
    legacy fixtures use a dict keyed by label name. Returns ``{}`` on
    unknown shapes.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(labels, dict):
        for k, v in labels.items():
            if isinstance(v, dict):
                out[k] = {
                    "values": list(v.get("values") or []),
                    "unresolved": list(v.get("unresolvedValues") or []),
                }
            else:
                out[k] = {"values": [], "unresolved": []}
    elif isinstance(labels, list):
        for lbl in labels:
            if not isinstance(lbl, dict):
                continue
            k = lbl.get("key")
            if not k:
                continue
            out[k] = {
                "values": list(lbl.get("values") or []),
                "unresolved": list(lbl.get("unresolvedValues") or []),
            }
    return out


def _derive_architecture_from_labels(labels: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, List[str]]]:
    """Best-effort architecture from ``usecase`` + ``general`` labels.

    NVIDIA's RSC payload does NOT carry explicit input/output_modalities
    fields. The closest signals are:

      * ``usecase`` values like ``"Text-to-Embedding"``,
        ``"Image Generation"``, ``"Text-to-Speech"``, ``"Image-to-Text"``,
        ``"Optical Character Recognition"``.
      * ``general`` values like ``"Vision Language Model"`` or
        ``"Multimodal MOE"``.

    Returns ``None`` when the labels give no actionable signal (this is
    common — many live endpoints have neither ``usecase`` nor a
    ``general`` value indicating modality).
    """
    usecases: List[str] = labels.get("usecase", {}).get("values", []) or []
    generals: List[str] = labels.get("general", {}).get("values", []) or []

    inputs: List[str] = []
    outputs: List[str] = []

    # Output modality inference from usecase.
    for uc in usecases:
        if uc == "Text-to-Embedding":
            outputs.append("embedding")
        elif uc == "Image Generation":
            outputs.append("image")
        elif uc == "Text-to-Speech":
            outputs.append("audio")
        elif uc == "Optical Character Recognition":
            outputs.append("text")
        # Chat / RAG / Synthetic-Data / Translation → text output (covered below
        # by the chat-from-playgroundType branch).
        # Image-to-Text → text output (covered below).

    # Chat inference from playgroundType (almost always "chat" on live data).
    playground_types: List[str] = labels.get("playgroundType", {}).get("values", []) or []
    if "chat" in playground_types:
        if "text" not in outputs:
            outputs.append("text")

    # Input modality inference from usecase prefix.
    for uc in usecases:
        if uc.startswith("Image-to-") or uc.startswith("Image-to"):
            if "image" not in inputs:
                inputs.append("image")

    # Vision hint from ``general`` (covers multimodal chat models that
    # don't have a vision-specific usecase).
    if "Vision Language Model" in generals and "image" not in inputs:
        inputs.append("image")

    # Multimodal input hint from ``general``.
    if "Multimodal MOE" in generals and "image" not in inputs:
        inputs.append("image")

    # Text-to-Image: text in, image out.
    if "Text-to-Image" in usecases:
        if "text" not in inputs:
            inputs.append("text")

    # Image Generation: text in (prompt), image out. Also a text-input
    # model — needs the same "text" prefix as Text-to-X usecases.
    if "Image Generation" in usecases:
        if "text" not in inputs:
            inputs.append("text")

    # Text-to-X usecases (Text-to-Embedding, Text-to-Speech, Text-to-Image)
    # implicitly have ``text`` input. Adding this explicitly so the
    # ``input`` field is accurate when the model takes text in and
    # produces some other modality out.
    if any(uc.startswith("Text-to-") for uc in usecases):
        if "text" not in inputs:
            inputs.append("text")

    # Dedupe while preserving order.
    seen = set()
    dedup_inputs = [s for s in inputs if not (s in seen or seen.add(s))]
    seen.clear()
    dedup_outputs = [s for s in outputs if not (s in seen or seen.add(s))]

    if not dedup_inputs and not dedup_outputs:
        return None
    return {"input": dedup_inputs, "output": dedup_outputs}


def _slugify_name(name: str) -> str:
    """Turn a human-readable ``displayName`` into a URL-safe slug.

    NVIDIA's catalog page exposes 38 free models but the pipeline
    used to write only 34. The 4 missing models all have spaces
    in their ``displayName`` ("Kumo Relational", "Active Speaker
    Detection", "Background Noise Removal", "Studio Voice") — the
    parser built ``model_id = "nvidia/Kumo Relational"`` and the
    validator (``_MODEL_ID_RE = re.compile(r"^\\S+$")``) rejected
    it for containing whitespace. The public catalog resolves
    these to URL slugs like ``nvidia/kumo-relational``; this
    helper mirrors that convention so the IDs the pipeline writes
    match the URLs a user can click through on build.nvidia.com.

    Slugification rules:
      * lowercase
      * any whitespace run → single hyphen
      * preserve alphanumerics, ``.`` and ``-`` (NVIDIA's URL
        slugs keep periods, e.g. ``deepseek-v4.1-flash``)
      * drop other punctuation (parens, slashes, etc.)
      * collapse consecutive hyphens and trim leading/trailing ``-``
    """
    if not name:
        return name
    slug = re.sub(r"\s+", "-", name.strip().lower())
    slug = re.sub(r"[^a-z0-9\.\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or name


def _normalize_model(obj: Dict) -> ModelEndpoint:
    """Convert raw ENDPOINT object to ModelEndpoint."""
    resource_id = obj.get("resourceId", "")
    name = obj.get("displayName", obj.get("name", ""))
    publisher = _extract_publisher(obj)
    if "/" in resource_id and publisher:
        # Live RSC: resourceId is the NIM namespace prefix
        # (e.g. "qc69jvmznzxy/deepseek-v4.1-flash"); the real org/name
        # pair comes from publisher + displayName. Use the publisher
        # as the org so model_ids stay consistent with HF/AMD
        # (``org/name`` shape). Slugify the displayName so values
        # containing spaces ("Kumo Relational" → "kumo-relational")
        # match the URL the public catalog exposes and survive the
        # model's validator regex (^\S+$).
        model_id = f"{publisher}/{_slugify_name(name)}" if name else resource_id
    elif "/" in resource_id:
        # Legacy / fallback: resourceId is already ``org/name``.
        model_id = resource_id
    else:
        # No org info anywhere — legacy synthesis uses the NIM
        # namespace prefix to avoid collisions.
        model_id = f"qc69jvmznzxy/{_slugify_name(name)}"

    labels = obj.get("labels", {})

    # --- NVIDIA special-case model_id correction ---
    # NIM's /v1/models endpoint exposes canonical ids using dot notation
    # for the GLM family (z-ai/glm-5.3, z-ai/glm-5.3-flash), not the
    # hyphenated form (z-ai/glm-5-3, z-ai/glm-5-3-flash) seen in the RSC payload.
    # As an explicit exception (not a general transformation) we normalize
    # these for the catalog/schema contract. The ValidateStage will still flag
    # them as missing from the NIM API and mark them invalid — this is expected
    # behavior per the MVP scope.
    if model_id.startswith("z-ai/glm-5-3"):
        model_id = model_id.replace("glm-5-3", "glm-5.3")

    labels_dict = _labels_to_dict(labels)

    # Read the legacy ``attributes`` block once
    attrs = obj.get("attributes", {})

    # Read the legacy ``attributes`` block once — it's the source of
    # CHAT_MODALITY / TOOL_CALLING signals in older RSC payloads. Modern
    # labels-driven payloads don't carry it. Stored under metadata
    # unchanged for back-compat with consumers that read metadata
    # directly.

    # Free detection: "Free Endpoint" in nimType.values → free=True.
    nim_values: List[str] = labels_dict.get("nimType", {}).get("values", []) or []
    free = "Free Endpoint" in nim_values

    # Capability detection from the legacy ``attributes`` shape
    # (``CHAT_MODALITY`` / ``TOOL_CALLING``). Live RSC has stopped
    # carrying these — see the label-driven architecture derivation
    # below for the current path.
    attrs = obj.get("attributes", {})
    capabilities = {}
    if isinstance(attrs, dict):
        if attrs.get("CHAT_MODALITY") == "text2textDiffusion":
            capabilities["chat"] = True
        if attrs.get("TOOL_CALLING") == "true":
            capabilities["tool_calling"] = True
    elif isinstance(attrs, list):
        for a in attrs:
            if isinstance(a, dict):
                if a.get("key") == "CHAT_MODALITY" and a.get("value") == "text2textDiffusion":
                    capabilities["chat"] = True
                if a.get("key") == "TOOL_CALLING" and a.get("value") == "true":
                    capabilities["tool_calling"] = True
    
    # Modern labels-driven path.
    usecases = labels_dict.get("usecase", {}).get("values", [])
    if any("translation" in uc.lower() or "translate" in uc.lower() for uc in usecases):
        capabilities["translation"] = True
    if any("embedding" in uc.lower() for uc in usecases):
        capabilities["embedding"] = True

    # Architecture derivation: try labels first (live data path),
    # then fall back to the capability-based legacy path.
    architecture = _derive_architecture_from_labels(labels_dict)
    if architecture is None:
        output_modalities: List[str] = []
        if capabilities.get("chat"):
            output_modalities.append("text")
        if capabilities.get("tool_calling"):
            if "text" not in output_modalities:
                output_modalities.append("text")
            output_modalities.append("tool_calls")
        architecture = {"input": [], "output": output_modalities} if output_modalities else None

    metadata: Dict[str, Any] = {}
    if "raw_obj" in obj:
        metadata["raw_obj"] = obj
    if "attributes" in obj:
        metadata["attributes"] = obj["attributes"]
    if "labels" in obj:
        if isinstance(obj["labels"], dict):
            meta_labels = {k: {"values": v.get("values", []), "unresolved": v.get("unresolvedValues", [])}
                           for k, v in obj["labels"].items()}
            metadata["labels"] = meta_labels
        elif isinstance(obj["labels"], list):
            meta_labels = {}
            for lbl in obj["labels"]:
                if not isinstance(lbl, dict) or "key" not in lbl:
                    continue
                meta_labels[lbl["key"]] = {
                    "values": lbl.get("values", []),
                    "unresolved": lbl.get("unresolvedValues", []),
                }
            metadata["labels"] = meta_labels

    # NVIDIA Build catalog URL — the human-readable source page for
    # the model. ``model_id`` is the canonical id (``<owner>/<name>``
    # or the legacy ``qc69jvmznzxy/<slug>`` shape). Both are valid
    # path components in the Build catalog. URL validation runs via
    # the shared ``data.models.source_url.normalize_source_url`` so an
    # unsafe scheme can never reach the public API or Browse UI.
    source_url = normalize_source_url(
        f"https://build.nvidia.com/{model_id}"
    )
    return ModelEndpoint(
        data_source="nvidia",
        provider="nvidia",
        model_id=model_id,
        free=free,
        # AMD/HF providers stamp fetched_at when they build the endpoint dict;
        # NVIDIA yields ModelEndpoint objects directly from parse_html, so
        # we set it here. Without this, ValidateStage rejects every NVIDIA
        # endpoint as 'fetched_at is not a datetime' (see validate.py).
        fetched_at=datetime.now(timezone.utc),
        name=name,
        description=obj.get("description", ""),
        source_url=source_url,
        # Legacy two-key capabilities shape — the normalize stage
        # (``data.process.normalize.normalize_capabilities``) replaces
        # this with the canonical 7-key boolean shape on its way
        # through. Provider adapters that bypass the normalize stage
        # (e.g. unit tests instantiating ModelEndpoint directly) still
        # see this legacy shape; downstream code reading
        # ``ep.capabilities`` via ``normalize_endpoints`` always sees
        # the canonical shape.
        capabilities=capabilities,
        architecture=architecture,
        # ``pricing`` and ``context_length`` are deliberately left as
        # ``None`` — NVIDIA's RSC payload does not expose per-token
        # prices or context window size. The schema contract treats
        # these as optional fields (set when the upstream actually
        # carries them; absent otherwise). Downstream code that needs
        # NVIDIA-specific context window info can fall back to
        # ``metadata.labels`` (some endpoints include ``general``
        # values that hint at model class) or the canonical catalog
        # page (https://build.nvidia.com/models/<slug>) which renders
        # per-model details in HTML.
        pricing=None,
        context_length=None,
        metadata=metadata,
    )


def parse_html(html: str) -> List[ModelEndpoint]:
    """Parse model list from HTML response.

    Layered strategy (defence-in-depth against upstream RSC shape changes):

      1. Try the RSC payload parser (``_extract_rsc_payload`` +
         ``_parse_objects``). When the upstream is serving React Server
         Components with embedded Flight JSON, this is the rich path:
         it captures display name, labels, description, architecture,
         capabilities, and publisher-derived ``model_id``.

      2. If the RSC path returns zero models but the HTML body is
         non-empty (i.e. we got a successful HTTP 200 that nonetheless
         contains no Flight chunks), fall back to
         :func:`_extract_models_from_static_html`. This path recovers
         the URL slugs (``/nvidia/<slug>``), adjacent display names,
         and the "Free Endpoint" badge from the rendered HTML. It
         captures less metadata (no description, no labels, no
         architecture derivation) but survives the upstream's move
         away from RSC payloads — which happened 2026-10.

    Audit context: per docs/tfi_open_source_security_audit.md §24, the
    pipeline must NEVER treat ``count = 0`` from a provider as a
    legitimate empty catalog without confirming the parser still
    recognised the response shape. The layered parser + a counter that
    names the path taken addresses that rule.
    """
    rsc = _extract_rsc_payload(html)
    raw_objects = _parse_objects(rsc)

    seen: Dict[str, ModelEndpoint] = {}
    for obj in raw_objects:
        ep = _normalize_model(obj)
        if ep.model_id not in seen:
            seen[ep.model_id] = ep

    endpoints = list(seen.values())
    if endpoints:
        return endpoints

    # Layered fallback — see docstring.
    if html and html.strip():
        fallback = _extract_models_from_static_html(html)
        if fallback:
            logger.warning(
                "nvidia RSC parser returned 0 endpoints on a non-empty "
                "response (%d bytes); falling back to static-HTML "
                "extractor which recovered %d endpoints",
                len(html), len(fallback),
            )
            return fallback

    # Convert fetched_at from None (caller will set before returning)
    return endpoints


def _extract_models_from_static_html(html: str) -> List[ModelEndpoint]:
    """Fallback parser: recover NVIDIA model slugs from the rendered HTML.

    Used when the RSC payload is absent (upstream moved away from Flight
    JSON). The rendered catalog page embeds ``<a href="/nvidia/<slug>">``
    linkboxes whose display name sits in an adjacent ``<span>``. Each
    card also carries a "Free Endpoint" badge that we use to set
    ``free=True``.

    Trade-offs vs the RSC path:
      * No description, no labels, no architecture derivation.
      * Display name recovery uses the literal inner text of the
        span, which is human-readable; ``_slugify_name`` produces the
        URL slug we store as the canonical ``model_id``.

    Returns:
        Deduplicated list of ``ModelEndpoint`` objects with
        ``provider='nvidia'``, ``data_source='nvidia'``,
        ``free=True`` (the upstream URL filter ``nimType=nim_type_preview``
        already restricts to free endpoints), and
        ``fetched_at`` set to ``now(UTC)``.
    """
    endpoints: List[ModelEndpoint] = []
    seen: Set[str] = set()
    # The rendered card structure (verified 2026-10):
    #   <a href="/nvidia/<slug>" ...> <span ...>Display Name</span> </a>
    for m in re.finditer(
        r'<a[^>]*href="/nvidia/([a-z0-9_\-\.]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.DOTALL,
    ):
        slug = m.group(1)
        if slug in seen:
            continue
        body = m.group(2)
        name_match = re.search(r'<span[^>]*>([^<]+)</span>', body)
        name = name_match.group(1).strip() if name_match else slug
        # URL filter already restricts to nim_type_preview (free).
        # Treat everything we see as free; the badged "Free Endpoint"
        # span is present in 100% of live samples but we don't depend
        # on it to avoid regressing on minor markup changes.
        seen.add(slug)
        # Static-HTML fallback uses ``nvidia/<slug>`` as the canonical
        # model_id. The NVIDIA Build URL mirrors that shape so the
        # public API can surface a working source link even when the
        # RSC parser is unavailable. Validation via normalize_source_url
        # is a defensive belt-and-braces; ``https://build.nvidia.com``
        # is hardcoded so the result is always safe.
        fallback_source_url = normalize_source_url(
            f"https://build.nvidia.com/nvidia/{slug}"
        )
        endpoints.append(
            ModelEndpoint(
                data_source='nvidia',
                provider='nvidia',
                model_id=f'nvidia/{slug}',
                free=True,
                fetched_at=datetime.now(timezone.utc),
                name=name,
                description=None,
                capabilities={},
                architecture=None,
                pricing=None,
                context_length=None,
                source_url=fallback_source_url,
                metadata={
                    'extraction': 'static_html_fallback',
                    'url_slug': slug,
                },
            )
        )
    return endpoints


def _build_headers() -> dict:
    """Build browser-like request headers for WAF compatibility.

    UA matches Chrome 153 stable on Linux x86_64 (released 2026-09-08).
    Chrome patch segments in the UA always serialize as ``.0.0.0``.
    """
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch_with_cooldown(session: Any, params: Dict[str, str], wait: int = WAIT_AFTER_202) -> str:
    """Fetch URL with WAF cooldown handling.

    Returns the HTML text after resolving any 202/403 responses.
    """
    for attempt in range(5):
        r = session.get(BASE_URL, params=params, timeout=30)
        if r.status_code == 200:
            return r.text
        if r.status_code == 202:
            time.sleep(wait)
            continue
        if r.status_code == 403:
            time.sleep(wait)
            continue
        break
    return ""


class NvidiaCatalogParser:
    """
    Parser for NVIDIA Build Catalog RSC payloads.

    Usage:
        parser = NvidiaCatalogParser()
        models = parser.fetch_and_parse({"nimType": "nim_type_preview"})
    """

    def __init__(self, session=None, timeout: int = 30):
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self, filters: Optional[Dict[str, str]] = None, page: Optional[int] = None) -> str:
        """Fetch catalog page HTML, handling WAF cookie establishment."""
        # Step 1: establish session/WAF cookies
        r = self.session.get(BASE_URL, timeout=self.timeout)
        if r.status_code != 200:
            return ""

        if filters or page is not None:
            params = {**(filters or {}), **({"page": str(page)} if page is not None else {})}
            r = fetch_with_cooldown(self.session, params)
            if r.status_code == 200:
                return r.text
            return ""

        return r.text

    def fetch_all_pages(
        self,
        filters: Optional[Dict[str, str]] = None,
        max_pages: int = 1,
    ) -> List[str]:
        """Fetch the filtered NVIDIA catalog as raw HTML.

        Single-page fetch. ``BASE_URL`` already includes
        ``pageSize=96&filters=nimType:nim_type_preview``, which
        constrains the upstream response to the entire free
        catalog (currently ~38 endpoints). Pagination is a no-op:
        upstream returns a footer-only page for ``page >= 2`` with
        no model data, and the loop would waste 4 HTTP requests
        per pipeline run. ``max_pages`` is kept for backwards
        compatibility but capped to 1 by default — raise it if
        the catalog ever exceeds 96 free models AND ``BASE_URL``’s
        ``pageSize`` is bumped accordingly.

        Use :func:`parse_nvidia_pages` to turn the HTML into
        ``ModelEndpoint`` objects.

        Args:
            filters: query filters, e.g. ``{"nimType": "nim_type_preview"}``.
            max_pages: maximum number of pages to fetch (default 1).

        Returns:
            List of HTML response bodies, one per page that returned
            non-empty content. Empty pages terminate the loop.
        """
        pages: List[str] = []
        for pg in range(1, max_pages + 1):
            params = {**(filters or {}), "page": str(pg)}
            html = fetch_with_cooldown(self.session, params)
            if html:
                pages.append(html)
            else:
                logger.warning(f"No data on page {pg}")
                break
            # No sleep on single-page mode. Pagination callers
            # (max_pages > 1) get a 1s inter-page pause to avoid
            # tripping the WAF.
            if max_pages > 1:
                time.sleep(1)
        return pages

    def get_all_pages(
        self,
        filters: Optional[Dict[str, str]] = None,
        max_pages: int = 5,
    ) -> List[str]:
        """Convenience: fetch all filtered pages (default preview/free).

        Equivalent to ``fetch_all_pages({"nimType": "nim_type_preview"}, max_pages)``.
        """
        return self.fetch_all_pages(
            {"nimType": "nim_type_preview"} if filters is None else filters,
            max_pages=max_pages,
        )

    def get_all_models(self) -> List[ModelEndpoint]:
        """Convenience: fetch all preview pages and parse them.

        Equivalent to ``parse_nvidia_pages(parser.get_all_pages())``.
        Kept for backwards compatibility — new code should call the
        fetch + parse functions directly.
        """
        return parse_nvidia_pages(self.get_all_pages())


def parse_nvidia_pages(
    html_pages: List[str],
) -> List[ModelEndpoint]:
    """Parse one or more NVIDIA catalog HTML pages into ``ModelEndpoint`` objects.

    Pure parser: takes raw HTML (typically the list returned by
    :meth:`NvidiaCatalogParser.fetch_all_pages`) and returns the
    canonical endpoint objects. No network access, no filtering —
    every endpoint the parser recognizes is returned, including
    "Run Anywhere" partner endpoints (``ModelEndpoint.free=False``).
    Use :func:`data.providers.free_filter.filter_nvidia_free` (or the
    ``FilterFreeStage`` pipeline stage) to keep only the free subset.

    Args:
        html_pages: HTML bodies, one per page.

    Returns:
        Concatenated, deduplicated list of endpoints across all pages.
        The ``ModelEndpoint.free`` flag is set by :func:`_normalize_model`
        based on ``labels.nimType.values contains "Free Endpoint"``;
        callers decide whether to keep the non-free rows.
    """
    endpoints: List[ModelEndpoint] = []
    for html in html_pages:
        endpoints.extend(parse_html(html))
    return endpoints


def fetch_catalog_page(filters: Optional[Dict[str, str]] = None) -> List[ModelEndpoint]:
    """Convenience: fetch, parse, and free-filter the NVIDIA catalog.

    Thin composition of three steps:

        parser = NvidiaCatalogParser()
        pages = parser.fetch_all_pages(filters)        # raw HTML
        endpoints = parse_nvidia_pages(pages)          # parse only
        return filter_nvidia_free(endpoints)           # drop non-free

    The free filter is applied here so existing callers that expect a
    free-only list keep working. Pipeline code should call the three
    functions separately (Fetch → Parse → FilterFreeStage) so the
    filter step is observable as its own pipeline stage.

    Returns:
        List of free ``ModelEndpoint`` objects.
    """
    from data.providers.free_filter import filter_nvidia_free

    parser = NvidiaCatalogParser()
    pages = parser.fetch_all_pages(filters)
    return filter_nvidia_free(parse_nvidia_pages(pages))


if __name__ == "__main__":
    import sys
    parser = NvidiaCatalogParser()

    if len(sys.argv) > 1 and sys.argv[1] == "all":
        models = parser.get_all_models()
        print(f"Total unique models: {len(models)}")
    elif len(sys.argv) > 1 and sys.argv[1] == "preview":
        models = parser.fetch_and_parse({"nimType": "nim_type_preview"})
        print(f"Preview-filtered models: {len(models)}")
    else:
        models = parser.fetch_and_parse()
        print(f"Unfiltered models: {len(models)}")

    for m in models:
        free_mark = " [FREE]" if m.free else ""
        print(f"  {m.model_id:<55} pub={m.name:<12}{free_mark}")