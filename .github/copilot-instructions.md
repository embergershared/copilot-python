# Repository instructions

This repository is an Azure-ready Python FastAPI service. Optimize changes for correctness, type safety, testability, secure defaults, and deterministic local and CI execution.

## Python standards

- Use Python 3.12+ syntax and explicit type hints for all function signatures.
- Keep application code under `src/copilot_python_app` and tests under `tests`.
- Prefer small, cohesive modules with clear boundaries between API routes, configuration, health checks, telemetry, and infrastructure integration.
- Load runtime configuration through `pydantic-settings`; do not read environment variables directly throughout the codebase.
- Use structured logging through the existing telemetry setup instead of `print`.

## Testing and validation

- Add or update pytest coverage for behavior changes.
- Run `ruff check .`, `mypy`, and `pytest` before completing code changes.
- Keep coverage meaningful; do not add tests that only exercise implementation details.
- Include integration tests for FastAPI routes that affect HTTP behavior.

## Security and operations

- Never commit secrets, connection strings, tokens, private keys, or local `.env` files.
- Prefer GitHub OIDC federation for Azure authentication instead of long-lived credentials.
- Keep health endpoints lightweight, dependency-aware when needed, and safe for container or Azure probes.
- Use least-privilege Azure role assignments and managed identities for cloud resources.

## Dependency and tooling guidance

- Declare runtime and development dependencies in `pyproject.toml`.
- Prefer standard Python packaging and reproducible commands that work locally, in GitHub Actions, and in Copilot cloud agent setup.
- Do not introduce a new framework, package manager, or infrastructure tool without updating docs and validation commands.

