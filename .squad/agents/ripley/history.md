# Project Context

- **Owner:** Emmanuel
- **Project:** copilot-python — Azure-ready Python FastAPI service scaffold optimized for GitHub Copilot CLI, local dev, GitHub Actions, and Copilot cloud agent workflows
- **Stack:** Python 3.12+, FastAPI, pydantic-settings, pytest, ruff, mypy, Docker, Azure Container Apps, azure-monitor-opentelemetry, OpenTelemetry, Seq (log aggregation)
- **Created:** 2026-05-13

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

- **2026-05-13:** Designed architecture for `ember_logging` — a reusable structured logging module at `src/ember_logging/`. Key decisions: separate top-level package in same repo (not a sub-package of `copilot_python_app`), handler-list composition driven by `LoggingSettings` (pydantic-settings, `LOG_*` prefix), CLEF-over-HTTP for Seq, optional extras `[seq]`/`[azure]` to keep base deps minimal. Console always on; remote sinks best-effort. Proposal at `.squad/decisions/inbox/ripley-logging-module-design.md`. Handoff spec written for Bishop (14 files, ordered).
- **2026-05-13:** Current `telemetry.py` is a 34-line `dictConfig` wrapper — console only, no structured format, no remote sinks. Migration plan: thin to a one-liner delegation to `ember_logging`, rename function to `setup_app_logging` to avoid import confusion.
- **2026-05-13:** `pyproject.toml` uses hatchling with `packages = ["src/copilot_python_app"]`. Adding `ember_logging` requires updating the `packages` list. Existing optional extras pattern: `[azure]`, `[dev]`.
- **2026-05-13:** Bishop completed implementation of `emm_logging` per design (10 files, gpt-5.3-codex). All validation passed (ruff/mypy/pytest). Package renamed to `emm_logging` per Emmanuel's round-1 resolution. Hudson test suite queued. Reviewer gate (Ripley) scheduled after Hudson.
