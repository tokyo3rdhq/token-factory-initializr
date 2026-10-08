"""Helpers for canonical source URLs on model records.

This module owns the URL safety contract: only `https:` URLs are
admitted, and a small set of unsafe / surprising schemes is
rejected. URL construction is centralised here so the source
adapters do not need to know the per-provider URL shape and the
public API / Browse UI do not need to know how each adapter
populated the value.

Per docs/tfi_model_source_url.md §8:

    * Accept only absolute https: URLs.
    * Reject javascript:, data:, file:, and other unsafe schemes.
    * Preserve valid URLs without unnecessary rewriting.
    * No server-side URL fetching.
"""

from __future__ import annotations

import re
from typing import Optional

# Anchored to scheme + netloc + path. No fragment (#) or query (?) is
# required, but both are accepted when present. Trailing slashes are
# preserved as-written. We do NOT enforce a particular host list —
# third-party platforms appear and disappear; the safety contract
# is the scheme, not the destination.
_HTTPS_URL_RE = re.compile(
    r"^https://"           # scheme (case-insensitive via the check below)
    r"[^\s/?#]+"           # netloc (host [+ :port])
    r"(?:[/?#][^\s]*)?$",  # optional path / query / fragment
    re.IGNORECASE,
)

# Schemes that look like URLs but are never legitimate human source
# pages. Caught at the boundary so a single rejection point protects
# the projection + Browse UI.
_BLOCKED_SCHEMES = frozenset({
    "javascript",
    "data",
    "vbscript",
    "file",
    "about",
    "blob",
})


def is_safe_source_url(value: object) -> bool:
    """True iff ``value`` is an absolute https URL with a netloc.

    Tolerates None / empty string / non-string by returning False.
    No URL fetching, no DNS, no validation beyond the syntactic check
    the spec asks for (§8).
    """
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate:
        return False
    if " " in candidate or "\t" in candidate or "\n" in candidate:
        # Whitespace anywhere means it is not a real URL.
        return False
    if not _HTTPS_URL_RE.match(candidate):
        return False
    # Belt-and-braces: even if the regex matched, verify the scheme
    # explicitly so a future tweak to the regex can't let an
    # unsafe scheme through.
    scheme = candidate.split("://", 1)[0].lower()
    if scheme != "https":
        return False
    if scheme in _BLOCKED_SCHEMES:
        return False
    return True


def normalize_source_url(value: object) -> Optional[str]:
    """Return the canonical source_url for a record, or None.

    Centralises the "is this URL safe to surface" decision so every
    layer (source adapter, normalize stage, projection, Browse UI)
    reaches the same conclusion without duplicating the check.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if is_safe_source_url(candidate):
        return candidate
    return None
