"""Integration tests for ``data.tests.download_fixtures``.

These tests verify the fixture-refresh path itself: the download
functions run, hit the live APIs, write the expected ``_live``-suffixed
files, and report non-``ok`` status when the network is unreachable.
They are marked ``integration`` and skipped unless
``RUN_INTEGRATION_TESTS=1`` is set, matching the rest of the
integration suite.

Why have tests for a test-fixture downloader?
    The downloader is the single source of truth for what the offline
    test suites see. If a provider changes its payload shape (e.g. AMD
    renames ``detail_url``, NVIDIA drops a cookie header) and the
    downloader silently writes a fixture the parsers can no longer
    read, every offline test would then start failing in confusing
    ways. Pinning the downloader to round-trip through the live API
    catches that drift at refresh time, not at the next pytest run.

Why ``_live`` suffix?
    The repository ships curated fixtures (``nvidia_html.html``,
    ``amd_bootstrap.json`` etc.) that exercise specific edge cases
    (deduplication, Run Anywhere partners, paid HF providers). The
    live downloader writes to ``<name>_live.<ext>`` instead, so a
    refresh can never trample the curated fixtures. The tests below
    assert that contract.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_HERE_DIR = _HERE.parent
# Allow running `pytest data/tests/` from repo root without setting PYTHONPATH.
if str(_HERE_DIR.parents[1]) not in sys.path:
    sys.path.insert(0, str(_HERE_DIR.parents[1]))

from data.tests.download_fixtures import (
    DEFAULT_LIVE_SUFFIX,
    DownloadResult,
    _apply_suffix,
    _find_dotenv,
    _is_proxy_configured,
    _is_reachable,
    _load_dotenv,
    download_all,
    download_amd,
    download_huggingface,
    download_nvidia,
)


FIXTURES = _HERE_DIR / "fixtures"


def _host_reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


# ---------------------------------------------------------------------------
# Offline unit tests for the downloader machinery itself
# ---------------------------------------------------------------------------


def test_apply_suffix_inserts_before_extension():
    """Default suffix lands between stem and extension."""
    assert _apply_suffix("nvidia_html.html", "_live") == "nvidia_html_live.html"
    assert _apply_suffix("amd_bootstrap.json", "_live") == "amd_bootstrap_live.json"
    assert (
        _apply_suffix("amd_detail_MiMo.json", "_live")
        == "amd_detail_MiMo_live.json"
    )


def test_apply_suffix_empty_is_noop():
    """Empty suffix must produce the original filename unchanged."""
    assert _apply_suffix("nvidia_html.html", "") == "nvidia_html.html"


def test_apply_suffix_handles_no_extension():
    """Files without an extension just get the suffix appended."""
    assert _apply_suffix("README", "_live") == "README_live"


def test_default_live_suffix_is_live():
    """The default suffix must be ``_live`` — the safety contract."""
    assert DEFAULT_LIVE_SUFFIX == "_live"


def test_load_dotenv_populates_missing_env_vars(tmp_path, monkeypatch):
    """An explicit ``.env`` file populates env vars that aren't yet set."""
    monkeypatch.delenv("TFI_TEST_DOTENV_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# leading comment\n"
        "\n"
        "TFI_TEST_DOTENV_KEY=hello-from-dotenv\n"
        "TFI_TEST_DOTENV_TAIL=trailing\n",
        encoding="utf-8",
    )
    loaded = _load_dotenv(env_file)
    assert loaded == env_file
    assert os.environ["TFI_TEST_DOTENV_KEY"] == "hello-from-dotenv"
    assert os.environ["TFI_TEST_DOTENV_TAIL"] == "trailing"


def test_load_dotenv_does_not_clobber_real_env(tmp_path, monkeypatch):
    """A pre-set env var wins over the ``.env`` value."""
    monkeypatch.setenv("TFI_TEST_DOTENV_KEY", "from-real-env")
    env_file = tmp_path / ".env"
    env_file.write_text("TFI_TEST_DOTENV_KEY=from-dotenv\n", encoding="utf-8")
    _load_dotenv(env_file)
    assert os.environ["TFI_TEST_DOTENV_KEY"] == "from-real-env"


def test_load_dotenv_skips_comments_and_blanks(tmp_path, monkeypatch):
    """Comment lines and blank lines must not produce env entries."""
    monkeypatch.delenv("TFI_TEST_BLANK_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# header comment\n"
        "\n"
        "   \n"
        "TFI_TEST_BLANK_KEY=value\n",
        encoding="utf-8",
    )
    _load_dotenv(env_file)
    assert os.environ["TFI_TEST_BLANK_KEY"] == "value"
    assert "TFI_TEST_BLANK_KEY_HEADER" not in os.environ


def test_load_dotenv_returns_none_when_missing(tmp_path):
    """A missing ``.env`` is a no-op (returns None), not an error.

    We only exercise the explicit-path branch here — the auto-detect
    branch is covered by ``test_find_dotenv_prefers_cwd``, and it
    would otherwise pick up the real ``data/.env`` in this sandbox.
    """
    assert _load_dotenv(tmp_path / "does-not-exist.env") is None


def test_find_dotenv_prefers_cwd(tmp_path, monkeypatch):
    """When both ``./.env`` and ``data/.env`` exist, cwd wins."""
    cwd_env = tmp_path / ".env"
    cwd_env.write_text("TFI_TEST_FIND_KEY=cwd\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    found = _find_dotenv()
    assert found is not None
    assert found.resolve() == cwd_env.resolve()


def test_download_huggingface_loads_env_file(tmp_path, monkeypatch):
    """``download_huggingface`` auto-loads the supplied ``.env`` before
    checking reachability, so a developer who has SOCKS5_PROXY set in
    ``.env`` doesn't need to export it manually.

    The test points env_file at a custom path with a known proxy URL;
    the proxy is then consulted by the HF provider's request call
    (we only assert that the value made it into ``os.environ``).
    """
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "SOCKS5_PROXY=socks5h://127.0.0.1:9999\n", encoding="utf-8"
    )
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)

    # Force the reachable probe to fail so we exit before hitting the
    # network — we only care that .env was loaded.
    monkeypatch.setattr(
        "data.tests.download_fixtures._is_reachable",
        lambda host, port=443, timeout=5.0: False,
    )
    # Mock the actual fetch so it raises instantly (instead of waiting
    # on a 30-second requests retry loop when no real proxy is running).
    import requests as real_requests

    def fake_get(*_a, **_kw):
        raise real_requests.exceptions.ConnectionError("synthetic unreachable")

    monkeypatch.setattr(real_requests, "get", fake_get)

    r = download_huggingface(tmp_path, env_file=env_file, reachable_check=False)
    # reachable_check=False skips the probe, so we attempt the fetch
    # and hit URLError/RuntimeError. Either way, .env must have loaded.
    assert os.environ.get("SOCKS5_PROXY") == "socks5h://127.0.0.1:9999"
    # And the fetch must have failed (not skipped) because the fake
    # probe was bypassed — verifying env_file was actually consulted.
    assert r.status == "failed"


def test_download_huggingface_env_file_nonexistent_is_silent(tmp_path, monkeypatch):
    """Pointing env_file at a missing path must not crash."""
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
    monkeypatch.setattr(
        "data.tests.download_fixtures._is_reachable",
        lambda host, port=443, timeout=5.0: False,
    )
    # Without SOCKS5_PROXY the HF fetcher falls back to urllib — mock
    # it to raise immediately instead of waiting on a 30-second direct
    # connect retry.
    import urllib.error

    def fake_urlopen(*_a, **_kw):
        raise urllib.error.URLError("synthetic unreachable")

    monkeypatch.setattr(
        "data.providers.huggingface.urllib.request.urlopen", fake_urlopen
    )

    r = download_huggingface(
        tmp_path,
        env_file=tmp_path / "missing.env",
        reachable_check=False,
    )
    # The fetch path runs (reachable_check=False), sees no proxy, and
    # fails on the unreachable host. Critically, it must not raise.
    assert r.status == "failed"


def test_is_proxy_configured_true_when_set(monkeypatch):
    """A populated ``SOCKS5_PROXY`` is detected as configured."""
    monkeypatch.setenv("SOCKS5_PROXY", "socks5h://127.0.0.1:7897")
    assert _is_proxy_configured() is True


def test_is_proxy_configured_false_when_unset(monkeypatch):
    """An unset / empty ``SOCKS5_PROXY`` is treated as not configured."""
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
    assert _is_proxy_configured() is False
    monkeypatch.setenv("SOCKS5_PROXY", "   ")
    assert _is_proxy_configured() is False


def test_download_huggingface_skips_probe_when_proxy_set(tmp_path, monkeypatch):
    """When ``SOCKS5_PROXY`` is set, the direct reachability probe must
    be skipped — otherwise we'd report "skipped" even though the proxy
    can reach the host. A misconfigured proxy still surfaces as a
    failed fetch (we only assert the *probe* is bypassed here).
    """
    monkeypatch.setenv("SOCKS5_PROXY", "socks5h://127.0.0.1:7897")
    probe_calls: list[str] = []

    def fake_probe(host, port=443, timeout=5.0):
        probe_calls.append(host)
        return False  # would normally cause a skip

    monkeypatch.setattr(
        "data.tests.download_fixtures._is_reachable", fake_probe
    )
    # Mock the actual HTTP call so it raises instantly (instead of
    # waiting on a 30-second requests retry loop when no real proxy
    # is running). The new HF fetcher uses ``requests``, not urllib.
    import requests as real_requests

    def fake_get(*_a, **_kw):
        raise real_requests.exceptions.ConnectionError("synthetic network failure")

    monkeypatch.setattr(real_requests, "get", fake_get)

    r = download_huggingface(tmp_path, env_file=tmp_path / "missing.env")

    # The probe must NOT have been called for router.huggingface.co.
    assert probe_calls == [], (
        f"reachability probe was called even with proxy configured: {probe_calls}"
    )
    # The fetch was attempted (probe was bypassed) and failed because
    # we injected a ConnectionError above.
    assert r.status == "failed"
    assert any("synthetic network failure" in e for e in r.errors)


def test_download_huggingface_still_probes_without_proxy(tmp_path, monkeypatch):
    """When no proxy is configured, the probe still runs and a failure
    produces a clean ``skipped`` result (the existing behaviour)."""
    monkeypatch.delenv("SOCKS5_PROXY", raising=False)
    monkeypatch.setattr(
        "data.tests.download_fixtures._is_reachable",
        lambda host, port=443, timeout=5.0: False,
    )
    r = download_huggingface(tmp_path, env_file=tmp_path / "missing.env")
    assert r.status == "skipped"
    assert any("not reachable" in e for e in r.errors)


def test_download_all_reports_every_requested_provider():
    """Each provider in the selection must produce a result, even on failure.

    Calls download_all with all three providers but bypasses the network
    probes (``reachable_check=False``). The HF provider fails immediately
    in this environment (router.huggingface.co is not reachable), but
    AMD and NVIDIA still get a real fetch attempt. Either way, every
    requested provider must show up in the result list.
    """
    results = download_all(
        FIXTURES,
        providers=["nvidia", "amd", "huggingface"],
        live_suffix="_live",
    )
    assert {r.provider for r in results} == {"nvidia", "amd", "huggingface"}
    for r in results:
        assert isinstance(r, DownloadResult)
        assert r.status in {"ok", "failed", "skipped"}


def test_download_all_unknown_provider_returns_failed_result():
    """An unknown provider name must surface as a failed result, not crash."""
    results = download_all(
        FIXTURES,
        providers=["definitely-not-a-provider"],
        live_suffix="_live",
    )
    assert len(results) == 1
    r = results[0]
    assert r.provider == "definitely-not-a-provider"
    assert r.status == "failed"
    assert r.errors and "unknown provider" in r.errors[0]


def test_download_all_writes_only_live_suffixed_files(tmp_path):
    """Live-suffix downloads must NEVER touch the curated fixture names.
    A successful or skipped run still must not write to the curated
    paths. (Run AMD/NVIDIA writes below will exercise the success case;
    here we only assert the filename contract.)
    """
    curated = {
        "nvidia_html.html",
        "amd_bootstrap.json",
        "amd_detail_ragdoll.json",
        "amd_detail_mistral.json",
        "huggingface_router.json",
    }
    # Pre-create all curated files in tmp_path; after a download attempt
    # their mtime must be unchanged.
    for name in curated:
        (tmp_path / name).write_text("curated")
    before = {n: (tmp_path / n).stat().st_mtime for n in curated}

    download_all(
        tmp_path,
        providers=["nvidia", "amd", "huggingface"],
        live_suffix="_live",
    )

    for name, mtime in before.items():
        assert (tmp_path / name).stat().st_mtime == mtime, (
            f"download_fixtures must not write to curated fixture {name}"
        )


def test_download_all_live_suffixed_files_point_under_fixtures_dir():
    """Successful downloads must report paths inside the requested directory."""
    results = download_all(FIXTURES, live_suffix="_live")
    for r in results:
        if r.status != "ok":
            continue
        for rel in r.files:
            assert rel.endswith("_live.html") or rel.endswith("_live.json")
            assert (FIXTURES / rel).exists(), f"{rel} not written under {FIXTURES}"


def test_download_all_empty_suffix_overwrites_curated(tmp_path):
    """``live_suffix=""`` must write to the curated fixture names.

    This is the explicit "I'm refreshing the canonical fixtures on
    purpose" path. Network is unreachable in this env so we can't
    assert file content, but we *can* assert that on success the
    curated name is the one returned.
    """
    # Stub each provider's download function so we don't hit the network.
    from data.tests import download_fixtures as dl

    def fake_nvidia(fixtures_dir, *, live_suffix, force=True, reachable_check=True):
        r = DownloadResult(provider="nvidia", status="ok")
        name = dl._apply_suffix("nvidia_html.html", live_suffix)
        (fixtures_dir / name).write_text("<html/>")
        r.files.append(name)
        r.bytes = (fixtures_dir / name).stat().st_size
        return r

    def fake_amd(fixtures_dir, *, live_suffix, max_details=5, force=True, reachable_check=True):
        r = DownloadResult(provider="amd", status="ok")
        name = dl._apply_suffix("amd_bootstrap.json", live_suffix)
        (fixtures_dir / name).write_text("{}")
        r.files.append(name)
        r.bytes = (fixtures_dir / name).stat().st_size
        return r

    originals = (dl.download_nvidia, dl.download_amd, dl.download_huggingface)
    dl.download_nvidia = fake_nvidia
    dl.download_amd = fake_amd
    try:
        results = download_all(tmp_path, providers=["nvidia", "amd"], live_suffix="")
        assert [r.files[0] for r in results] == ["nvidia_html.html", "amd_bootstrap.json"]
        assert (tmp_path / "nvidia_html.html").exists()
        assert (tmp_path / "amd_bootstrap.json").exists()
    finally:
        dl.download_nvidia, dl.download_amd = originals[:2]


# ---------------------------------------------------------------------------
# Live integration tests (network required)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_download_nvidia():
    """Real NVIDIA API: write a fresh ``nvidia_html_live.html`` with RSC chunks."""
    if not _host_reachable("build.nvidia.com"):
        pytest.skip("build.nvidia.com not reachable from this environment")
    r = download_nvidia(FIXTURES, live_suffix="_live", reachable_check=False)
    assert r.status == "ok", r.errors
    assert "nvidia_html_live.html" in r.files
    html = (FIXTURES / "nvidia_html_live.html").read_text(encoding="utf-8")
    assert "self.__next_f.push" in html, "captured HTML has no RSC chunks"


@pytest.mark.integration
def test_integration_download_amd():
    """Real AMD API: write bootstrap + at least one detail page."""
    if not _host_reachable("developer.amd.com.cn"):
        pytest.skip("developer.amd.com.cn not reachable from this environment")
    r = download_amd(FIXTURES, live_suffix="_live", max_details=3, reachable_check=False)
    assert r.status == "ok", r.errors
    assert "amd_bootstrap_live.json" in r.files
    bootstrap = (FIXTURES / "amd_bootstrap_live.json").read_text(encoding="utf-8")
    assert bootstrap.startswith("{") and bootstrap.endswith("}")
    detail_files = [f for f in r.files if f.startswith("amd_detail_") and f.endswith("_live.json")]
    assert detail_files, "expected at least one AMD detail fixture"


@pytest.mark.integration
def test_integration_download_huggingface():
    """Real HF API: write the raw router JSON. May skip in environments where
    ``router.huggingface.co`` is not directly reachable (set
    ``SOCKS5_PROXY`` to override)."""
    if not _host_reachable("router.huggingface.co"):
        pytest.skip("router.huggingface.co not reachable from this environment")
    r = download_huggingface(FIXTURES, live_suffix="_live", reachable_check=False)
    assert r.status == "ok", r.errors
    assert "huggingface_router_live.json" in r.files
    payload = (FIXTURES / "huggingface_router_live.json").read_text(encoding="utf-8")
    assert payload.startswith("{") and '"data"' in payload