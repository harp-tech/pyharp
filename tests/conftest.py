"""Pytest configuration, shared fixtures and helpers for all suites."""

from pathlib import Path

import pytest

from tests.fixtures import (  # re-export so conftest-aware code still works
    TIMESTAMP_1S,
    make_frame_from_raw,
)

__all__ = ["make_frame_from_raw", "TIMESTAMP_1S"]

# Shared schema assets, usable across suites via the fixtures below.
ASSETS = Path(__file__).parent / "assets"


@pytest.fixture(scope="session")
def device_yml() -> str:
    """The generators test-metadata ``device.yml`` as text."""
    return (ASSETS / "device.yml").read_text()


@pytest.fixture(scope="session")
def core_yml() -> str:
    """The generators core metadata ``core.yml`` as text."""
    return (ASSETS / "core.yml").read_text()
