"""Tests for the canonical source URL contract.

Per docs/tfi_model_source_url.md §8: only absolute https URLs are
admitted, and a small set of unsafe / surprising schemes is
rejected. This is the single test file for that contract — every
provider-adapter-level test (test_nvidia.py, test_huggingface.py,
test_amd.py) covers its own URL derivation shape, but the universal
safety contract lives here."""

from __future__ import annotations

import pytest

from data.models.source_url import is_safe_source_url, normalize_source_url


class TestIsSafeSourceUrl:
    """The pure safety predicate. Drives both the source-adapter
    layer and any future reader that needs to validate URLs."""

    def test_https_url_with_host_and_path_passes(self):
        assert is_safe_source_url("https://huggingface.co/foo/bar")

    def test_https_url_with_query_passes(self):
        assert is_safe_source_url("https://build.nvidia.com/models?page=1")

    def test_https_url_with_fragment_passes(self):
        assert is_safe_source_url("https://example.com/path#section")

    def test_https_url_with_port_passes(self):
        assert is_safe_source_url("https://localhost:8788/api/v1/models")

    def test_https_url_with_subdomain_passes(self):
        assert is_safe_source_url("https://api.deepinfra.com/v1/openai")

    def test_uppercase_https_passes(self):
        # Scheme is matched case-insensitively.
        assert is_safe_source_url("HTTPS://example.com/path")

    # --- rejected schemes ---

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "vbscript:msgbox(1)",
            "about:blank",
            "blob:https://x.com/y",
        ],
    )
    def test_unsafe_schemes_rejected(self, url: str) -> None:
        assert not is_safe_source_url(url), f"expected {url!r} to be rejected"

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/path",  # not https
            "ftp://example.com/path",
            "ws://example.com",
            "file:/etc/passwd",
        ],
    )
    def test_non_https_schemes_rejected(self, url: str) -> None:
        assert not is_safe_source_url(url), f"expected {url!r} to be rejected"

    def test_empty_string_rejected(self) -> None:
        assert not is_safe_source_url("")

    def test_none_rejected(self) -> None:
        assert not is_safe_source_url(None)  # type: ignore[arg-type]

    def test_non_string_rejected(self) -> None:
        # Numeric / dict / list inputs must be tolerated and rejected
        # rather than raising — callers use this in a tight loop.
        assert not is_safe_source_url(42)
        assert not is_safe_source_url(["https://x.com"])
        assert not is_safe_source_url({"url": "https://x.com"})

    def test_whitespace_containing_string_rejected(self) -> None:
        # Internal whitespace is a heuristic for "this is not a
        # real URL" — strings with newlines / tabs in them are
        # not valid URLs.
        assert not is_safe_source_url("https://x.com\nattack")
        assert not is_safe_source_url("https://x.com\ty")
        assert not is_safe_source_url("https://x.com y")

    def test_relative_path_rejected(self) -> None:
        assert not is_safe_source_url("/path/only")

    def test_scheme_only_rejected(self) -> None:
        assert not is_safe_source_url("https://")
        assert not is_safe_source_url("https:/x")

    def test_string_with_leading_whitespace_stripped(self) -> None:
        # normalize_source_url strips; is_safe_source_url on the
        # stripped form should pass.
        assert is_safe_source_url("  https://x.com  ".strip())


class TestNormalizeSourceUrl:
    """Convenience wrapper. Returns the canonical URL or None."""

    def test_returns_canonical_string(self) -> None:
        assert (
            normalize_source_url("https://huggingface.co/foo/bar")
            == "https://huggingface.co/foo/bar"
        )

    def test_strips_whitespace(self) -> None:
        assert (
            normalize_source_url("  https://x.com  ") == "https://x.com"
        )

    def test_returns_none_for_unsafe(self) -> None:
        assert normalize_source_url("javascript:alert(1)") is None

    def test_returns_none_for_non_string(self) -> None:
        assert normalize_source_url(None) is None
        assert normalize_source_url(42) is None
