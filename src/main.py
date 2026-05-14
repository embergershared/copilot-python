"""Reference launcher for all application components in this repo.

Why this exists
---------------
A single, predictable entry point for every runnable component (today: the
FastAPI service; tomorrow: workers, scheduled jobs, migrations, ad-hoc
scripts). New components add a subcommand here rather than scattering
new top-level scripts, so the launcher contract stays uniform:

    1. Source ``.env`` files via :func:`emm_settings.load_dotenv_files`.
    2. Activate logging via :func:`emm_logging.setup_logging`.
    3. Dispatch the requested subcommand with logging already live.

Usage
-----
.. code-block:: powershell

    python src\\main.py serve [--host HOST] [--port PORT] [--reload] [--workers N]

Notes
-----
* This module sits at ``src/main.py`` — outside any package — so it is
  *not* shipped in the wheel. It is a developer/operator launcher that
  expects either ``pip install -e .`` (recommended) or ``src`` on
  ``PYTHONPATH``.
* Subcommands that import :mod:`copilot_python_app.main` will re-run the
  app's own ``_bootstrap()`` — that is intentional and idempotent
  (``load_dotenv`` defaults to ``override=False`` and logging
  re-configures cleanly).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from emm_logging import LoggingSettings, get_logger, setup_logging
from emm_settings import load_dotenv_files

_logger = get_logger("launcher")


def _cmd_serve(args: argparse.Namespace) -> int:
    """Run the FastAPI service via uvicorn.

    ``log_config=None`` keeps uvicorn from replacing the root logging
    configuration installed by :func:`emm_logging.setup_logging`, so
    uvicorn's own loggers (``uvicorn``, ``uvicorn.error``) propagate to
    our sinks. ``access_log=False`` disables uvicorn's plain-text access
    log; the structured equivalent is emitted by
    :class:`copilot_python_app.middleware.AccessLogMiddleware`.
    """

    import uvicorn

    workers = args.workers
    if args.reload and workers > 1:
        _logger.warning(
            "uvicorn reload mode forces single-worker; ignoring workers=%d",
            workers,
        )
        workers = 1

    _logger.info(
        "launcher.serve starting host=%s port=%d reload=%s workers=%d",
        args.host,
        args.port,
        args.reload,
        workers,
    )
    uvicorn.run(
        "copilot_python_app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=workers,
        log_config=None,
        access_log=False,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""

    parser = argparse.ArgumentParser(
        prog="copilot-python",
        description="Launch entry point for all application components.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    serve = subparsers.add_parser(
        "serve",
        help="Run the FastAPI service via uvicorn.",
        description="Run the FastAPI service via uvicorn.",
    )
    serve.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0).",
    )
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only; forces single worker).",
    )
    serve.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Worker processes (ignored when --reload is set).",
    )
    serve.set_defaults(func=_cmd_serve)

    return parser


def _bootstrap_launcher() -> None:
    """Source ``.env`` then activate logging so launcher steps are observable."""

    load_dotenv_files(".env")
    setup_logging(LoggingSettings())


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    _bootstrap_launcher()

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        _logger.info("launcher interrupted by user")
        return 130
    except Exception:
        _logger.exception("launcher failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
