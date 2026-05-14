"""Tests for emm_settings.snapshot — log_settings field redaction & emission."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from emm_settings import log_settings


class _SampleSettings(BaseSettings):
    """Pydantic-settings model exercising secret + plain field shapes."""

    model_config = SettingsConfigDict(env_prefix="SAMPLE_", extra="ignore")

    name: str = Field(default="svc")
    environment: str = Field(default="local")
    db_password: str = Field(default="hunter2")
    api_key: str = Field(default="key-123")
    azure_connection_string: str = Field(default="InstrumentationKey=abc")
    auth_token: str = Field(default="tok-xyz")
    custom_field: str = Field(default="visible")


# ── basic emission ────────────────────────────────────────────────────────────


def test_log_settings_emits_one_line_per_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _SampleSettings()
    with caplog.at_level(logging.INFO):
        log_settings(settings)
    field_lines = [r for r in caplog.records if "setting:" in r.getMessage()]
    assert len(field_lines) == len(settings.model_dump())


def test_log_settings_includes_non_secret_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(name="svc-A"))
    messages = [r.getMessage() for r in caplog.records]
    assert any("key=name" in m and "svc-A" in m for m in messages)


def test_log_settings_includes_environment_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(environment="dev"))
    messages = [r.getMessage() for r in caplog.records]
    assert any("key=environment" in m and "dev" in m for m in messages)


# ── built-in secret patterns ──────────────────────────────────────────────────


def test_log_settings_redacts_password_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(db_password="my-password"))
    messages = [r.getMessage() for r in caplog.records]
    assert all("my-password" not in m for m in messages)
    assert any("key=db_password" in m and "***" in m for m in messages)


def test_log_settings_redacts_api_key(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(api_key="ABCDEF"))
    messages = [r.getMessage() for r in caplog.records]
    assert all("ABCDEF" not in m for m in messages)


def test_log_settings_redacts_connection_string(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(azure_connection_string="InstrumentationKey=zzz"))
    messages = [r.getMessage() for r in caplog.records]
    assert all("zzz" not in m for m in messages)


def test_log_settings_redacts_token(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(auth_token="bearer-xyz"))
    messages = [r.getMessage() for r in caplog.records]
    assert all("bearer-xyz" not in m for m in messages)


# ── user-supplied redact ──────────────────────────────────────────────────────


def test_log_settings_user_redact_substring(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(custom_field="leaky"), redact=["custom"])
    messages = [r.getMessage() for r in caplog.records]
    assert all("leaky" not in m for m in messages)


def test_log_settings_user_redact_is_case_insensitive(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(custom_field="leaky"), redact=["CUSTOM"])
    assert all("leaky" not in r.getMessage() for r in caplog.records)


# ── logger override ───────────────────────────────────────────────────────────


def test_log_settings_uses_explicit_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = logging.getLogger("custom.snapshot.logger")
    with caplog.at_level(logging.INFO):
        log_settings(_SampleSettings(), logger=target)
    assert any(r.name == "custom.snapshot.logger" for r in caplog.records)


# ── plain-object fallback ─────────────────────────────────────────────────────


def test_log_settings_accepts_plain_object_via_vars(
    caplog: pytest.LogCaptureFixture,
) -> None:
    obj = SimpleNamespace(name="svc", api_key="hidden-key", debug=True)
    with caplog.at_level(logging.INFO):
        log_settings(obj)
    messages = [r.getMessage() for r in caplog.records]
    assert any("key=name" in m for m in messages)
    assert all("hidden-key" not in m for m in messages)
