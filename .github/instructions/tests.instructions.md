---
applyTo: "tests/**/*.py"
---

# Test instructions

- Use pytest and FastAPI `TestClient` for HTTP route behavior.
- Name tests after observable behavior, not implementation details.
- Use fixtures for repeated setup and keep test data explicit.
- Cover success paths, validation errors, edge cases, and regressions for bugs.
- Keep tests deterministic; do not call live Azure services or external networks from unit tests.

