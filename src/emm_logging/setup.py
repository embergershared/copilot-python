"""Runtime logging configuration entry point for emm_logging."""

from __future__ import annotations

import logging
import sys
from contextlib import suppress
from dataclasses import dataclass, field

from emm_logging._handlers.azure import configure_azure_sink
from emm_logging._handlers.console import build_console_handler
from emm_logging._handlers.seq import build_seq_handler
from emm_logging.config import LoggingSettings


@dataclass
class LoggingResult:
    """Describe which logging sinks were configured."""

    console: bool
    seq: bool
    azure_monitor: bool
    warnings: list[str] = field(default_factory=list)


def _fallback_console_handler() -> logging.Handler:
    """Create a conservative stderr console handler for failure paths."""

    fallback_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fallback_handler.setFormatter(formatter)
    return fallback_handler


def configure_logging(
    settings: LoggingSettings | None = None,
    *,
    extra_handlers: list[logging.Handler] | None = None,
) -> LoggingResult:
    """Configure root logging with console output and optional remote sinks."""

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
            format="json",
            service_name="unknown-service",
            seq_url=None,
            seq_api_key=None,
            azure_connection_string=None,
        )
        warnings.append("Failed to load LOG_* settings; defaults were used.")

    try:
        console_handler, console_warnings = build_console_handler(active_settings)
        warnings.extend(console_warnings)
        configured_handlers.append(console_handler)

        seq_handler, seq_warnings = build_seq_handler(active_settings)
        warnings.extend(seq_warnings)
        if seq_handler is not None:
            configured_handlers.append(seq_handler)
            seq_enabled = True

        azure_enabled, azure_warnings = configure_azure_sink(
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
        logging.getLogger(__name__).info("logging_configured")

    return LoggingResult(
        console=True,
        seq=seq_enabled,
        azure_monitor=azure_enabled,
        warnings=warnings,
    )
