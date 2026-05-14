"""Portability gate — importing emm_logging must not pull in FastAPI/Starlette/Uvicorn.

Uses subprocess isolation so the current test session's already-imported modules
cannot produce a false pass.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Absolute path to the src/ directory so the subprocess can find emm_logging
# regardless of how the package is (or isn't) installed in the active venv.
_SRC_DIR = str(Path(__file__).parent.parent.parent / "src")


def _run_isolation_check(extra_script: str) -> subprocess.CompletedProcess[str]:
    """Run *extra_script* in a clean Python process with emm_logging importable."""
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{_SRC_DIR}'); "
        "mods_before = set(sys.modules.keys()); "
        "import emm_logging; "
        "new_mods = set(sys.modules.keys()) - mods_before; "
        + extra_script
    )
    env = {**os.environ, "PYTHONPATH": _SRC_DIR}
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )


def test_importing_emm_logging_does_not_import_fastapi() -> None:
    result = _run_isolation_check(
        "assert 'fastapi' not in new_mods, "
        "f'fastapi was imported as a side-effect: {new_mods & {\"fastapi\"}}'"
    )
    assert result.returncode == 0, (
        f"Portability violation — fastapi imported.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


def test_importing_emm_logging_does_not_import_starlette() -> None:
    result = _run_isolation_check(
        "assert 'starlette' not in new_mods, "
        "f'starlette was imported as a side-effect: {new_mods & {\"starlette\"}}'"
    )
    assert result.returncode == 0, (
        f"Portability violation — starlette imported.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


def test_importing_emm_logging_does_not_import_uvicorn() -> None:
    result = _run_isolation_check(
        "assert 'uvicorn' not in new_mods, "
        "f'uvicorn was imported as a side-effect: {new_mods & {\"uvicorn\"}}'"
    )
    assert result.returncode == 0, (
        f"Portability violation — uvicorn imported.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


def test_emm_logging_public_api_importable_in_isolation() -> None:
    """Smoke-test: the public API symbols exist in a clean process."""
    result = _run_isolation_check(
        "from emm_logging import "
        "LoggingSettings, setup_logging, LoggingSinks, get_logger, timestamp_prefix; "
        "assert LoggingSettings is not None; "
        "assert setup_logging is not None; "
        "assert LoggingSinks is not None; "
        "assert get_logger is not None; "
        "assert timestamp_prefix is not None"
    )
    assert result.returncode == 0, (
        f"Public API broken in isolation.\n"
        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
