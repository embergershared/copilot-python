---
applyTo: "**/*"
---

# Security instructions

- Do not commit secrets or generated credential files.
- Keep `.env` ignored and maintain `.env.example` with safe placeholder values only.
- Validate all user-controlled inputs at API boundaries with Pydantic or FastAPI validation.
- Prefer secure defaults for container users, network exposure, Azure RBAC, and logging.
- Add or update security checks when dependencies, Dockerfiles, or deployment workflows change.

