"""Tests for the console sink — JSON fields, timestamps, extras, fallback."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from emm_logging import LoggingSettings
from emm_logging.sinks.console import build_console_sink


def _make_record(
    msg: str = "test message",
    level: int = logging.INFO,
    name: str = "test.logger",
    **extra: Any,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def _json_output(
    record: logging.LogRecord,
    settings: LoggingSettings | None = None,
) -> dict[str, Any]:
    """Build console handler with json format and return parsed output."""
    s = settings or LoggingSettings(console_format="json")
    handler, _ = build_console_sink(s)
    assert handler.formatter is not None
    return dict(json.loads(handler.formatter.format(record)))


# ── required JSON field names ─────────────────────────────────────────────────


def test_json_output_has_timestamp_field() -> None:
    data = _json_output(_make_record())
    assert "timestamp" in data


def test_json_output_has_level_field() -> None:
    data = _json_output(_make_record())
    assert "level" in data


def test_json_output_has_message_field() -> None:
    data = _json_output(_make_record())
    assert "message" in data


def test_json_output_has_logger_field() -> None:
    data = _json_output(_make_record())
    assert "logger" in data


def test_json_output_does_not_use_clef_field_names() -> None:
    """Console JSON must NOT use CLEF names — those belong to the Seq sink only."""
    data = _json_output(_make_record())
    for clef_key in ("@t", "@l", "@m", "@mt"):
        assert clef_key not in data, f"CLEF key {clef_key!r} leaked into console JSON"


# ── field values ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "level, name",
    [
        (logging.DEBUG, "DEBUG"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "CRITICAL"),
    ],
)
def test_json_level_matches_logging_level(level: int, name: str) -> None:
    data = _json_output(_make_record(level=level))
    assert data["level"] == name


def test_json_message_contains_log_text() -> None:
    data = _json_output(_make_record(msg="hello structured world"))
    assert data["message"] == "hello structured world"


def test_json_logger_matches_record_name() -> None:
    data = _json_output(_make_record(name="my.app.module"))
    assert data["logger"] == "my.app.module"


def test_json_timestamp_is_iso8601_utc() -> None:
    data = _json_output(_make_record())
    ts: str = data["timestamp"]
    # Must be YYYY-MM-DDTHH:MM:SSZ (UTC, no offset notation)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), (
        f"timestamp {ts!r} does not match ISO-8601 UTC pattern"
    )


# ── extra fields ──────────────────────────────────────────────────────────────


def test_extra_string_field_survives_serialization() -> None:
    data = _json_output(_make_record(request_id="req-abc-123"))
    assert data.get("request_id") == "req-abc-123"


def test_extra_int_field_survives_serialization() -> None:
    data = _json_output(_make_record(status_code=404))
    assert data.get("status_code") == 404


def test_extra_uuid_serialized_as_string_without_error() -> None:
    uid = UUID("12345678-1234-5678-1234-567812345678")
    # python-json-logger uses default=str; this must not raise
    data = _json_output(_make_record(trace_id=uid))
    assert "12345678" in str(data.get("trace_id", ""))


def test_extra_datetime_serialized_without_error() -> None:
    dt = datetime(2026, 5, 13, 9, 45, 57, tzinfo=UTC)
    # Must not raise — default=str handles non-JSON-native types
    _json_output(_make_record(event_time=dt))


# ── text format ───────────────────────────────────────────────────────────────


def test_text_format_is_not_valid_json() -> None:
    handler, _ = build_console_sink(LoggingSettings(console_format="text"))
    assert handler.formatter is not None
    output = handler.formatter.format(_make_record(msg="plain text line"))
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


def test_text_format_contains_log_message() -> None:
    handler, _ = build_console_sink(LoggingSettings(console_format="text"))
    assert handler.formatter is not None
    output = handler.formatter.format(_make_record(msg="the text content"))
    assert "the text content" in output


def test_text_format_returns_no_warnings() -> None:
    _, warnings = build_console_sink(LoggingSettings(console_format="text"))
    assert warnings == []


# ── python-json-logger missing ────────────────────────────────────────────────


def test_missing_json_logger_produces_degradation_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import emm_logging.sinks.console as console_mod

    monkeypatch.setattr(console_mod, "_HAS_PYTHON_JSON_LOGGER", False)
    monkeypatch.setattr(console_mod, "JsonFormatter", None)

    _, warnings = build_console_sink(LoggingSettings(console_format="json"))

    assert len(warnings) == 1
    assert "python-json-logger" in warnings[0].lower()


def test_missing_json_logger_falls_back_to_text_formatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import emm_logging.sinks.console as console_mod

    monkeypatch.setattr(console_mod, "_HAS_PYTHON_JSON_LOGGER", False)
    monkeypatch.setattr(console_mod, "JsonFormatter", None)

    handler, _ = build_console_sink(LoggingSettings(console_format="json"))
    assert handler.formatter is not None
    output = handler.formatter.format(_make_record(msg="fallback"))
    # Fallback is text — must not be valid JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


# ── build_console_sink return shape ──────────────────────────────────────────


def test_build_console_sink_returns_tuple() -> None:
    result = build_console_sink(LoggingSettings())
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_build_console_sink_handler_is_logging_handler() -> None:
    handler, _ = build_console_sink(LoggingSettings())
    assert isinstance(handler, logging.Handler)


def test_build_console_sink_warnings_is_list() -> None:
    _, warnings = build_console_sink(LoggingSettings())
    assert isinstance(warnings, list)


# ── ANSI color on text format ─────────────────────────────────────────────────


_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _format_text(record: logging.LogRecord) -> str:
    handler, _ = build_console_sink(LoggingSettings(console_format="text"))
    assert handler.formatter is not None
    return handler.formatter.format(record)


def test_text_format_has_no_ansi_codes_when_stdout_is_not_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False, raising=False)
    output = _format_text(_make_record(msg="plain"))
    assert _ANSI_PATTERN.search(output) is None


def test_text_format_has_ansi_codes_when_stdout_is_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    output = _format_text(_make_record(msg="colored", level=logging.INFO))
    assert "\x1b[32m" in output  # green for INFO
    assert "\x1b[0m" in output  # reset


def test_no_color_env_disables_ansi_even_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    output = _format_text(_make_record(msg="plain"))
    assert _ANSI_PATTERN.search(output) is None


def test_force_color_env_enables_ansi_when_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: False, raising=False)
    output = _format_text(_make_record(msg="forced", level=logging.INFO))
    assert "\x1b[32m" in output


@pytest.mark.parametrize(
    ("level", "color"),
    [
        (logging.DEBUG, "\x1b[36m"),
        (logging.INFO, "\x1b[32m"),
        (logging.WARNING, "\x1b[33m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[1;31m"),
    ],
)
def test_each_level_uses_distinct_color(
    level: int,
    color: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    output = _format_text(_make_record(level=level))
    assert color in output


def test_color_formatter_restores_levelname_for_downstream_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seq sink reads ``record.levelname`` directly — must see the unmutated value."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    record = _make_record(level=logging.WARNING)
    _format_text(record)
    assert record.levelname == "WARNING"
