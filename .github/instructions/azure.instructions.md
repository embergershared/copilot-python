---
applyTo: "{infra/**/*.tf,.github/workflows/*azure*.yml,Dockerfile,docker-compose.yml}"
---

# Azure instructions

- Default hosting target is Azure Container Apps with Azure Container Registry and Log Analytics.
- Use managed identities and GitHub OIDC federation; do not add long-lived Azure credentials.
- Prefer least-privilege role assignments scoped to the smallest practical resource.
- Ensure health probes use `/health` and containers listen on port `8000` unless explicitly changed.
- Document required Azure resource names, GitHub environment variables, and deployment prerequisites.

