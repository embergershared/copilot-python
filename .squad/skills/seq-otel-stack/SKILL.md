---
name: seq-otel-stack
description: Wire Seq and Azure Monitor as log sinks using OpenTelemetry SDK for Python services
domain: telemetry, logging, observability, Azure, Python
confidence: high
source: earned (copilot-python-app logging module research)
---

## Context

Modern Python services need to ship logs to multiple sinks (self-hosted Seq, cloud Azure Monitor, console fallback) while staying resilient to network outages. OpenTelemetry SDK provides a standard way to do this, but wiring it requires careful choices about:
- Which ingestion protocol (OTLP vs vendor-specific)
- How to handle batching, retry, and degradation
- How to configure and secret-manage without leaking credentials

This skill codifies the recommended pattern for Python FastAPI services.

## Pattern

### 1. Dependency Strategy (pyproject.toml)

Use optional extras to avoid bloating simple apps:

```toml
[project.optional-dependencies]
logging = [
  "opentelemetry-sdk>=1.26.0",
  "opentelemetry-api>=1.26.0",
  "python-json-logger>=3.2.0",
]
logging-seq = [
  "opentelemetry-exporter-otlp-proto-http>=0.48b0",
]
logging-azure = [
  "azure-monitor-opentelemetry>=1.6.0",
]
logging-full = [
  "opentelemetry-sdk>=1.26.0",
  "opentelemetry-api>=1.26.0",
  "python-json-logger>=3.2.0",
  "opentelemetry-exporter-otlp-proto-http>=0.48b0",
  "azure-monitor-opentelemetry>=1.6.0",
]
```

Users install based on sink needs:
- `pip install ./` — console only
- `pip install ".[logging-seq]"` — console + Seq
- `pip install ".[logging-azure]"` — console + Azure
- `pip install ".[logging-full]"` — console + both

### 2. Sink Ingestion Paths

#### Seq (Recommended: OTLP over HTTP)
- **Protocol:** OpenTelemetry Protocol (OTLP) over HTTP
- **Seq version:** 2024.1+ (OTLP support stable)
- **Package:** `opentelemetry-exporter-otlp-proto-http>=0.48b0`
- **Endpoint:** `{seq_url}/api/events` (e.g., `http://localhost:5341/api/events`)
- **Auth:** OTLP is unauthenticated by default; for secured Seq, use custom HTTP headers (future enhancement)

**Why OTLP:**
- Standard OpenTelemetry wire format (not Seq-specific CLEF)
- Unified path: same exporter code routes to Seq, Azure, or other OTel-compatible backends
- Batching, retry, and backpressure baked into OTel SDK; no custom buffering needed
- Seq 2024+ treats OTLP as first-class protocol

#### Azure Monitor (Recommended: azure-monitor-opentelemetry distro)
- **Package:** `azure-monitor-opentelemetry>=1.6.0`
- **Connection:** Standard `APPLICATIONINSIGHTS_CONNECTION_STRING` env var (Azure convention)
- **Setup:** Call `configure_azure_monitor()` once at app startup

**Why distro:**
- Official Microsoft package; battle-tested in production Azure workloads
- Covers logs, traces, metrics in one call (not just logs)
- Idempotent; thread-safe; handles context propagation (trace IDs) automatically
- Respects Azure Container Apps environment; no boilerplate

### 3. Configuration Pattern

Use `pydantic_settings` with `APP_*` prefix for app config + standard Azure var name:

```python
# config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )
    
    name: str = Field(default="my-app")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    
    # Logging
    log_format: str = Field(default="json")
    log_seq_url: str | None = Field(default=None)  # http://localhost:5341
    log_batch_size: int = Field(default=512)
    log_queue_max: int = Field(default=2048)
    log_export_timeout_secs: int = Field(default=5)
    log_failsafe_mode: str = Field(default="console")
    
    # Resource attributes
    log_service_name: str | None = Field(default=None)
    log_service_version: str | None = Field(default=None)
    log_region: str | None = Field(default=None)
    
    # Azure Monitor uses standard env var (not APP_* prefix)
    @property
    def azure_monitor_connection_string(self) -> str | None:
        return os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4. Graceful Degradation Pattern

Use OTel SDK's `BatchLogRecordProcessor` with bounded queue and silent drop on failure:

```python
# logging_module.py (pseudocode, implement per Ripley's API)
import logging
from opentelemetry.sdk.logs import LoggerProvider
from opentelemetry.sdk.logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http.log_exporter import OTLPLogExporter
from azure.monitor.opentelemetry import configure_azure_monitor

def configure_logging(settings: Settings) -> None:
    """Set up logging to console, Seq (OTLP), and/or Azure Monitor."""
    
    # 1. Configure console logging (always available)
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    
    # 2. Configure Azure Monitor if connection string is set
    if settings.azure_monitor_connection_string:
        try:
            configure_azure_monitor(
                logger_provider=None,  # Use default
                instrumentation_options={"resource_attributes": {
                    "service.name": settings.log_service_name or settings.name,
                    "deployment.environment": settings.environment,
                }},
            )
            logging.info("Azure Monitor configured")
        except Exception as e:
            logging.warning(f"Azure Monitor setup failed: {e}")
    
    # 3. Configure Seq (OTLP) if URL is set
    if settings.log_seq_url:
        try:
            logger_provider = LoggerProvider()
            otlp_exporter = OTLPLogExporter(
                endpoint=f"{settings.log_seq_url}/api/events",
                timeout=settings.log_export_timeout_secs,
            )
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    otlp_exporter,
                    max_queue_size=settings.log_queue_max,
                    schedule_delay_millis=5000,  # batch every 5s
                    max_export_batch_size=settings.log_batch_size,
                    export_timeout_millis=settings.log_export_timeout_secs * 1000,
                )
            )
            logging.info(f"Seq (OTLP) configured: {settings.log_seq_url}")
        except Exception as e:
            logging.warning(f"Seq setup failed: {e}")
    
    # 4. If both failed, log to console only (failsafe)
    logging.info(f"Logging configured (failsafe_mode={settings.log_failsafe_mode})")
```

**Degradation behavior:**
- If Seq URL is unreachable, OTel's `BatchLogRecordProcessor` retries with exponential backoff
- After ~5 failed attempts (30s total), batch is silently dropped
- App continues running; new logs keep being accepted
- Console logs always available as fallback
- Configurable via `APP_LOG_FAILSAFE_MODE=console|silent|raise`

### 5. Local Dev (Docker Compose Snippet)

For testing Seq integration locally:

```yaml
services:
  seq:
    image: datalust/seq:2024.2  # Pin to 2024+ for OTLP
    environment:
      ACCEPT_EULA: "Y"
    ports:
      - "5341:5341"  # OTLP/CLEF/JSON ingestion
      - "80:80"      # Web UI
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

Usage:
```bash
docker-compose up seq
export APP_LOG_SEQ_URL=http://localhost:5341
# app logs now route to http://localhost/seq
```

### 6. Secret Handling

| Var | Secret? | Storage | Never In |
|-----|---------|---------|----------|
| `APP_LOG_*` (except API key) | No | Git OK | — |
| `APP_LOG_SEQ_API_KEY` | **Yes** | `.env` / secrets manager | Logs, code, `.squad/` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | **Yes** | `.env` / secrets manager | Logs, code, `.squad/` |

**Implementation rules:**
- Read secrets once at init; store in private module variables
- Never print connection strings in logs or `__repr__`
- Use `.env.example` with placeholder values only
- Use GitHub OIDC + Azure Workload Identity for prod (no long-lived secrets)

### 7. Testing Graceful Degradation

```python
# Test that app logs to console if Seq is down
def test_logging_console_fallback(settings_with_bad_seq_url):
    settings = Settings(log_seq_url="http://invalid.example.com:5341")
    configure_logging(settings)
    
    logger = logging.getLogger(__name__)
    logger.info("test message")
    # Should appear on stdout/stderr, not hang or crash
```

## Anti-Patterns

- ❌ Writing Seq connection string / Azure credentials to code or `.squad/` files
- ❌ Calling `configure_azure_monitor()` multiple times per request (thread-safety risk)
- ❌ Replicating OTel `BatchLogRecordProcessor` retry logic instead of using the SDK
- ❌ Using CLEF directly (vendor-specific) when OTLP (standard) is available
- ❌ Bloating app dependencies with Seq/Azure packages when logging module should be separate
- ❌ Blocking app startup if Seq/Azure is unreachable (graceful degradation required)

## Examples

### Minimal Setup (Console Only)
```python
from logging_module import configure_logging
from config import get_settings

settings = get_settings()  # APP_LOG_LEVEL=INFO, no Seq/Azure
configure_logging(settings)  # Console only; no sink errors
```

### Seq + Console (Local Dev)
```bash
export APP_LOG_SEQ_URL=http://localhost:5341
export APP_LOG_LEVEL=DEBUG
python -m myapp.main
# Logs appear both on console and in Seq UI (http://localhost/seq)
```

### Seq + Azure Monitor (Prod)
```bash
export APP_LOG_SEQ_URL=https://seq.prod.internal:5341
export APP_LOG_SEQ_API_KEY=<secret>
export APPLICATIONINSIGHTS_CONNECTION_STRING=<secret>
python -m myapp.main
# Logs route to both Seq (on-prem) and Azure Monitor (cloud)
# If either is down, app continues; other sink still receives logs
```

## Related Skills

- **secret-handling** — never commit secrets; use `.env.example` patterns
- **pydantic-settings** — configuration via env vars and .env files
- **opentelemetry-python** — standard instrumentation (spans, metrics, context propagation)

## References

- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/instrumentation/python/getting-started/)
- [Seq OTLP Ingestion](https://docs.datalust.co/articles/net-events#OTLP)
- [Azure Monitor OpenTelemetry](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable?tabs=python)
- [OpenTelemetry BatchLogRecordProcessor](https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-sdk/src/opentelemetry/sdk/logs/export/__init__.py)
