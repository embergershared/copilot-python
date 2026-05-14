"""Tests for uvicorn logger unification."""

from __future__ import annotations

import logging

from copilot_python_app.main import _unify_uvicorn_loggers


def test_unify_uvicorn_loggers_strips_handlers_and_enables_propagate() -> None:
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.StreamHandler()]
        logger.propagate = False

    _unify_uvicorn_loggers()

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True


def test_unify_uvicorn_loggers_is_idempotent() -> None:
    _unify_uvicorn_loggers()
    _unify_uvicorn_loggers()
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True
