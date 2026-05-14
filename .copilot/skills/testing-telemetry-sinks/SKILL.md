---
name: "testing-telemetry-sinks"
description: "Test logging/telemetry sinks (Seq, Azure Monitor, OTLP) without real network I/O"
domain: "quality"
confidence: "high"
source: "earned (logging module test plan + implementation, 2026-05-13)"
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

### 2. Isolated logging state (global autouse)

Place in `tests/conftest.py` as `autouse=True`. This is safe for non-logging tests too.

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

**Key insight:** `logging.Logger.manager.loggerDict.clear()` is necessary — without it,
named loggers created during a test retain their handlers even after `root.handlers` is
restored.

**⚠ Gotcha — module-level cached loggers + caplog DEBUG capture:** `loggerDict.clear()`
removes loggers from the manager dict but does NOT touch their internal `Logger._cache`.
If a module caches its logger at import time
(e.g., `_logger = logging.getLogger("emm_settings.sources")`) and an early test calls
`_logger.debug(...)` while the effective level is `WARNING`, the cache gets
`{10: False}`. A later test that raises root level to `DEBUG` via
`caplog.at_level(logging.DEBUG)` then sees no records because `isEnabledFor(DEBUG)`
returns the stale cached `False`. Fix it with a sub-package autouse fixture that wipes
the cache:

```python
@pytest.fixture(autouse=True)
def reset_emm_settings_loggers() -> Generator[None, None, None]:
    import emm_settings.dotenv as _dotenv_mod
    import emm_settings.sources as _sources_mod
    for mod in (_dotenv_mod, _sources_mod):
        cache = getattr(mod._logger, "_cache", None)
        if isinstance(cache, dict):
            cache.clear()
    yield
```

### 3. Mock HTTP sink via monkeypatch (no extra deps)

For per-event POST sinks (like CLEF/Seq), `monkeypatch` on `requests.post` is sufficient
and avoids adding `pytest-httpserver` to dev deps.

```python
def fake_post(url: str, **kwargs: Any) -> MagicMock:
    calls.append({"url": url, **kwargs})
    return MagicMock(raise_for_status=MagicMock())

monkeypatch.setattr(requests, "post", fake_post)
```

**Why this works:** When a module does `import requests as _requests`, `_requests` IS the
same module object as `requests`. Patching `requests.post` patches `_requests.post` too.
This means you patch at the top-level module, not at the `sinks.seq` module.

For failure tests:
```python
monkeypatch.setattr(requests, "post", MagicMock(side_effect=requests.ConnectionError("x")))
```

### 4. Rate-limiter tests with time.monotonic

When the handler uses `time.monotonic()` to throttle warnings, use a closure-based mock:

```python
def test_rate_limit() -> None:
    tick = 0.0

    def monotonic_mock() -> float:
        return tick  # reads tick at call time — closure by reference

    monkeypatch.setattr(time, "monotonic", monotonic_mock)
    handler._last_warning_at = -1_000_000.0  # force first warning to fire

    handler.emit(record)           # t=0 → warning fires
    tick = 30.0
    handler.emit(record)           # t=30 → still within 60s window, suppressed
    tick = 61.0
    handler.emit(record)           # t=61 → window expired, warning fires again
```

**Key:** reassign `tick` directly — no second `setattr` needed because Python closures
read the variable cell at call time, not at definition time.

Always reset `handler._last_warning_at = -1_000_000.0` at the start of each test so the
first emit() predictably fires a warning regardless of test order.

### 5. SDK-level exporter mock (Azure Monitor)

Never make real Azure calls from tests. Monkeypatch the module-level flag and function on
the public `sinks.azure` module:

```python
import emm_logging.sinks.azure as azure_mod

@pytest.fixture
def mock_azure_monitor(monkeypatch):
    calls: list[dict] = []
    def fake_configure(**kwargs) -> None:
        calls.append(kwargs)
    monkeypatch.setattr(azure_mod, "_HAS_AZURE_MONITOR", True)
    monkeypatch.setattr(azure_mod, "configure_azure_monitor", fake_configure)
    return calls
```

For the "package missing" path:
```python
monkeypatch.setattr(azure_mod, "_HAS_AZURE_MONITOR", False)
monkeypatch.setattr(azure_mod, "configure_azure_monitor", None)
```

### 6. Portability / no-FastAPI import check (subprocess, not sys.modules snapshot)

**NEVER** use `sys.modules` snapshot for portability tests within a pytest session.
If FastAPI is imported by conftest or any earlier test, the snapshot will miss it.
Use subprocess isolation instead:

```python
import os, subprocess, sys
from pathlib import Path

_SRC_DIR = str(Path(__file__).parent.parent.parent / "src")

def test_no_fastapi() -> None:
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{_SRC_DIR}'); "
        "before = set(sys.modules.keys()); "
        "import your_logging_module; "
        "new = set(sys.modules.keys()) - before; "
        "assert 'fastapi' not in new, f'fastapi imported: {new & {\"fastapi\"}}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": _SRC_DIR},
    )
    assert result.returncode == 0, result.stderr
```

Set `PYTHONPATH` explicitly so the subprocess can import the source tree even if the
package isn't pip-installed in the active venv.

## Anti-Patterns

- ❌ Using real Seq/Azure URLs in unit tests (flaky, environment-dependent, slow)
- ❌ Forgetting to remove handlers in teardown (handler leak causes false positives)
- ❌ Relying on import-order guarantees for portability tests (FastAPI imported by conftest
  will hide violations — use subprocess)
- ❌ Using `logging.disable()` to suppress output in tests — this masks real coverage gaps
- ❌ Assuming 100% coverage on network I/O paths — mock at the SDK boundary, not the socket level
- ❌ Hardcoding JSON field names without confirming with the module author (timestamp field name
  varies between python-json-logger versions and CLEF format)
- ❌ Not resetting `handler._last_warning_at` in rate-limit tests — test order dependency
- ❌ Using `time.sleep(61)` to test a 60s throttle window — always monkeypatch `time.monotonic`

## Dependencies

Add to `pyproject.toml` `[project.optional-dependencies]` dev section:
- `python-json-logger>=3.0.0` — runtime dep for module under test (already in base deps)
- No additional test deps needed for HTTP mocking — `monkeypatch` on `requests` is sufficient

## Coverage guidance

- Target 85% branch coverage for new telemetry modules (higher than repo floor)
- `# pragma: no cover` only for genuinely unreachable SDK internals (global safety-net catch blocks)
- Branch coverage (`branch = true`) is more meaningful than line coverage for
  conditional sink-wiring logic
- `_fallback_console_handler()` called only from `# pragma: no cover` safety-net is acceptable
  to leave uncovered — do not add a test that imports the private function just to hit it
