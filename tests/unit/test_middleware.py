"""Tests for the structured access log middleware."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from copilot_python_app.config import Settings
from copilot_python_app.main import create_app


@pytest.fixture
def app_client() -> TestClient:
    app = create_app(Settings(name="example", environment="test", version="1.2.3"))
    return TestClient(app)


def test_access_log_emitted_with_structured_extras(
    app_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    access_logger = logging.getLogger("copilot_python_app.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = True

    with caplog.at_level(logging.INFO, logger="copilot_python_app.access"):
        response = app_client.get("/")

    assert response.status_code == 200

    access_records = [r for r in caplog.records if r.name == "copilot_python_app.access"]
    assert len(access_records) == 1
    record = access_records[0]
    assert record.http_method == "GET"
    assert record.http_path == "/"
    assert record.http_status_code == 200
    assert isinstance(record.http_duration_ms, float)
    assert record.http_duration_ms >= 0
    assert isinstance(record.http_client, str)


def test_access_log_records_error_status(
    app_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    access_logger = logging.getLogger("copilot_python_app.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = True

    with caplog.at_level(logging.INFO, logger="copilot_python_app.access"):
        response = app_client.get("/does-not-exist")

    assert response.status_code == 404
    access_records = [r for r in caplog.records if r.name == "copilot_python_app.access"]
    assert len(access_records) == 1
    assert access_records[0].http_status_code == 404
    assert access_records[0].http_path == "/does-not-exist"
