"""Utility helpers exposed by emm_logging.

These helpers mirror the small ergonomic conveniences popularized by the
``bc_config`` reference module: a thin :func:`get_logger` wrapper for the
public API surface and :func:`timestamp_prefix` for filename-safe timestamps.
"""

from __future__ import annotations

import logging
from datetime import datetime


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib logger bound to ``name``.

    Thin wrapper over :func:`logging.getLogger` so application code can import
    a single logger factory from ``emm_logging`` instead of mixing standard
    library imports with the rest of the public API.
    """

    return logging.getLogger(name)


def timestamp_prefix() -> str:
    """Return a filename-safe local timestamp in ``YYYY-MM-DD_HHhMMmSSsmmm`` form.

    The format mirrors the helper from ``bc_config.py``: dashes inside the date,
    underscores between date and time, and ``h``/``m``/``s`` separators inside
    the time component, ending with three-digit milliseconds. The timestamp is
    derived from local time so it lines up with operator-facing log output.
    """

    now = datetime.now()
    milliseconds = now.microsecond // 1000
    return f"{now.strftime('%Y-%m-%d_%Hh%Mm%S')}s{milliseconds:03d}"
