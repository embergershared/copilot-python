---
name: "testing-telemetry-sinks"
description: "Test logging/telemetry sinks (Seq, Azure Monitor, OTLP) without real network I/O"
domain: "quality"
confidence: "high"
source: "earned (logging module test plan, 2026-05-13)"
---

## Context

Logging modules that ship events to external sinks (Seq, Azure Monitor, OTLP collectors) are
notoriously hard to test because:
- Real network calls make tests slow, flaky, and environment-dependent
- Python's `logging` module is global mutable state; handlers leak between tests
- Degradation behavior (what happens when sink is DOWN) is the most important contract to test
  and the hardest to trigger in real setups
- Portability claims ("no FastAPI in import graph") can give false passes if FastAPI was already
  imported earlier in the test session

## Patterns

### 1. In-memory log capture handler

```python
import logging
import json
from collections.abc import Generator
import pytest

class JsonCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(json.loads(self.format(record)))
        except json.JSONDecodeError:
            self.records.append({"_raw": self.format(record)})

@pytest.fixture
def capture_json_logs(request) -> Generator[JsonCaptureHandler, None, None]:
    handler = JsonCaptureHandler()
    logger = logging.getLogger(request.param if hasattr(request, "param") else "root")
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)
```

### 2. Isolated logging state

Python logging is global. Without isolation, handler registrations from one test bleed into the
next. Always reset between tests:

```python
@pytest.fixture(autouse=True)
def isolated_logging() -> Generator[None, None, None]:
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level
    yield
    logging.root.handlers = original_handlers
    logging.root.setLevel(original_level)
    # Clear child loggers to prevent handler accumulation
    logging.Logger.manager.loggerDict.clear()
```

### 3. Mock HTTP sink with pytest-httpserver

```python
from pytest_httpserver import HTTPServer
import pytest

@pytest.fixture
def mock_seq_server(httpserver: HTTPServer):
    httpserver.expect_request("/api/events/raw", method="POST").respond_with_data("", status=201)
    return httpserver

@pytest.fixture
def seq_down_url() -> str:
    """Return a URL that will always refuse connections."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"
```

### 4. SDK-level exporter mock (Azure Monitor)

Never make real Azure calls from tests. Monkeypatch the SDK configure function:

```python
@pytest.fixture
def mock_azure_monitor_configure(monkeypatch):
    calls: list[dict] = []
    def fake_configure(**kwargs) -> None:
        calls.append(kwargs)
    monkeypatch.setattr(
        "azure.monitor.opentelemetry.configure_azure_monitor",
        fake_configure,
    )
    return calls
```

### 5. Portability / no-FastAPI import check

```python
import sys
import importlib

def test_module_does_not_import_fastapi() -> None:
    # Must run in isolation — if FastAPI was imported earlier, snapshot won't catch it.
    # Use sys_modules_snapshot fixture to guard against session-level pollution.
    before = set(sys.modules.keys())
    importlib.import_module("your_logging_module")
    after = set(sys.modules.keys())
    new_imports = after - before
    forbidden = {"fastapi", "starlette", "uvicorn"}
    assert not (new_imports & forbidden), f"Forbidden imports: {new_imports & forbidden}"
```

### 6. Write tests for BOTH degradation contracts; let architect pick

When the degradation behavior (drop vs. buffer) is not yet decided, write labeled tests for both:

```python
def test_seq_sink_drops_event_silently_when_server_unreachable(seq_down_url) -> None:
    # CONTRACT A: drop
    # ... configure with seq_down_url, log, assert no exception, assert event not buffered

def test_seq_sink_buffers_and_delivers_when_server_recovers(mock_seq_server) -> None:
    # CONTRACT B: buffer
    # ... configure with down URL, log, bring server up, assert event eventually arrives
```

Delete the non-chosen contract once the architect decides. Keep both until then — do not bake
assumptions.

## Anti-Patterns

- ❌ Using real Seq/Azure URLs in unit tests (flaky, environment-dependent, slow)
- ❌ Forgetting to remove handlers in teardown (handler leak causes false positives)
- ❌ Relying on import-order guarantees for portability tests (FastAPI imported by conftest
  will hide violations)
- ❌ Using `logging.disable()` to suppress output in tests — this masks real coverage gaps
- ❌ Assuming 100% coverage on network I/O paths — mock at the SDK boundary, not the socket level
- ❌ Hardcoding JSON field names without confirming with the module author (timestamp field name
  varies between python-json-logger versions and CLEF format)

## Dependencies

Add to `pyproject.toml` `[project.optional-dependencies]` dev section:
- `pytest-httpserver>=1.0.0` — HTTP sink mocking
- `python-json-logger>=2.0.0` — runtime dep for module under test

## Coverage guidance

- Target 85% branch coverage for new telemetry modules (higher than repo floor)
- `# pragma: no cover` only for genuinely unreachable SDK internals
- Branch coverage (`branch = true`) is more meaningful than line coverage for
  conditional sink-wiring logic
