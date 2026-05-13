"""Shared pytest fixtures for the entire test suite."""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def isolated_logging() -> Generator[None, None, None]:
    """Reset root logger state after every test to prevent handler leakage.

    Python's logging module is global mutable state.  Without this fixture,
    handlers registered by one test bleed into the next, producing false
    positives and hard-to-diagnose failures.
    """
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level
    yield
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)
    # Clear named-logger cache so configure_logging() always starts clean.
    logging.Logger.manager.loggerDict.clear()
