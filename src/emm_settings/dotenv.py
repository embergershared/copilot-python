"""Optional ``.env`` file loading via ``python-dotenv``.

Loaded paths are returned so callers can log them once logging is configured.
The loader is intentionally silent on success because it is expected to run
*before* the application's logging pipeline is set up.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_load_dotenv: Any
try:
    from dotenv import load_dotenv as _load_dotenv

    _HAS_DOTENV = True
except ImportError:  # pragma: no cover - protected optional import
    _load_dotenv = None
    _HAS_DOTENV = False

_logger = logging.getLogger("emm_settings.dotenv")
_missing_dotenv_warned = False


def _logging_is_configured() -> bool:
    """Return ``True`` when the root logger has at least one handler attached."""

    return bool(logging.getLogger().handlers)


def _warn_dotenv_missing_once() -> None:
    """Emit a single stderr warning when python-dotenv cannot be imported."""

    global _missing_dotenv_warned
    if _missing_dotenv_warned:
        return
    _missing_dotenv_warned = True
    sys.stderr.write(
        "WARNING: python-dotenv not installed; .env files will be ignored.\n",
    )


def load_dotenv_files(*paths: str | Path, override: bool = False) -> list[Path]:
    """Load each ``.env`` file in order and return the paths that existed.

    The function is meant to run *before* logging is configured. On success it
    stays silent; missing files are reported via a debug log only when logging
    is already configured. When ``python-dotenv`` is missing, a single stderr
    warning is emitted on first call and the loader becomes a no-op.

    Set ``override=True`` to let later files (and ``.env`` values) override
    variables already present in the process environment.
    """

    if not _HAS_DOTENV or _load_dotenv is None:
        _warn_dotenv_missing_once()
        return []

    loaded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            if _logging_is_configured():
                _logger.debug("dotenv file missing: %s", path)
            continue

        _load_dotenv(str(path), override=override)
        loaded.append(path)

    return loaded
