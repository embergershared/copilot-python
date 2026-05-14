---
name: "reusable-module-review"
description: "Checklist for reviewing a reusable Python module added to an existing repo"
domain: "code-review"
confidence: "high"
source: "extracted from emm_logging reviewer gate (2026-05-13)"
---

## Context

When a new reusable Python module (separate top-level package in `src/`) is added to this monorepo, the reviewer gate should verify portability, API surface discipline, and operational safety beyond normal code review.

## Checklist Pattern

### Portability & isolation
- **grep for forbidden imports** (`fastapi|starlette|uvicorn` or whatever the host framework is) inside the new package directory. Zero hits required.
- **Subprocess portability tests** must be real: spawn a fresh Python process, import the module, check `sys.modules` for the forbidden frameworks. `import foo; assert True` is not a portability test.
- **No `print()` anywhere** in the new package — use `sys.stderr.write` or `logging` for diagnostics.

### Public API surface
- **`__all__` declared** in `__init__.py` — verify the exported symbols match the design spec exactly.
- **`LoggingResult`-style return types are dataclasses**, not Pydantic, unless Pydantic is an intentional public dependency.
- **Every public function/method has a return type annotation.** Run `mypy --strict` to catch gaps.

### Optional dependency guards
- Every handler module that imports an optional package (requests, azure-monitor-opentelemetry, etc.) must use `try/except ImportError` and set a module-level `_HAS_*` boolean.
- The build function (e.g., `build_seq_handler`) checks the flag and returns `None` + warning — never raises.
- Tests monkeypatch the `_HAS_*` flag to simulate missing packages without actually uninstalling them.

### Degradation contract
- The main `configure_*` function **must never raise**. Wrap in try/except with a fallback path.
- Rate-limit runtime warnings (e.g., Seq POST failures) to avoid log storms. Verify tests monkeypatch `time.monotonic` instead of actually sleeping.
- Console/default sink is **always attached** — remote sinks are best-effort.

### Configure-twice / idempotency
- Second call replaces handlers, doesn't accumulate them. Verify with a test that checks `len(root.handlers)` before and after.

### YAGNI gate
- Cross-reference the design's "out of scope" list. Grep for keywords (trace, correlation, file, dynamic, metrics, async, buffer, registry, plugin). Any hit requires justification.
- No unused base classes or abstract registries. The handler list should be concrete handlers only.

### Validation commands
```bash
python -m ruff check .
python -m mypy src/
python -m pytest
python -m pytest --cov=<new_package> --cov-report=term-missing --cov-branch
python -c "from <package> import <public_symbols>; result = <configure_fn>(); print(result)"
```

### Coverage acceptance
- 95%+ branch coverage is the bar. The only acceptable uncovered branches are defensive safety nets (global try/except fallback paths marked `pragma: no cover`). Document each one explicitly in the verdict.

## Anti-Patterns
- ❌ Accepting `import foo; assert True` as a portability test
- ❌ Letting `configure_*` raise on bad settings (it should fall back to safe defaults)
- ❌ Rate-limit tests that use `time.sleep(60)` instead of mocking `time.monotonic`
- ❌ Exporting internal handler classes in `__all__`
- ❌ Adding out-of-scope features "while I'm in here"
