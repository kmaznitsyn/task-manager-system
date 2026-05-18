terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
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
