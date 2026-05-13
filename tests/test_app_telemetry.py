"""Integration tests — FastAPI app still starts and responds correctly
after the emm_logging wiring was introduced.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from copilot_python_app.config import Settings
from copilot_python_app.main import create_app
from copilot_python_app.telemetry import setup_app_logging

# ── setup_app_logging ─────────────────────────────────────────────────────────


def test_setup_app_logging_configures_root_logger() -> None:
    setup_app_logging("INFO")
    assert len(logging.getLogger().handlers) >= 1


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
def test_setup_app_logging_accepts_valid_level(level: str) -> None:
    setup_app_logging(level)  # must not raise


# ── app startup ───────────────────────────────────────────────────────────────


def test_create_app_starts_cleanly_with_emm_logging() -> None:
    """App creation must not raise even with the new setup_app_logging wiring."""
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
