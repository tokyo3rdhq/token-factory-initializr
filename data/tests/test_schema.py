"""Tests for JSON Schema validation of ModelEndpoint dicts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.models.validate import (
    validate_endpoint_dict,
    validate_model_endpoint,
    validate_schema_path,
)
from data.models.schema import ModelEndpoint
from datetime import datetime, timezone


def test_validate_schema_path_points_to_shared():
    p = validate_schema_path()
    assert p.exists()
    assert p.name == "model.schema.json"
    assert "shared/schema" in str(p)


def test_validate_endpoint_dict_accepts_valid_dict():
    ep = {
        "provider": "amd",
        "data_source": "amd",
        "model_id": "x/y",
        "free": True,
        "fetched_at": "2026-09-24T00:00:00+00:00",
        "name": "X",
        "description": None,
        "capabilities": {},
        "metadata": {},
    }
    assert validate_endpoint_dict(ep) == []


def test_validate_endpoint_dict_rejects_missing_required():
    errs = validate_endpoint_dict({"provider": "amd"})
    assert any("model_id" in e for e in errs)
    assert any("data_source" in e for e in errs)
    assert any("free" in e for e in errs)
    assert any("fetched_at" in e for e in errs)


def test_validate_endpoint_dict_rejects_wrong_type():
    errs = validate_endpoint_dict({
        "provider": "amd",
        "data_source": "amd",
        "model_id": "x/y",
        "free": "yes",  # should be bool
        "fetched_at": "2026-09-24",
    })
    assert any("free" in e for e in errs)


def test_validate_endpoint_dict_rejects_unknown_field():
    errs = validate_endpoint_dict({
        "provider": "amd",
        "data_source": "amd",
        "model_id": "x/y",
        "free": True,
        "fetched_at": "2026-09-24",
        "rogue_field": "value",
    })
    assert any("rogue_field" in e for e in errs)


def test_validate_model_endpoint_round_trips():
    ep = ModelEndpoint(
        provider="amd",
        data_source="amd",
        model_id="x/y",
        free=True,
        fetched_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )
    assert validate_model_endpoint(ep) == []