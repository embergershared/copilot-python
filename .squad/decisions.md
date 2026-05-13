# Decisions

Decisions made for the logging module design phase (Round 1). All entries are "Active" — pending implementation or user approval.

---

## Active Decisions

### 2026-05-13T09:17:33-05:00: Reusable logging module — architecture
**By:** Ripley (architecture proposal)
**Status:** Proposed — pending user approval
**Why:** Emmanuel needs structured JSON logging with Seq and optional Azure Monitor across multiple Python projects. The current `telemetry.py` is a 30-line `dictConfig` wrapper hardwired to console output — it can't ship logs anywhere, has no structured format, and lives inside the FastAPI app package. A standalone, portable module solves all three problems and avoids copy-pasting logging boilerplate into every new project.

---

**Decisions:**

#### 1. Module location & packaging: new top-level package in this repo

**Choice: (a) — new top-level package `src/ember_logging/` as a separate distribution in this monorepo.**

Trade-offs considered:

| Option | Pros | Cons |
|---|---|---|
| **(a) `src/ember_logging/` in this repo** | Single repo to iterate in, testable alongside the app that uses it, publishable to PyPI later, hatch already supports multi-package | Slightly more `pyproject.toml` complexity (two packages) |
| **(b) Separate repo** | Clean boundary | Too early — no stable API yet. Cross-repo iteration is slow. Move later when the API stabilizes. |
| **(c) Sub-package of `copilot_python_app`** | Zero config | **Rejected.** Violates the portability requirement. Other apps would depend on a FastAPI scaffold package to get logging. |

Concrete plan:
- New directory: `src/ember_logging/` with its own `__init__.py`.
- Update `pyproject.toml`: add `ember-logging` as a second hatch build target, OR (simpler for v1) keep one distribution and add `ember_logging` to the wheel's `packages` list. Both packages ship in the same wheel for now. When it's stable enough for PyPI, extract.
- Optional extras on the **new package's dependencies**:
  - Base: `python-json-logger>=3.0.0` (CLEF formatter, zero-config JSON)
  - `[seq]`: `requests>=2.32.0` (CLEF HTTP handler — see §3)
  - `[azure]`: `azure-monitor-opentelemetry>=1.6.0`
  - `[otel]`: `opentelemetry-sdk>=1.25.0`, `opentelemetry-exporter-otlp>=1.25.0`

**Why extras:** Emmanuel's other apps shouldn't pull `azure-monitor-opentelemetry` (200+ transitive deps) just to get JSON console logs. Extras make each sink opt-in. The base install is `python-json-logger` only.

#### 2. Public API surface

Smallest viable surface — one settings model, one configure function, one typed return.

```python
# ember_logging/__init__.py
from ember_logging.config import LoggingSettings
from ember_logging.setup import configure_logging

__all__ = ["LoggingSettings", "configure_logging"]
```

```python
# ember_logging/config.py
from typing import Literal
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class LoggingSettings(BaseSettings):
    """Env-driven logging configuration. All fields have safe defaults."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "text"] = "json"
    service_name: str = "unknown-service"

    # Seq sink (optional)
    seq_url: HttpUrl | None = Field(default=None, description="Seq server URL, e.g. http://seq:5341")
    seq_api_key: str | None = Field(default=None, description="Seq API key (optional)")

    # Azure Monitor sink (optional)
    azure_connection_string: str | None = Field(
        default=None,
        description="Azure Monitor connection string. If set, azure-monitor-opentelemetry must be installed.",
    )
```

```python
# ember_logging/setup.py
import logging
from ember_logging.config import LoggingSettings

class LoggingResult:
    """Returned by configure_logging so callers know what was wired."""
    console: bool
    seq: bool
    azure_monitor: bool
    warnings: list[str]  # degradation notices

def configure_logging(
    settings: LoggingSettings | None = None,
    *,
    extra_handlers: list[logging.Handler] | None = None,
) -> LoggingResult:
    """
    Configure the root logger with structured JSON output and optional
    remote sinks based on settings / environment variables.

    Safe to call once at startup. Idempotent — second call replaces handlers.
    """
    ...
```

**What's NOT exposed:** individual handler classes, sink internals, OTel provider details. Consumers call `configure_logging()` and get structured logs. If they need a custom handler, `extra_handlers` is the escape hatch.

**Env var contract:** all vars prefixed `LOG_`. Examples:
- `LOG_LEVEL=INFO`
- `LOG_FORMAT=json`
- `LOG_SERVICE_NAME=my-api`
- `LOG_SEQ_URL=http://seq:5341`
- `LOG_SEQ_API_KEY=<optional>`
- `LOG_AZURE_CONNECTION_STRING=InstrumentationKey=...`

#### 3. Sink composition: handler list driven by settings (option a)

**Choice: (a) — all-or-nothing handler list driven by `LoggingSettings`.**

Rationale:
- **(b) Pluggable sink registry** is premature. We have exactly three sinks (console, Seq, Azure Monitor). A registry adds API surface for a problem that doesn't exist yet. YAGNI.
- **(c) OTel LogProvider** couples the base module to the OTel SDK even when the consumer only wants console + Seq. OTel is heavy. It should be opt-in via the `[otel]` extra, not load-bearing for the core path.

Implementation sketch:

```
configure_logging(settings):
    handlers = []
    handlers.append(make_console_handler(settings))       # always
    if settings.seq_url:
        handlers.append(make_seq_handler(settings))       # CLEF over HTTP
    if settings.azure_connection_string:
        handlers.append(make_azure_handler(settings))     # azure-monitor-opentelemetry
    if extra_handlers:
        handlers.extend(extra_handlers)
    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(settings.level)
```

**Seq transport:** CLEF (Compact Log Event Format) over HTTP POST to `{seq_url}/api/events/raw`. This is Seq's native structured format and avoids pulling in the full OTel exporter chain. The `[seq]` extra adds `requests` for the HTTP transport. The handler is a custom `logging.Handler` subclass that batches and POSTs — ~80 lines, no external Seq SDK needed.

**Azure Monitor transport:** `azure-monitor-opentelemetry` provides `configure_azure_monitor()` which auto-instruments the logging module. We call it when the connection string is present and the package is installed.

#### 4. Degradation contract

Explicit behaviors when sinks are unreachable:

| Scenario | Behavior |
|---|---|
| **Seq URL set but unreachable at startup** | Log a WARNING to console: `"seq_sink_unreachable url={url}"`. Console handler remains active. Seq handler is still attached — it retries on each log emit. |
| **Seq POST fails at runtime** | Handler catches the exception, logs a WARNING to console (rate-limited: once per 60s), drops the batch. No retry queue, no unbounded buffer. Logs are not worth OOM. |
| **Azure Monitor connection string set but package not installed** | `configure_logging` logs a WARNING: `"azure-monitor-opentelemetry not installed — azure sink disabled"`. Returns `LoggingResult(azure_monitor=False, warnings=[...])`. |
| **Azure Monitor configured but unreachable** | Delegated to `azure-monitor-opentelemetry`'s built-in retry/backoff. We don't wrap it. |
| **No sinks configured (no Seq, no Azure)** | Console-only. This is the default, safe, zero-dep path. |
| **`configure_logging` itself raises** | Must not happen. Internal errors are caught, logged to stderr, console handler is always attached. The app starts. |

**Key principle:** console is always on. Remote sinks are best-effort. The application never fails to start because of a logging configuration problem.

#### 5. Migration of existing `telemetry.py`

**Thin it to a one-liner glue module.** Don't delete it — it's the FastAPI-specific integration point.

After migration:

```python
# src/copilot_python_app/telemetry.py
"""FastAPI-specific logging setup — delegates to ember_logging."""

from ember_logging import LoggingSettings, configure_logging


def setup_app_logging(log_level: str) -> None:
    """Configure logging for the FastAPI app using the shared module."""
    settings = LoggingSettings(level=log_level)  # type: ignore[arg-type]
    configure_logging(settings)
```

Changes in `main.py`:
```python
# Before
from copilot_python_app.telemetry import configure_logging
configure_logging(active_settings.log_level)

# After
from copilot_python_app.telemetry import setup_app_logging
setup_app_logging(active_settings.log_level)
```

The existing `configure_logging` function name is deliberately NOT reused in the wrapper to avoid import confusion. The app's `Settings.log_level` feeds into `LoggingSettings.level`. Seq/Azure settings flow from the environment automatically (the `LOG_*` prefix).

Long-term, once other apps also use `ember_logging`, the glue in `telemetry.py` could move into `main.py` directly. But for now, keeping the file preserves the existing module boundary and avoids churn.

#### 6. Out of scope (v1) — explicit YAGNI list

1. **Log correlation / distributed tracing.** No trace-id propagation, no OTel trace context injection into logs. Useful, but a separate concern. Add when tracing is wired.
2. **File-based log sinks.** No `RotatingFileHandler`, no log-to-disk. This is a containerized service — stdout is the file. Seq is the archive.
3. **Dynamic log level changes at runtime.** No admin endpoint, no signal handler. Restart the process. Containers make this cheap.
4. **Custom structured fields / context managers.** No `with log_context(request_id=...)` magic. Use `logging.LoggerAdapter` or `extra={}` if needed — that's stdlib, not our problem.
5. **Metrics or tracing export.** This module does *logging*. Metrics and tracing are separate OTel signals with different lifecycles. Don't conflate them.
6. **Buffered async log shipping.** No background thread with a queue for Seq. Synchronous POST per batch, fail-fast. Async adds complexity, backpressure decisions, and shutdown ordering problems. Not worth it for v1.

---

**Handoff to Bishop:**

Files to create (in order):

1. **`src/ember_logging/__init__.py`** — public API re-exports (`LoggingSettings`, `configure_logging`, `LoggingResult`)
2. **`src/ember_logging/config.py`** — `LoggingSettings` pydantic-settings model (exact contract above)
3. **`src/ember_logging/setup.py`** — `configure_logging()` implementation, `LoggingResult` dataclass
4. **`src/ember_logging/_handlers/__init__.py`** — internal handler sub-package
5. **`src/ember_logging/_handlers/console.py`** — JSON console handler using `python-json-logger`
6. **`src/ember_logging/_handlers/seq.py`** — CLEF-over-HTTP handler (guarded by `requests` import)
7. **`src/ember_logging/_handlers/azure.py`** — Azure Monitor integration (guarded by `azure-monitor-opentelemetry` import)

Files to modify:

8. **`pyproject.toml`** — add `python-json-logger` to deps, add optional extras `[seq]`, `[azure]`, add `ember_logging` to hatch wheel packages
9. **`src/copilot_python_app/telemetry.py`** — replace body with one-liner delegation to `ember_logging`
10. **`src/copilot_python_app/main.py`** — update import to use new function name

Tests to create:

11. **`tests/test_ember_logging/test_configure_logging.py`** — unit tests: default config produces JSON console, Seq handler attached when URL set, Azure handler attached when connection string set, graceful degradation when packages missing
12. **`tests/test_ember_logging/test_settings.py`** — env var parsing for all `LOG_*` fields
13. **`tests/test_ember_logging/test_seq_handler.py`** — CLEF formatting, HTTP POST mock, failure handling
14. **`tests/test_app_telemetry.py`** — existing app still starts correctly with new wiring (integration)

Bishop should implement files 1–7, then 8–10, then 11–14. Run `ruff check .`, `mypy`, `pytest` after each group.

**Implementation constraints for Bishop:**
- Zero FastAPI imports anywhere in `src/ember_logging/`. This is enforced.
- All handler modules must guard optional imports with `try/except ImportError` and set a module-level flag (e.g., `_HAS_REQUESTS = True/False`).
- `LoggingResult` is a `dataclass`, not a Pydantic model — keep the base dependency to `pydantic-settings` + `python-json-logger` only.
- The `_handlers` package is private (underscore prefix). Nothing outside `ember_logging` imports from it.
- Every function has a return type annotation. No exceptions.

---

**Open questions for Emmanuel:**

1. **Package name:** I used `ember_logging` as a working name. Is this the name you want for the reusable module, or do you have a preferred name? This affects the import path and the `LOG_` env prefix.
2. **Seq batching:** The v1 design POSTs to Seq per-log-event (simplest). Do you have volume expectations that would require micro-batching (e.g., buffer 50 events or 1 second, whichever comes first)? I'd rather add it when there's evidence it's needed.
3. **`LOG_` vs `APP_` prefix:** The new module uses `LOG_` to stay independent of any app's `APP_` prefix. This means two prefixes in the same process. Are you OK with that, or do you want the logging settings folded into the app's `APP_` namespace? (I recommend keeping them separate — portability wins.)
4. **PyPI publishing timeline:** The design supports extracting `ember_logging` to its own repo/package later. Do you want Bishop to set up a separate `[project]` entry in `pyproject.toml` now (hatch workspace), or is shipping both packages in one wheel acceptable for v1?


---

### 2026-05-13T09:17:33-05:00: Sink wiring options — Seq + Azure Monitor
**By:** Parker (research brief — pre-implementation)
**Status:** Options laid out — Ripley to pick before Bishop implements
**Why:** Ripley is designing a reusable Python logging module. This brief compares credible paths for shipping logs to Seq (self-hosted) and Azure Monitor / Application Insights. Each path has operational trade-offs that need to be baked into the API design early. Bishop will implement once Ripley settles the sink strategy.

---

## Recommendations

### Seq Ingestion Path
**🟢 Recommended: OTLP over HTTP to Seq's `/api/events` endpoint (Seq 2024+)**

**Rationale:**
- Seq 2024+ accepts OpenTelemetry Protocol (OTLP) natively; no proprietary library needed beyond `opentelemetry-exporter-otlp-proto-http`
- **Single wire format:** Logs can route to Seq or Azure Monitor without code changes (just env var switch)
- Plays well with OpenTelemetry ecosystem; no `seqlog` vendor lock-in
- Batching, retry, and backpressure are baked into OTel SDK's `BatchLogRecordProcessor`
- Network-resilient: failed exports are queued in-memory up to a bound (default ~2048 log records)

**Alternative considered but not recommended:**
- **CLEF over HTTP (`seqlog` library):** Lighter weight, no OTel dependency. Trade-off: Custom retry/batch logic; not portable to other sinks (Azure Monitor doesn't ingest CLEF). Risk: Feature creep if reusable module needs to support multiple formats.
- **OTel Collector sidecar:** Decouples app from sink. Trade-off: Extra container, requires Docker Compose / K8s orchestration; overkill for local dev. Reserve for production if Ops wants to centralize log filtering / sampling.

**Package requirements:**
```
opentelemetry-exporter-otlp-proto-http>=0.48b0  # HTTP/protobuf exporter
```

**Seq version requirement:** 2024.1 or later (OTLP support stable)

**Configuration in logging module:**
- Accept `seq_url` (e.g., `https://seq.example.com:5341`) as optional init parameter
- If `seq_url` provided, register `OTelHTTPExporter` pointing to `{seq_url}/api/events` with `BatchLogRecordProcessor`
- If not provided or unreachable, degrade gracefully (see degradation section)

---

### Azure Monitor / Application Insights Path
**🟢 Recommended: `azure-monitor-opentelemetry` distro with `APPLICATIONINSIGHTS_CONNECTION_STRING`**

**Rationale:**
- Azure's official distribution; supported, battle-tested, covers logs + traces + metrics in one call
- Connection string is Azure standard (same env var name across all Azure SDKs)
- Idempotent: `configure_azure_monitor()` can be called multiple times without side effects (uses `atexit` + singleton pattern)
- Minimal config boilerplate for users; most defaults are sensible

**Alternative considered:**
- **Raw `opentelemetry-exporter-azure-monitor`:** Requires manual setup of SDK, processors, exporters. More control but 3x boilerplate. Not recommended unless Ripley needs that granularity.

**Package requirements:**
```
azure-monitor-opentelemetry>=1.6.0  # Already in project pyproject.toml
```

**Connection string sourcing:**
- Prefer standard **`APPLICATIONINSIGHTS_CONNECTION_STRING`** env var (set by Azure Container Apps, Azure Portal, CI/CD tooling automatically)
- **Do NOT** wrap in custom `APP_AZURE_*` var; respect Azure conventions
- If missing at runtime, log warning (not error); app continues without Azure Monitor

**Configuration timing:**
- Call `configure_azure_monitor()` **once at app startup**, before creating app instance
- Safe to call in `config.py:Settings.__post_init__()` or in `main.py` at module level if Ripley's module is invoked from there
- Verify thread-safe: Azure Monitor distro uses thread-local context for trace/span handling; safe in FastAPI's worker pool

**Resource attributes (proposed, for Ripley's API):**
```python
# Set these so Azure / Seq dashboards show service identity
"service.name": "copilot-python-app"  # from APP_NAME in config
"service.version": "0.1.0"            # from APP_VERSION
"deployment.environment": "prod"      # from APP_ENVIRONMENT
"cloud.region": "eastus"              # optional, from APP_AZURE_REGION if set
```
These can be passed to logging module init: `logger = Logger(service_name="copilot-python-app", environment="prod")`

---

### Graceful Degradation (Network Failures)
**🟢 Recommended: In-process buffering with exponential backoff + silent drop after N retries**

**Rationale:**
- App must never block or crash if Seq / Azure Monitor is unreachable
- OpenTelemetry SDK's `BatchLogRecordProcessor` already does this well; use it as base

**Default behavior:**
1. **Buffering:** OTel batches up to `max_queue_size=2048` log records in memory (configurable)
2. **Export retry:** Processor batches on interval (default 5s) and attempts export. If network fails:
   - Retry with **exponential backoff** (1s → 2s → 4s → 8s → fail)
   - After 5 failed attempts spanning ~30s, **silently drop the batch**
   - Continue accepting new logs
3. **Console fallback (optional):** If both Seq and Azure are unreachable, logs already go to console (app's root logger)

**Configurable knobs (proposed env vars):**
```
APP_LOG_BATCH_SIZE=512              # Records per batch (default; tune for throughput vs latency)
APP_LOG_QUEUE_MAX=2048              # Max pending records before dropping (default; tune for memory)
APP_LOG_EXPORT_TIMEOUT_SECS=5       # HTTP timeout per export attempt (default)
APP_LOG_FAILSAFE_MODE=console       # On sink failure: console|silent|raise (default: console)
```

**Why not "log once, drop silently"?**
- OTel batching is already an optimization; don't reimplement it
- Silent drop is the right default; if Seq is down, losing individual log records is acceptable (service continuity wins)
- Option to set `APP_LOG_FAILSAFE_MODE=console` for local dev if troubleshooting is needed

**Thread safety:**
- `BatchLogRecordProcessor` uses thread-safe queue; safe in FastAPI's async + threaded context
- OTel context (trace IDs) is thread-local by design

---

## Environment Variable Contract (Proposed)

### Core Logging Settings
```
APP_LOG_LEVEL=INFO                           # DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
APP_LOG_FORMAT=json|console                  # json=structured, console=text (default: json)
```

### Seq Configuration (Optional)
```
APP_LOG_SEQ_URL=https://seq.example.com:5341  # Seq ingestion endpoint (default: not set; Seq disabled)
# No API key needed for OTLP; CLEF-over-HTTP would need:
# APP_LOG_SEQ_API_KEY=<set in .env>           # (secret)
```

### Azure Monitor Configuration (Optional)
```
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...  # Azure standard (secret)
# Set automatically by Azure Container Apps; no need for APP_* wrapper
```

### OTel Resource Attributes (Optional)
```
APP_LOG_SERVICE_NAME=copilot-python-app     # Defaults to APP_NAME
APP_LOG_SERVICE_VERSION=0.1.0                # Defaults to APP_VERSION
APP_LOG_ENVIRONMENT=prod                     # Defaults to APP_ENVIRONMENT
APP_LOG_REGION=eastus                        # Optional; for cloud.region resource attr
```

### Degradation & Advanced (Optional)
```
APP_LOG_BATCH_SIZE=512                      # Records per export batch (default)
APP_LOG_QUEUE_MAX=2048                       # Max queued records before drop (default)
APP_LOG_EXPORT_TIMEOUT_SECS=5                # HTTP timeout (default)
APP_LOG_FAILSAFE_MODE=console                # console|silent|raise (default: console)
```

### .env.example Template
```ini
APP_NAME=copilot-python-app
APP_ENVIRONMENT=local
APP_VERSION=0.1.0

# Logging
APP_LOG_LEVEL=INFO
APP_LOG_FORMAT=json

# Seq (optional; if not set, Seq ingestion is disabled)
# APP_LOG_SEQ_URL=http://localhost:5341

# Azure Monitor (optional; if not set, Azure ingestion is disabled)
# APPLICATIONINSIGHTS_CONNECTION_STRING=<set in deployment or secrets manager>

# Resource attributes (optional; defaults use APP_NAME, APP_VERSION, APP_ENVIRONMENT)
# APP_LOG_SERVICE_NAME=copilot-python-app
# APP_LOG_SERVICE_VERSION=0.1.0
# APP_LOG_REGION=eastus
```

---

## Dependency Footprint

**Proposal: Add new optional extras to pyproject.toml**

```toml
[project.optional-dependencies]
# Existing
azure = [
  "azure-identity>=1.19.0",
  "azure-monitor-opentelemetry>=1.6.0",
]
dev = [...]

# New: Logging extras
# Base OTel (required by logging module regardless of sink choice)
logging = [
  "opentelemetry-sdk>=1.26.0",
  "opentelemetry-api>=1.26.0",
  "python-json-logger>=3.2.0",
]

# OTel exporters (optional; user picks based on sink strategy)
logging-seq = [
  "opentelemetry-exporter-otlp-proto-http>=0.48b0",
]
logging-azure = [
  "azure-monitor-opentelemetry>=1.6.0",
]

# Convenience: both Seq and Azure
logging-full = [
  "opentelemetry-sdk>=1.26.0",
  "opentelemetry-api>=1.26.0",
  "python-json-logger>=3.2.0",
  "opentelemetry-exporter-otlp-proto-http>=0.48b0",
  "azure-monitor-opentelemetry>=1.6.0",
]
```

**Installation examples:**
```bash
# Just console logging, no sinks
pip install ./

# Console + Seq
pip install ".[logging,logging-seq]"

# Console + Azure Monitor
pip install ".[logging,logging-azure]"

# Console + both sinks
pip install ".[logging-full]"
```

**Rationale:**
- Apps that just need console logging don't bloat with Azure/OTel packages
- Ripley's reusable module is portable; users opt into sinks
- `azure-monitor-opentelemetry` is already in optional `azure` extra; don't duplicate

---

## Local Dev Story

**Goal:** Emmanuel spins up Seq locally to test logging module without cloud credentials.

### Docker Compose Snippet (Seq only)
Add this to `docker-compose.yml` or create `docker-compose.local-dev.yml`:

```yaml
services:
  seq:
    image: datalust/seq:2024.2  # Pin to 2024+ for OTLP support
    environment:
      ACCEPT_EULA: "Y"
    ports:
      - "5341:5341"        # Ingestion API (OTLP, CLEF, JSON)
      - "80:80"            # Web UI (http://localhost/seq)
    volumes:
      - seq-storage:/data   # Persistent event storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  seq-storage:
```

**Usage:**
```bash
# Start Seq locally
docker-compose -f docker-compose.local-dev.yml up seq

# In another terminal, set env var and run app
export APP_LOG_SEQ_URL=http://localhost:5341
export APP_LOG_FORMAT=json
python -m copilot_python_app.main

# View logs in Seq UI
open http://localhost/seq
```

**Notes:**
- `ACCEPT_EULA: "Y"` required; Seq is free for dev but requires acknowledgment
- Port 5341 is standard for Seq ingestion (HTTP/OTLP/CLEF/JSON)
- Port 80 (UI) redirects to `/seq` path; or set `HTTP_PORT=80 UI_PATH=/seq` in env
- Volume `seq-storage` persists events across restarts
- Health check uses `/health` endpoint (Seq always running, doesn't need Datalust cloud)

**Optional: Add to existing docker-compose.yml for integrated local dev**
If Emmanuel wants to run app + Seq together:

```yaml
services:
  app:
    # ... existing config ...
    environment:
      APP_LOG_SEQ_URL: http://seq:5341  # Service name inside Docker network
    depends_on:
      seq:
        condition: service_healthy
  
  seq:
    image: datalust/seq:2024.2
    environment:
      ACCEPT_EULA: "Y"
    ports:
      - "5341:5341"
      - "80:80"
    volumes:
      - seq-storage:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  seq-storage:
```

Then:
```bash
docker-compose up  # app + seq together; app logs go to Seq
curl http://localhost:8000/health  # app
open http://localhost/seq           # Seq UI
```

---

## Secret Handling Checklist

| Env Var | Secret? | Never In | `.env.example` | Storage |
|---------|---------|----------|--------|---------|
| `APP_LOG_LEVEL` | No | — | `INFO` | Git OK |
| `APP_LOG_FORMAT` | No | — | `json` | Git OK |
| `APP_LOG_SEQ_URL` | No | — | `http://localhost:5341` | Git OK |
| `APP_LOG_SEQ_API_KEY` | **Yes** | Logs, error messages, code | `<set in .env>` | **`.env` only** |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | **Yes** | Logs, error messages, code, `.squad/` files | `<set in deployment>` | **`.env` or secrets manager** |
| `APP_LOG_SERVICE_NAME` | No | — | `copilot-python-app` | Git OK |
| `APP_LOG_SERVICE_VERSION` | No | — | `0.1.0` | Git OK |
| `APP_LOG_ENVIRONMENT` | No | — | `local` | Git OK |
| `APP_LOG_REGION` | No | — | `eastus` | Git OK |
| `APP_LOG_BATCH_SIZE` | No | — | `512` | Git OK |
| `APP_LOG_QUEUE_MAX` | No | — | `2048` | Git OK |
| `APP_LOG_EXPORT_TIMEOUT_SECS` | No | — | `5` | Git OK |
| `APP_LOG_FAILSAFE_MODE` | No | — | `console` | Git OK |

### Rules for Secret Vars:
1. **`APP_LOG_SEQ_API_KEY` (if using CLEF path instead of OTLP):**
   - NEVER write to code, logs, `.squad/` files, or error messages
   - In local dev: read from `.env` only (not committed)
   - In CI/CD: inject via GitHub secrets → GitHub Actions → container env
   - In Azure: store in Azure Key Vault, managed by Workload Identity / OIDC
   - If unset and Seq URL provided, assume Seq is unauthenticated (dev/private network)

2. **`APPLICATIONINSIGHTS_CONNECTION_STRING`:**
   - NEVER write to code, logs, `.squad/` files
   - Use Azure standard var name (not `APP_AZURE_*` wrapper)
   - In Azure Container Apps: set via Application Settings (encrypted at rest)
   - In local dev: optional; if missing, Azure Monitor is disabled (no error)
   - If unset and both Seq + Azure URLs not provided, app logs to console only

### Implementation Notes for Logging Module:
- If `APP_LOG_SEQ_API_KEY` is needed, read once at init and store in private module variable (never re-read or log)
- If `APPLICATIONINSIGHTS_CONNECTION_STRING` is missing, log at DEBUG level (not WARNING): "Azure Monitor not configured"
- If both Seq URL and Azure connection string are missing, log at INFO level: "Logging to console only"
- **Never** print connection strings in `__repr__` or debug output; mask them in logging: `Seq URL: <redacted>`

---

## Local Development Notes

### Using OTLP (Recommended Path)
No authentication needed for local Seq. Add to `.devcontainer/devcontainer.json` or `.env`:
```json
{
  "services": {
    "app": { ... },
    "seq": {
      "image": "datalust/seq:2024.2",
      "environment": ["ACCEPT_EULA=Y"],
      "ports": ["5341:5341", "80:80"]
    }
  }
}
```

Or set env var at runtime:
```bash
export APP_LOG_SEQ_URL=http://localhost:5341
# No API key needed; OTLP is unauthenticated by default
python -m copilot_python_app.main
```

### Testing Graceful Degradation
```bash
# Start app with Seq URL set
export APP_LOG_SEQ_URL=http://invalid.example.com:5341
python -m copilot_python_app.main

# App should log to console without error; export attempts fail silently after retry backoff
# (If APP_LOG_FAILSAFE_MODE=console, degraded logs still appear on stdout)

# Now start real Seq
docker-compose up seq
# Logs now route to both console and Seq (OTel exporter becomes healthy)
```

---

## Open Questions for Ripley

1. **Module portability:** Should the logging module be a standalone package (e.g., `ripley-logging`) or live in this repo under `src/`? Impact: If standalone, Ripley needs to decide on packaging, versioning, and PyPI publication strategy.

2. **Structured field mapping:** OTLP and CLEF have slightly different field schemas. When Ripley designs the logging API, should it expose raw OTel fields (`attributes`, `resource`, `trace_id`) or a simplified interface? (e.g., `logger.info("message", tags={"user_id": 123})`)

3. **Sampler / filtering:** Should the logging module support server-side sampling (Seq / Azure can filter on ingestion)? Or keep it simple: all logs ship, filtering is sink's job?

4. **Async vs sync export:** OTel's `BatchLogRecordProcessor` is async-safe but blocks on `flush()`. For FastAPI apps, should Ripley expose a `flush_and_close()` method to call in shutdown handler? Or rely on `atexit` hook?

5. **Metrics / Traces:** This brief focuses on logs. Does Ripley's module also need to instrument metrics (e.g., request counts, latency) and traces? That would change the dependency footprint and sink complexity.

6. **Config location:** Should logging config live in the logging module itself (import and call `Logger()` from Ripley's package), or in the app's `config.py` / `main.py` to keep app-specific setup centralized?

---

## Summary of Choices Made

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Seq path** | OTLP over HTTP (not CLEF, not Collector) | Unified wire format with Azure; standard OTel; batching/retry built-in |
| **Azure path** | `azure-monitor-opentelemetry` distro | Official, battle-tested, all-in-one (logs+traces+metrics) |
| **Degradation** | OTel SDK `BatchLogRecordProcessor` + silent drop | Network resilience without breaking app; tunable retry / queue bounds |
| **Env prefix** | `APP_LOG_*` + standard `APPLICATIONINSIGHTS_CONNECTION_STRING` | Consistent with app config; respects Azure conventions |
| **Dep strategy** | Optional extras (`logging`, `logging-seq`, `logging-azure`, `logging-full`) | No bloat for simple apps; users opt into sinks |
| **Local dev** | Docker Compose Seq snippet with OTLP, no auth | Fast iteration; same code path as prod (OTLP); no mock creds needed |
| **Secrets** | `.env` only; standard Azure var names | Complies with team secret-handling policy; no leaks to `.squad/` |

---

**Next step:** Ripley reviews, picks a path (or asks clarifying questions), then Bishop implements.


---

### 2026-05-13T09:17:33-05:00: Test plan — reusable logging module

**By:** Hudson (proactive — implementation not yet built)
**Status:** Plan only — tests will be written after Ripley's design lands
**Why:** Ripley is designing a reusable structured logging module that ships JSON logs to Seq and optionally to Azure Monitor. Before a single line of implementation exists, we need an agreed behavioral contract that tests can be written against. This plan defines that contract in terms of observable behavior only — no coupling to class names, function signatures, or internal implementation details. Every test case below can be adapted once Ripley's public API lands. The goal is to find the failure modes before Bishop writes the code, not after.

📌 **Proactive — written from requirements before implementation exists. May need adjustment once API lands.**

---

## Test categories & cases

### 1. Structured JSON output

Every log record emitted by the module MUST be parseable as a single-line JSON object with required fields intact. `extra` kwargs must survive serialization. Non-JSON-native types must be handled without crashing the caller.

- `test_emitted_log_line_is_valid_json` — a single `logger.info("msg")` call produces output that `json.loads()` parses without error 📌
- `test_emitted_json_contains_timestamp_field` — parsed record has a timestamp field (exact name TBD with Ripley: `timestamp`, `@t`, or `asctime`) 📌
- `test_emitted_json_contains_level_field` — parsed record has a level/severity field 📌
- `test_emitted_json_contains_message_field` — parsed record has a `message` (or `@m`) field matching the logged string 📌
- `test_emitted_json_contains_logger_name_field` — parsed record has a `name` field identifying the logger 📌
- `test_extra_scalar_survives_serialization` — `logger.info("msg", extra={"request_id": "abc123"})` — `request_id` key present in JSON output 📌
- `test_extra_nested_dict_survives_serialization` — nested dict in `extra` appears in emitted JSON 📌
- `test_extra_with_datetime_value_serializes_without_error` — `extra={"ts": datetime.utcnow()}` does not raise; field present in output 📌
- `test_extra_with_uuid_value_serializes_without_error` — `extra={"id": uuid4()}` does not raise; field present in output 📌
- `test_exception_info_captured_as_structured_field` — `logger.error("boom", exc_info=True)` inside an `except` block produces a JSON record containing exception type/message/traceback 📌
- `test_exception_object_in_extra_does_not_raise` — passing a live Exception instance as an `extra` value does not crash the logging call 📌

---

### 2. Log levels & filtering

The module must respect Python's standard level hierarchy. Filtering at the logger level and at the handler level must both work correctly.

- `test_debug_message_emitted_when_level_is_debug` — `logger.debug("x")` appears in captured output when module configured at DEBUG 📌
- `test_debug_message_suppressed_when_level_is_info` — `logger.debug("x")` does NOT appear when module configured at INFO 📌
- `test_info_message_emitted_at_info_level` — `logger.info("x")` appears when configured at INFO 📌
- `test_warning_message_emitted_at_info_level` — WARNING passes through when root level is INFO 📌
- `test_error_message_emitted` — ERROR always appears 📌
- `test_critical_message_emitted` — CRITICAL always appears 📌
- `test_handler_level_threshold_drops_messages_below_threshold` — handler configured at WARNING drops DEBUG and INFO records 📌
- `test_root_level_below_handler_threshold_handler_decides` — when root logger is DEBUG but handler is WARNING, only WARNING+ records appear in handler output 📌
- `test_log_level_change_at_runtime_takes_effect` — dynamically changing the logger's level mid-run filters subsequent messages correctly 📌

---

### 3. Seq sink behavior

The Seq handler must ship events to the configured server. When the server is unreachable, the module must NOT raise exceptions to the caller. Ripley's degradation contract (drop vs. buffer) is not yet decided — we write tests for both contracts and let Ripley choose.

- `test_seq_sink_sends_event_to_mock_server_when_reachable` — `logger.info("hello")` results in exactly one request received by the mock Seq CLEF/OTLP endpoint 📌
- `test_seq_sink_sends_correct_content_type_header` — request to mock Seq has expected Content-Type (CLEF: `application/vnd.serilog.clef` or OTLP: `application/json`) 📌
- `test_seq_sink_includes_api_key_header_when_configured` — request to mock Seq includes `X-Seq-ApiKey` header matching `SEQ_API_KEY` setting 📌
- `test_seq_sink_uses_configured_url_not_hardcoded_default` — requests go to the URL from settings, not a hardcoded fallback 📌
- `test_seq_sink_not_added_when_seq_url_not_configured` — no Seq-related handler registered when `SEQ_URL` is absent from settings 📌
- `test_seq_sink_does_not_raise_when_server_unreachable` [Contract A & B] — `logger.info("x")` with Seq pointed at a refused port raises no exception in the calling code 📌
- `test_seq_sink_drops_event_silently_when_server_unreachable` [Contract A — drop] — event is not buffered or retried; it is silently discarded 📌
- `test_seq_sink_buffers_event_and_delivers_when_server_recovers` [Contract B — buffer] — event queued while Seq is down; after server comes back online, event eventually arrives 📌
- `test_seq_sink_connection_error_does_not_corrupt_subsequent_log_calls` — after a Seq failure, the next `logger.info()` call works normally (console sink still active) 📌
- `test_seq_sink_no_exception_leaks_on_http_5xx_response` — mock Seq returning 500 does not propagate an exception to the caller 📌

---

### 4. Azure Monitor sink behavior

The Azure Monitor exporter must be conditionally wired. Absent configuration must be a no-op, not an error.

- `test_azure_monitor_exporter_registered_when_connection_string_present` — when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (to a fake value), the Azure Monitor exporter is present in the handler/exporter chain 📌
- `test_azure_monitor_exporter_not_added_when_connection_string_absent` — when connection string env var is not set, no Azure Monitor handler/exporter is present 📌
- `test_absent_azure_connection_string_is_not_an_error` — module initializes without raising when `APPLICATIONINSIGHTS_CONNECTION_STRING` is absent 📌
- `test_azure_monitor_exporter_does_not_raise_when_endpoint_unreachable` — with a fake/invalid connection string, log calls do not raise exceptions to caller 📌
- `test_azure_monitor_exporter_does_not_block_other_sinks` — console and Seq sinks continue working even when Azure Monitor exporter fails 📌

---

### 5. Graceful degradation contract

This category validates the *system-level* promise: the application keeps running regardless of sink health. Warnings about sink failures must not flood logs.

- `test_module_configures_without_raising_when_seq_unreachable_at_startup` — passing an unreachable `SEQ_URL` at configure time does not raise; module returns successfully 📌
- `test_logging_continues_normally_when_seq_goes_down_mid_run` — after successful initialization, simulate Seq going away; subsequent `logger.info()` calls do not raise 📌
- `test_seq_failure_warning_logged_once_not_per_call` — when Seq is persistently down, the internal warning about sink failure appears exactly once in the console output, not repeated per log call 📌
- `test_module_configures_without_raising_when_azure_monitor_endpoint_unreachable` — fake/invalid AI connection string does not block startup 📌
- `test_console_sink_always_active_regardless_of_other_sink_health` — even with both Seq and Azure Monitor down, console output still receives log records 📌

---

### 6. Portability / no-FastAPI

The module must be importable into non-FastAPI Python apps. We verify this at the import graph level.

- `test_importing_logging_module_does_not_import_fastapi` — after `importlib.import_module("...")`, `"fastapi"` is NOT in `sys.modules` 📌
- `test_importing_logging_module_does_not_import_starlette` — `"starlette"` is NOT in `sys.modules` after import 📌
- `test_importing_logging_module_does_not_import_uvicorn` — `"uvicorn"` is NOT in `sys.modules` after import 📌
- `test_logging_module_usable_in_plain_python_script` — a minimal script that does NOT create a FastAPI app can call the module's configure function and emit logs without error 📌

  > Implementation note: these tests MUST run in an isolated subprocess or a fixture that clears `sys.modules` before import to avoid false passes from FastAPI being imported earlier in the test session.

---

### 7. Settings / env var contract

All configuration flows through `pydantic-settings`. No bare `os.getenv()` calls in the module.

- `test_default_log_level_is_info_when_env_var_absent` — when `APP_LOG_LEVEL` is not set, effective level is INFO 📌
- `test_log_level_overridden_by_app_log_level_env_var` — `APP_LOG_LEVEL=DEBUG` → module configured at DEBUG 📌
- `test_seq_url_read_from_seq_url_env_var` — `SEQ_URL=http://localhost:5341` → Seq sink wired to that URL 📌
- `test_seq_api_key_read_from_seq_api_key_env_var` — `SEQ_API_KEY=test-key` → key sent in Seq request header 📌
- `test_azure_connection_string_read_from_env_var` — `APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...` → Azure exporter wired 📌
- `test_missing_optional_settings_do_not_raise` — module with only defaults (no SEQ_URL, no AI string) initializes cleanly 📌
- `test_invalid_log_level_string_produces_clear_validation_error` — `APP_LOG_LEVEL=BANANAS` raises a descriptive `ValidationError` (or equivalent), not a cryptic `AttributeError` 📌
- `test_settings_not_read_from_env_vars_directly_in_module_code` — the module source contains no `os.getenv` or `os.environ` calls outside the Settings class (static analysis / grep check) 📌

---

### 8. Backward compatibility / migration

The existing `configure_logging(log_level: str)` in `src/copilot_python_app/telemetry.py` must either continue to work or have a clear migration shim. The test must validate whichever path Ripley selects.

- `test_existing_configure_logging_callable_still_works` [Shim contract] — `configure_logging("INFO")` raises no error after the new module is introduced 📌
- `test_configure_logging_shim_produces_json_output` [Shim contract] — if shim wraps the new module, output is JSON-structured, not the old plain-text format 📌
- `test_configure_logging_shim_wires_same_handlers_as_new_api` [Shim contract] — calling the shim produces the same observable handler configuration as calling the new API directly 📌
- `test_migration_import_path_resolves_without_error` [Hard-migration contract] — the new import path recommended in the migration guide resolves without `ImportError` 📌

  > ⚠️ Ripley must decide: shim (backward compat) or clean break (migration guide). Write the test for the chosen path and delete the other.

---

### 9. Edge cases & failure modes

The module must survive hostile inputs without crashing the caller or corrupting log output.

- `test_log_message_with_embedded_newlines_produces_single_json_line` — `"line1\nline2"` as message results in exactly one valid JSON object per log call (newline escaped, not literal) 📌
- `test_log_message_with_utf8_multibyte_characters_survives_round_trip` — message containing `"café ☕ 日本語"` appears correctly in JSON output 📌
- `test_bytes_value_in_extra_handled_without_crash` — `extra={"raw": b"\xff\xfe"}` does not raise a `TypeError`; field is present (repr or base64 or omitted — any is acceptable, must not crash) 📌
- `test_very_large_extras_dict_does_not_raise` — `extra={f"key_{i}": i for i in range(1000)}` logs without error 📌
- `test_concurrent_threads_produce_valid_json_lines` — 20 threads each calling `logger.info(f"thread {n}")` concurrently; every captured line is valid JSON with no interleaved corruption 📌
- `test_configure_twice_does_not_add_duplicate_handlers` — calling the configure function a second time does not result in duplicate handlers (duplicate console lines, double Seq POSTs) 📌
- `test_configure_twice_behavior_is_documented` — whichever behavior is chosen (idempotent no-op, raise, or de-dup), it is exercised by a test with an explicit assertion so the contract is locked 📌
- `test_none_value_in_extra_serialized_as_null_not_string` — `extra={"thing": None}` → JSON contains `"thing": null`, not `"thing": "None"` 📌

---

### 10. Coverage gates

**Recommended target: 85% branch coverage** for the new logging module.

Rationale:
- The repo floor is 80% (`fail_under = 80` in `pyproject.toml`). A new, purpose-built module with explicit behavioral contracts warrants a higher bar.
- 100% is unrealistic — the Azure Monitor and Seq network paths have SDK internals we don't own.
- 85% branch coverage forces us to exercise both sides of every `if connection_string:` / `if seq_url:` / `if reachable:` gate, which is exactly where the meaningful bugs live.
- The 15% headroom covers: SDK internals we mock out, `__all__` / `__version__` module-level constants, and OS-level exception branches in HTTP sends.
- Coverage must be measured with `branch = true` (already set in `pyproject.toml`).
- Add a `# pragma: no cover` comment only for lines that are genuinely unreachable from tests (SDK internals, type stubs). Do not use it to hide logic.

---

### 11. Fixtures & test infrastructure needed

| Fixture | Purpose | Implementation |
|---------|---------|----------------|
| `capture_json_logs(logger_name)` | In-memory `logging.Handler` that collects formatted records; exposes `.records` as `list[dict]` | Custom `Handler` subclass; yields from a `pytest.fixture`; removed from logger on teardown |
| `parse_log_json(line)` | Helper that calls `json.loads()` and asserts no parse error | Simple helper function in `conftest.py` |
| `mock_seq_server` | A `pytest-httpserver`-based fixture mimicking a Seq CLEF endpoint; records received requests; supports configuring failure mode (5xx, connection refused) | Requires adding `pytest-httpserver` to dev deps |
| `seq_refused_url` | A fixture that provides a URL pointing at a port with no listener (refused connection) | Bind a socket, get port, close socket, return URL |
| `env_logging(monkeypatch, **kwargs)` | Wraps `monkeypatch.setenv` for `APP_LOG_LEVEL`, `SEQ_URL`, `SEQ_API_KEY`, `APPLICATIONINSIGHTS_CONNECTION_STRING`; clears them all on teardown | Parametrized helper fixture |
| `mock_azure_monitor_configure` | Monkeypatches `azure.monitor.opentelemetry.configure_azure_monitor` to a no-op spy; prevents real HTTP to Azure | `monkeypatch.setattr` |
| `isolated_logging` | Resets the Python `logging.root` handler list and clears all module-level logger state before/after each test | Session-scoped or function-scoped fixture using `logging.root.handlers.clear()` + `logging.Logger.manager.loggerDict.clear()` |
| `sys_modules_snapshot` | Captures `sys.modules` keys before a test, restores them after; required for portability tests | `pytest.fixture` with `yield` and set subtraction |

**New dev dependencies to add to `pyproject.toml`:**
- `pytest-httpserver>=1.0.0` — for `mock_seq_server`
- `python-json-logger>=2.0.0` — runtime dep; may already be added by Bishop
- `pytest-xdist` (optional) — if we want to verify concurrency tests in parallel mode

---

### 12. Open questions for Ripley / Bishop

These ambiguities must be resolved before tests are written. I'm flagging them now so they don't become silent assumptions baked into the implementation.

1. **Seq degradation contract** — Drop silently? Buffer with retry? Fall-through to console only? This controls whether tests verify "event never arrives" vs. "event eventually arrives." MUST be decided before Seq sink tests are finalized.

2. **Exact JSON field names** — What are the canonical field names for timestamp (`timestamp`? `@t`? `asctime`?), level (`level`? `levelname`? `@l`?), and message (`message`? `@m`?). Tests will hard-code these — they need to be stable.

3. **Public entry point** — Is this `configure_logging(settings: LoggingSettings)`, a class instantiation `LoggingModule(settings)`, or something else? The fixture infrastructure depends on this.

4. **Module location & package name** — Is this a new top-level package (`python_logging` / `structured_logging`), a submodule of the existing app, or a separate installable? The portability import test needs the exact module path.

5. **Own Settings class or shared Settings** — Does the logging module expose its own `LoggingSettings(BaseSettings)` or consume the app's existing `Settings`? If shared, the portability guarantee is harder to maintain.

6. **Seq transport: CLEF (HTTP) or OTLP?** — Affects the mock server setup and the Content-Type assertions in category 3.

7. **Configure-twice behavior** — Idempotent no-op? Raise? De-dup handlers? One of these must be chosen and locked in. "Undefined" is not acceptable — callers (especially startup hooks) will call this twice.

8. **Backward-compat decision** — Shim the old `configure_logging(log_level: str)` or mandate migration? Bishop needs to know before touching `telemetry.py`.

9. **Flush/shutdown hook** — Is there a `shutdown()` or `flush()` call expected (e.g., at app lifespan end)? If yes, it needs testing. If no, we need to verify Seq events aren't silently dropped at process exit.

10. **python-json-logger optional or required?** — If it's an optional dependency, we need a test for the "not installed" graceful fallback. If required, simpler.

