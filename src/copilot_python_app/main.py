"""FastAPI application entry point."""

from fastapi import FastAPI

from copilot_python_app.config import Settings, get_settings
from copilot_python_app.health import HealthResponse, get_health
from copilot_python_app.telemetry import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    app = FastAPI(
        title=active_settings.name,
        version=active_settings.version,
        docs_url="/docs" if active_settings.environment != "prod" else None,
        redoc_url="/redoc" if active_settings.environment != "prod" else None,
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return get_health(active_settings)

    @app.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"service": active_settings.name, "status": "ok"}

    return app


app = create_app()

