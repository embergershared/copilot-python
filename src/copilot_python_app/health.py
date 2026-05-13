"""Health check models and route handlers."""

from typing import Literal

from pydantic import BaseModel

from copilot_python_app.config import Settings, get_settings


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


def get_health(settings: Settings | None = None) -> HealthResponse:
    """Build a health response from runtime settings."""

    active_settings = settings or get_settings()
    return HealthResponse(
        status="ok",
        service=active_settings.name,
        environment=active_settings.environment,
        version=active_settings.version,
    )

