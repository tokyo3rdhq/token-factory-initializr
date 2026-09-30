"""Cloudflare KV storage adapter.

REST API:
  GET    /client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/{key}
  PUT    /client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/{key}
  DELETE /client/v4/accounts/{account_id}/storage/kv/namespaces/{ns_id}/values/{key}

Auth: ``Authorization: Bearer <CLOUDFLARE_API_TOKEN>``.

KV stores opaque string values up to 25 MiB per key. We serialize dicts as
JSON; on read we parse the JSON back. Values that aren't valid JSON are
returned as ``{"raw": "<value>"}`` so callers can still observe the data.

Retry policy:
  - 5xx, 429     → exponential backoff up to 3 attempts
  - 4xx (except 429) → no retry; raise immediately

The adapter never logs or echoes the API token. On failure, error messages
include the HTTP status and Cloudflare error code, but never the response
body verbatim (it may echo back the token on some auth errors).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

# All KV keys share this prefix so the namespace can also host unrelated
# keys without collision (e.g. when sharing a namespace with another app
# during development). Prefix is appended to every key automatically —
# callers never type it.
KEY_PREFIX = "tfi:"

# KV key names used by the pipeline. Stable across deploys.
# Use the ``model_key`` / ``manifest_key`` helpers below; don't hand-roll
# these strings elsewhere.
KEYS: dict[str, str | object] = {
    "latest": "tfi:models:latest",
    "nvidia": "tfi:models:nvidia:latest",
    "amd": "tfi:models:amd:latest",
    "huggingface": "tfi:models:huggingface:latest",
    "manifest": "tfi:manifest:latest",
    "dated_manifest": lambda date: f"tfi:manifest:{date}",
    # Legacy alias retained for one cycle so old callers don't break.
    # New code should use ``dated_manifest``.
    "snapshot": lambda date: f"tfi:manifest:{date}",
}


def model_key(provider: str) -> str:
    """Return the canonical KV key for a per-provider models snapshot.

    Example: model_key("amd") -> "tfi:models:amd:latest"

    .. deprecated::
        Retained for back-compat with the pre-data_source key namespace.
        New code MUST use :func:`provider_models_key` and the
        ``(data_source, provider)`` namespace — the legacy
        ``tfi:models:<provider>:latest`` keys are no longer an active
        source of truth and will be reclaimed on the next successful
        publish run that deletes providers no longer in the desired
        state.
    """
    return f"{KEY_PREFIX}models:{provider}:latest"


def manifest_key(date: str | None = None) -> str:
    """Return the KV key for the manifest.

    Args:
        date: ISO date string ``YYYY-MM-DD``. If None, returns the
            ``manifest:latest`` key (overwritten on every run).
            If provided, returns the dated key retained per run.

    Example:
        manifest_key()              -> "tfi:manifest:latest"
        manifest_key("2026-09-24")  -> "tfi:manifest:2026-09-24"
    """
    if date is None:
        return f"{KEY_PREFIX}manifest:latest"
    return f"{KEY_PREFIX}manifest:{date}"


# ---------------------------------------------------------------------------
# New (data_source, provider) namespace — see
# docs/data_source_provider_refactor.md §2 / §3.
# ---------------------------------------------------------------------------


def provider_models_key(data_source: str, provider: str) -> str:
    """Return the KV key for a per-(data_source, provider) model catalog.

    This is the source of truth going forward. The legacy
    ``tfi:models:<provider>:latest`` key is no longer written by the
    pipeline; readers should use ``provider_manifest_key(data_source)``
    to enumerate providers, then ``provider_models_key`` to fetch each.

    Example:
        provider_models_key("nvidia", "nvidia")           -> "tfi:models:nvidia:nvidia:latest"
        provider_models_key("huggingface", "zai-org")     -> "tfi:models:huggingface:zai-org:latest"
    """
    return f"{KEY_PREFIX}models:{data_source}:{provider}:latest"


def provider_manifest_key(data_source: str) -> str:
    """Return the KV key for a data-source provider manifest.

    The manifest contains the set of currently-active inference
    providers for that data source. Consumers MUST enumerate the
    manifest before reading model catalogs — per the refactor
    invariant (§4) every active
    ``tfi:models:{data_source}:{provider}:latest`` key MUST be present
    in this manifest.

    Example:
        provider_manifest_key("huggingface") -> "tfi:providers:huggingface:latest"
    """
    return f"{KEY_PREFIX}providers:{data_source}:latest"


# Centralize the list of data sources that participate in the
# pipeline. Used by the snapshot stage to ensure every source emits a
# provider manifest, even if it had zero providers in the run (so
# consumers can distinguish "no providers" from "no data yet").
KNOWN_DATA_SOURCES: tuple[str, ...] = ("nvidia", "amd", "huggingface")

# Cloudflare REST API base (v4).
_API_BASE = "https://api.cloudflare.com/client/v4"

# Default retry budget for transient errors.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds; exponential backoff
DEFAULT_TIMEOUT = 30  # seconds per HTTP call


class KVError(Exception):
    """Raised on non-retryable KV errors (4xx other than 429)."""


class KVTransientError(Exception):
    """Raised on retryable KV errors (5xx, 429, network)."""

    def __init__(self, message: str, *, attempts: int = 1):
        super().__init__(message)
        self.attempts = attempts


class KVStorage:
    """Wrap Cloudflare KV access with retry and fallback.

    Construct directly or via :meth:`from_env` (reads
    ``CLOUDFLARE_ACCOUNT_ID``, ``CLOUDFLARE_API_TOKEN``,
    ``CLOUDFLARE_KV_NAMESPACE_ID``).
    """

    def __init__(
        self,
        account_id: str,
        api_token: str,
        namespace_id: str,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.account_id = account_id
        self.api_token = api_token
        self.namespace_id = namespace_id
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "KVStorage":
        """Build a KVStorage from env vars. Raises RuntimeError if any is missing.

        Values are stripped of surrounding whitespace; Cloudflare IDs and
        tokens are short hex / alphanumeric strings that never legitimately
        contain newlines. This guards against trailing-newline artifacts
        introduced when secrets are pasted into GitHub Secrets / .env files
        via UI textareas.
        """
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID", "").strip()
        if not account_id or not api_token or not namespace_id:
            raise RuntimeError(
                "CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and "
                "CLOUDFLARE_KV_NAMESPACE_ID must be set for KV storage"
            )
        return cls(account_id, api_token, namespace_id)

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _url(self, key: str) -> str:
        # Cloudflare keys can contain colons but no special chars that need
        # percent-encoding for the path. URL-encode just to be safe.
        encoded = urllib.parse.quote(key, safe="")
        return f"{_API_BASE}/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}/values/{encoded}"

    def _auth_header(self) -> str:
        return f"Bearer {self.api_token}"

    def _request(
        self,
        method: str,
        key: str,
        body: Optional[bytes] = None,
        extra_headers: Optional[dict] = None,
    ) -> tuple[int, bytes]:
        """Single HTTP attempt. Returns (status_code, raw_response_bytes).

        Raises KVTransientError on retryable conditions, KVError on hard 4xx.
        """
        url = self._url(key)
        headers = {"Authorization": self._auth_header()}
        if body is not None:
            headers["Content-Type"] = "text/plain"
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read() if exc.fp else b""
            if status == 404:
                # Key not found — return 404 + empty body for the caller to detect.
                return status, b""
            if status == 429 or 500 <= status < 600:
                # Try to extract a sanitized error message (never include the response body
                # verbatim — auth errors can echo back the token).
                safe_msg = self._safe_error_message(raw)
                raise KVTransientError(
                    f"Cloudflare KV {status} on {method} {key}: {safe_msg}"
                ) from exc
            safe_msg = self._safe_error_message(raw)
            raise KVError(
                f"Cloudflare KV {status} on {method} {key}: {safe_msg}"
            ) from exc
        except urllib.error.URLError as exc:
            raise KVTransientError(
                f"Cloudflare KV network error on {method} {key}: {exc.reason}"
            ) from exc

    @staticmethod
    def _safe_error_message(raw: bytes) -> str:
        """Extract Cloudflare error messages without leaking the request body.

        Auth errors sometimes echo back the token in the response body, so we
        only emit the structured ``errors[].message`` fields.
        """
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "<unparseable>"
        msgs = []
        for e in parsed.get("errors", []) if isinstance(parsed, dict) else []:
            if isinstance(e, dict):
                code = e.get("code", "")
                msg = e.get("message", "")
                msgs.append(f"[{code}] {msg}")
        return "; ".join(msgs) or "<no error message>"

    def _request_with_retry(
        self,
        method: str,
        key: str,
        body: Optional[bytes] = None,
        extra_headers: Optional[dict] = None,
    ) -> tuple[int, bytes]:
        """Retry wrapper around _request. Raises after exhausting retries."""
        attempts = 0
        last_exc: Optional[Exception] = None
        while attempts < self.max_retries:
            try:
                return self._request(method, key, body=body, extra_headers=extra_headers)
            except KVTransientError as exc:
                attempts += 1
                last_exc = exc
                if attempts < self.max_retries:
                    delay = self.base_delay * (2 ** (attempts - 1))
                    logger.warning(
                        "Cloudflare KV %s %s attempt %d/%d failed: %s; retrying in %.2fs",
                        method, key, attempts, self.max_retries, exc, delay,
                    )
                    time.sleep(delay)
                else:
                    break
        raise KVTransientError(
            f"Cloudflare KV {method} {key} exhausted {self.max_retries} retries",
            attempts=attempts,
        ) from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[dict[str, Any]]:
        """Retrieve a value from KV. Returns None if the key is missing.

        Values are JSON-decoded into dicts. Non-JSON values are returned as
        ``{"raw": "<value>"}`` so callers can still observe the bytes.
        """
        status, raw = self._request_with_retry("GET", key)
        if status == 404:
            return None
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
        if not isinstance(decoded, dict):
            # KV stored something other than an object — wrap for callers.
            return {"value": decoded}
        return decoded

    def put(
        self,
        key: str,
        value: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Store a dict at ``key``. Serializes via JSON.

        Args:
            key: The KV key (e.g. ``tfi:models:amd:latest``). The ``tfi:``
                prefix is applied by the caller via :func:`model_key` /
                :func:`manifest_key` helpers.
            value: Dict to serialize; must be JSON-encodable.
            ttl: Optional expiration in seconds (≥ 60). Cloudflare ignores
                values smaller than 60.
        """
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(body) > 25 * 1024 * 1024:
            raise KVError(f"value for {key} exceeds 25 MiB KV limit ({len(body)} bytes)")
        extra: dict[str, str] = {}
        if ttl is not None:
            extra["TTL"] = str(int(ttl))
        self._request_with_retry("PUT", key, body=body, extra_headers=extra)

    def delete(self, key: str) -> None:
        """Delete a key from KV.

        Idempotent: a 404 from the backend is treated as success because
        ``delete`` is naturally convergent — the publisher calls it to
        ensure a key is gone, and it already being gone is a no-op.
        """
        try:
            self._request_with_retry("DELETE", key)
        except KVError as exc:
            # Non-retryable backend errors include 404 in some
            # configurations; treat the missing-key case as success.
            if "404" in str(exc):
                logger.info("delete: key %s already absent", key)
                return
            raise

    def get_snapshot(self, provider: str) -> Optional[dict[str, Any]]:
        """Get the latest snapshot for a provider.

        .. deprecated::
            Use :meth:`get_provider_models` with the
            ``(data_source, provider)`` namespace.
        """
        return self.get(model_key(provider))

    def put_snapshot(self, provider: str, data: list[dict[str, Any]]) -> None:
        """Persist a provider snapshot (never overwrite with empty data).

        .. deprecated::
            Use :meth:`put_provider_models` with the
            ``(data_source, provider)`` namespace. Empty-data refusal
            is preserved there too, but the publisher's
            ``reconcile → publish`` flow owns removal of stale
            providers explicitly rather than relying on this
            fail-safe as a side effect.
        """
        if not data:
            logger.warning(f"Refusing to store empty snapshot for {provider}")
            return
        self.put(model_key(provider), {"provider": provider, "models": data})

    # ------------------------------------------------------------------
    # New (data_source, provider) API — see refactor doc §19.
    # ------------------------------------------------------------------

    def get_provider_manifest(self, data_source: str) -> Optional[dict[str, Any]]:
        """Read the provider manifest for a data source.

        Returns ``None`` if the manifest has never been written.
        """
        return self.get(provider_manifest_key(data_source))

    def put_provider_manifest(
        self,
        data_source: str,
        manifest: dict[str, Any],
    ) -> None:
        """Write the provider manifest for a data source.

        Caller is expected to publish the manifest LAST, after all
        corresponding model keys have been reconciled (refactor §10).
        """
        self.put(provider_manifest_key(data_source), manifest)

    def get_provider_models(
        self,
        data_source: str,
        provider: str,
    ) -> Optional[dict[str, Any]]:
        """Read a per-(data_source, provider) model catalog."""
        return self.get(provider_models_key(data_source, provider))

    def put_provider_models(
        self,
        data_source: str,
        provider: str,
        models: list[dict[str, Any]],
    ) -> None:
        """Write a per-(data_source, provider) model catalog.

        Empty-data refusal mirrors the legacy ``put_snapshot`` rule:
        the publisher treats an empty ``models`` list as "this provider
        should be removed from the manifest" and triggers a DELETE in
        the reconcile stage rather than overwriting with an empty
        payload here. Callers that really need to wipe a catalog should
        use :meth:`delete_provider_models` directly.
        """
        if not models:
            logger.warning(
                "Refusing to store empty model catalog for "
                "(%s, %s); use delete_provider_models instead",
                data_source,
                provider,
            )
            return
        self.put(
            provider_models_key(data_source, provider),
            {
                "data_source": data_source,
                "provider": provider,
                "models": models,
            },
        )

    def delete_provider_models(self, data_source: str, provider: str) -> None:
        """Delete a per-(data_source, provider) model catalog.

        Provider deletion is a meaningful destructive operation — see
        refactor doc §20 (the publisher must only call this when the
        provider is genuinely absent from the desired snapshot).
        """
        self.delete(provider_models_key(data_source, provider))


# ----------------------------------------------------------------------
# Module-level helpers (preserved for backward compatibility)
# ----------------------------------------------------------------------


def store_snapshot(kv: KVStorage, endpoints: list[Any]) -> None:
    """Persist per-provider snapshots for a normalized endpoint list.

    Never overwrites valid data with an empty snapshot (fail-safe rule).
    """
    by_provider: dict[str, list[dict]] = {}
    for ep in endpoints:
        d = ep.__dict__ if hasattr(ep, "__dict__") else dict(ep)
        by_provider.setdefault(d.get("provider", "unknown"), []).append(d)
    for provider, models in by_provider.items():
        kv.put_snapshot(provider, models)


def load_snapshot(kv: KVStorage, provider: str) -> Optional[dict[str, Any]]:
    """Load the latest snapshot for a provider. Returns None if missing."""
    return kv.get_snapshot(provider)