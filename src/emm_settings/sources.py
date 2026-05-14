"""Typed environment-variable accessors with structured logging.

Every read is logged so operators can audit configuration at startup. Values
flagged with ``secret=True`` are redacted in log output. Coercion failures fall
back to the supplied default with a warning instead of raising, except for
:func:`env_str` with ``required=True``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

# This module is a peer of ``emm_logging``; importing the latter would couple
# the two modules unnecessarily. Use stdlib logging directly so ``emm_settings``
# stays standalone-portable.
_logger = logging.getLogger("emm_settings.sources")

_REDACTED = "***"
_TRUE_TOKENS = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "off"})


def _display(value: object, *, secret: bool) -> str:
    """Format a value for logging, redacting when ``secret`` is set."""

    if secret:
        return _REDACTED
    return str(value)


def _log_env(key: str, source: str, value: object, *, secret: bool) -> None:
    """Emit a structured ``env source`` log line at the appropriate level."""

    level = logging.INFO if source == "env" else logging.DEBUG
    _logger.log(
        level,
        "env source: key=%s source=%s value=%s",
        key,
        source,
        _display(value, secret=secret),
    )


def _log_coercion_failure(
    key: str, raw: str, target: str, default: object, *, secret: bool
) -> None:
    """Warn when a raw env value cannot be coerced to the requested type."""

    _logger.warning(
        "env coercion failed: key=%s target=%s raw=%s falling back to default=%s",
        key,
        target,
        _display(raw, secret=secret),
        _display(default, secret=secret),
    )


def env_str(
    key: str,
    default: str | None = None,
    *,
    required: bool = False,
    secret: bool = False,
) -> str | None:
    """Read a string env var, logging the source and respecting ``required``.

    When ``required=True`` and neither the environment nor a default supplies a
    value, raise :class:`RuntimeError`. Otherwise return the env value or the
    default (which may be ``None``).
    """

    raw = os.environ.get(key)
    if raw is not None:
        _log_env(key, "env", raw, secret=secret)
        return raw

    if required and default is None:
        raise RuntimeError(f"Required env var {key} is not set")

    _log_env(key, "default", default, secret=secret)
    return default


def env_int(key: str, default: int, *, secret: bool = False) -> int:
    """Read an integer env var, falling back to ``default`` on failure."""

    raw = os.environ.get(key)
    if raw is None:
        _log_env(key, "default", default, secret=secret)
        return default

    try:
        value = int(raw)
    except ValueError:
        _log_coercion_failure(key, raw, "int", default, secret=secret)
        return default

    _log_env(key, "env", value, secret=secret)
    return value


def env_float(key: str, default: float, *, secret: bool = False) -> float:
    """Read a float env var, falling back to ``default`` on failure."""

    raw = os.environ.get(key)
    if raw is None:
        _log_env(key, "default", default, secret=secret)
        return default

    try:
        value = float(raw)
    except ValueError:
        _log_coercion_failure(key, raw, "float", default, secret=secret)
        return default

    _log_env(key, "env", value, secret=secret)
    return value


def env_bool(key: str, default: bool, *, secret: bool = False) -> bool:
    """Read a boolean env var (``1/true/yes/on`` or ``0/false/no/off``).

    Comparison is case-insensitive; unknown tokens log a warning and fall back
    to ``default``.
    """

    raw = os.environ.get(key)
    if raw is None:
        _log_env(key, "default", default, secret=secret)
        return default

    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        _log_env(key, "env", True, secret=secret)
        return True
    if token in _FALSE_TOKENS:
        _log_env(key, "env", False, secret=secret)
        return False

    _log_coercion_failure(key, raw, "bool", default, secret=secret)
    return default


def env_path(key: str, default: str | Path, *, secret: bool = False) -> Path:
    """Read a filesystem path env var, returning a :class:`pathlib.Path`."""

    raw = os.environ.get(key)
    if raw is None:
        path = Path(default)
        _log_env(key, "default", path, secret=secret)
        return path

    path = Path(raw)
    _log_env(key, "env", path, secret=secret)
    return path


def env_csv[T](
    key: str,
    default: str = "",
    *,
    sep: str = ",",
    item_type: Callable[[str], T] = str,  # type: ignore[assignment]
    secret: bool = False,
) -> list[T]:
    """Read a comma-separated env var, coercing each item via ``item_type``.

    Empty entries (resulting from leading/trailing/duplicate separators) are
    skipped. If any item fails to coerce, the whole list falls back to the
    parsed ``default`` and a warning is logged.
    """

    raw = os.environ.get(key)
    source = "env" if raw is not None else "default"
    text = raw if raw is not None else default

    parts = [chunk.strip() for chunk in text.split(sep) if chunk.strip()]

    try:
        values: list[T] = [item_type(part) for part in parts]
    except (ValueError, TypeError):
        # Re-parse the default so the fallback value matches the declared type.
        default_parts = [chunk.strip() for chunk in default.split(sep) if chunk.strip()]
        try:
            fallback: list[T] = [item_type(part) for part in default_parts]
        except (ValueError, TypeError):
            fallback = []
        _log_coercion_failure(
            key,
            text,
            f"list[{getattr(item_type, '__name__', 'item')}]",
            fallback,
            secret=secret,
        )
        return fallback

    _log_env(key, source, values, secret=secret)
    return values
