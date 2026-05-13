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
- **2026-05-13:** **Reviewer gate APPROVED** `emm_logging` implementation (Bishop) + test suite (Hudson). 31-point checklist passed clean. Key verification patterns that worked well: (1) grep for forbidden imports (`fastapi|starlette|uvicorn`) in the package as a hard gate, (2) subprocess portability tests in Hudson's suite are genuinely isolated — they insert `src/` into a fresh Python process's path and check `sys.modules`, not just `import emm_logging; assert True`, (3) rate-limit throttle tests monkeypatch `time.monotonic` instead of sleeping — deterministic and fast, (4) `dataclass_fields()` call in test to verify `LoggingResult` is a dataclass not Pydantic — reusable pattern for API boundary contracts. Coverage: 98.35% branch on `emm_logging`, 135 tests, 18s runtime. Only uncovered branch: `setup.py:29-32` (defensive fallback console handler invoked only when `build_console_handler` itself raises — legitimate `pragma: no cover`). Non-blocking suggestion: add a usage-example README for `emm_logging`. Future: add `emm_logging` to default pytest coverage config so both packages are tracked in CI.
