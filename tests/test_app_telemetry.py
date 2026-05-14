"""Integration tests — FastAPI app boots through the new bootstrap pipeline."""

from __future__ import annotations

import importlib
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

import copilot_python_app.main as main_mod
from copilot_python_app.config import Settings
from copilot_python_app.main import create_app

# ── bootstrap wiring ──────────────────────────────────────────────────────────


def test_bootstrap_invokes_dotenv_setup_logging_and_log_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_bootstrap must call dotenv → setup_logging → log_settings in order."""

    calls: list[str] = []

    def fake_load_dotenv(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append("load_dotenv_files")
        return []

    def fake_setup_logging(*args: Any, **kwargs: Any) -> Any:
        calls.append("setup_logging")
        return None

    def fake_log_settings(*args: Any, **kwargs: Any) -> None:
        calls.append("log_settings")

    monkeypatch.setattr(main_mod, "load_dotenv_files", fake_load_dotenv)
    monkeypatch.setattr(main_mod, "setup_logging", fake_setup_logging)
    monkeypatch.setattr(main_mod, "log_settings", fake_log_settings)

    main_mod._bootstrap()

    assert calls == ["load_dotenv_files", "setup_logging", "log_settings"]


def test_bootstrap_returns_settings_instance() -> None:
    settings = main_mod._bootstrap()
    assert isinstance(settings, Settings)


def test_app_module_import_runs_bootstrap_side_effect() -> None:
    """Importing copilot_python_app.main must yield a configured FastAPI app."""

    reloaded = importlib.reload(main_mod)
    assert reloaded.app is not None
    assert hasattr(reloaded, "_settings")
    assert isinstance(reloaded._settings, Settings)


# ── app startup ───────────────────────────────────────────────────────────────


def test_create_app_starts_cleanly_with_emm_logging() -> None:
    """App creation must not raise even with the bootstrap pipeline already run."""
    app = create_app(Settings(name="test-svc", environment="test", version="0.0.1"))
    assert app is not None


# ── HTTP health probe ─────────────────────────────────────────────────────────


def test_health_endpoint_returns_200() -> None:
    app = create_app(Settings(name="test-svc", environment="test", version="0.0.1"))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_body_is_correct() -> None:
    app = create_app(Settings(name="my-svc", environment="dev", version="1.2.3"))
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "my-svc"
    assert data["environment"] == "dev"
    assert data["version"] == "1.2.3"


def test_root_endpoint_returns_200() -> None:
    app = create_app(Settings(name="svc", environment="test", version="0.1.0"))
    client = TestClient(app)
    assert client.get("/").status_code == 200


def test_root_endpoint_body_is_correct() -> None:
    app = create_app(Settings(name="svc", environment="test", version="0.1.0"))
    client = TestClient(app)
    assert client.get("/").json() == {"service": "svc", "status": "ok"}


# ── logging is functional after app creation ──────────────────────────────────


def test_logging_works_after_create_app() -> None:
    create_app(Settings(name="x", environment="test", version="0.0.0"))
    # Logging should be configured and functional; this must not raise.
    logging.getLogger("integration.test").info("post-create_app log message")
