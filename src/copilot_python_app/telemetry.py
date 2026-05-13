"""FastAPI-specific logging setup — delegates to emm_logging."""

from emm_logging import LoggingSettings, configure_logging


def setup_app_logging(log_level: str) -> None:
    """Configure logging for the FastAPI app using the shared module."""

    settings = LoggingSettings(level=log_level)  # type: ignore[arg-type]
    configure_logging(settings)

