"""Pipeline — light-weight execution / orchestration framework.

Per docs/arch_pipeline.md:

    Pipeline is responsible for:
      - Stage registration
      - Stage execution order
      - PipelineContext passing
      - Basic execution lifecycle
      - Basic error handling
      - Basic execution result / metrics

    Pipeline is NOT responsible for:
      - Any provider/storage/notification business logic
      - DAG / parallel / branch DSL
      - Persistent workflow state

DSL:

    pipeline = (
        Pipeline()
        .then(FetchStage())
        .then(ParseStage())
        .then(NormalizeStage())
        ...
        .then(NotifyStage())
        .end()
    )

    result = pipeline.run(context)
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from data.pipeline.context import PipelineContext
from data.pipeline.result import PipelineResult, StageResult, StageStatus
from data.pipeline.stage import Stage

logger = logging.getLogger(__name__)


class Pipeline:
    """A composed sequence of stages executed in registration order."""

    def __init__(self) -> None:
        self._stages: List[Stage] = []

    # ------------------------------------------------------------------
    # DSL: definition
    # ------------------------------------------------------------------

    def then(self, stage: Stage) -> "Pipeline":
        """Register a stage. Returns self to allow chaining."""
        self._stages.append(stage)
        return self

    def end(self) -> "Pipeline":
        """Mark the pipeline definition as complete.

        Does NOT execute the pipeline. Definition and execution are
        deliberately separated (see spec §3).
        """
        return self

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def stages(self) -> List[Stage]:
        """Read-only view of the registered stages."""
        return list(self._stages)

    def __len__(self) -> int:
        return len(self._stages)

    def __iter__(self):
        return iter(self._stages)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, context: Optional[PipelineContext] = None) -> PipelineResult:
        """Execute the pipeline and return a PipelineResult.

        On stage exception the pipeline records the failure, marks the
        pipeline as aborted, and **continues** running subsequent stages.
        This guarantees NotifyStage (always last) gets a chance to fire a
        Feishu alert even when an earlier stage blew up. Per-stage recovery
        semantics are the responsibility of each Stage.execute()
        implementation.
        """
        if context is None:
            context = PipelineContext()

        results: List[StageResult] = []
        aborted = False

        for stage in self._stages:
            started = time.monotonic()
            stage_name = getattr(stage, "name", type(stage).__name__)
            logger.info("Running stage: %s", stage_name)
            try:
                context = stage.execute(context)
                status = StageStatus.SUCCESS
                error = None
            except Exception as exc:  # noqa: BLE001
                logger.exception("Stage %s failed: %s", stage_name, exc)
                status = StageStatus.FAILED
                error = repr(exc)
                context.errors.append({"stage": stage_name, "error": error})
                aborted = True
            results.append(
                StageResult(stage_name, status, started, time.monotonic(), error)
            )

        result = PipelineResult(stages=results, context=context, aborted=aborted)
        for line in result.summary_lines():
            logger.info(line)
        return result


__all__ = ["Pipeline", "Stage", "PipelineContext", "PipelineResult", "StageResult", "StageStatus"]