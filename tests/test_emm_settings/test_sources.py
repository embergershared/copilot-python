"""Tests for emm_settings.sources — typed accessors with structured logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from emm_settings import env_bool, env_csv, env_float, env_int, env_path, env_str

_LOGGER_NAME = "emm_settings.sources"


# ── env_str ───────────────────────────────────────────────────────────────────


def test_env_str_returns_env_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STR_KEY", "hello")
    assert env_str("STR_KEY") == "hello"


def test_env_str_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STR_KEY", raising=False)
    assert env_str("STR_KEY", default="fallback") == "fallback"


def test_env_str_returns_none_when_unset_and_no_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STR_KEY", raising=False)
    assert env_str("STR_KEY") is None


def test_env_str_required_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STR_KEY", raising=False)
    with pytest.raises(RuntimeError, match="STR_KEY"):
        env_str("STR_KEY", required=True)


def test_env_str_required_with_default_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STR_KEY", raising=False)
    assert env_str("STR_KEY", default="d", required=True) == "d"


def test_env_str_logs_env_at_info_level(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STR_KEY", "v")
    with caplog.at_level(logging.INFO):
        env_str("STR_KEY")
    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("source=env" in r.getMessage() for r in info_records)


def test_env_str_logs_default_at_debug_level(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STR_KEY", raising=False)
    with caplog.at_level(logging.DEBUG):
        env_str("STR_KEY", default="d")
    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("source=default" in r.getMessage() for r in debug_records)


def test_env_str_secret_redacts_env_value(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRET_KEY", "supersecret")
    with caplog.at_level(logging.INFO):
        env_str("SECRET_KEY", secret=True)
    messages = [r.getMessage() for r in caplog.records]
    assert all("supersecret" not in m for m in messages)
    assert any("***" in m for m in messages)


def test_env_str_secret_redacts_default_value(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with caplog.at_level(logging.DEBUG):
        env_str("SECRET_KEY", default="default-secret", secret=True)
    messages = [r.getMessage() for r in caplog.records]
    assert all("default-secret" not in m for m in messages)


# ── env_int ───────────────────────────────────────────────────────────────────


def test_env_int_parses_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INT_KEY", "42")
    assert env_int("INT_KEY", default=0) == 42


def test_env_int_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INT_KEY", raising=False)
    assert env_int("INT_KEY", default=99) == 99


def test_env_int_falls_back_on_coercion_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("INT_KEY", "not-a-number")
    with caplog.at_level(logging.WARNING):
        result = env_int("INT_KEY", default=7)
    assert result == 7
    assert any("coercion failed" in r.getMessage() for r in caplog.records)


def test_env_int_secret_redaction(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INT_KEY", "12345")
    with caplog.at_level(logging.INFO):
        env_int("INT_KEY", default=0, secret=True)
    assert all("12345" not in r.getMessage() for r in caplog.records)


# ── env_float ─────────────────────────────────────────────────────────────────


def test_env_float_parses_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOAT_KEY", "3.14")
    assert env_float("FLOAT_KEY", default=0.0) == pytest.approx(3.14)


def test_env_float_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLOAT_KEY", raising=False)
    assert env_float("FLOAT_KEY", default=1.5) == pytest.approx(1.5)


def test_env_float_falls_back_on_coercion_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FLOAT_KEY", "nope")
    with caplog.at_level(logging.WARNING):
        result = env_float("FLOAT_KEY", default=2.0)
    assert result == pytest.approx(2.0)
    assert any("coercion failed" in r.getMessage() for r in caplog.records)


# ── env_bool ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("token", ["1", "true", "True", "TRUE", "yes", "Yes", "on", "ON"])
def test_env_bool_truthy_tokens(token: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOL_KEY", token)
    assert env_bool("BOOL_KEY", default=False) is True


@pytest.mark.parametrize("token", ["0", "false", "False", "FALSE", "no", "off"])
def test_env_bool_falsy_tokens(token: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOL_KEY", token)
    assert env_bool("BOOL_KEY", default=True) is False


def test_env_bool_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOOL_KEY", raising=False)
    assert env_bool("BOOL_KEY", default=True) is True


def test_env_bool_unknown_token_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("BOOL_KEY", "maybe")
    with caplog.at_level(logging.WARNING):
        result = env_bool("BOOL_KEY", default=True)
    assert result is True
    assert any("coercion failed" in r.getMessage() for r in caplog.records)


def test_env_bool_secret_redacts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("BOOL_KEY", "true")
    with caplog.at_level(logging.INFO):
        env_bool("BOOL_KEY", default=False, secret=True)
    assert all("True" not in r.getMessage() for r in caplog.records)


# ── env_path ──────────────────────────────────────────────────────────────────


def test_env_path_returns_path_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH_KEY", "/tmp/example")
    result = env_path("PATH_KEY", default="/var/lib")
    assert isinstance(result, Path)
    assert str(result).replace("\\", "/").endswith("tmp/example")


def test_env_path_returns_default_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PATH_KEY", raising=False)
    result = env_path("PATH_KEY", default="/data")
    assert isinstance(result, Path)
    assert str(result).replace("\\", "/").endswith("/data") or str(result) == "/data"


def test_env_path_secret_redacts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("PATH_KEY", "/secret/path")
    with caplog.at_level(logging.INFO):
        env_path("PATH_KEY", default="/x", secret=True)
    assert all("secret/path" not in r.getMessage() for r in caplog.records)


# ── env_csv ───────────────────────────────────────────────────────────────────


def test_env_csv_parses_string_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSV_KEY", "a,b,c")
    assert env_csv("CSV_KEY") == ["a", "b", "c"]


def test_env_csv_strips_whitespace_and_drops_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CSV_KEY", " a , , b ,, c ")
    assert env_csv("CSV_KEY") == ["a", "b", "c"]


def test_env_csv_uses_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CSV_KEY", raising=False)
    assert env_csv("CSV_KEY", default="x,y") == ["x", "y"]


def test_env_csv_custom_separator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSV_KEY", "a;b;c")
    assert env_csv("CSV_KEY", sep=";") == ["a", "b", "c"]


def test_env_csv_int_item_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSV_KEY", "1,2,3")
    assert env_csv("CSV_KEY", item_type=int) == [1, 2, 3]


def test_env_csv_coercion_failure_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CSV_KEY", "1,bad,3")
    with caplog.at_level(logging.WARNING):
        result = env_csv("CSV_KEY", default="9,10", item_type=int)
    assert result == [9, 10]
    assert any("coercion failed" in r.getMessage() for r in caplog.records)


def test_env_csv_secret_redacts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CSV_KEY", "secret-a,secret-b")
    with caplog.at_level(logging.INFO):
        env_csv("CSV_KEY", secret=True)
    assert all("secret-a" not in r.getMessage() for r in caplog.records)


def test_env_csv_returns_empty_when_no_default_and_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CSV_KEY", raising=False)
    assert env_csv("CSV_KEY") == []
