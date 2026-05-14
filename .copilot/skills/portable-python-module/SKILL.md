---
name: "portable-python-module"
description: "Pattern for packaging a reusable Python module alongside an existing app in a monorepo"
domain: "architecture"
confidence: "high"
source: "ripley-logging-module-design decision (2026-05-13); refined by bishop-emm-logging-refactor-and-emm-settings (2026-05-13)"
---

## Context
When building a utility module (e.g., logging, telemetry, shared config) that must be portable across multiple Python projects but is developed alongside a specific app.

## Pattern

### Module placement
- Create a new top-level package under `src/` (e.g., `src/emm_logging/`, `src/emm_settings/`) in the same repo as the consuming app.
- Do NOT nest it as a sub-package of the app — this couples consumers to the app's distribution.
- Add the new package to `[tool.hatch.build.targets.wheel] packages` in `pyproject.toml` (path form: `"src/emm_logging"`).
- Extract to its own repo/PyPI package later when the API stabilizes.

### Public surface — `__init__.__all__`
- The package `__init__.py` should expose ONLY the public API via `__all__` and re-export from internal modules.
- Internal sink/handler implementations live under a public `sinks/` subpackage (or a `_private/` underscore module if intentionally private), but the entry point users import is the top-level package.
- Example: `from emm_logging import setup_logging, LoggingSettings, LoggingSinks, get_logger, timestamp_prefix`.

### Dependency isolation with optional extras
- Keep the base package's dependencies minimal (only what's needed for the default code path).
- Use `[project.optional-dependencies]` for optional sinks/integrations (e.g., `[seq]`, `[azure]`).
- Guard optional imports with `try/except ImportError` and a module-level flag (e.g., `_HAS_AZURE_MONITOR`).
- The same pattern applies to `python-dotenv` in `emm_settings`: import is guarded, missing dep degrades gracefully with a single stderr warning.

### No framework coupling
- Zero imports from the consuming framework (FastAPI, Django, etc.) inside the portable module.
- The consuming app writes a thin glue module (`copilot_python_app.main._bootstrap`) that bridges app settings to the portable module's API.
- A subprocess-based portability test (see `testing-telemetry-sinks` skill) protects this invariant.

### Settings contract
- Use `pydantic-settings` with a dedicated env prefix (e.g., `LOG_`) separate from the app's prefix (e.g., `APP_`).
- Set `extra="ignore"` so unknown env vars don't crash construction in shared environments.
- This keeps the module independently configurable across different host apps.

### Companion settings/dotenv module
- A peer module (e.g., `emm_settings`) can provide typed env accessors (`env_str`, `env_int`, `env_bool`, `env_path`, `env_csv`), `.env` loading (`load_dotenv_files`), and a redacting `log_settings` snapshot helper.
- Such a peer must NOT import the logging module — instead it uses `logging.getLogger("emm_settings.<sub>")` directly so the modules can be adopted independently.

## Anti-Patterns
- **Sub-packaging under the app** — forces every consumer to `pip install the-whole-app` for a utility.
- **Shared env prefix** — couples the module's config namespace to a specific app.
- **Exposing internals** — keep low-level helpers off `__all__`. Public API is the bootstrap function (`setup_logging`), the settings model (`LoggingSettings`), the result dataclass (`LoggingSinks`), and minimal utilities (`get_logger`, `timestamp_prefix`).
- **Cross-module coupling between portable peers** — `emm_settings` must not import `emm_logging` (or vice versa); each must work standalone.
