"""Tests for SeqHandler — CLEF formatting, HTTP mocking, failure/rate-limiting."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from emm_logging import LoggingSettings
from emm_logging.sinks.seq import SeqHandler, build_seq_sink


def _make_record(
    msg: str = "test message",
    level: int = logging.INFO,
    name: str = "test.seq",
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


# ── build_seq_sink ────────────────────────────────────────────────────────────


def test_build_seq_sink_returns_none_when_no_url() -> None:
    handler, warnings = build_seq_sink(LoggingSettings())
    assert handler is None
    assert warnings == []


def test_build_seq_sink_returns_handler_when_url_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    handler, warnings = build_seq_sink(LoggingSettings())
    assert isinstance(handler, SeqHandler)
    assert warnings == []


def test_build_seq_sink_warns_when_requests_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import emm_logging.sinks.seq as seq_mod

    monkeypatch.setenv("LOG_SEQ_URL", "http://seq:5341")
    monkeypatch.setattr(seq_mod, "_HAS_REQUESTS", False)

    handler, warnings = build_seq_sink(LoggingSettings())

    assert handler is None
    assert any("requests" in w.lower() for w in warnings)


# ── endpoint construction ─────────────────────────────────────────────────────


def test_seq_endpoint_appends_api_events_raw_path() -> None:
    handler = SeqHandler("http://seq:5341", None)
    assert handler._endpoint == "http://seq:5341/api/events/raw"


def test_seq_endpoint_strips_trailing_slash_before_appending() -> None:
    handler = SeqHandler("http://seq:5341/", None)
    assert handler._endpoint == "http://seq:5341/api/events/raw"


def test_seq_endpoint_preserves_path_prefix() -> None:
    handler = SeqHandler("http://proxy/seq", None)
    assert handler._endpoint == "http://proxy/seq/api/events/raw"


# ── CLEF field names (_build_event) ──────────────────────────────────────────


def test_clef_event_has_at_t() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    assert "@t" in event


def test_clef_event_has_at_l() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    assert "@l" in event


def test_clef_event_has_at_m() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    assert "@m" in event


def test_clef_event_has_at_mt() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    assert "@mt" in event


def test_clef_at_l_matches_level_name() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(
        _make_record(level=logging.WARNING)
    )
    assert event["@l"] == "WARNING"


def test_clef_at_m_is_formatted_message() -> None:
    record = _make_record(msg="hello %s")
    record.args = ("world",)
    event = SeqHandler("http://seq:5341", None)._build_event(record)
    assert event["@m"] == "hello world"


def test_clef_at_mt_is_raw_message_template() -> None:
    record = _make_record(msg="hello {name}")
    event = SeqHandler("http://seq:5341", None)._build_event(record)
    assert event["@mt"] == "hello {name}"


def test_clef_event_has_at_x_when_exc_info_present() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = _make_record()
    record.exc_info = exc_info
    event = SeqHandler("http://seq:5341", None)._build_event(record)

    assert "@x" in event
    assert "ValueError" in event["@x"]
    assert "boom" in event["@x"]


def test_clef_event_no_at_x_when_no_exception() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    assert "@x" not in event


def test_clef_extra_fields_propagated_to_event() -> None:
    event = SeqHandler("http://seq:5341", None)._build_event(
        _make_record(request_id="req-999")
    )
    assert event.get("request_id") == "req-999"


def test_clef_standard_log_record_fields_excluded() -> None:
    """Fields like levelname, lineno, filename must not appear in CLEF payload."""
    event = SeqHandler("http://seq:5341", None)._build_event(_make_record())
    for std in ("levelname", "levelno", "filename", "funcName", "lineno", "module"):
        assert std not in event, f"Standard field {std!r} leaked into CLEF event"


# ── HTTP POST mechanics ───────────────────────────────────────────────────────


def test_emit_posts_to_correct_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        calls.append({"url": url, **kwargs})
        return MagicMock(raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "post", fake_post)

    SeqHandler("http://seq:5341", None).emit(_make_record())

    assert len(calls) == 1
    assert calls[0]["url"] == "http://seq:5341/api/events/raw"


def test_emit_includes_api_key_header_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_headers: list[dict[str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured_headers.append(kwargs.get("headers", {}))
        return MagicMock(raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "post", fake_post)

    SeqHandler("http://seq:5341", "my-api-key").emit(_make_record())

    assert captured_headers[0].get("X-Seq-ApiKey") == "my-api-key"


def test_emit_omits_api_key_header_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_headers: list[dict[str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured_headers.append(kwargs.get("headers", {}))
        return MagicMock(raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "post", fake_post)

    SeqHandler("http://seq:5341", None).emit(_make_record())

    assert "X-Seq-ApiKey" not in captured_headers[0]


def test_emit_payload_is_valid_clef_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[str] = []

    def fake_post(url: str, data: str = "", **kwargs: Any) -> MagicMock:
        payloads.append(data)
        return MagicMock(raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "post", fake_post)

    SeqHandler("http://seq:5341", None).emit(_make_record(msg="clef payload check"))

    assert len(payloads) == 1
    event = json.loads(payloads[0].strip())
    assert "@t" in event
    assert event["@m"] == "clef payload check"


def test_emit_uses_clef_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_headers: list[dict[str, str]] = []

    def fake_post(url: str, **kwargs: Any) -> MagicMock:
        captured_headers.append(kwargs.get("headers", {}))
        return MagicMock(raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "post", fake_post)
    SeqHandler("http://seq:5341", None).emit(_make_record())

    assert captured_headers[0].get("Content-Type") == "application/vnd.serilog.clef"


# ── failure handling ──────────────────────────────────────────────────────────


def test_emit_does_not_raise_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        MagicMock(side_effect=requests.ConnectionError("refused")),
    )
    SeqHandler("http://seq:5341", None).emit(_make_record())  # must NOT raise


def test_emit_does_not_raise_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
    monkeypatch.setattr(requests, "post", MagicMock(return_value=mock_resp))
    SeqHandler("http://seq:5341", None).emit(_make_record())  # must NOT raise


def test_emit_writes_warning_to_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        MagicMock(side_effect=requests.ConnectionError("server down")),
    )
    handler = SeqHandler("http://seq:5341", None)
    handler._last_warning_at = -1_000_000.0  # ensure warning fires

    handler.emit(_make_record())

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "Seq" in captured.err


# ── rate-limiting ─────────────────────────────────────────────────────────────


def test_two_failures_within_60s_produce_only_one_warning(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tick = 0.0

    def monotonic_mock() -> float:
        return tick

    monkeypatch.setattr(
        requests,
        "post",
        MagicMock(side_effect=requests.ConnectionError("down")),
    )
    monkeypatch.setattr(time, "monotonic", monotonic_mock)

    handler = SeqHandler("http://seq:5341", None)
    handler._last_warning_at = -1_000_000.0

    # t=0 — first failure → warning fires
    handler.emit(_make_record())
    first_stderr = capsys.readouterr().err

    # t=30 — still inside 60-second window → no warning
    tick = 30.0
    handler.emit(_make_record())
    second_stderr = capsys.readouterr().err

    assert "WARNING" in first_stderr
    assert second_stderr == ""


def test_warning_fires_again_after_60s_window(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tick = 0.0

    def monotonic_mock() -> float:
        return tick

    monkeypatch.setattr(
        requests,
        "post",
        MagicMock(side_effect=requests.ConnectionError("down")),
    )
    monkeypatch.setattr(time, "monotonic", monotonic_mock)

    handler = SeqHandler("http://seq:5341", None)
    handler._last_warning_at = -1_000_000.0

    # t=0 — first warning
    handler.emit(_make_record())
    capsys.readouterr()  # consume

    # t=61 — window expired → warning fires again
    tick = 61.0
    handler.emit(_make_record())
    later_stderr = capsys.readouterr().err

    assert "WARNING" in later_stderr


def test_emit_warns_and_returns_when_requests_disabled_post_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SeqHandler.emit() falls back gracefully if _HAS_REQUESTS is False at emit time.

    This is an uncommon but valid scenario: the handler was constructed while
    requests was installed, then the module flag was patched (e.g. in tests).
    The handler must not raise and must rate-limit its warning.
    """
    import emm_logging.sinks.seq as seq_mod

    handler = SeqHandler("http://seq:5341", None)
    handler._last_warning_at = -1_000_000.0

    monkeypatch.setattr(seq_mod, "_HAS_REQUESTS", False)
    monkeypatch.setattr(seq_mod, "_requests", None)

    handler.emit(_make_record())  # must not raise

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "requests" in err.lower() or "Seq" in err


@pytest.mark.parametrize("elapsed", [0.0, 15.0, 59.9])
def test_warning_suppressed_while_within_window(
    elapsed: float,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Any elapsed time < 60s must suppress the repeat warning."""
    base = 1000.0
    monkeypatch.setattr(
        requests,
        "post",
        MagicMock(side_effect=requests.ConnectionError("x")),
    )
    monkeypatch.setattr(time, "monotonic", lambda: base + elapsed)

    handler = SeqHandler("http://seq:5341", None)
    handler._last_warning_at = base  # simulate a recent warning

    handler.emit(_make_record())

    assert capsys.readouterr().err == ""
