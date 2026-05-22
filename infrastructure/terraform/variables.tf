variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west3"
}

variable "env" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "user_db_url" {
  description = "Connection string for user-service DB"
  type        = string
  sensitive   = true
}

variable "task_db_url" {
  description = "Connection string for task-service DB"
  type        = string
  sensitive   = true
}

variable "keycloak_issuer" {
  type = string
}

variable "keycloak_jwks_url" {
  type = string
}

variable "keycloak_audience" {
  description = "JWT audience claim the backend services validate."
  type        = string
  default     = "taskmanager-api"
}

variable "keycloak_admin_url" {
  type = string
}

variable "keycloak_client_id" {
  type = string
}

variable "sendgrid_from_address" {
  type = string
}

variable "public_domain" {
  description = "Apex domain — Keycloak is served at auth.<public_domain>."
  type        = string
}
