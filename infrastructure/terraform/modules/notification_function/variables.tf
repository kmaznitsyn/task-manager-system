variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "tasks_events_topic_id" {
  type        = string
  description = "Full topic ID (projects/<p>/topics/<t>) for the Eventarc trigger."
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
