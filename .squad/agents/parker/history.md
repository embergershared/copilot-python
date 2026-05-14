# Project Context

- **Owner:** Emmanuel
- **Project:** copilot-python — Azure-ready Python FastAPI service scaffold optimized for GitHub Copilot CLI, local dev, GitHub Actions, and Copilot cloud agent workflows
- **Stack:** Python 3.12+, FastAPI, pydantic-settings, pytest, ruff, mypy, Docker, Azure Container Apps, azure-monitor-opentelemetry, OpenTelemetry, Seq (log aggregation)
- **Created:** 2026-05-13

## Learnings

- **Seq ingestion strategy:** OTLP over HTTP (not CLEF or Collector sidecar) is the recommended path for log shipping to Seq 2024+. Rationale: unified wire format with Azure Monitor, standard OpenTelemetry SDK batching/retry, no vendor lock-in. Trade-offs documented in brief.

- **Azure Monitor approach:** Use `azure-monitor-opentelemetry` distro (official Microsoft package) with standard `APPLICATIONINSIGHTS_CONNECTION_STRING` env var. Covers logs, traces, metrics; idempotent setup; respects Azure conventions.

- **Graceful degradation:** Rely on OTel SDK's `BatchLogRecordProcessor` (bounded queue ~2048 records, exponential backoff retry, silent drop after ~30s of failures). App stays up; console fallback always available. Configurable via `APP_LOG_*` env vars (batch size, queue max, timeout, failsafe mode).

- **Env var namespace:** Use `APP_LOG_*` prefix for all logging config (e.g., `APP_LOG_LEVEL`, `APP_LOG_SEQ_URL`, `APP_LOG_BATCH_SIZE`). For Azure, use standard `APPLICATIONINSIGHTS_CONNECTION_STRING` (not wrapped in `APP_*`). Secrets (Seq API key, Azure conn string) stay in `.env` or secrets manager only.

- **Dependency strategy:** Introduce optional extras in `pyproject.toml`: `logging` (base OTel), `logging-seq` (Seq exporter), `logging-azure` (Azure Monitor), `logging-full` (both). Keeps simple apps lightweight; users opt into sinks.

- **Local dev tooling:** Seq runs in Docker (`datalust/seq:2024.2`); compose snippet provided in brief. OTLP ingestion is unauthenticated (dev default); persistent volume. No mocking needed—same code path as prod.

- **Secret hygiene:** Seq API key and Azure connection string are secrets; never write to `.squad/` files, code, or logs. Use `.env.example` with placeholders. Implementation: read secrets once at module init, store in private vars, mask in debug output.

- **Open questions for Ripley:** Module portability (standalone package vs src/), structured field API design, sampler / filtering, async flush for FastAPI shutdown, metrics/traces scope, config location (module vs app).

<!-- Append new learnings below. Each entry is something lasting about the project. -->
