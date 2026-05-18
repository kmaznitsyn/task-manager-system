data "archive_file" "notification_src" {
    type        = "zip"
    source_dir  = "${path.module}/../../../../cloud-functions/notification"
  output_path = "${path.module}/.build/notification.zip"
    excludes    = ["__pycache__", "tests", "pytest.ini", ".pytest_cache"]
  }

  resource "google_storage_bucket" "function_src" {
    name                        = "${var.project_id}-function-src"
    location                    = var.region
    uniform_bucket_level_access = true
    force_destroy               = false
  }

resource "google_storage_bucket_object" "notification_zip" {
    # filename includes the hash → updating source replaces the object
    # and forces the function to redeploy.
    name   = "notification-${data.archive_file.notification_src.output_md5}.zip"
    bucket = google_storage_bucket.function_src.name
    source = data.archive_file.notification_src.output_path
  }

# ---- runtime identity ----
  resource "google_service_account" "notification_fn" {
    account_id   = "notification-fn"
    display_name = "Notification Cloud Function"
  }

  # Eventarc needs to invoke the underlying Cloud Run service.
  resource "google_project_iam_member" "notification_fn_invoker" {
    project = var.project_id
    role    = "roles/run.invoker"
    member  = "serviceAccount:${google_service_account.notification_fn.email}"
  }

  resource "google_project_iam_member" "notification_fn_eventarc" {
    project = var.project_id
    role    = "roles/eventarc.eventReceiver"
    member  = "serviceAccount:${google_service_account.notification_fn.email}"
  }

# The Pub/Sub service agent must be allowed to mint tokens for Eventarc.
  # Look up the project number once.
  data "google_project" "current" {}

  resource "google_project_iam_member" "pubsub_token_creator" {
    project = var.project_id
    role    = "roles/iam.serviceAccountTokenCreator"
    member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
  }

# ---- the function ----
  resource "google_cloudfunctions2_function" "notification" {
    name     = "notification"
    location = var.region

    build_config {
      runtime     = "python312"
      entry_point = "handle_task_event"
      source {
        storage_source {
          bucket = google_storage_bucket.function_src.name
          object = google_storage_bucket_object.notification_zip.name
        }
      }
    }

    service_config {
      available_memory      = "256M"
      timeout_seconds       = 60
      max_instance_count    = 5
      min_instance_count    = 0
      service_account_email = google_service_account.notification_fn.email
      ingress_settings      = "ALLOW_INTERNAL_ONLY"

      environment_variables = {
        KEYCLOAK_ADMIN_URL    = var.keycloak_admin_url
        KEYCLOAK_CLIENT_ID    = var.keycloak_client_id
        SENDGRID_FROM_ADDRESS = var.sendgrid_from_address
      }

      # Secrets (SendGrid API key, Keycloak admin client secret) should come
      # from Secret Manager, not env_vars. Add `secret_environment_variables`
      # blocks once the secrets exist.
    }

    event_trigger {
      trigger_region        = var.region
      event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
      pubsub_topic          = var.tasks_events_topic_id   # pass topic.id from root
      retry_policy          = "RETRY_POLICY_RETRY"
      service_account_email = google_service_account.notification_fn.email
    }

    depends_on = [
      google_project_iam_member.notification_fn_invoker,
      google_project_iam_member.notification_fn_eventarc,
      google_project_iam_member.pubsub_token_creator,
    ]
  }