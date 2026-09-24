"""Pipeline package — orchestration primitives only.

Public surface:
    Pipeline          — fluent executor (.then() ... .end() ... .run())
    Stage             — Protocol every Stage must satisfy
    PipelineContext   — shared mutable state container
    PipelineResult    — lightweight execution summary
    StageResult       — per-stage outcome
    StageStatus       — enum: success / failed / skipped
"""

from data.pipeline.context import PipelineContext
from data.pipeline.pipeline import Pipeline
from data.pipeline.result import PipelineResult, StageResult, StageStatus
from data.pipeline.stage import Stage

__all__ = [
    "Pipeline",
    "Stage",
    "PipelineContext",
    "PipelineResult",
    "StageResult",
    "StageStatus",
]