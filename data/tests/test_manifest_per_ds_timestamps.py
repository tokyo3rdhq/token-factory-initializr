"""Tests for the per-data-source ``generated_at`` field on the
aggregated manifest.

Each ``providers.{ds}`` entry should carry the actual KV write time
the publish stage recorded, so consumers can see exactly when each
ds was last written without re-running the pipeline. The top-level
``generated_at`` is preserved as ``max(per-ds timestamps)`` so it
agrees with what publish actually committed.
"""

from __future__ import annotations

from data.process.summarize import summarize_all


def test_per_data_source_timestamps_appear_in_providers():
    """Each ``providers.{ds}.generated_at`` reflects the publish-stage
    timestamp for that ds."""
    m = summarize_all(
        endpoints=[],
        fetch_errors={},
        reconciliation_plan=None,
        per_data_source_timestamps={
            "amd": "2026-10-05T14:30:00+00:00",
            "huggingface": "2026-10-05T14:30:05+00:00",
            "nvidia": "2026-10-05T14:30:10+00:00",
        },
    )
    assert m["providers"]["amd"]["generated_at"] == "2026-10-05T14:30:00+00:00"
    assert m["providers"]["huggingface"]["generated_at"] == "2026-10-05T14:30:05+00:00"
    assert m["providers"]["nvidia"]["generated_at"] == "2026-10-05T14:30:10+00:00"


def test_top_level_generated_at_is_max_of_per_ds():
    """Top-level ``generated_at`` falls back to ``max(per-ds timestamps)``
    so it agrees with what publish actually committed."""
    m = summarize_all(
        endpoints=[],
        per_data_source_timestamps={
            "amd": "2026-10-05T14:30:00+00:00",
            "nvidia": "2026-10-05T14:30:10+00:00",
        },
    )
    # The latest per-ds timestamp — independent of any single ds.
    assert m["generated_at"] == "2026-10-05T14:30:10+00:00"


def test_unknown_ds_falls_back_to_now_when_no_timestamps():
    """When publish didn't run (e.g. KV init failed), the per-ds
    ``generated_at`` is ``None`` and the top-level falls back to
    ``datetime.now()``."""
    m = summarize_all(endpoints=[], per_data_source_timestamps=None)
    # Per-ds entries that already appeared (via fetch_errors /
    # provider counts) still get a None ``generated_at`` slot.
    for entry in m["providers"].values():
        assert entry["generated_at"] is None
    assert "generated_at" in m


def test_ds_in_timestamps_only_appears_in_providers():
    """A ds that only exists in ``per_data_source_timestamps`` (no
    fetch, no models) still appears in ``providers`` with its
    timestamp."""
    m = summarize_all(
        endpoints=[],
        per_data_source_timestamps={
            "models_dev": "2026-10-05T14:30:00+00:00",
        },
    )
    assert "models_dev" in m["providers"]
    assert m["providers"]["models_dev"]["generated_at"] == "2026-10-05T14:30:00+00:00"


def test_ds_failed_to_fetch_has_null_generated_at():
    """When a ds fetch failed, the publish stage never wrote it,
    so ``generated_at`` is ``None`` even if other ds timestamps
    are present."""
    m = summarize_all(
        endpoints=[],
        fetch_errors={"huggingface": "Network error"},
        per_data_source_timestamps={
            "amd": "2026-10-05T14:30:00+00:00",
            # Note: huggingface intentionally absent from the timestamps.
        },
    )
    assert m["providers"]["amd"]["generated_at"] == "2026-10-05T14:30:00+00:00"
    assert m["providers"]["huggingface"]["generated_at"] is None
    assert m["providers"]["huggingface"]["status"] == "failed"
