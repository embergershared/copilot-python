---
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Actions instructions

- Pin actions to stable major versions and grant minimal `permissions` per workflow.
- Use `actions/setup-python` with dependency caching for Python workflows.
- Run `ruff check .`, `mypy`, and `pytest` in CI for application changes.
- Use GitHub OIDC with `azure/login` for Azure deployments.
- Keep `copilot-setup-steps.yml` focused on preparing deterministic tools and dependencies for Copilot cloud agent.

