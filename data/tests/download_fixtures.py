"""Download raw provider fixtures for offline tests.

Each provider exports its catalog through HTTP. This script pulls the
**unfiltered** raw payloads (HTML / JSON) and writes them under
``data/tests/fixtures/`` so the offline test suites can replay them
without network access.

Why "raw / unfiltered"?
    The downstream free-only filter (``filter_free_providers`` for HF,
    the ``free_only=True`` flag on the NVIDIA parser, the ``status ==
    "free"`` check in AMD ``build_endpoint_dict``) is itself part of what
    we want to *test*. Capturing the raw payload lets unit tests assert
    both the filter behaviour and the parser's handling of the
    un-filtered shape (e.g. NVIDIA's "Run Anywhere" partner endpoints).

Naming:
    By default the script writes to ``<name>_live.<ext>`` (e.g.
    ``nvidia_html_live.html``, ``amd_bootstrap_live.json``) so the
    **curated** fixtures already in the repository (``nvidia_html.html``
    etc., which exercise specific edge cases) are never overwritten.
    Pass ``--live-suffix ""`` to write into the curated names instead
    — useful when refreshing the canonical fixtures on purpose.

Usage:
    # Refresh live fixtures (default; safe: never touches curated files)
    cd data && python -m tests.download_fixtures

    # Refresh a single provider
    cd data && python -m tests.download_fixtures --provider nvidia
    cd data && python -m tests.download_fixtures --provider amd
    cd data && python -m tests.download_fixtures --provider huggingface

    # Refresh AMD with more detail pages (cap defaults to 5)
    cd data && python -m tests.download_fixtures --provider amd --max-details 10

    # Overwrite curated fixtures (use with care)
    cd data && python -m tests.download_fixtures --live-suffix ""

    # Use a non-default .env file (or skip with --env-file /dev/null)
    cd data && python -m tests.download_fixtures --env-file path/to/.env

Proxy / .env handling:
    ``router.huggingface.co`` is unreachable from some networks, so the
    HF provider is normally routed through ``SOCKS5_PROXY``. The HF
    downloader auto-loads ``./.env`` or ``data/.env`` (whichever exists)
    so a developer who has set ``SOCKS5_PROXY`` in their local
    ``data/.env`` doesn't need to export it on the command line.
    Real environment variables always win over ``.env`` entries, so
    CI secrets and explicit shell exports are honoured.

Exit codes:
    0 — all requested providers succeeded
    1 — at least one provider failed (details printed)

Failure handling:
    Each provider runs independently. A network failure for one provider
    does not block the others; the failed provider is reported with the
    underlying error and the script continues.

Network prerequisites:
    NVIDIA   — build.nvidia.com          (publicly reachable)
    AMD      — developer.amd.com.cn      (publicly reachable)
    HuggingFace — router.huggingface.co  (unreachable from some networks;
                set ``SOCKS5_PROXY=socks5h://host:port`` to route through
                a local SOCKS5 proxy, mirroring the runtime behaviour)
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Make `data.*` importable when run as a plain script (`python
# tests/download_fixtures.py`) without `python -m`.
_HERE = Path(__file__).resolve()
_HERE_DIR = _HERE.parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data.providers import amd as amd_mod
from data.providers import huggingface as hf_mod
from data.providers import nvidia as nvidia_mod


# Default suffix; pass ``_live""`` (empty) via CLI to overwrite curated.
DEFAULT_LIVE_SUFFIX = "_live"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class DownloadResult:
    """Outcome of a single provider download.

    Attributes:
        provider: provider key (``nvidia`` / ``amd`` / ``huggingface``).
        status:   ``"ok"`` if every requested file was written,
                  ``"skipped"`` if the provider is unreachable but the
                  failure is recoverable, ``"failed"`` otherwise.
        files:    relative paths (under fixtures_dir) of written files.
        errors:   human-readable error messages, one per failure.
        bytes:    total bytes written across all files.
    """

    provider: str
    status: str = "ok"
    files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "files": list(self.files),
            "errors": list(self.errors),
            "bytes": self.bytes,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (write to .tmp, then rename).

    A partial write (crash, disk full) must never leave a half-written
    fixture — downstream tests would silently load the truncated version.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _is_reachable(host: str, port: int = 443, timeout: float = 5.0) -> bool:
    """Best-effort TCP probe. False on any error."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _is_proxy_configured() -> bool:
    """True when ``SOCKS5_PROXY`` is set in the environment.

    Used by the HF downloader to decide whether the *direct* TCP
    reachability probe is meaningful: if a SOCKS5 proxy is configured,
    direct probes always fail (the host is unreachable without the
    proxy), so the probe is skipped and the actual fetch — which the
    HF provider routes through the proxy — is allowed to run.
    """
    return bool(os.getenv("SOCKS5_PROXY", "").strip())


def _find_dotenv() -> Optional[Path]:
    """Locate a ``.env`` file, preferring cwd over the bundled data dir.

    Search order:
        1. ``./.env`` (cwd) — supports running from repo root
        2. ``data/.env``  — supports running as ``cd data && python -m ...``

    Returns the first existing match, or ``None``.
    """
    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate.is_file():
        return cwd_candidate
    data_candidate = _HERE_DIR.parent / ".env"
    if data_candidate.is_file():
        return data_candidate
    return None


def _load_dotenv(path: Optional[Path] = None) -> Optional[Path]:
    """Load ``KEY=VALUE`` pairs from ``.env`` into ``os.environ``.

    Behaviour:
        * Existing real environment variables always win (we never
          overwrite them — so a CI-set ``SOCKS5_PROXY`` survives a
          ``.env`` entry from a developer).
        * Lines starting with ``#`` and blank lines are skipped.
        * Inline ``# comments`` are NOT supported; values containing
          ``#`` (rare in practice) would be truncated. The
          ``data/.env.example`` and ``data/.env`` files in this repo
          don't use them, so this trade-off keeps the parser tiny.

    Args:
        path: explicit ``.env`` path; when ``None``, autodetects via
              :func:`_find_dotenv`.

    Returns:
        The path that was loaded, or ``None`` when no ``.env`` exists.
    """
    env_path = path or _find_dotenv()
    if env_path is None or not env_path.is_file():
        return None
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Don't clobber real env vars (CI secrets, shell exports, etc.)
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def _apply_suffix(name: str, suffix: str) -> str:
    """Insert ``suffix`` before the file extension.

    ``_apply_suffix("nvidia_html.html", "_live")`` → ``"nvidia_html_live.html"``
    ``_apply_suffix("amd_detail_MiMo.json", "_live")`` → ``"amd_detail_MiMo_live.json"``
    ``_apply_suffix("foo", "")`` → ``"foo"`` (no-op when suffix is empty)
    """
    if not suffix:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        return name + suffix
    return f"{stem}{suffix}.{ext}"


def _slugify_amd_model_id(model_id: str) -> str:
    """Make a filesystem-safe label from an AMD model id like
    ``model_gateway:MiMo-V2.6-Flash`` → ``MiMo-V2.6-Flash``.
    """
    raw = model_id.split(":", 1)[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw)
    return safe or "unknown"


# ---------------------------------------------------------------------------
# NVIDIA
# ---------------------------------------------------------------------------


def download_nvidia(
    fixtures_dir: Path,
    *,
    live_suffix: str = DEFAULT_LIVE_SUFFIX,
    force: bool = True,
    reachable_check: bool = True,
) -> DownloadResult:
    """Capture an unfiltered NVIDIA catalog page as raw HTML.

    The catalog page is fetched with browser-like headers (matching the
    production ``_build_headers()``) and written verbatim — *before* the
    RSC payload is extracted, before any ``nimType`` filter is applied,
    and before the parser strips "Run Anywhere" partner endpoints.

    Args:
        fixtures_dir: directory to write the file into.
        live_suffix:  suffix inserted before the extension
                      (default ``"_live"``). Empty string overwrites
                      the curated ``nvidia_html.html``.
        force:        when True (default), overwrite any existing file.
        reachable_check: when True, skip the TCP probe before fetching
                         (saves 5s when caller has already probed).

    Returns:
        :class:`DownloadResult` summarising what happened.
    """
    result = DownloadResult(provider="nvidia")

    if reachable_check and not _is_reachable("build.nvidia.com"):
        result.status = "skipped"
        result.errors.append("build.nvidia.com not reachable from this environment")
        return result

    headers = nvidia_mod._build_headers()
    req = urllib.request.Request("https://build.nvidia.com/models", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            encoding = (resp.headers.get("Content-Encoding") or "").lower()
    except urllib.error.URLError as exc:
        result.status = "failed"
        result.errors.append(f"HTTP fetch failed: {exc}")
        return result

    html = gzip.decompress(raw).decode("utf-8") if encoding == "gzip" else raw.decode("utf-8")

    # Quick sanity check — refuse to overwrite a healthy fixture with a
    # WAF-blocked HTML body that has no RSC chunks.
    rsc = nvidia_mod._extract_rsc_payload(html)
    if not rsc:
        result.status = "failed"
        result.errors.append("captured HTML contains no RSC chunks (likely WAF block)")
        return result

    target_name = _apply_suffix("nvidia_html.html", live_suffix)
    target = fixtures_dir / target_name
    if target.exists() and not force:
        result.files.append(target_name)
        return result

    _atomic_write(target, html.encode("utf-8"))
    result.files.append(target_name)
    result.bytes = len(html.encode("utf-8"))
    return result


# ---------------------------------------------------------------------------
# AMD
# ---------------------------------------------------------------------------


def download_amd(
    fixtures_dir: Path,
    *,
    live_suffix: str = DEFAULT_LIVE_SUFFIX,
    max_details: int = 5,
    force: bool = True,
    reachable_check: bool = True,
) -> DownloadResult:
    """Capture the AMD bootstrap listing plus detail pages.

    Writes:
        * ``amd_bootstrap<suffix>.json`` — full directory listing
        * ``amd_detail_<slug><suffix>.json`` — first ``max_details``
          detail pages (slug = filesystem-safe model id)

    Args:
        fixtures_dir: target directory.
        live_suffix:  suffix inserted before each file's extension.
        max_details:  cap on detail pages captured (default 5) to keep
                      the fixture set small. The bootstrap always
                      captures every card.
        force:        overwrite existing fixtures (default True).
        reachable_check: skip the TCP probe when caller has already done it.

    Returns:
        :class:`DownloadResult`.
    """
    result = DownloadResult(provider="amd")

    if reachable_check and not _is_reachable("developer.amd.com.cn"):
        result.status = "skipped"
        result.errors.append("developer.amd.com.cn not reachable from this environment")
        return result

    try:
        bootstrap = amd_mod.fetch_bootstrap(amd_mod.DEFAULT_UA, timeout=30)
    except urllib.error.URLError as exc:
        result.status = "failed"
        result.errors.append(f"bootstrap fetch failed: {exc}")
        return result
    except Exception as exc:  # noqa: BLE001 — surface any decoder/HTTP error
        result.status = "failed"
        result.errors.append(f"bootstrap fetch raised {type(exc).__name__}: {exc}")
        return result

    if not isinstance(bootstrap, dict) or "cards" not in bootstrap:
        result.status = "failed"
        result.errors.append("bootstrap response missing 'cards' key (unexpected shape)")
        return result

    bootstrap_name = _apply_suffix("amd_bootstrap.json", live_suffix)
    bootstrap_path = fixtures_dir / bootstrap_name
    if not bootstrap_path.exists() or force:
        _atomic_write(
            bootstrap_path,
            json.dumps(bootstrap, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    result.files.append(bootstrap_name)
    result.bytes += bootstrap_path.stat().st_size

    cards = bootstrap.get("cards") or []
    captured = 0
    for card in cards:
        if captured >= max_details:
            break
        model_id = card.get("id")
        if not model_id:
            continue
        slug = _slugify_amd_model_id(model_id)
        detail_name = _apply_suffix(f"amd_detail_{slug}.json", live_suffix)
        detail_path = fixtures_dir / detail_name
        try:
            detail = amd_mod.fetch_detail(model_id, amd_mod.DEFAULT_UA, timeout=30)
        except urllib.error.URLError as exc:
            result.errors.append(f"detail fetch failed for {model_id}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            result.errors.append(
                f"detail fetch raised {type(exc).__name__} for {model_id}: {exc}"
            )
            continue

        if not isinstance(detail, dict):
            result.errors.append(f"detail for {model_id} is not a dict: {type(detail).__name__}")
            continue

        if not detail_path.exists() or force:
            _atomic_write(
                detail_path,
                json.dumps(detail, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        result.files.append(detail_name)
        result.bytes += detail_path.stat().st_size
        captured += 1

    return result


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------


def download_huggingface(
    fixtures_dir: Path,
    *,
    live_suffix: str = DEFAULT_LIVE_SUFFIX,
    force: bool = True,
    reachable_check: bool = True,
    env_file: Optional[Path] = None,
) -> DownloadResult:
    """Capture the raw Hugging Face Inference Router payload.

    The router endpoint returns a JSON document listing every model
    visible through the inference router. This fixture is captured
    *before* ``filter_free_providers`` runs, so unit tests can assert
    both the filter behaviour and the parser's handling of paid-only
    providers.

    Proxy support:
        ``router.huggingface.co`` is unreachable from some networks, so
        the HF provider routes through ``SOCKS5_PROXY`` when set.
        This function auto-loads ``.env`` from the cwd or
        ``data/.env`` (whichever exists) so a developer who has set
        ``SOCKS5_PROXY`` in their local ``data/.env`` doesn't need to
        export it on the command line. Real environment variables
        always win over ``.env`` entries. Pass ``env_file`` to override.

    Args:
        fixtures_dir: target directory.
        live_suffix:  suffix inserted before the extension.
        force:        overwrite existing fixture (default True).
        reachable_check: skip the TCP probe when caller has already done it.
        env_file:     explicit path to a ``.env`` file; ``None`` (default)
                      auto-detects via :func:`_find_dotenv`. Pass a path
                      to a non-existent file to suppress the auto-load.

    Returns:
        :class:`DownloadResult`.
    """
    result = DownloadResult(provider="huggingface")

    # Auto-load .env so a developer who has SOCKS5_PROXY in data/.env
    # doesn't need to export it before running this script. PySocks is
    # only needed when the proxy is actually configured.
    _load_dotenv(env_file)

    # If a SOCKS5 proxy is configured, the direct TCP probe would fail
    # even when the proxy can reach the host — so skip the probe and
    # let the actual fetch (which the HF provider routes through the
    # proxy) decide reachability. A misconfigured proxy will surface as
    # a "failed" result with the underlying URLError.
    proxy_configured = _is_proxy_configured()
    if reachable_check and not proxy_configured and not _is_reachable(
        "router.huggingface.co"
    ):
        result.status = "skipped"
        result.errors.append("router.huggingface.co not reachable from this environment")
        return result

    try:
        payload = hf_mod.fetch_router_json(timeout=30)
    except RuntimeError as exc:
        # fetch_router_json wraps URLError in RuntimeError
        result.status = "failed"
        result.errors.append(str(exc))
        return result
    except urllib.error.URLError as exc:
        result.status = "failed"
        result.errors.append(f"router fetch failed: {exc}")
        return result
    except Exception as exc:  # noqa: BLE001
        result.status = "failed"
        result.errors.append(f"router fetch raised {type(exc).__name__}: {exc}")
        return result

    if not isinstance(payload, dict) or "data" not in payload:
        result.status = "failed"
        result.errors.append("router response missing 'data' key (unexpected shape)")
        return result

    target_name = _apply_suffix("huggingface_router.json", live_suffix)
    target = fixtures_dir / target_name
    if not target.exists() or force:
        _atomic_write(target, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    result.files.append(target_name)
    result.bytes = target.stat().st_size
    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def download_all(
    fixtures_dir: Optional[Path] = None,
    *,
    providers: Optional[List[str]] = None,
    live_suffix: str = DEFAULT_LIVE_SUFFIX,
    max_details: int = 5,
    env_file: Optional[Path] = None,
) -> List[DownloadResult]:
    """Run the requested providers sequentially.

    Args:
        fixtures_dir: target directory. Defaults to
                      ``data/tests/fixtures/`` alongside this file.
        providers:    subset of provider keys to run. Defaults to all.
        live_suffix:  forwarded to each provider's downloader.
        max_details:  forwarded to ``download_amd``.
        env_file:     forwarded to ``download_huggingface`` (other
                      providers don't need it).

    Returns:
        One :class:`DownloadResult` per provider, in the order they ran.
        A failed/skipped provider still produces a result (with
        ``status != 'ok'``); the next provider runs regardless.
    """
    fixtures_dir = fixtures_dir or (_HERE_DIR / "fixtures")
    selected = providers or ["nvidia", "amd", "huggingface"]

    def _run(name: str) -> DownloadResult:
        if name == "nvidia":
            return download_nvidia(
                fixtures_dir,
                live_suffix=live_suffix,
            )
        if name == "amd":
            return download_amd(
                fixtures_dir,
                live_suffix=live_suffix,
                max_details=max_details,
            )
        if name == "huggingface":
            return download_huggingface(
                fixtures_dir,
                live_suffix=live_suffix,
                env_file=env_file,
            )
        return DownloadResult(
            provider=name,
            status="failed",
            errors=[f"unknown provider '{name}'; known: nvidia, amd, huggingface"],
        )

    return [_run(name) for name in selected]


def _format_summary(results: List[DownloadResult]) -> str:
    lines = []
    for r in results:
        size_kb = r.bytes / 1024 if r.bytes else 0
        lines.append(
            f"  {r.provider:<12} {r.status:<8} "
            f"{len(r.files):>2} file(s) {size_kb:>7.1f} KB"
        )
        for err in r.errors:
            lines.append(f"    ! {err}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh raw provider fixtures under data/tests/fixtures/. "
            "By default writes to <name>_live.<ext> so curated fixtures "
            "are never overwritten; pass --live-suffix '' to overwrite them."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["nvidia", "amd", "huggingface", "all"],
        default="all",
        help="which provider(s) to refresh (default: all)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=_HERE_DIR / "fixtures",
        help="target directory (default: data/tests/fixtures/)",
    )
    parser.add_argument(
        "--live-suffix",
        default=DEFAULT_LIVE_SUFFIX,
        help=(
            "suffix inserted before the file extension "
            "(default: %(default)s). Empty string overwrites curated "
            "fixtures."
        ),
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=5,
        help="AMD only: cap on detail pages captured (default: 5)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=(
            "explicit path to a .env file used to populate "
            "SOCKS5_PROXY for the HF provider (default: autodetect "
            "./.env or data/.env). Pass --env-file /dev/null to skip."
        ),
    )
    args = parser.parse_args(argv)

    providers = None if args.provider == "all" else [args.provider]
    results = download_all(
        args.fixtures_dir,
        providers=providers,
        live_suffix=args.live_suffix,
        max_details=args.max_details,
        env_file=args.env_file,
    )

    print(_format_summary(results))

    return 0 if all(r.status == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())