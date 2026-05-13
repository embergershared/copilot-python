# Azure deployment prompt

Prepare or review deployment of this service to Azure Container Apps.

## Expectations

- Use GitHub OIDC federation and least-privilege Azure role assignments.
- Build and push the container image to Azure Container Registry.
- Deploy to Azure Container Apps with `/health` probes and Log Analytics.
- Document required GitHub environment variables, secrets, and Azure resources.
- Include smoke test and rollback checks.

