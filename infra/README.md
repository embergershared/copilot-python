# Azure infrastructure

This Terraform configuration provisions an Azure Container Apps deployment target for the FastAPI service.

## Resources

- Resource group
- Log Analytics workspace
- Azure Container Registry
- Azure Container Apps environment
- Azure Container App with `/health` liveness and readiness probes
- User-assigned managed identity for the app
- User-assigned managed identity and federated credential for GitHub Actions OIDC
- Least-privilege role assignments for image pull, image push, and container app deployment

## Bootstrap

```powershell
cd infra
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

After apply, configure the `azure-prod` GitHub environment with these variables:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | `github_actions_client_id` output |
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | `resource_group_name` output |
| `AZURE_CONTAINER_REGISTRY_NAME` | `container_registry_name` output |
| `AZURE_CONTAINER_REGISTRY_LOGIN_SERVER` | `container_registry_login_server` output |
| `AZURE_CONTAINER_APP_NAME` | `container_app_name` output |
| `AZURE_CONTAINER_APP_URL` | `container_app_url` output |

## Operational checks

- Confirm `GET /health` returns HTTP 200 after deployment.
- Review Container Apps revision status after image updates.
- Check Log Analytics for application startup errors and request failures.
- Roll back by redeploying a known-good image tag through the deployment workflow.
- Rotate or recreate the GitHub Actions federated identity if repository ownership or environment names change.

