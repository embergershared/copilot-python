"""Fixtures shared across all emm_logging test modules."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest


class _JsonCaptureHandler(logging.Handler):
    """In-memory handler that parses each emitted record as JSON."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(json.loads(self.format(record)))
        except (json.JSONDecodeError, Exception):
            self.records.append({"_raw": self.format(record)})


@pytest.fixture()
def json_capture() -> _JsonCaptureHandler:
    """Return a fresh JSON-capture handler; caller attaches/detaches as needed."""
    return _JsonCaptureHandler()


def make_log_record(
    msg: str = "test message",
    level: int = logging.INFO,
    name: str = "test.logger",
    **extra: Any,
) -> logging.LogRecord:
    """Build a ``LogRecord`` suitable for direct formatter/handler testing."""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="test_file.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record
