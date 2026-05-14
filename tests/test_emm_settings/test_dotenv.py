"""Tests for emm_settings.dotenv — file loading, override, missing dependency."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import emm_settings.dotenv as dotenv_mod
from emm_settings import load_dotenv_files


@pytest.fixture(autouse=True)
def _reset_missing_dotenv_warning() -> None:
    """Clear the once-per-process warning sentinel between tests."""
    dotenv_mod._missing_dotenv_warned = False


# ── happy path ────────────────────────────────────────────────────────────────


def test_loads_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LOAD_TEST_VAR=loaded\n", encoding="utf-8")
    monkeypatch.delenv("LOAD_TEST_VAR", raising=False)

    loaded = load_dotenv_files(env_file)

    assert loaded == [env_file]
    import os

    assert os.environ.get("LOAD_TEST_VAR") == "loaded"


def test_returns_empty_when_no_files_provided() -> None:
    assert load_dotenv_files() == []


def test_missing_file_is_skipped_silently(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.env"
    assert load_dotenv_files(missing) == []


def test_missing_file_emits_debug_when_logging_configured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "missing.env"
    # Ensure the root logger has at least one handler so _logging_is_configured returns True.
    root = logging.getLogger()
    root.addHandler(logging.NullHandler())
    try:
        with caplog.at_level(logging.DEBUG):
            load_dotenv_files(missing)
    finally:
        root.handlers.pop()

    assert any("missing" in r.getMessage() for r in caplog.records)


def test_missing_file_silent_when_logging_not_configured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "missing.env"
    # Strip handlers so _logging_is_configured returns False.
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    try:
        with caplog.at_level(logging.DEBUG):
            load_dotenv_files(missing)
    finally:
        root.handlers = saved

    assert not any("missing" in r.getMessage() for r in caplog.records)


def test_mixed_existing_and_missing_returns_only_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = tmp_path / "real.env"
    existing.write_text("MIXED_VAR=ok\n", encoding="utf-8")
    missing = tmp_path / "ghost.env"
    monkeypatch.delenv("MIXED_VAR", raising=False)

    loaded = load_dotenv_files(missing, existing)

    assert loaded == [existing]


# ── override flag ─────────────────────────────────────────────────────────────


def test_override_false_keeps_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OVERRIDE_TEST=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OVERRIDE_TEST", "from-process")

    load_dotenv_files(env_file, override=False)

    import os

    assert os.environ["OVERRIDE_TEST"] == "from-process"


def test_override_true_replaces_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OVERRIDE_TEST=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OVERRIDE_TEST", "from-process")

    load_dotenv_files(env_file, override=True)

    import os

    assert os.environ["OVERRIDE_TEST"] == "from-file"


# ── string vs Path arguments ──────────────────────────────────────────────────


def test_string_path_argument_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("STR_PATH_VAR=ok\n", encoding="utf-8")
    monkeypatch.delenv("STR_PATH_VAR", raising=False)

    loaded = load_dotenv_files(str(env_file))

    assert loaded == [env_file]


# ── missing python-dotenv graceful path ───────────────────────────────────────


def test_missing_dotenv_returns_empty_and_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(dotenv_mod, "_HAS_DOTENV", False)
    monkeypatch.setattr(dotenv_mod, "_load_dotenv", None)

    env_file = tmp_path / ".env"
    env_file.write_text("X=1\n", encoding="utf-8")

    assert load_dotenv_files(env_file) == []
    first = capsys.readouterr().err
    assert "python-dotenv" in first

    # Second call must NOT re-emit the warning.
    assert load_dotenv_files(env_file) == []
    second = capsys.readouterr().err
    assert second == ""
