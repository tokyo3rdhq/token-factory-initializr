"""StageResult / PipelineResult — lightweight execution result data classes.

Used to summarise one stage (StageResult) or the whole pipeline
(PipelineResult). Keeps Pipeline.print_summary() boring and dependency-free.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class StageStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """One stage's execution outcome."""

    name: str
    status: StageStatus
    started_at: float
    ended_at: float
    error: Optional[str] = None

    @property
    def duration_s(self) -> float:
        return max(self.ended_at - self.started_at, 0.0)


@dataclass
class PipelineResult:
    """Whole pipeline execution outcome."""

    stages: List[StageResult] = field(default_factory=list)
    context: Optional[object] = None  # the final PipelineContext, set after run()
    aborted: bool = False

    @property
    def total_s(self) -> float:
        return sum(s.duration_s for s in self.stages)

    def status_by_name(self) -> Dict[str, StageStatus]:
        return {s.name: s.status for s in self.stages}

    def summary_lines(self) -> List[str]:
        """Render a one-line-per-stage summary suitable for logging."""
        lines = [f"{'stage':<18} {'status':<10} {'duration':>10}"]
        for s in self.stages:
            lines.append(
                f"{s.name:<18} {s.status.value:<10} {s.duration_s:>9.3f}s"
            )
        lines.append(f"{'total':<18} {'':<10} {self.total_s:>9.3f}s")
        return lines