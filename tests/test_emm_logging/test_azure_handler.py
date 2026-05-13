"""Tests for Azure Monitor sink integration in emm_logging."""

from __future__ import annotations

from typing import Any

import pytest

import emm_logging._handlers.azure as _azure_mod
from emm_logging import LoggingSettings
from emm_logging._handlers.azure import configure_azure_sink

# ── no connection string ──────────────────────────────────────────────────────


def test_returns_false_when_no_connection_string() -> None:
    enabled, warnings = configure_azure_sink(LoggingSettings(), logger_name="test")
    assert enabled is False
    assert warnings == []


# ── package missing ───────────────────────────────────────────────────────────


def test_returns_false_when_azure_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", False)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", None)

    enabled, _warnings = configure_azure_sink(LoggingSettings(), logger_name="svc")

    assert enabled is False


def test_warning_describes_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", False)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", None)

    _, warnings = configure_azure_sink(LoggingSettings(), logger_name="svc")

    assert len(warnings) == 1
    w = warnings[0].lower()
    assert "azure" in w
    assert "not installed" in w or "disabled" in w


def test_warning_is_not_an_exception_when_package_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Graceful degradation: missing package returns a warning, never raises."""
    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", False)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", None)

    # Must not raise — this is the core graceful-degradation contract
    result = configure_azure_sink(LoggingSettings(), logger_name="svc")
    assert isinstance(result, tuple)


# ── package present (mocked) ──────────────────────────────────────────────────


def test_returns_true_when_mock_package_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=test")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)

    enabled, warnings = configure_azure_sink(LoggingSettings(), logger_name="svc")

    assert enabled is True
    assert warnings == []


def test_configure_azure_monitor_called_with_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = "InstrumentationKey=key123;IngestionEndpoint=https://ex.com"
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", conn)
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)

    configure_azure_sink(LoggingSettings(), logger_name="svc")

    assert calls[0]["connection_string"] == conn


def test_configure_azure_monitor_called_with_logger_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", "InstrumentationKey=abc")
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)

    configure_azure_sink(LoggingSettings(), logger_name="my-service")

    assert calls[0]["logger_name"] == "my-service"


# ── real package (conditional) ────────────────────────────────────────────────


def test_real_azure_package_if_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """If azure-monitor-opentelemetry is installed, verify the real call path works."""
    azure = pytest.importorskip(
        "azure.monitor.opentelemetry",
        reason="azure-monitor-opentelemetry not installed — skipping real-package test",
    )
    conn = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
    calls: list[dict[str, Any]] = []

    def fake_configure(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setenv("LOG_AZURE_CONNECTION_STRING", conn)
    # Patch at the SDK level so we don't actually hit Azure
    monkeypatch.setattr(azure, "configure_azure_monitor", fake_configure)
    monkeypatch.setattr(_azure_mod, "configure_azure_monitor", fake_configure)
    monkeypatch.setattr(_azure_mod, "_HAS_AZURE_MONITOR", True)

    enabled, _warnings = configure_azure_sink(LoggingSettings(), logger_name="svc")

    assert enabled is True
    assert len(calls) == 1
