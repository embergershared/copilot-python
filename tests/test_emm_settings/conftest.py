"""Fixtures shared across all emm_settings test modules."""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def reset_emm_settings_loggers() -> Generator[None, None, None]:
    """Restore each ``emm_settings.*`` logger's level/cache after every test.

    The repo-wide ``isolated_logging`` autouse fixture in ``tests/conftest.py``
    calls ``logging.Logger.manager.loggerDict.clear()`` to keep
    ``setup_logging`` tests isolated. Module-level cached loggers (used by
    ``emm_settings.dotenv`` and ``emm_settings.sources``) keep their internal
    ``_cache`` dict across that clear, which causes stale ``isEnabledFor``
    answers when a later test raises the root level to ``DEBUG`` via caplog.
    Wiping the per-logger ``_cache`` before each test makes test order
    irrelevant.
    """

    names = ("emm_settings.sources", "emm_settings.snapshot", "emm_settings.dotenv")
    saved_levels = {name: logging.getLogger(name).level for name in names}

    # Clear stale per-logger caches on the module-cached loggers, so that the
    # next isEnabledFor() call recomputes against the (possibly raised) root
    # level instead of returning a stale False from a prior test.
    import emm_settings.dotenv as _dotenv_mod
    import emm_settings.sources as _sources_mod

    for mod in (_dotenv_mod, _sources_mod):
        cache = getattr(mod._logger, "_cache", None)
        if isinstance(cache, dict):
            cache.clear()

    try:
        yield
    finally:
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)
