"""Azure Monitor wiring helpers for emm_logging."""

from __future__ import annotations

from typing import Any

from emm_logging.config import LoggingSettings

configure_azure_monitor: Any
try:
    from azure.monitor.opentelemetry import configure_azure_monitor

    _HAS_AZURE_MONITOR = True
except ImportError:  # pragma: no cover - protected optional import
    configure_azure_monitor = None
    _HAS_AZURE_MONITOR = False


def configure_azure_sink(
    settings: LoggingSettings, *, logger_name: str
) -> tuple[bool, list[str]]:
    """Configure Azure Monitor logging integration when requested."""

    warnings: list[str] = []
    if settings.azure_connection_string is None:
        return False, warnings

    if not _HAS_AZURE_MONITOR or configure_azure_monitor is None:
        warnings.append("azure-monitor-opentelemetry not installed; azure sink disabled.")
        return False, warnings

    try:
        configure_azure_monitor(
            connection_string=settings.azure_connection_string,
            logger_name=logger_name,
        )
    except Exception as exc:  # pragma: no cover - defensive for optional dependency behavior
        warnings.append(f"azure monitor setup failed; azure sink disabled ({exc}).")
        return False, warnings

    return True, warnings
