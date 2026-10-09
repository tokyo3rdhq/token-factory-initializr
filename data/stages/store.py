"""StoreStage — persist per-provider + aggregate snapshot to Cloudflare KV.

Per docs/arch_pipeline.md §10, this Stage is a thin adapter that calls
``data.storage.cloudflare_kv.KVStorage``. Severe errors (KV init failure,
per-snapshot write failure) are recorded to ``context.errors`` and logged so
the downstream ``NotifyStage`` can fire a Feishu alert — silent data loss
is unacceptable for the catalog.

Writes per run (all prefixed ``tfi:``):
  - ``tfi:manifest:<YYYY-MM-DD>`` — dated snapshot (14-day TTL) for that
  - ``tfi:models:<provider>:latest`` — per-provider snapshots
  - ``tfi:models:latest`` — aggregate list
  - ``tfi:manifest:latest`` — current manifest (overwrites previous)
  - ``tfi:manifest:<YYYY-MM-DD>`` — dated snapshot for that day's run, so
    the GitHub Actions "Validate results" step can confirm the write by
    GETting the dated key (immune to previous-day artifacts that may
    still be at ``tfi:manifest:latest``).

On any severe failure (KV init or per-snapshot write) the Stage records
the error to ``context.errors`` and continues, so the NotifyStage can
surface it via Feishu. Successful per-provider writes proceed even if
one provider's put fails.
"""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from typing import Optional

from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage
from data.process.normalize import endpoint_to_dict
from data.storage.cloudflare_kv import (
    KEYS,
    KVStorage,
    manifest_key,
    model_key,
)

logger = logging.getLogger(__name__)


def _today_key() -> str:
    """Return the dated manifest key for the current UTC day.

    Thin wrapper around :func:`manifest_key` so the call site documents
    its semantics; the prefix is applied by the helper.
    """
    return manifest_key(_dt.utcnow().strftime("%Y-%m-%d"))


class StoreStage(Stage):
    """Persist endpoints to Cloudflare KV."""

    name = "store"

    def __init__(self, kv: Optional[KVStorage] = None) -> None:
        self.kv = kv  # If None, will try to construct from env at execute time.

    def execute(self, context: PipelineContext) -> PipelineContext:
        endpoints = context.data.get("enriched", [])
        manifest = context.artifacts.get("manifest", {})

        kv = self.kv
        if kv is None:
            try:
                kv = KVStorage.from_env()
            except Exception as exc:  # noqa: BLE001
                msg = f"StoreStage: KV init failed: {exc!r}"
                logger.error(msg)
                context.errors.append({"stage": self.name, "error": msg})
                return context

        endpoint_dicts = [endpoint_to_dict(ep) for ep in endpoints]
        by_provider: dict[str, list[dict]] = {}
        for d in endpoint_dicts:
            by_provider.setdefault(d["provider"], []).append(d)

        any_failure = False
        for provider, models in by_provider.items():
            try:
                kv.put_snapshot(provider, models)
            except Exception as exc:  # noqa: BLE001
                any_failure = True
                msg = f"StoreStage: put_snapshot({provider}) failed: {exc!r}"
                logger.error(msg)
                context.errors.append({"stage": self.name, "error": msg})

        try:
            kv.put(KEYS["latest"], {"version": manifest.get("version", ""), "models": endpoint_dicts})
        except Exception as exc:  # noqa: BLE001
            any_failure = True
            msg = f"StoreStage: put({KEYS['latest']}) failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})

        # manifest:latest — overwrites previous run
        try:
            kv.put(KEYS["manifest"], manifest)
        except Exception as exc:  # noqa: BLE001
            any_failure = True
            msg = f"StoreStage: put({KEYS['manifest']}) failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})

        # manifest:<YYYY-MM-DD> — dated snapshot, retained for 14 days
        # via KV expirationTtl so old dates auto-expire without a
        # cleanup job. The CI "Validate results" step reads today's
        # key only (immune to previous-day artifacts at latest), so
        # the 14-day window covers any post-run validation window.
        DATED_MANIFEST_TTL_SECONDS = 14 * 86400
        dated_key = _today_key()
        try:
            kv.put(dated_key, manifest, ttl=DATED_MANIFEST_TTL_SECONDS)
            logger.info(
                "Wrote dated manifest snapshot to %s (ttl=%ds)",
                dated_key,
                DATED_MANIFEST_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            any_failure = True
            msg = f"StoreStage: put({dated_key}) failed: {exc!r}"
            logger.error(msg)
            context.errors.append({"stage": self.name, "error": msg})

        if not any_failure and endpoint_dicts:
            logger.info("Stored %d endpoints across %d providers", len(endpoint_dicts), len(by_provider))
        return context