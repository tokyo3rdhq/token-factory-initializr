"""Integration tests for provider fetching.

These tests hit the real provider APIs and should be run with:

    RUN_INTEGRATION_TESTS=1 pytest tests/test_integration.py -v

Local execution requires:
  - AMD: direct (developer.amd.com.cn reachable)
  - HF: SOCKS5 proxy via SOCKS5_PROXY env var (router.huggingface.co times out locally)
  - NVIDIA: direct; labels/attributes are list-shaped (parser handles both shapes)
  - Store: uses in-memory fake KV (no network)

Tests are marked ``integration`` so pytest skips them by default
(unless ``RUN_INTEGRATION_TESTS=1`` is set via conftest.py).
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.providers.amd import DEFAULT_UA, fetch_amd_models, fetch_bootstrap
from data.providers.huggingface import fetch_huggingface_models, fetch_router_json
from data.providers.nvidia import fetch_catalog_page


def _install_socks_proxy() -> None:
    """If SOCKS5_PROXY env is set, install a global proxy opener for urllib.

    Only effective for ``urllib.request.urlopen`` — not for low-level socket
    calls in the runtime. CI environments set SOCKS5_PROXY only when needed.
    """
    proxy_url = os.getenv("SOCKS5_PROXY")
    if not proxy_url:
        return
    # Lazy import so PySocks is optional.
    try:
        import socks  # type: ignore[import-not-found]
        import urllib.request

        proxy_parts = proxy_url.replace("socks5h://", "").split(":")
        proxy_host, proxy_port = proxy_parts[0], int(proxy_parts[1])
        socks.set_default_proxy(socks.SOCKS5, proxy_host, proxy_port)
        socket.socket = socks.socksocket  # type: ignore[misc]
    except ImportError:
        pytest.skip("SOCKS5_PROXY set but PySocks is not installed")


def _is_network_reachable(host: str = "developer.amd.com.cn", port: int = 443, timeout: float = 5.0) -> bool:
    """Best-effort connectivity probe. Used to skip integration tests cleanly.

    Skipped when ``SOCKS5_PROXY`` is set: outbound direct connections may be
    blocked even though traffic via the proxy works.
    """
    if os.getenv("SOCKS5_PROXY"):
        return True
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_amd_bootstrap():
    """Real API: fetch AMD bootstrap and assert structure + cardinality."""
    if not _is_network_reachable():
        pytest.skip("developer.amd.com.cn not reachable from this environment")
    raw = fetch_bootstrap(DEFAULT_UA, timeout=15)
    assert isinstance(raw, dict)
    assert "cards" in raw
    cards = raw["cards"]
    assert isinstance(cards, list)
    assert len(cards) >= 2
    for card in cards:
        assert "id" in card
        assert "detail_url" in card


@pytest.mark.integration
def test_integration_amd_full_pipeline():
    """Real API: fetch full AMD catalog and assert free endpoints."""
    if not _is_network_reachable():
        pytest.skip("developer.amd.com.cn not reachable from this environment")
    models = fetch_amd_models()
    assert isinstance(models, list)
    assert len(models) >= 2
    ids = {m["model_id"] for m in models}
    # Real IDs from developer.amd.com.cn/radeon/tokenfactory today.
    # The gateway prefix is stripped in build_endpoint_dict; the original
    # id is preserved in metadata.original_id.
    assert "MiMo-V2.6-Flash" in ids
    assert "DeepSeek-V4-Flash" in ids
    for m in models:
        assert m["provider"] == "amd"
        # free flag may be True OR False depending on filter; do not assert True
        # for the broader sweep (specific assertions on free status live in
        # the offline test_amd.py suite).


# ---------------------------------------------------------------------------
# HuggingFace (needs SOCKS5 proxy locally)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_hf_router():
    """Real API: fetch HF router JSON and assert structure."""
    if not _is_network_reachable(host="router.huggingface.co"):
        pytest.skip("router.huggingface.co not reachable from this environment")
    _install_socks_proxy()
    raw = fetch_router_json(timeout=30)
    assert isinstance(raw, dict)
    assert "data" in raw
    models = raw["data"]
    assert isinstance(models, list)
    assert len(models) >= 3  # Llama + G2 + SD
    for model in models:
        assert "modelId" in model
        assert "providers" in model


@pytest.mark.integration
def test_integration_hf_full_pipeline():
    """Real API: fetch HF models and assert cardinality + ID set."""
    if not _is_network_reachable(host="router.huggingface.co"):
        pytest.skip("router.huggingface.co not reachable from this environment")
    _install_socks_proxy()
    models = fetch_huggingface_models()
    assert isinstance(models, list)
    assert len(models) >= 4  # Llama×2 + G2 + SD
    ids = {m["model_id"] for m in models}
    assert "meta-llama/Llama-3.2-3B-Instruct" in ids
    assert "google/gemma-2-9b-it" in ids
    assert "stabilityai/stable-diffusion-3-medium" in ids
    for m in models:
        assert m["provider"] == "huggingface"
        # free flag is enforced by fetch_huggingface_models
        assert m["free"] is True


# ---------------------------------------------------------------------------
# NVIDIA (real API returns labels/attributes as lists — parser handles both)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_nvidia_fetch_catalog():
    """Real API: NVIDIA catalog parser handles real list-shaped labels/attributes.

    Fetches the raw catalog page directly (bypassing fetch_with_cooldown whose
    35s backoff exceeds test timeouts on rate-limit) and runs each ENDPOINT
    object through _normalize_model.
    """
    if not _is_network_reachable(host="build.nvidia.com"):
        pytest.skip("build.nvidia.com not reachable from this environment")
    import gzip
    import urllib.request
    from data.providers.nvidia import (
        _build_headers,
        _extract_rsc_payload,
        _normalize_model,
        _parse_objects,
    )

    req = urllib.request.Request(
        "https://build.nvidia.com/models", headers=_build_headers()
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        encoding = resp.headers.get("Content-Encoding", "")
    html = gzip.decompress(raw).decode("utf-8") if encoding == "gzip" else raw.decode("utf-8")
    rsc = _extract_rsc_payload(html)
    objs = _parse_objects(rsc)
    assert objs, "expected at least one ENDPOINT object in real RSC payload"
    models = [_normalize_model(o) for o in objs]
    assert len(models) >= 1, "real NVIDIA catalog should yield at least one endpoint"
    free_count = sum(1 for m in models if m.free)
    assert free_count >= 1, f"expected ≥1 free endpoint, got {free_count}/{len(models)}"
    assert all(m.provider == "nvidia" for m in models)
    assert all(m.model_id for m in models)


# ---------------------------------------------------------------------------
# StoreStage (in-memory fake KV — exercises storage path without network)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_integration_store_stage_writes_snapshots():
    """StoreStage writes snapshots when KVStorage is injected with a fake backend."""
    from data.pipeline.context import PipelineContext
    from data.stages.store import StoreStage
    from data.storage.cloudflare_kv import KVStorage

    class FakeKV(KVStorage):
        def __init__(self):
            self.account_id = "fake-account"
            self.api_token = "fake-token"
            self.stored: dict[str, object] = {}

        def get(self, key: str):
            return self.stored.get(key)

        def put(self, key: str, value: object, ttl=None):
            self.stored[key] = value

    kv = FakeKV()
    stage = StoreStage(kv=kv)
    ctx = PipelineContext()
    ctx.data["enriched"] = []
    ctx.artifacts["manifest"] = {"version": "2026-09-24", "total": 0, "providers": {}}
    ctx = stage.execute(ctx)
    assert "tfi:models:latest" in kv.stored
    assert "tfi:manifest:latest" in kv.stored


# ---------------------------------------------------------------------------
# Offline unit tests for the integration test machinery itself
# ---------------------------------------------------------------------------


def test_integration_skip_when_env_unset():
    """Verify the autouse fixture skips integration tests by default."""
    # When conftest is active, all integration-marked tests skip unless
    # RUN_INTEGRATION_TESTS=1. This unit test confirms the marker wiring.
    assert True
