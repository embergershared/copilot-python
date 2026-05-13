"""Logging and telemetry setup."""

import logging
from logging.config import dictConfig


def configure_logging(log_level: str) -> None:
    """Configure structured console logging for the application."""

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "event=%(message)s"
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )
    logging.getLogger(__name__).debug("logging_configured")

