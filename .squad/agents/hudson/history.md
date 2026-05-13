# Project Context

- **Owner:** Emmanuel
- **Project:** copilot-python — Azure-ready Python FastAPI service scaffold optimized for GitHub Copilot CLI, local dev, GitHub Actions, and Copilot cloud agent workflows
- **Stack:** Python 3.12+, FastAPI, pydantic-settings, pytest, ruff, mypy, Docker, Azure Container Apps, azure-monitor-opentelemetry, OpenTelemetry, Seq (log aggregation)
- **Created:** 2026-05-13

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-05-13T09:17:33-05:00 — Logging module test plan (proactive)

**Fixture conventions chosen:**
- `capture_json_logs(logger_name)` — in-memory handler fixture; exposes `.records` as `list[dict]`; must be removed from logger on teardown to prevent handler leakage between tests
- `isolated_logging` — always reset `logging.root.handlers` and `logging.Logger.manager.loggerDict` between tests; Python's logging module is global state and will bleed between tests without this
- `sys_modules_snapshot` — required for portability tests; capture `sys.modules` keys before, restore after; never rely on import-order side effects

**Test patterns identified:**
- Telemetry sinks (Seq, Azure Monitor) must be tested without real network I/O; use `pytest-httpserver` for HTTP sinks and `monkeypatch.setattr` for SDK-level exporters
- Write tests for BOTH possible degradation contracts (drop vs. buffer) and let the architect pick — don't bake assumptions into test infrastructure
- Portability/"no-FastAPI" tests require subprocess isolation or `sys.modules` snapshot; a FastAPI-importing test earlier in the session will cause false passes without it
- Configure-twice idempotency must be an explicit test, not an assumption — duplicate handlers are a classic silent failure mode in Python logging

**Coverage philosophy applied:**
- 85% branch coverage recommended for new purpose-built modules (vs. 80% repo floor)
- `# pragma: no cover` reserved strictly for lines that are genuinely unreachable from tests (SDK internals, type stubs) — never used to hide logic
- Branch coverage (`branch = true`, already set) is more meaningful than line coverage for conditional sink wiring

**Open risks flagged to team:**
- Seq degradation contract unresolved (drop vs. buffer)
- Exact JSON field names unresolved (affects hard-coded assertions)
- Configure-twice behavior unresolved
- Backward-compat decision for `configure_logging()` shim unresolved

### 2026-05-13T14:45:57Z — Bishop's implementation landed; test code in progress

Bishop's `emm_logging` implementation (10 files) is complete and validated. Hudson now owns test files 11–14 and will design and execute the 54-test plan against the locked API. Implementation-level decisions are finalized (CLEF over HTTP for Seq, per-event POST, `LOG_*` prefix, human-readable console JSON fields).
