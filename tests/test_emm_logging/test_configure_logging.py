"""Tests for configure_logging() entry point and LoggingResult contract."""

from __future__ import annotations

import logging
from dataclasses import fields as dataclass_fields
from typing import Any

import pytest

import emm_logging._handlers.azure as _azure_mod
from emm_logging import LoggingSettings, configure_logging
from emm_logging._handlers.seq import SeqHandler

# ── LoggingResult shape ───────────────────────────────────────────────────────


def test_logging_result_has_all_required_fields() -> None:
    result = configure_logging(LoggingSettings())
    names = {f.name for f in dataclass_fields(result)}
    assert names == {"console", "seq", "azure_monitor", "warnings"}


def test_logging_result_warnings_is_a_list() -> None:
    result = configure_logging(LoggingSettings())
    assert isinstance(result.warnings, list)


def test_logging_result_is_dataclass_not_pydantic() -> None:
    """LoggingResult must be a plain dataclass — no Pydantic dependency."""
    result = configure_logging(LoggingSettings())
    assert dataclass_fields(result)  # would raise TypeError if not a dataclass


# ── default config ────────────────────────────────────────────────────────────


def test_default_console_is_true() -> None:
    assert configure_logging(LoggingSettings()).console is True


def test_default_seq_is_false() -> None:
    assert configure_logging(LoggingSettings()).seq is False


def test_default_azure_monitor_is_false() -> None:
    assert configure_logging(LoggingSettings()).azure_monitor is False


def test_default_warnings_is_empty() -> None:
    assert configure_logging(LoggingSettings()).warnings == []


def test_root_logger_has_at_least_one_handler() -> None:
    configure_logging(LoggingSettings())
    assert len(logging.getLogger().handlers) >= 1


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_root_logger_level_matches_settings(level: str) -> None:
    configure_logging(LoggingSettings(level=level))
    assert logging.getLogger().level == getattr(logging, level)


def test_logging_a_message_after_configure_does_not_raise() -> None:
    configure_logging(LoggingSettings())
    logging.getLogger("emm.test").info("sanity check")


def test_none_settings_uses_env_defaults() -> None:
    result = configure_logging(None)
    assert result.console is True
    assert result.seq is False


# ── seq sink ──────────────────────────────────────────────────────────────────


def test_seq_enabled_when_url_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    result = configure_logging(LoggingSettings())
    assert result.seq is True


def test_seq_handler_attached_to_root_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    configure_logging(LoggingSettings())
    assert any(isinstance(h, SeqHandler) for h in logging.getLogger().handlers)


def test_seq_disabled_when_requests_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import emm_logging._handlers.seq as seq_mod

    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    monkeypatch.setattr(seq_mod, "_HAS_REQUESTS", False)
    result = configure_logging(LoggingSettings())
    assert result.seq is False
    assert any("requests" in w.lower() for w in result.warnings)


# ── azure sink ────────────────────────────────────────────────────────────────


def test_azure_disabled_without_connection_string() -> None:
    result = configure_logging(LoggingSettings())
    assert result.azure_monitor is False


def test_azure_warning_when_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", False)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", None)

    result = configure_logging(LoggingSettings())

    assert result.azure_monitor is False
    assert any("azure" in w.lower() for w in result.warnings)


def test_azure_enabled_when_mock_package_present(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)

    result = configure_logging(LoggingSettings())

    assert result.azure_monitor is True
    assert len(calls) == 1


def test_azure_configure_receives_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = "InstrumentationKey=test-key;IngestionEndpoint=https://example.com"
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", conn)
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)

    configure_logging(LoggingSettings())

    assert calls[0]["connection_string"] == conn


# ── configure-twice ───────────────────────────────────────────────────────────


def test_configure_twice_replaces_not_accumulates_handlers() -> None:
    configure_logging(LoggingSettings())
    count_after_first = len(logging.getLogger().handlers)
    configure_logging(LoggingSettings())
    count_after_second = len(logging.getLogger().handlers)
    assert count_after_second == count_after_first


def test_configure_twice_second_result_is_valid() -> None:
    configure_logging(LoggingSettings())
    result = configure_logging(LoggingSettings())
    assert result.console is True
    assert result.seq is False
    assert result.warnings == []


def test_configure_twice_seq_count_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seq handler must not double after second configure_logging call."""
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    configure_logging(LoggingSettings())
    first = sum(isinstance(h, SeqHandler) for h in logging.getLogger().handlers)
    configure_logging(LoggingSettings())
    second = sum(isinstance(h, SeqHandler) for h in logging.getLogger().handlers)
    assert second == first == 1


# ── extra_handlers ────────────────────────────────────────────────────────────


def test_extra_handler_is_attached_to_root() -> None:
    extra = logging.NullHandler()
    configure_logging(LoggingSettings(), extra_handlers=[extra])
    assert extra in logging.getLogger().handlers


def test_configure_twice_reused_extra_handler_not_closed() -> None:
    """An extra_handler that survives into the second call must not be closed.

    This exercises the ``if handler in configured_handlers: continue`` branch
    in setup.py's handler-cleanup loop.
    """
    extra = logging.NullHandler()
    configure_logging(LoggingSettings(), extra_handlers=[extra])
    # Second call passes the same handler object — it must still be in handlers
    configure_logging(LoggingSettings(), extra_handlers=[extra])
    assert extra in logging.getLogger().handlers





def test_multiple_extra_handlers_all_attached() -> None:
    extras = [logging.NullHandler(), logging.NullHandler()]
    configure_logging(LoggingSettings(), extra_handlers=extras)
    for h in extras:
        assert h in logging.getLogger().handlers


# ── warnings list ─────────────────────────────────────────────────────────────


def test_warnings_list_is_empty_for_clean_config() -> None:
    result = configure_logging(LoggingSettings())
    assert result.warnings == []


def test_warnings_populated_for_missing_azure_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", False)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", None)
    result = configure_logging(LoggingSettings())
    assert len(result.warnings) >= 1
