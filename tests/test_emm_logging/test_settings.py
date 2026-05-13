"""Tests for LoggingSettings — LOG_* env-var contract, defaults, validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emm_logging import LoggingSettings

# ── defaults ──────────────────────────────────────────────────────────────────


def test_default_level_is_info() -> None:
    assert LoggingSettings().level == "INFO"


def test_default_format_is_json() -> None:
    assert LoggingSettings().format == "json"


def test_default_service_name_is_unknown_service() -> None:
    assert LoggingSettings().service_name == "unknown-service"


def test_default_seq_url_is_none() -> None:
    assert LoggingSettings().seq_url is None


def test_default_seq_api_key_is_none() -> None:
    assert LoggingSettings().seq_api_key is None


def test_default_azure_connection_string_is_none() -> None:
    assert LoggingSettings().azure_connection_string is None


def test_all_defaults_without_any_log_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset every LOG_* var — safe defaults must still apply."""
    for var in [
        "LOG_LEVEL",
        "LOG_FORMAT",
        "LOG_SERVICE_NAME",
        "LOG_SEQ_URL",
        "LOG_SEQ_API_KEY",
        "LOG_AZURE_CONNECTION_STRING",
    ]:
        monkeypatch.delenv(var, raising=False)

    s = LoggingSettings()
    assert s.level == "INFO"
    assert s.format == "json"
    assert s.service_name == "unknown-service"
    assert s.seq_url is None
    assert s.seq_api_key is None
    assert s.azure_connection_string is None


# ── env-var parsing ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_log_level_accepted_from_env(level: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", level)
    assert LoggingSettings().level == level


@pytest.mark.parametrize("fmt", ["json", "text"])
def test_log_format_accepted_from_env(fmt: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", fmt)
    assert LoggingSettings().format == fmt


def test_log_service_name_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SERVICE_NAME", "my-api")
    assert LoggingSettings().service_name == "my-api"


def test_log_seq_url_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    s = LoggingSettings()
    assert s.seq_url is not None
    assert "5341" in str(s.seq_url)


def test_log_seq_url_with_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341/")
    assert LoggingSettings().seq_url is not None


def test_log_seq_api_key_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_API_KEY", "secret-key")
    assert LoggingSettings().seq_api_key == "secret-key"


def test_log_azure_connection_string_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc123")
    assert LoggingSettings().azure_connection_string == "InstrumentationKey=abc123"


# ── validation errors ─────────────────────────────────────────────────────────


def test_invalid_level_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
    with pytest.raises(ValidationError):
        LoggingSettings()


def test_invalid_format_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "xml")
    with pytest.raises(ValidationError):
        LoggingSettings()


def test_invalid_seq_url_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "not-a-url")
    with pytest.raises(ValidationError):
        LoggingSettings()


# ── extra / unknown vars ──────────────────────────────────────────────────────


def test_unknown_log_env_vars_are_silently_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """extra='ignore' contract: LOG_UNKNOWN_* must not raise."""
    monkeypatch.setenv("LOG_UNKNOWN_FIELD", "ignored")
    LoggingSettings()  # must not raise


def test_non_log_prefix_vars_do_not_affect_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_LEVEL should not influence LOG_LEVEL."""
    monkeypatch.setenv("APP_LEVEL", "DEBUG")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert LoggingSettings().level == "INFO"
