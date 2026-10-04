"""models.dev provider for cross-source model enrichment.

Fetches https://models.dev/models.json and exposes the entries as RAW
observations shaped the same way :mod:`data.providers.openrouter`
does — i.e. they participate in the single normalize pass that the
primary-source endpoints go through.

Schema reminder (per entry):

    {
      "id": "openbmb/minicpm5-2b",
      "name": "MiniCPM5-2B",
      "description": "Dense 2B-class open-source model for ...",
      "attachment": false,
      "reasoning": true,
      "tool_call": true,
      "temperature": true,
      "release_date": "2026-09-06",
      "last_updated": "2026-09-12",
      "modalities": {"input": ["text"], "output": ["text"]},
      "open_weights": true,
      "limit": {"context": 131072, "output": 131072},
      "license": "apache-2.0",
      "weights": [{"label": "Hugging Face", "url": "..."}],
    }

We translate the models.dev schema into TFI's normalized cross-source
observation shape:

    architecture.modalities  ->  architecture.{input, output}
    limit.context            ->  context_length
    reasoning/tool_call      ->  metadata.supported_parameters
    description / name       ->  description / name

Reasoning uses a different signaling convention than OpenRouter —
boolean top-level rather than a structured ``reasoning`` block with
``default_enabled``. We surface it via ``supported_parameters`` so the
existing normalize_capabilities() cross-source path picks it up
without further changes.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

BASE_URL = "https://models.dev/models.json"

# A descriptive User-Agent is required — models.dev returns 403 to the
# default urllib User-Agent. This is a polite identifier only; no
# personal data.
DEFAULT_USER_AGENT = (
    "token-factory-initializr/1.0 "
    "(+https://models.magi.website)"
)


def _fetch_models_page(
    url: str = BASE_URL,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Fetch the raw models.dev catalog and return the parsed JSON."""
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — trusted URL
        return json.loads(resp.read())


def _build_raw_observation(entry: dict[str, Any]) -> dict[str, Any]:
    """Translate a single models.dev entry into a TFI cross-source observation.

    Mirrors the shape produced by :mod:`data.providers.openrouter` so the
    normalize stage can treat both sources uniformly. The
    ``architecture`` dict keeps the original modality lists (input /
    output); the metadata block carries the supported_parameters-style
    signal list and any extra models.dev-only fields that downstream
    consumers might want to read (license, open_weights, weights URLs).
    """
    model_id = entry.get("id") or ""
    if not model_id:
        return {}

    modalities = entry.get("modalities") if isinstance(entry.get("modalities"), dict) else {}
    arch_input = modalities.get("input") if isinstance(modalities.get("input"), list) else []
    arch_output = modalities.get("output") if isinstance(modalities.get("output"), list) else []

    architecture: dict[str, list[str]] | None
    if isinstance(arch_input, list) and isinstance(arch_output, list):
        architecture = {
            "input": [m for m in arch_input if isinstance(m, str)],
            "output": [m for m in arch_output if isinstance(m, str)],
        }
    else:
        architecture = None

    limit = entry.get("limit") if isinstance(entry.get("limit"), dict) else {}
    context_length = limit.get("context") if isinstance(limit.get("context"), int) else None

    # Models.dev exposes reasoning/tool_call as plain booleans at the
    # top level. We surface both via ``supported_parameters`` so the
    # existing normalize_capabilities() cross-source signal path picks
    # them up without special-casing models.dev.
    supported_parameters: list[str] = []
    if entry.get("reasoning") is True:
        supported_parameters.append("reasoning")
    if entry.get("tool_call") is True:
        supported_parameters.append("tools")
        supported_parameters.append("tool_choice")

    weights = entry.get("weights") if isinstance(entry.get("weights"), list) else []
    weights_clean = [
        {"label": w.get("label"), "url": w.get("url")}
        for w in weights
        if isinstance(w, dict) and (w.get("label") or w.get("url"))
    ]

    return {
        "provider": "models_dev",
        "data_source": "models_dev",
        "model_id": model_id,
        "name": entry.get("name"),
        "description": entry.get("description"),
        "architecture": architecture,
        "context_length": context_length,
        "metadata": {
            "supported_parameters": supported_parameters,
            "license": entry.get("license"),
            "open_weights": entry.get("open_weights"),
            "release_date": entry.get("release_date"),
            "last_updated": entry.get("last_updated"),
            "attachment": entry.get("attachment"),
            "weights": weights_clean,
            "limit_output": limit.get("output") if isinstance(limit.get("output"), int) else None,
            "source_id": model_id,
        },
    }


def fetch_models_dev_models(
    url: str = BASE_URL,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Fetch raw models.dev observations.

    Returns a list of dicts shaped like
    :func:`data.process.normalize.normalize_endpoints`'s ``raw`` parameter.
    Each record carries raw ``architecture`` modalities + a synthetic
    ``supported_parameters`` list (derived from models.dev's
    ``reasoning`` / ``tool_call`` booleans) so the normalize stage can
    fuse them with the primary source's signals.
    """
    try:
        payload = _fetch_models_page(url, user_agent=user_agent, timeout=timeout)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.error("Failed to fetch models.dev catalog: %s", exc)
        return []
    except Exception as exc:  # noqa: BLE001 — defensive at provider boundary
        logger.error("Unexpected error fetching models.dev: %s", exc)
        return []

    if not isinstance(payload, dict):
        logger.error(
            "Unexpected models.dev payload shape: expected dict, got %s",
            type(payload).__name__,
        )
        return []

    observations: list[dict[str, Any]] = []
    for model_id, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        # The catalog keys are ``provider/model_id``; the entry's
        # ``id`` field carries the same value. Prefer the entry's id
        # so a renamed key won't slip through.
        entry = dict(entry)
        entry.setdefault("id", model_id)
        try:
            obs = _build_raw_observation(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to parse models.dev model %s: %s", model_id, exc
            )
            continue
        if obs and obs.get("model_id"):
            observations.append(obs)

    logger.info("Fetched %d models.dev models", len(observations))
    return observations


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    models = fetch_models_dev_models()
    print(f"Total models: {len(models)}", file=sys.stderr)
    for m in models[:5]:
        print(
            f"  {m['model_id']:<50} "
            f"arch={m.get('architecture')} "
            f"params={m['metadata'].get('supported_parameters')}",
            file=sys.stderr,
        )
