"""Shared pytest configuration.

Defines:
  - ``integration`` marker: tests requiring network or external services.
  - ``skip_integration`` fixture: skips tests marked integration unless
    ``RUN_INTEGRATION_TESTS=1`` is set in the environment.

Unit tests should remain fast and hermetic; integration tests are opt-in.
"""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring network or external services",
    )


@pytest.fixture(autouse=True)
def skip_integration(request):
    """Skip integration tests unless explicitly enabled."""
    if "integration" in request.keywords:
        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("integration test skipped; set RUN_INTEGRATION_TESTS=1 to run")