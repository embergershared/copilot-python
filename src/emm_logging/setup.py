"""Runtime logging configuration entry point for emm_logging."""

from __future__ import annotations

import logging
import sys
from contextlib import suppress
from dataclasses import dataclass, field

from emm_logging.config import LoggingSettings
from emm_logging.sinks.azure import build_azure_sink
from emm_logging.sinks.console import build_console_sink
from emm_logging.sinks.seq import build_seq_sink


@dataclass
class LoggingSinks:
    """Describe which logging sinks were configured.

    The dataclass form keeps the result lightweight (no Pydantic dependency)
    and easy to inspect from tests or operator-facing diagnostics. The
    ``service_name``/``service_version`` fields echo the active settings so
    callers can correlate the sinks with the service identity that produced
    them.
    """

    console: bool
    seq: bool
    azure_monitor: bool
    service_name: str = "unknown-service"
    service_version: str = "0.0.0"
    warnings: list[str] = field(default_factory=list)


def _fallback_console_handler() -> logging.Handler:
    """Create a conservative stderr console handler for failure paths."""

    fallback_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fallback_handler.setFormatter(formatter)
    return fallback_handler


def setup_logging(
    settings: LoggingSettings | None = None,
    *,
    extra_handlers: list[logging.Handler] | None = None,
) -> LoggingSinks:
    """Configure root logging with console output and optional remote sinks.

    Pass an explicit :class:`LoggingSettings` instance to bypass environment
    parsing (useful for tests or pre-validated settings). Additional
    ``extra_handlers`` are attached to the root logger after the built-in
    sinks. The function never raises: any catastrophic failure falls back to a
    plain stderr console handler so the application keeps logging.
    """

    warnings: list[str] = []
    seq_enabled = False
    azure_enabled = False
    configured_handlers: list[logging.Handler] = []

    try:
        active_settings = settings or LoggingSettings()
    except Exception as exc:  # pragma: no cover - defensive fallback for bad env config
        sys.stderr.write(f"WARNING: failed to load logging settings; using defaults ({exc}).\n")
        active_settings = LoggingSettings(
            level="INFO",
            console_format="json",
            service_name="unknown-service",
            service_version="0.0.0",
            seq_url=None,
            seq_api_key=None,
            azure_connection_string=None,
        )
        warnings.append("Failed to load LOG_* settings; defaults were used.")

    try:
        console_handler, console_warnings = build_console_sink(active_settings)
        warnings.extend(console_warnings)
        configured_handlers.append(console_handler)

        seq_handler, seq_warnings = build_seq_sink(active_settings)
        warnings.extend(seq_warnings)
        if seq_handler is not None:
            configured_handlers.append(seq_handler)
            seq_enabled = True

        azure_enabled, azure_warnings = build_azure_sink(
            active_settings,
            logger_name=active_settings.service_name,
        )
        warnings.extend(azure_warnings)

        if extra_handlers:
            configured_handlers.extend(extra_handlers)

        root_logger = logging.getLogger()
        previous_handlers = list(root_logger.handlers)
        root_logger.handlers = configured_handlers
        root_logger.setLevel(active_settings.level)

        for handler in previous_handlers:
            if handler in configured_handlers:
                continue
            try:
                handler.close()
            except Exception:  # pragma: no cover - defensive cleanup
                continue
    except Exception as exc:  # pragma: no cover - defensive global safety net
        sys.stderr.write(
            f"WARNING: logging configuration failed; using fallback console ({exc}).\n"
        )
        fallback_handler = _fallback_console_handler()
        root_logger = logging.getLogger()
        root_logger.handlers = [fallback_handler]
        root_logger.setLevel(logging.INFO)
        warnings.append("Logging configuration failed; fallback console logger enabled.")
        seq_enabled = False
        azure_enabled = False

    with suppress(Exception):
        logging.getLogger(__name__).info(
            "logging_configured",
            extra={
                "service_name": active_settings.service_name,
                "service_version": active_settings.service_version,
            },
        )

    return LoggingSinks(
        console=True,
        seq=seq_enabled,
        azure_monitor=azure_enabled,
        service_name=active_settings.service_name,
        service_version=active_settings.service_version,
        warnings=warnings,
    )
