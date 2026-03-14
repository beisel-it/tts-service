"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from app.config import Config, reset_config


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Ensure the config singleton is cleared between tests."""
    reset_config()
    yield
    reset_config()
