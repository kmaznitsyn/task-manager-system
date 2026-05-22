# Non-secret default values. Loaded automatically by Terraform.
# Secrets (DB passwords etc.) come from random_password + Secret Manager,
# not from here. Override locally with a gitignored terraform.tfvars.
project_id            = "still-function-494322-d7"
region                = "europe-west3"
env                   = "dev"
keycloak_issuer       = "https://keycloak-d57bj7qdsa-ey.a.run.app/realms/taskmanager"
keycloak_jwks_url     = "https://keycloak-d57bj7qdsa-ey.a.run.app/realms/taskmanager/protocol/openid-connect/certs"
keycloak_admin_url    = "https://keycloak-d57bj7qdsa-ey.a.run.app/admin/realms/taskmanager"
keycloak_client_id    = "notification-fn"
sendgrid_from_address = "noreply@example.com"
public_domain         = "example.com"
