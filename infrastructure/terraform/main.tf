terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "gcs" {
    bucket = "still-function-494322-d7-tfstate"
    prefix = "env/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------- Networking ----------
# TODO: VPC connector for Cloud Run -> Cloud SQL private IP (ticket TM-17)
resource "google_compute_network" "vpc" {
  name                    = "app-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_global_address" "private_ip_range" {
  name          = "cloudsql-private-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
  deletion_policy         = "ABANDON"
}

# ---------- Cloud SQL (Postgres) ----------
resource "google_sql_database_instance" "main" {
  name             = "${var.env}-taskmanager-pg"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 10
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }

  deletion_protection = false
  depends_on          = [google_service_networking_connection.private_vpc_connection]
}

resource "google_vpc_access_connector" "connector" {
  name          = "run-connector"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2
  max_instances = 3
}

resource "google_sql_database" "users" {
  name     = "users_db"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_database" "tasks" {
  name     = "tasks_db"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_database" "keycloak" {
  name     = "keycloak_db"
  instance = google_sql_database_instance.main.name
}

# A DB user for Keycloak (don't reuse 'postgres').
resource "random_password" "keycloak_db" {
  length  = 32
  special = false
}

resource "google_sql_user" "keycloak" {
  name     = "keycloak"
  instance = google_sql_database_instance.main.name
  password = random_password.keycloak_db.result
}

# Secrets — admin password and DB password live in Secret Manager.
resource "random_password" "keycloak_admin" {
  length  = 24
  special = true
}

resource "google_secret_manager_secret" "kc_admin_pw" {
  secret_id = "keycloak-admin-password"
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret_version" "kc_admin_pw" {
  secret      = google_secret_manager_secret.kc_admin_pw.id
  secret_data = random_password.keycloak_admin.result
}

resource "google_secret_manager_secret" "kc_db_pw" {
  secret_id = "keycloak-db-password"
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret_version" "kc_db_pw" {
  secret      = google_secret_manager_secret.kc_db_pw.id
  secret_data = random_password.keycloak_db.result
}

resource "google_service_account" "keycloak" {
  account_id   = "keycloak"
  display_name = "Keycloak runtime SA"
}

resource "google_secret_manager_secret_iam_member" "kc_admin_pw_access" {
  secret_id = google_secret_manager_secret.kc_admin_pw.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.keycloak.email}"
}
resource "google_secret_manager_secret_iam_member" "kc_db_pw_access" {
  secret_id = google_secret_manager_secret.kc_db_pw.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.keycloak.email}"
}

resource "google_cloud_run_v2_service" "keycloak" {
  name     = "keycloak"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # tighten via TM-19 (gateway/LB)

  template {
    service_account = google_service_account.keycloak.email
    scaling {
      min_instance_count = 1 # cold-start mitigation
      max_instance_count = 2
    }
    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.quay_remote.repository_id}/keycloak/keycloak:25.0"
      # Vanilla quay image isn't pre-built. The implicit auto-build inside
      # `kc.sh start` doesn't reliably pick up KC_DB, leaving Keycloak with
      # no Postgres driver registered. Run `build` explicitly first, then
      # `start --optimized`. Slow cold start (~60–90s) — bake a custom
      # image with the build step baked in to get this down.
      command = ["/bin/sh", "-c"]
      args = [
        "/opt/keycloak/bin/kc.sh build && exec /opt/keycloak/bin/kc.sh start --optimized"
      ]
      startup_probe {
        tcp_socket {
          port = 8080
        }
        initial_delay_seconds = 30
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 30 # ~5 min total for first-start build
      }
      ports { container_port = 8080 }

      resources {
        limits = { cpu = "2", memory = "1Gi" }
      }

      env {
        name  = "KC_DB"
        value = "postgres"
      }
      env {
        name = "KC_DB_URL"
        # Private IP of Cloud SQL instance, reachable via VPC connector.
        value = "jdbc:postgresql://${google_sql_database_instance.main.private_ip_address}:5432/keycloak_db"
      }
      env {
        name  = "KC_DB_USERNAME"
        value = google_sql_user.keycloak.name
      }
      env {
        name = "KC_DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.kc_db_pw.secret_id
            version = "latest"
          }
        }
      }
      # No KC_HOSTNAME: with KC_HOSTNAME_STRICT=false Keycloak derives URLs
      # from the request Host header — fine for the auto-assigned Cloud Run
      # URL. When the LB + custom domain follow-up lands, set KC_HOSTNAME to
      # the public domain and flip strict back on.
      env {
        name  = "KC_HOSTNAME_STRICT"
        value = "false"
      }
      env {
        name  = "KC_PROXY"
        value = "edge" # Cloud Run terminates TLS
      }
      env {
        name  = "KC_HTTP_ENABLED"
        value = "true"
      }
      env {
        name  = "KEYCLOAK_ADMIN"
        value = "admin"
      }
      env {
        name = "KEYCLOAK_ADMIN_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.kc_admin_pw.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  deletion_protection = false
  depends_on          = [google_sql_user.keycloak]
}

# Keycloak must be reachable by unauthenticated browsers — Cloud Run blocks
# anonymous invocation by default regardless of ingress settings. This binds
# allUsers to roles/run.invoker so the SPA's redirect to /auth and the
# backends' JWKS fetches go through.
resource "google_cloud_run_v2_service_iam_member" "keycloak_public" {
  location = google_cloud_run_v2_service.keycloak.location
  name     = google_cloud_run_v2_service.keycloak.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# FOLLOW-UP: stable custom domain. Cloud Run v1 domain mappings are not
# offered in europe-west3 (and many other regions). The supported path is a
# Global External Application Load Balancer with a Serverless NEG pointing
# at this Cloud Run service, plus a google_compute_managed_ssl_certificate
# for auth.<public_domain>. Until that lands, the issuer URL is the
# auto-assigned Cloud Run URL emitted below — note that it changes if the
# service is destroyed and recreated, so anything trusting it (Angular
# app, task-service, user-service) has to be redeployed in that case.
output "keycloak_issuer" {
  value = "${google_cloud_run_v2_service.keycloak.uri}/realms/taskmanager"
}

output "keycloak_service_url" {
  value = google_cloud_run_v2_service.keycloak.uri
}

# ---------- Pub/Sub for task events ----------
resource "google_pubsub_topic" "tasks_events" {
  name = "tasks-events"
}

# Dead-letter topic for messages the notification function can't process.
# Without this, a permanently-broken message retries until the 7-day TTL.
resource "google_pubsub_topic" "tasks_events_dlq" {
  name = "tasks-events-dlq"
}

# Pull subscription so dead-lettered messages are retained for inspection
# instead of expiring silently on the bare topic.
resource "google_pubsub_subscription" "tasks_events_dlq_inspect" {
  name                       = "tasks-events-dlq-inspect"
  topic                      = google_pubsub_topic.tasks_events_dlq.name
  message_retention_duration = "604800s" # 7 days
  ack_deadline_seconds       = 60
}

# The Pub/Sub service agent forwards nacked/expired messages to the DLQ
# on behalf of the source subscription, so it needs publisher rights here.
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.tasks_events_dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.root.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

data "google_project" "root" {}

# FOLLOW-UP: attach a dead_letter_policy pointing at
# google_pubsub_topic.tasks_events_dlq to the subscription Eventarc creates
# for the notification function. The 2nd-gen event_trigger manages that
# subscription internally and Terraform can't address it directly. Options:
#   1. Replace the event_trigger with a hand-rolled
#      google_pubsub_subscription + google_eventarc_trigger pair so the
#      dead_letter_policy lives in Terraform.
#   2. Patch it post-apply via gcloud:
#        gcloud pubsub subscriptions update <eventarc-sub-name> \
#          --dead-letter-topic=tasks-events-dlq \
#          --max-delivery-attempts=5
#      and grant the Pub/Sub service agent roles/pubsub.subscriber on that
#      subscription so it can ack failed messages.
# Until one of those lands, the DLQ topic exists but receives nothing.

# ---------- Artifact Registry ----------
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "taskmanager"
  format        = "DOCKER"
}

# Cloud Run can't pull from quay.io directly; this remote repo proxies it.
# Image path becomes <region>-docker.pkg.dev/<project>/quay-remote/<upstream-path>.
resource "google_artifact_registry_repository" "quay_remote" {
  location      = var.region
  repository_id = "quay-remote"
  format        = "DOCKER"
  mode          = "REMOTE_REPOSITORY"

  remote_repository_config {
    description = "Mirror of quay.io"
    docker_repository {
      custom_repository {
        uri = "https://quay.io"
      }
    }
  }
}

# ---------- Cloud Run services ----------
# NOTE: images must already be pushed to Artifact Registry.
# See module calls below.

module "user_service" {
  source    = "./modules/cloud_run_service"
  name      = "user-service"
  region    = var.region
  image     = "${var.region}-docker.pkg.dev/${var.project_id}/taskmanager/user-service:latest"
  connector = google_vpc_access_connector.connector.id
  env_vars = {
    DATABASE_URL      = var.user_db_url
    KEYCLOAK_ISSUER   = var.keycloak_issuer
    KEYCLOAK_JWKS_URL = var.keycloak_jwks_url
  }
}

module "task_service" {
  source    = "./modules/cloud_run_service"
  name      = "task-service"
  region    = var.region
  image     = "${var.region}-docker.pkg.dev/${var.project_id}/taskmanager/task-service:latest"
  connector = google_vpc_access_connector.connector.id
  env_vars = {
    DATABASE_URL              = var.task_db_url
    KEYCLOAK_ISSUER           = var.keycloak_issuer
    KEYCLOAK_JWKS_URL         = var.keycloak_jwks_url
    PUBSUB_TOPIC_TASKS_EVENTS = google_pubsub_topic.tasks_events.name
  }
}

# ---------- Cloud Function (notification) ----------
module "notification_function" {
  source                = "./modules/notification_function"
  project_id            = var.project_id
  region                = var.region
  tasks_events_topic_id = google_pubsub_topic.tasks_events.id
  keycloak_admin_url    = var.keycloak_admin_url
  keycloak_client_id    = var.keycloak_client_id
  sendgrid_from_address = var.sendgrid_from_address
}
