"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from copilot_python_app.config import Settings, get_settings
from copilot_python_app.health import HealthResponse, get_health
from copilot_python_app.middleware import AccessLogMiddleware
from emm_logging import LoggingSettings, setup_logging
from emm_settings import load_dotenv_files, log_settings

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")


def _unify_uvicorn_loggers() -> None:
    """Route uvicorn's loggers through the root logger configured by emm_logging.

    Uvicorn applies its default ``LOGGING_CONFIG`` on startup, attaching its
    own stderr handlers to the ``uvicorn*`` loggers and setting
    ``propagate=False``. We strip those handlers and re-enable propagation
    so every uvicorn line flows through our console JSON, Seq, and Azure
    sinks. Idempotent — safe to call after every reload of the app module.
    """

    for name in _UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        logger.propagate = True


def _bootstrap() -> Settings:
    """Run the deterministic startup sequence and return cached app settings.

    Order matters:

    1. Load ``.env`` files **before** logging is configured so subsequent
       :class:`pydantic-settings` reads see the right values (silent on
       success — the logging pipeline isn't up yet).
    2. Configure logging via ``emm_logging`` so every later step is captured.
    3. Re-route uvicorn's loggers through the now-configured root pipeline,
       in case uvicorn (or gunicorn) installed its own handlers before
       importing the app.
    4. Resolve cached :class:`Settings`.
    5. Snapshot the resolved settings through the now-configured pipeline.
    """

    load_dotenv_files(".env")
    setup_logging(LoggingSettings())
    _unify_uvicorn_loggers()
    settings = get_settings()
    log_settings(settings)
    return settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()

    app = FastAPI(
        title=active_settings.name,
        version=active_settings.version,
        docs_url="/docs" if active_settings.environment != "prod" else None,
        redoc_url="/redoc" if active_settings.environment != "prod" else None,
    )

    app.add_middleware(AccessLogMiddleware)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return get_health(active_settings)

    @app.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"service": active_settings.name, "status": "ok"}

    return app


_settings = _bootstrap()
app = create_app(_settings)

