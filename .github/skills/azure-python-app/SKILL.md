---
name: azure-python-app
description: Guidance for implementing or reviewing Azure-facing behavior for this FastAPI service.
---

# Azure Python app skill

Use this skill when implementing or reviewing Azure-facing behavior for the FastAPI service.

## Checklist

- Keep `/health` fast, unauthenticated, and suitable for Azure Container Apps probes.
- Load configuration through `pydantic-settings` and document required `APP_` variables.
- Prefer managed identity for Azure service access.
- Keep Azure SDK clients isolated behind typed modules that can be mocked in tests.
- Do not call live Azure resources from unit tests.
- Document required Azure resources and operational checks.

