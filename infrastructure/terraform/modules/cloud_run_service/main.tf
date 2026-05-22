variable "name" { type = string }
variable "region" { type = string }
variable "image" { type = string }
variable "env_vars" {
  type    = map(string)
  default = {}
}
variable "secret_env_vars" {
  description = "Env vars sourced from Secret Manager. Map of env var name -> { secret = secret_id, version = optional }."
  type = map(object({
    secret  = string
    version = optional(string, "latest")
  }))
  default = {}
}
variable "service_account" {
  description = "Runtime service account email. If null, Cloud Run uses the default compute SA."
  type        = string
  default     = null
}
variable "connector" {
    type    = string
    default = null
}

resource "google_cloud_run_v2_service" "this" {
  name                = var.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = var.service_account

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
    connector = var.connector
    egress    = "PRIVATE_RANGES_ONLY"
    }
  }
}

# TODO: Decide whether this should be public or IAM-gated.
# For a dev scaffold this allows unauthenticated; locking down is ticket TM-19.
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.this.project
  location = google_cloud_run_v2_service.this.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "url" {
  value = google_cloud_run_v2_service.this.uri
}
