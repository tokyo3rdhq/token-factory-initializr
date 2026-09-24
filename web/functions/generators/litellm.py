"""LiteLLM configuration generator."""

from __future__ import annotations

from typing import Any


class LiteLLMGenerator:
    """Generate LiteLLM-compatible model_list YAML from model endpoints."""

    def generate(self, models: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a LiteLLM config dict.

        Each model becomes:
          model_name: {provider}-{slug}
          litellm_params:
            model: {provider}/{model_id}
            api_key: os.environ/{PROVIDER}_API_KEY

        TODO: Implement full generation logic.
        """
        raise NotImplementedError("LiteLLM generator not yet implemented")