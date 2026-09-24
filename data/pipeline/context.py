"""PipelineContext — shared mutable state container between Stages.

A stage reads fields it cares about, writes new fields, and returns the
context. PipelineContext is not tied to any single business object — it is
a generic execution scratchpad (data, state, metrics, artifacts, errors).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PipelineContext:
    """Shared mutable context passed between pipeline stages.

    Slots:
      data      : payload that flows stage-to-stage (raw dicts, normalized endpoints, …)
      state     : control signals (e.g. ``{'should_store': True}``)
      metrics   : numeric counters (counters of records fetched/kept/dropped, …)
      artifacts : outputs / side outputs (manifest dict, generated config, …)
      errors    : list of error dicts accumulated during pipeline execution
    """

    data: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)