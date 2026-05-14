"""ASGI middleware for the FastAPI application.

The :class:`AccessLogMiddleware` replaces uvicorn's built-in access logger
with a structured record routed through the standard :mod:`logging` pipeline.
This keeps every line — application, framework, and HTTP access — flowing
through the sinks configured by :func:`emm_logging.setup_logging` (console
JSON, Seq, Azure Monitor).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class AccessLogMiddleware:
    """Emit one structured log record per HTTP request.

    The record carries ``method``, ``path``, ``status_code``,
    ``duration_ms``, and ``client`` in ``extra`` so JSON/Seq sinks index them
    as fields rather than plain text.
    """

    def __init__(self, app: ASGIApp, *, logger_name: str = "copilot_python_app.access") -> None:
        self._app = app
        self._logger = logging.getLogger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
            client = scope.get("client")
            client_addr = f"{client[0]}:{client[1]}" if client else "-"
            method = scope.get("method", "-")
            path = scope.get("path", "-")
            self._logger.info(
                "%s %s %d %.3fms",
                method,
                path,
                status_code,
                duration_ms,
                extra={
                    "http_method": method,
                    "http_path": path,
                    "http_status_code": status_code,
                    "http_duration_ms": duration_ms,
                    "http_client": client_addr,
                },
            )
