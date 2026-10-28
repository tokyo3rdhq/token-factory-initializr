"""Entry point for the Free Model Aggregator data pipeline.

Runs the full pipeline via the light-weight DSL:

    fetch → parse → normalize → validate → enrich
    → summarize → store → notify

Per docs/arch_models_intelligence_layer_evo.md §2, the ``enrich`` slot is
a placeholder; no enrichers are wired yet. The former ``deduplicate``
step was removed (doc §12).

``SummarizeStage`` runs before ``StoreStage`` so the manifest written to
KV reflects the actual endpoints being persisted.

Run via GitHub Actions workflow or manually with:
  python -m data.main
"""

import logging
import os
import sys

from dotenv import load_dotenv

from data.pipeline.context import PipelineContext
from data.stages import build_default_pipeline

logger = logging.getLogger(__name__)


def _load_env() -> None:
    """Load ``data/.env`` (or ``./.env``) into ``os.environ``.

    Real environment variables win over file values (never clobbered).
    GitHub Actions passes secrets as real env vars; local runs read
    them from the checked-out-ignored ``data/.env`` file.
    """
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def main() -> None:
    """Compose + run the default pipeline."""
    _load_env()
    print("=" * 60)
    print("Token Factory Initializr — Model Aggregator — Data Pipeline")
    print("=" * 60)
    pipeline = build_default_pipeline()
    result = pipeline.run(PipelineContext())

    manifest = result.context.artifacts.get("manifest", {}) if result.context else {}
    total = manifest.get("total", 0)
    print(f"\nPipeline complete: {total} endpoints (aborted={result.aborted})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
    main()
