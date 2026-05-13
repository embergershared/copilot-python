# Project Context

- **Owner:** Emmanuel
- **Project:** copilot-python — Azure-ready Python FastAPI service scaffold optimized for GitHub Copilot CLI, local dev, GitHub Actions, and Copilot cloud agent workflows
- **Stack:** Python 3.12+, FastAPI, pydantic-settings, pytest, ruff, mypy, Docker, Azure Container Apps, azure-monitor-opentelemetry, OpenTelemetry, Seq (log aggregation)
- **Created:** 2026-05-13

## Learnings

- **2026-05-13:** Logging module design phase completed (Ripley architecture proposal + Parker sink research + Hudson test plan all in `.squad/decisions/decisions.md`). Implementation queued — awaiting Emmanuel to resolve 4 architectural questions + pick CLEF-vs-OTLP transport choice. Orchestration logs at `.squad/orchestration-log/`. See `.squad/decisions/decisions.md` (Active section) for full design spec.

<!-- Append new learnings below. Each entry is something lasting about the project. -->
