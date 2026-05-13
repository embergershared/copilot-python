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

### 2026-05-13T09:45:57-05:00 — Round 2: 135-test suite implemented against emm_logging

**Fixture conventions confirmed (implemented, not just planned):**
- `isolated_logging` — placed in `tests/conftest.py` as `autouse=True`, globally. Resets `logging.root.handlers`, `logging.root.level`, and calls `logging.Logger.manager.loggerDict.clear()` after every test. This is safe even for non-logging tests (existing unit/integration tests are unaffected).
- `_JsonCaptureHandler` + `make_log_record` — helper class/function in `tests/test_emm_logging/conftest.py`; not exposed as a fixture since most tests use direct formatter calls rather than handler emit.

**Mocking approach for Seq HTTP transport:**
- `monkeypatch.setattr(requests, "post", fake_fn)` — patches the `requests` module directly. Works because `_requests` in `seq.py` is an alias for the same module object (`_requests is requests`). Patching the module attribute patches all references, including `_requests.post`.
- Do NOT need `requests-mock` or `pytest-httpserver` — monkeypatch is sufficient for the per-event POST pattern.
- `requests.ConnectionError` and `requests.HTTPError` (both subclasses of `requests.RequestException`) successfully trigger the handler's except clause.

**Rate-limiting test pattern (`time.monotonic` monkeypatching):**
```python
tick = 0.0
def monotonic_mock() -> float:
    return tick
monkeypatch.setattr(time, "monotonic", monotonic_mock)
# Now: reassign `tick` to advance simulated time between emit() calls.
# The closure reads `tick` at call time — no second setattr needed.
tick = 61.0
```
- Patch `time.monotonic` at the top-level `time` module (not at `emm_logging._handlers.seq.time`) — both work but top-level is cleaner.
- Always reset `handler._last_warning_at = -1_000_000.0` before the test to ensure the first warning fires predictably.

**Portability test pattern (subprocess isolation, not sys.modules snapshot):**
- `sys.modules` snapshot approach fails if FastAPI was imported before the test module (common in a pytest session).
- Subprocess approach is definitive: `subprocess.run([sys.executable, "-c", script])` with an explicit `PYTHONPATH` pointing to `src/`. Asserts `fastapi`, `starlette`, `uvicorn` are NOT in `new_mods = set(sys.modules.keys()) - mods_before`.

**Coverage achieved:**
- **98% branch coverage** on `src/emm_logging/` (132 tests in the new suite).
- Only uncovered: `setup.py:29-32` (`_fallback_console_handler()`) — reachable only from the global `# pragma: no cover` safety-net catch. Acceptable.
- All `# pragma: no cover` lines in Bishop's implementation are genuinely unreachable.

**python-json-logger behaviour confirmed:**
- `rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"}` produces `timestamp`, `level`, `message`, `logger` in console JSON output.
- `formatter.converter = time.gmtime` + `datefmt="%Y-%m-%dT%H:%M:%SZ"` produces ISO-8601 UTC timestamps matching `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z`.
- `json.dumps(..., default=str)` in SeqHandler ensures non-JSON-native extras (UUID, datetime) serialize cleanly.

**mypy status:**
- All `import-untyped` errors for `emm_logging` and `copilot_python_app` are pre-existing (no `py.typed` marker on either package). Not introduced by test code.
- No new mypy errors in test files beyond the project-wide pre-existing issue.

**Bugs found in Bishop's implementation:** None. All contracts verified as specified. `hudson-implementation-bugs.md` not created.

**Total test count:** 135 tests (132 new + 3 pre-existing), all passing.
