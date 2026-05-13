"""Reusable logging configuration package."""

from emm_logging.config import LoggingSettings
from emm_logging.setup import LoggingResult, configure_logging

__all__ = ["LoggingResult", "LoggingSettings", "configure_logging"]
