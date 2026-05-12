output "resource_group_name" {
  description = "Resource group name."
  value       = azurerm_resource_group.main.name
}

output "container_registry_name" {
  description = "Azure Container Registry name."
  value       = azurerm_container_registry.main.name
}

output "container_registry_login_server" {
  description = "Azure Container Registry login server."
  value       = azurerm_container_registry.main.login_server
}

output "container_app_name" {
  description = "Azure Container App name."
  value       = azurerm_container_app.main.name
}

output "container_app_url" {
  description = "Azure Container App URL."
  value       = "https://${azurerm_container_app.main.latest_revision_fqdn}"
}

output "github_actions_client_id" {
  description = "Client ID for GitHub Actions OIDC."
  value       = azurerm_user_assigned_identity.github_actions.client_id
}

output "github_actions_principal_id" {
  description = "Principal ID for GitHub Actions OIDC."
  value       = azurerm_user_assigned_identity.github_actions.principal_id
}

