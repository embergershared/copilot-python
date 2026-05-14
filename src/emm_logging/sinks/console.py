"""Console sink builder for emm_logging."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import IO, Any, cast

from emm_logging.config import LoggingSettings

JsonFormatter: Any
try:
    from pythonjsonlogger.json import JsonFormatter

    _HAS_PYTHON_JSON_LOGGER = True
except ImportError:  # pragma: no cover - protected optional import
    JsonFormatter = None
    _HAS_PYTHON_JSON_LOGGER = False


_TEXT_FORMAT = "%(asctime)s [%(levelname)s] (%(name)s.%(funcName)s) %(message)s"

_ANSI_RESET = "\033[0m"
_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "\033[36m",       # cyan
    "INFO": "\033[32m",        # green
    "WARNING": "\033[33m",     # yellow
    "ERROR": "\033[31m",       # red
    "CRITICAL": "\033[1;31m",  # bold red
}


def _should_use_color(stream: IO[str]) -> bool:
    """Decide whether to emit ANSI color codes for *stream*.

    Honors the de-facto standards `NO_COLOR <https://no-color.org/>`_ and
    ``FORCE_COLOR``; otherwise enables color only when the stream is a TTY.
    """

    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    isatty = getattr(stream, "isatty", None)
    return bool(isatty() if callable(isatty) else False)


class _ColorTextFormatter(logging.Formatter):
    """Text formatter that wraps ``levelname`` in ANSI color codes."""

    def __init__(self, fmt: str, *, use_color: bool) -> None:
        """Initialize the formatter and remember whether to colorize output."""

        super().__init__(fmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        """Format *record*, optionally wrapping the level name in ANSI colors.

        The mutation is restored before returning so that downstream handlers
        (e.g., the Seq sink reading ``record.levelname`` directly) see the
        original value.
        """

        if not self._use_color:
            return super().format(record)

        color = _LEVEL_COLORS.get(record.levelname)
        if color is None:
            return super().format(record)

        original = record.levelname
        record.levelname = f"{color}{original}{_ANSI_RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original


def _build_text_formatter(stream: IO[str]) -> logging.Formatter:
    """Return the human-readable text formatter used for console output."""

    return _ColorTextFormatter(_TEXT_FORMAT, use_color=_should_use_color(stream))


def _build_json_formatter() -> logging.Formatter:
    """Return the JSON formatter configured for UTC ISO-8601 timestamps."""

    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(message)s %(name)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime
    return cast(logging.Formatter, formatter)


def build_console_sink(settings: LoggingSettings) -> tuple[logging.Handler, list[str]]:
    """Build the always-on console handler and return any degradation warnings.

    The console sink always returns a handler so applications keep at least one
    log destination. When the optional ``python-json-logger`` dependency is
    missing or ``console_format`` is ``"text"``, a plain text formatter is used.
    Text output is colorized when the destination stream is a TTY (overridable
    via ``NO_COLOR`` / ``FORCE_COLOR`` environment variables).
    """

    warnings: list[str] = []
    stream = sys.stdout
    handler = logging.StreamHandler(stream=stream)

    if settings.console_format == "text":
        handler.setFormatter(_build_text_formatter(stream))
        return handler, warnings

    if not _HAS_PYTHON_JSON_LOGGER or JsonFormatter is None:
        warnings.append("python-json-logger not installed; falling back to text console logs.")
        handler.setFormatter(_build_text_formatter(stream))
        return handler, warnings

    handler.setFormatter(_build_json_formatter())
    return handler, warnings

