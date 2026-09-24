"""Abstract config generator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConfigGenerator(ABC):
    """All config generators must implement this interface."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Identifier for this generator, e.g. 'litellm'."""
        ...

    @abstractmethod
    def generate(self, models: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a configuration artifact from model endpoints."""
        ...