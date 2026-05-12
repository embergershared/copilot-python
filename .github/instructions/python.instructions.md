---
applyTo: "**/*.py"
---

# Python instructions

- Use Python 3.12+ features only when they improve readability or type safety.
- Add explicit return types to every function and method.
- Prefer dependency injection for settings and external clients so tests can pass deterministic inputs.
- Keep FastAPI app creation in `create_app` and avoid side effects at import time beyond constructing the default `app`.
- Use `pydantic` models for request, response, and configuration contracts.
- Avoid broad `except Exception` handlers unless the error is re-raised or converted to a typed, user-meaningful response with logging.

