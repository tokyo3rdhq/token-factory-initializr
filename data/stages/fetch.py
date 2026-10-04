"""FetchStage — drives all provider fetchers concurrently.

This Stage is a thin adapter: it calls ``data.providers.*`` fetchers via a
small retry+backoff wrapper and writes the resulting ``{provider: list}``
mapping into ``context.data["fetched"]`` and per-provider errors into
``context.state["fetch_errors"]``.

It does NOT depend on any specific provider — providers are injected via
``PROVIDER_FETCHERS``. Adding OpenRouter/Groq later is a one-line change.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider registry (data, not orchestration)
# ---------------------------------------------------------------------------


# Each provider is a (name, zero-arg fetcher) tuple. Order is informational.
# Populated lazily by :func:`_build_default_registry` so that importing this
# module does not force eager network imports of provider implementations.
PROVIDER_FETCHERS: List[Tuple[str, Callable[[], List[dict]]]] = []


def _build_default_registry() -> List[Tuple[str, Callable[[], List[dict]]]]:
    from data.providers.amd import fetch_amd_models
    from data.providers.huggingface import fetch_huggingface_models
    from data.providers.models_dev import fetch_models_dev_models
    from data.providers.nvidia import fetch_catalog_page
    from data.providers.openrouter import fetch_openrouter_models

    return [
        ("nvidia", fetch_catalog_page),
        ("amd", fetch_amd_models),
        ("huggingface", fetch_huggingface_models),
        ("openrouter", fetch_openrouter_models),
        ("models_dev", fetch_models_dev_models),
    ]


def _run_provider(
    name: str,
    func: Callable[[], List[dict]],
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
) -> Tuple[str, List[dict], Optional[str]]:
    """Run a provider fetcher with retry + exponential backoff.

    Pure I/O retry wrapper; returns ``(name, models, error_message_or_None)``.
    """
    logger.info("Fetching %s …", name)
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            models = func()
            logger.info("  → %d models", len(models))
            return (name, models, None)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 0.5), max_delay)
                logger.warning(
                    "  ✗ %s attempt %d/%d failed: %s; retrying in %.1fs",
                    name, attempt + 1, max_retries, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.exception("  ✗ %s failed after %d attempts: %s", name, max_retries, exc)
    return (name, [], str(last_exc) if last_exc else "unknown")


async def _fetch_all_async(
    providers: List[Tuple[str, Callable[[], List[dict]]]],
) -> Tuple[Dict[str, List[dict]], Dict[str, str]]:
    """Drive all provider fetchers concurrently via a thread pool."""
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            loop.run_in_executor(pool, _run_provider, name, func)
            for name, func in providers
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)

    fetched: Dict[str, List[dict]] = {}
    errors: Dict[str, str] = {}
    for result in results:
        if isinstance(result, Exception):
            errors["unknown"] = str(result)
            continue
        name, models, error = result
        fetched[name] = models
        if error:
            errors[name] = error
    return fetched, errors


class FetchStage(Stage):
    """Fetch from all registered providers concurrently."""

    name = "fetch"

    def __init__(self, providers: Optional[List[Tuple[str, Callable[[], List[dict]]]]] = None) -> None:
        if providers is None:
            if not PROVIDER_FETCHERS:
                PROVIDER_FETCHERS.extend(_build_default_registry())
            providers = PROVIDER_FETCHERS
        self.providers = providers

    def execute(self, context: PipelineContext) -> PipelineContext:
        fetched, errors = asyncio.run(_fetch_all_async(self.providers))
        context.data["fetched"] = fetched
        context.state["fetch_errors"] = errors
        # Also expose cross-source observations for downstream enrichment.
        # Both are fused into the primary source's normalize pass via
        # the matching identity-matcher path.
        context.data["openrouter_models"] = fetched.get("openrouter", [])
        context.data["models_dev_models"] = fetched.get("models_dev", [])
        return context