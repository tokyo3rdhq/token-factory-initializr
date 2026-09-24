"""Stage protocol — single-method contract for any Pipeline Stage.

A Stage receives a PipelineContext, mutates it, and returns it. The
Stage must NOT control other stages or know about the Pipeline's
internal execution model.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from data.pipeline.context import PipelineContext


@runtime_checkable
class Stage(Protocol):
    """Protocol every pipeline stage must satisfy."""

    @property
    def name(self) -> str:
        """Stable, human-readable stage name (used for logging + metrics)."""
        ...

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Run this stage; mutate and return ``context``."""
        ...