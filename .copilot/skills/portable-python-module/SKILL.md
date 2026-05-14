---
name: "portable-python-module"
description: "Pattern for packaging a reusable Python module alongside an existing app in a monorepo"
domain: "architecture"
confidence: "high"
source: "ripley-logging-module-design decision (2026-05-13)"
---

## Context
When building a utility module (e.g., logging, telemetry, shared config) that must be portable across multiple Python projects but is developed alongside a specific app.

## Pattern

### Module placement
- Create a new top-level package under `src/` (e.g., `src/ember_logging/`) in the same repo as the consuming app.
- Do NOT nest it as a sub-package of the app — this couples consumers to the app's distribution.
- Add the new package to `[tool.hatch.build.targets.wheel] packages` in `pyproject.toml`.
- Extract to its own repo/PyPI package later when the API stabilizes.

### Dependency isolation with optional extras
- Keep the base package's dependencies minimal (only what's needed for the default code path).
- Use `[project.optional-dependencies]` for optional sinks/integrations (e.g., `[seq]`, `[azure]`).
- Guard optional imports with `try/except ImportError` and a module-level flag.

### No framework coupling
- Zero imports from the consuming framework (FastAPI, Django, etc.) inside the portable module.
- The consuming app writes a thin glue module that bridges app settings to the portable module's API.

### Settings contract
- Use `pydantic-settings` with a dedicated env prefix (e.g., `LOG_`) separate from the app's prefix (e.g., `APP_`).
- This keeps the module independently configurable across different host apps.

## Anti-Patterns
- **Sub-packaging under the app** — forces every consumer to `pip install the-whole-app` for a utility.
- **Shared env prefix** — couples the module's config namespace to a specific app.
- **Exposing internals** — keep handler/sink implementations private (`_handlers/`). Public API is the configure function and settings model only.
