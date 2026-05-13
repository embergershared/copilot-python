"""Console handler factories for emm_logging."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, cast

from emm_logging.config import LoggingSettings

JsonFormatter: Any
try:
    from pythonjsonlogger.json import JsonFormatter

    _HAS_PYTHON_JSON_LOGGER = True
except ImportError:  # pragma: no cover - protected optional import
    JsonFormatter = None
    _HAS_PYTHON_JSON_LOGGER = False


def _build_text_formatter() -> logging.Formatter:
    """Return the fallback text formatter used for console output."""

    return logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")


def _build_json_formatter() -> logging.Formatter:
    """Return the JSON formatter configured for UTC ISO-8601 timestamps."""

    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(message)s %(name)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime
    return cast(logging.Formatter, formatter)


def build_console_handler(settings: LoggingSettings) -> tuple[logging.Handler, list[str]]:
    """Build the always-on console handler and return any degradation warnings."""

    warnings: list[str] = []
    handler = logging.StreamHandler(stream=sys.stdout)

    if settings.format == "text":
        handler.setFormatter(_build_text_formatter())
        return handler, warnings

    if not _HAS_PYTHON_JSON_LOGGER or JsonFormatter is None:
        warnings.append("python-json-logger not installed; falling back to text console logs.")
        handler.setFormatter(_build_text_formatter())
        return handler, warnings

    handler.setFormatter(_build_json_formatter())
    return handler, warnings
