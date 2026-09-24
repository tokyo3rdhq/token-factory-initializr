"""Abstract provider interface for model discovery."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from data.models.schema import ModelEndpoint


class Provider(Protocol):
    """All providers must implement this interface."""

    @property
    def name(self) -> str:
        """Unique provider identifier, e.g. 'nvidia', 'amd', 'huggingface'."""
        ...

    @abstractmethod
    def fetch_models(self) -> list[ModelEndpoint]:
        """Fetch free model endpoints from this provider.

        Returns an empty list when no models are available (not an error).
        Raises an exception only when parsing fails unexpectedly.
        """
        ...