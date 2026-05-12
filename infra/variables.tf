variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "location" {
  description = "Azure region for resources."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Resource group name."
  type        = string
  default     = "rg-copilot-python-app"
}

variable "app_name" {
  description = "Application and resource name prefix."
  type        = string
  default     = "copilot-python-app"
}

variable "container_image" {
  description = "Initial container image to deploy."
  type        = string
  default     = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
}

variable "github_repository" {
  description = "GitHub repository in owner/name format for OIDC federated credentials."
  type        = string
}

variable "github_environment" {
  description = "GitHub environment name allowed to deploy to Azure."
  type        = string
  default     = "azure-prod"
}

variable "tags" {
  description = "Tags applied to Azure resources."
  type        = map(string)
  default = {
    workload = "copilot-python-app"
    managed  = "terraform"
  }
}

