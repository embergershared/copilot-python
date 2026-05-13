"""Seq sink handler for CLEF over HTTP."""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from datetime import UTC, datetime
from typing import Any

from emm_logging.config import LoggingSettings

_requests: Any
try:
    import requests as _requests

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover - protected optional import
    _requests = None
    _HAS_REQUESTS = False

_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class SeqHandler(logging.Handler):
    """Ship Python log records to Seq's CLEF HTTP endpoint."""

    def __init__(self, seq_url: str, api_key: str | None) -> None:
        """Initialize the Seq handler with endpoint and optional API key."""

        super().__init__()
        self._endpoint = f"{seq_url.rstrip('/')}/api/events/raw"
        self._api_key = api_key
        self._last_warning_at: float = -1_000_000.0

    def emit(self, record: logging.LogRecord) -> None:
        """Send a single log record to Seq and never raise on failure."""

        if not _HAS_REQUESTS or _requests is None:
            self._warn_rate_limited("Seq handler disabled because requests is not installed.")
            return

        event = self._build_event(record)
        payload = f"{json.dumps(event, default=str)}\n"
        headers = {"Content-Type": "application/vnd.serilog.clef"}
        if self._api_key:
            headers["X-Seq-ApiKey"] = self._api_key

        try:
            response = _requests.post(
                self._endpoint,
                data=payload,
                headers=headers,
                timeout=2.0,
            )
            response.raise_for_status()
        except _requests.RequestException as exc:
            self._warn_rate_limited(f"Seq emit failed: {exc}")
        except Exception as exc:  # pragma: no cover - defensive for logging internals
            self._warn_rate_limited(f"Unexpected Seq handler failure: {exc}")

    def _build_event(self, record: logging.LogRecord) -> dict[str, Any]:
        """Convert a log record into a CLEF event payload."""

        event: dict[str, Any] = {
            "@t": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "@l": record.levelname,
            "@mt": str(record.msg),
            "@m": record.getMessage(),
        }

        if record.exc_info is not None:
            event["@x"] = "".join(traceback.format_exception(*record.exc_info))

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key.startswith("_") or key in event:
                continue
            event[key] = value

        return event

    def _warn_rate_limited(self, message: str) -> None:
        """Write warning messages at most once per 60 seconds."""

        now = time.monotonic()
        if now - self._last_warning_at < 60:
            return

        self._last_warning_at = now
        sys.stderr.write(f"WARNING: {message}\n")


def build_seq_handler(settings: LoggingSettings) -> tuple[logging.Handler | None, list[str]]:
    """Build a Seq handler when configured and available."""

    warnings: list[str] = []
    if settings.seq_url is None:
        return None, warnings

    if not _HAS_REQUESTS:
        warnings.append("requests not installed; Seq sink disabled.")
        return None, warnings

    return SeqHandler(str(settings.seq_url), settings.seq_api_key), warnings
