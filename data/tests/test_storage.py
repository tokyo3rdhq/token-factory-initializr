"""Unit tests for Cloudflare KV storage adapter."""

from __future__ import annotations

import io
import os
from unittest.mock import Mock, patch

import pytest

from data.storage.cloudflare_kv import KVStorage, store_snapshot, load_snapshot


def _BytesIO(b: bytes) -> io.BytesIO:
    return io.BytesIO(b)


# ---------------------------------------------------------------------------
# KVStorage.from_env
# ---------------------------------------------------------------------------


def test_kvstorage_from_env_raises_when_missing_account_id():
    """from_env() raises RuntimeError if any required env var is unset."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_KV_NAMESPACE_ID"):
            KVStorage.from_env()


def test_kvstorage_from_env_raises_when_missing_api_token():
    """from_env() raises RuntimeError if CLOUDFLARE_API_TOKEN is unset."""
    with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "test-account"}, clear=True):
        with pytest.raises(RuntimeError, match="CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_KV_NAMESPACE_ID"):
            KVStorage.from_env()


def test_kvstorage_from_env_raises_when_missing_namespace_id():
    """from_env() raises RuntimeError if CLOUDFLARE_KV_NAMESPACE_ID is unset."""
    with patch.dict(
        os.environ,
        {"CLOUDFLARE_ACCOUNT_ID": "a", "CLOUDFLARE_API_TOKEN": "b"},
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="CLOUDFLARE_KV_NAMESPACE_ID"):
            KVStorage.from_env()


def test_kvstorage_from_env_returns_instance_when_all_set():
    """from_env() returns KVStorage when all three env vars are present."""
    with patch.dict(
        os.environ,
        {
            "CLOUDFLARE_ACCOUNT_ID": "test-account",
            "CLOUDFLARE_API_TOKEN": "test-token",
            "CLOUDFLARE_KV_NAMESPACE_ID": "test-ns",
        },
        clear=True,
    ):
        kv = KVStorage.from_env()
        assert isinstance(kv, KVStorage)
        assert kv.account_id == "test-account"
        assert kv.api_token == "test-token"
        assert kv.namespace_id == "test-ns"


def test_kvstorage_from_env_strips_whitespace():
    """Trailing whitespace/newlines (from GitHub Secrets UI paste) must
    not leak into URL paths or auth headers."""
    with patch.dict(
        os.environ,
        {
            "CLOUDFLARE_ACCOUNT_ID": "  test-account  \n",
            "CLOUDFLARE_API_TOKEN": "test-token\n",
            "CLOUDFLARE_KV_NAMESPACE_ID": "\ttest-ns",
        },
        clear=True,
    ):
        kv = KVStorage.from_env()
        assert kv.account_id == "test-account"
        assert kv.api_token == "test-token"
        assert kv.namespace_id == "test-ns"
        # And the URL it constructs must not contain control characters.
        url = kv._url("any:key")
        for ch in ("\n", "\r", "\t"):
            assert ch not in url, f"control char {ch!r} leaked into URL: {url!r}"


# ---------------------------------------------------------------------------
# KVStorage.put_snapshot / get_snapshot (with mocked backend)
# ---------------------------------------------------------------------------


class FakeKV(KVStorage):
    """In-memory fake for KVStorage methods."""

    def __init__(self):
        self.account_id = "fake-account"
        self.api_token = "fake-token"
        self._store: dict[str, dict] = {}

    def get(self, key: str):
        return self._store.get(key)

    def put(self, key: str, value: dict, ttl: int | None = None):
        self._store[key] = value


def test_kvstorage_put_snapshot_writes_non_empty_data():
    """put_snapshot writes data when list is non-empty."""
    from data.storage.cloudflare_kv import model_key

    kv = FakeKV()
    models = [{"model_id": "test-model", "provider": "amd", "free": True}]
    kv.put_snapshot("amd", models)
    assert kv._store[model_key("amd")] == {"provider": "amd", "models": models}


def test_kvstorage_put_snapshot_refuses_empty_data():
    """put_snapshot does NOT write when list is empty (fail-safe rule)."""
    from data.storage.cloudflare_kv import model_key

    kv = FakeKV()
    kv.put_snapshot("amd", [])
    assert model_key("amd") not in kv._store


def test_kvstorage_get_snapshot_returns_stored_data():
    """get_snapshot returns the previously stored snapshot."""
    kv = FakeKV()
    models = [{"model_id": "test-model", "provider": "amd", "free": True}]
    kv.put_snapshot("amd", models)
    result = kv.get_snapshot("amd")
    assert result == {"provider": "amd", "models": models}


def test_kvstorage_get_snapshot_returns_none_when_missing():
    """get_snapshot returns None when key does not exist."""
    kv = FakeKV()
    result = kv.get_snapshot("amd")
    assert result is None


def test_kvstorage_snapshot_key_names():
    """KEYS dict provides expected key naming convention (all tfi:-prefixed)."""
    from data.storage.cloudflare_kv import KEYS, KEY_PREFIX

    assert KEY_PREFIX == "tfi:"
    assert KEYS["latest"] == "tfi:models:latest"
    assert KEYS["nvidia"] == "tfi:models:nvidia:latest"
    assert KEYS["amd"] == "tfi:models:amd:latest"
    assert KEYS["huggingface"] == "tfi:models:huggingface:latest"
    assert KEYS["manifest"] == "tfi:manifest:latest"
    # Both dated_manifest and snapshot (legacy alias) produce the same form.
    assert KEYS["dated_manifest"]("2026-09-24") == "tfi:manifest:2026-09-24"
    assert KEYS["snapshot"]("2026-09-24") == "tfi:manifest:2026-09-24"


def test_model_key_helper():
    """model_key(provider) builds a fully prefixed key."""
    from data.storage.cloudflare_kv import model_key

    assert model_key("amd") == "tfi:models:amd:latest"
    assert model_key("nvidia") == "tfi:models:nvidia:latest"
    assert model_key("huggingface") == "tfi:models:huggingface:latest"
    # Custom providers are accepted (we don't validate names — that's the
    # stage's responsibility).
    assert model_key("openrouter") == "tfi:models:openrouter:latest"


def test_manifest_key_helper():
    """manifest_key() and manifest_key(date) build the two variants."""
    from data.storage.cloudflare_kv import manifest_key

    assert manifest_key() == "tfi:manifest:latest"
    assert manifest_key("2026-09-24") == "tfi:manifest:2026-09-24"
    assert manifest_key(None) == "tfi:manifest:latest"


# ---------------------------------------------------------------------------
# store_snapshot / load_snapshot (higher-level helpers)
# ---------------------------------------------------------------------------


def test_store_snapshot_groups_by_provider():
    """store_snapshot groups endpoints by provider and stores each."""
    kv = FakeKV()
    endpoints = [
        {"provider": "amd", "model_id": "a", "free": True},
        {"provider": "amd", "model_id": "b", "free": True},
        {"provider": "nvidia", "model_id": "c", "free": True},
    ]
    store_snapshot(kv, endpoints)

    amd_snapshot = kv.get_snapshot("amd")
    nvidia_snapshot = kv.get_snapshot("nvidia")

    assert amd_snapshot is not None
    assert len(amd_snapshot["models"]) == 2
    assert nvidia_snapshot is not None
    assert len(nvidia_snapshot["models"]) == 1


def test_store_snapshot_skips_empty_provider_group():
    """store_snapshot does not write empty provider groups (guard)."""
    kv = FakeKV()
    endpoints = []  # all empty
    store_snapshot(kv, endpoints)
    assert kv._store == {}


def test_load_snapshot_returns_none_when_missing():
    """load_snapshot returns None when snapshot does not exist."""
    kv = FakeKV()
    result = load_snapshot(kv, "amd")
    assert result is None


def test_load_snapshot_returns_data_when_present():
    """load_snapshot returns snapshot data when present."""
    kv = FakeKV()
    kv.put_snapshot("amd", [{"model_id": "test", "provider": "amd"}])
    result = load_snapshot(kv, "amd")
    assert result == {"provider": "amd", "models": [{"model_id": "test", "provider": "amd"}]}


# ---------------------------------------------------------------------------
# KVStorage HTTP transport (real Cloudflare REST API, mocked urllib)
# ---------------------------------------------------------------------------


def _resp(status: int, body: bytes = b""):
    """Build a context-manager Mock mimicking urllib's response."""
    r = Mock()
    r.status = status
    r.read = Mock(return_value=body)
    r.__enter__ = Mock(return_value=r)
    r.__exit__ = Mock(return_value=False)
    return r


def _http_error(status: int, body: bytes = b""):
    """Build a real urllib.error.HTTPError with the given body."""
    import urllib.error as _ue

    return _ue.HTTPError(url="https://api.cloudflare", code=status, msg="", hdrs={}, fp=_BytesIO(body))


def _make_kv(**overrides) -> KVStorage:
    """Build a KVStorage with safe defaults for unit tests."""
    defaults = {
        "account_id": "test-account",
        "api_token": "test-token",
        "namespace_id": "test-ns",
        "max_retries": 2,
        "base_delay": 0.001,  # keep tests fast
        "timeout": 5,
    }
    defaults.update(overrides)
    return KVStorage(**defaults)


def test_kvstorage_put_sends_correct_url_and_auth():
    """put() must hit PUT /values/{key} with Bearer auth."""
    from data.storage.cloudflare_kv import model_key

    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200, b'{"success":true}')
        kv.put(model_key("amd"), {"provider": "amd", "models": []})
    args = mock_urlopen.call_args[0]
    req = args[0]
    assert req.method == "PUT"
    expected_key = "tfi%3Amodels%3Aamd%3Alatest"
    assert req.full_url.endswith(f"/values/{expected_key}"), req.full_url
    assert req.headers["Authorization"] == "Bearer test-token"
    # Body must be valid JSON, content-type text/plain (Cloudflare accepts this).
    import json as _json
    assert _json.loads(req.data.decode()) == {"provider": "amd", "models": []}
    assert req.headers["Content-type"] == "text/plain"


def test_kvstorage_put_sends_ttl_header_when_specified():
    """When ttl is set, the request includes a TTL header.

    urllib normalizes header names to title-case, so we check both forms.
    """
    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200, b'{"success":true}')
        kv.put("x", {"a": 1}, ttl=300)
    req = mock_urlopen.call_args[0][0]
    items = dict(req.header_items())
    ttl = items.get("TTL") or items.get("Ttl") or items.get("ttl")
    assert ttl == "300"


def test_kvstorage_put_rejects_oversize_payload():
    """Values exceeding Cloudflare's 25 MiB KV limit must fail loudly."""
    kv = _make_kv()
    huge = {"x": "a" * (26 * 1024 * 1024)}
    from data.storage.cloudflare_kv import KVError
    with pytest.raises(KVError, match="exceeds 25 MiB"):
        kv.put("x", huge)


def test_kvstorage_get_returns_decoded_dict():
    from data.storage.cloudflare_kv import model_key

    kv = _make_kv()
    body = b'{"provider":"amd","models":[{"model_id":"m:1"}]}'
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200, body)
        result = kv.get(model_key("amd"))
    assert result == {"provider": "amd", "models": [{"model_id": "m:1"}]}


def test_kvstorage_get_returns_none_on_404():
    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(404)
        result = kv.get("does:not:exist")
    assert result is None


def test_kvstorage_get_wraps_non_json_value():
    """If KV holds non-JSON bytes, get() returns {'raw': ...}."""
    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200, b"plain text")
        result = kv.get("some:key")
    assert result == {"raw": "plain text"}


def test_kvstorage_get_wraps_non_object_json():
    """JSON primitives (e.g. numbers, strings) come back as {'value': ...}."""
    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200, b"42")
        result = kv.get("some:key")
    assert result == {"value": 42}


def test_kvstorage_retries_on_500_then_succeeds():
    """5xx errors must be retried with exponential backoff."""
    kv = _make_kv(max_retries=3, base_delay=0.001)
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen, \
         patch("data.storage.cloudflare_kv.time.sleep"):
        mock_urlopen.side_effect = [
            _http_error(500, b'{"errors":[{"code":1,"message":"oops"}]}'),
            _http_error(500),
            _resp(200, b'{"ok":true}'),
        ]
        result = kv.get("k")
    assert result == {"ok": True}
    assert mock_urlopen.call_count == 3


def test_kvstorage_retries_on_429():
    """429 (rate limited) must be retried."""
    kv = _make_kv(max_retries=2, base_delay=0.001)
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen, \
         patch("data.storage.cloudflare_kv.time.sleep"):
        mock_urlopen.side_effect = [_http_error(429), _resp(200, b'{"ok":1}')]
        result = kv.get("k")
    assert result == {"ok": 1}


def test_kvstorage_gives_up_after_max_retries():
    """After max_retries transient errors, KVTransientError is raised."""
    from data.storage.cloudflare_kv import KVTransientError
    kv = _make_kv(max_retries=2, base_delay=0.001)
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen, \
         patch("data.storage.cloudflare_kv.time.sleep"):
        mock_urlopen.side_effect = _http_error(500)
        with pytest.raises(KVTransientError, match="exhausted"):
            kv.get("k")
    assert mock_urlopen.call_count == 2


def test_kvstorage_does_not_retry_4xx():
    """Hard 4xx errors (e.g. 400 bad request) raise immediately, no retry."""
    from data.storage.cloudflare_kv import KVError
    kv = _make_kv(max_retries=3, base_delay=0.001)
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(400, b'{"errors":[{"code":10028,"message":"bad limit"}]}')
        with pytest.raises(KVError, match="400"):
            kv.put("k", {"a": 1})
    assert mock_urlopen.call_count == 1


def test_kvstorage_error_message_does_not_echo_token():
    """Even when Cloudflare echoes back the token in an error body, our
    exception message must only contain the structured errors[].message,
    not the raw body."""
    from data.storage.cloudflare_kv import KVError
    kv = _make_kv()
    body = b'{"errors":[{"code":10000,"message":"Authentication error"}]}'
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(403, body)
        with pytest.raises(KVError) as excinfo:
            kv.put("k", {"a": 1})
    msg = str(excinfo.value)
    assert "Authentication error" in msg
    assert "Bearer test-token" not in msg
    assert "test-token" not in msg


def test_kvstorage_url_encodes_colons_in_keys():
    """Keys contain colons (e.g. tfi:models:amd:latest) — must be percent-encoded.

    The path portion ``/values/{key}`` must encode every key colon as %3A.
    The ``https://`` scheme and ``/accounts/{acct}/storage/...`` host/path
    parts are allowed to keep their raw colons.
    """
    from urllib.parse import urlparse
    from data.storage.cloudflare_kv import model_key

    kv = _make_kv()
    with patch("data.storage.cloudflare_kv.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _resp(200)
        kv.get(model_key("amd"))
    url = mock_urlopen.call_args[0][0].full_url

    # The encoded key segment must be present in the URL.
    assert "tfi%3Amodels%3Aamd%3Alatest" in url

    # The last path segment is the key; it must contain no raw colons.
    parsed = urlparse(url)
    key_segment = parsed.path.rsplit("/", 1)[-1]
    assert ":" not in key_segment, f"raw colons leaked into key segment: {key_segment!r}"