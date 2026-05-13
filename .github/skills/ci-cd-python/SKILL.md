---
name: ci-cd-python
description: Guidance for changing Python build, validation, or GitHub Actions automation.
---

# CI/CD Python skill

Use this skill when changing Python build, validation, or GitHub Actions automation.

## Checklist

- Install dependencies from `pyproject.toml`.
- Run `ruff check .`, `mypy`, and `pytest` in CI.
- Cache pip dependencies with `actions/setup-python`.
- Use minimal workflow permissions.
- Use GitHub OIDC for Azure deployments.
- Keep Copilot cloud agent setup aligned with local install commands.

