# Project Context

- **Owner:** Emmanuel
- **Project:** copilot-python — Azure-ready Python FastAPI service scaffold optimized for GitHub Copilot CLI, local dev, GitHub Actions, and Copilot cloud agent workflows
- **Stack:** Python 3.12+, FastAPI, pydantic-settings, pytest, ruff, mypy, Docker, Azure Container Apps, azure-monitor-opentelemetry, OpenTelemetry, Seq (log aggregation)
- **Created:** 2026-05-13

## Learnings

- **2026-05-13:** Logging module design phase completed (Ripley architecture proposal + Parker sink research + Hudson test plan all in `.squad/decisions/decisions.md`). Implementation queued — awaiting Emmanuel to resolve 4 architectural questions + pick CLEF-vs-OTLP transport choice. Orchestration logs at `.squad/orchestration-log/`. See `.squad/decisions/decisions.md` (Active section) for full design spec.
- **2026-05-13T09:45:57-05:00:** Implemented reusable `emm_logging` package under `src/emm_logging/` with public API (`LoggingSettings`, `configure_logging`, `LoggingResult`), guarded optional imports for Seq/Azure handlers, and configure-twice handler replacement. Added base dependency `python-json-logger>=3.0.0`, optional extras `seq` (`requests>=2.32.0`) and `azure` (`azure-monitor-opentelemetry>=1.6.0`), and included `src/emm_logging` in wheel packages in `pyproject.toml`. Migrated app glue in `src/copilot_python_app/telemetry.py` and `src/copilot_python_app/main.py`; modified files: `pyproject.toml`, `src/copilot_python_app/main.py`, `src/copilot_python_app/telemetry.py`, `src/emm_logging/__init__.py`, `src/emm_logging/config.py`, `src/emm_logging/setup.py`, `src/emm_logging/_handlers/__init__.py`, `src/emm_logging/_handlers/console.py`, `src/emm_logging/_handlers/seq.py`, `src/emm_logging/_handlers/azure.py`.

<!-- Append new learnings below. Each entry is something lasting about the project. -->

- **2026-05-13:** emm_logging implementation APPROVED by Ripley after 31-item checklist; 135 tests at 98.35% branch coverage; shipped in paired commit.
