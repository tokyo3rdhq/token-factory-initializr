"""NotifyStage — send pipeline summary to external systems (Feishu).

Two responsibilities:
  1. Always emit a summary card (success or failure) so operators see run state.
  2. On hard failure (pipeline aborted OR stage errors recorded), fire a
     plain-text alert so the on-call channel is pinged even if the summary
     is missed.

The actual sending is delegated to ``data.notify.feishu``. Best-effort: a
missing webhook URL or transient HTTP failure must not abort the pipeline.
"""

from __future__ import annotations

import logging
from typing import Iterable

from data.notify.feishu import send_alert, send_summary
from data.pipeline.context import PipelineContext
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


class NotifyStage(Stage):
    """Send pipeline summary + failure alert via Feishu.

    The summary card is always sent (when a webhook is configured). When
    ``context.errors`` is non-empty, an additional plain-text alert is
    sent so the failure is impossible to miss.
    """

    name = "notify"

    def execute(self, context: PipelineContext) -> PipelineContext:
        manifest = context.artifacts.get("manifest", {})
        invalid = context.data.get("invalid", [])
        errors = list(context.errors or [])

        # Summary card (always attempted; surfaces errors inline).
        try:
            send_summary(manifest, invalid, errors=errors)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Notification summary failed: %s", exc)

        # Failure alert (only when something went wrong).
        if errors:
            alert_lines = ["Pipeline aborted — one or more stages failed."]
            for e in errors:
                stage = e.get("stage", "?")
                err = e.get("error", "?")
                if len(err) > 300:
                    err = err[:300] + "..."
                alert_lines.append(f"- {stage}: {err}")
            alert_message = "\n".join(alert_lines)
            try:
                send_alert(alert_message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Alert notification failed: %s", exc)

        return context