# Task Manager — Microservice Scaffold

A basic microservice project scaffold with:

- **Backend:** FastAPI microservices (Python 3.12)
- **Frontend:** Angular 17+
- **Auth:** Keycloak (OIDC / JWT)
- **Database:** PostgreSQL (one DB per service)
- **Deployment:** Google Cloud Run
- **Async workloads:** Google Cloud Functions
- **Infra as Code:** Terraform

## Architecture

```
                 ┌──────────────┐
                 │   Angular    │
                 │   Frontend   │
                 └──────┬───────┘
                        │ (JWT)
                        ▼
                 ┌──────────────┐
                 │   Keycloak   │
                 └──────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   ┌───────────┐ ┌───────────┐ ┌──────────────┐
   │   User    │ │   Task    │ │ Notification │
   │  Service  │ │  Service  │ │  (Cloud Fn)  │
   │ (Cloud Run│ │ (Cloud Run│ │              │
   └─────┬─────┘ └─────┬─────┘ └──────────────┘
         │             │
         ▼             ▼
    PostgreSQL    PostgreSQL
    (users_db)    (tasks_db)
```

## Services

| Service             | Path                         | Responsibility                      |
|---------------------|------------------------------|-------------------------------------|
| user-service        | `services/user-service`      | User profiles, syncs from Keycloak  |
| task-service        | `services/task-service`      | CRUD for tasks, owned by users      |
| notification        | `cloud-functions/notification` | Sends notifications on task events |
| frontend            | `frontend`                   | Angular SPA                         |
| infrastructure      | `infrastructure/terraform`   | GCP infra provisioning              |

## Getting Started

See `docs/TICKETS.md` for the ordered list of tickets to implement.

## Developer Setup

### 1. Prerequisites

- Docker (for Postgres + Keycloak)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) or Poetry
- Node 20+ / npm
- Terraform ≥ 1.6 (only if touching infra)
- `gcloud` CLI (only for deploying to GCP)

### 2. Clone and recreate the gitignored configs

The repo intentionally ships *without* secrets/local configs. After cloning:

```bash
git clone https://github.com/kmaznitsyn/task-manager-system.git
cd task-manager-system

# Per-service .env files — service config (DB URL, Keycloak issuer/JWKS, ports).
# There is no .env.example yet; ask the team or copy from a teammate.
touch services/user-service/.env
touch services/task-service/.env

# Terraform variables (only if touching infra)
cp infrastructure/terraform/terraform.tfvars.example \
   infrastructure/terraform/terraform.tfvars
# then fill in real values
```

> **TODO:** commit `services/user-service/.env.example` and `services/task-service/.env.example` listing required keys (`DATABASE_URL`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, etc.) so new devs aren't guessing.

### 3. Start local infrastructure

```bash
docker compose up -d
```

This brings up:
- **Postgres** on `:5432` with three DBs auto-created (`users_db`, `tasks_db`, `keycloak_db`) via `scripts/init-multiple-dbs.sh`.
- **Keycloak** on `:8080` (admin/admin). You'll need to import or create the `taskmanager` realm + `taskmanager-api` client.

### 4. Install deps and run migrations (per service)

```bash
# user-service
cd services/user-service
uv sync                      # or: poetry install
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# task-service (new terminal)
cd services/task-service
uv sync
alembic upgrade head
uvicorn app.main:app --reload --port 8002
```

Each service owns its own DB, its own Alembic history, and its own `pyproject.toml`. They share the local `packages/auth` package via a relative path — no install step needed; edits there are picked up live.

### 5. Frontend

```bash
cd frontend/taskmanager-ui
npm install
npm start                    # ng serve on :4200
```

### 6. Notification Cloud Function (local)

It's a plain Pub/Sub handler. Locally there's no Pub/Sub — `task-service` only logs publish attempts unless `PUBSUB_EMULATOR_HOST` is set or `PUBSUB_ENABLED=1`. So for everyday dev you can ignore the function.

If you want to exercise it: run `pip install -r cloud-functions/notification/requirements.txt && functions-framework --target=handle_task_event` and point the emulator at it.

### 7. Tests

```bash
cd services/user-service && pytest                # unit (SQLite, no Docker)
cd services/user-service && pytest -m integration # spins testcontainers Postgres
cd services/task-service && pytest
cd frontend/taskmanager-ui && npm test
```

### 8. Cloud / Terraform

You do **not** need GCP access to run locally — everything above works on Docker alone.

To deploy or change infra:

1. Get `gcloud auth application-default login` set up.
2. Get added to the GCP project (`still-function-494322-d7`) with at least the roles Terraform needs.
3. Get the real `terraform.tfvars` values (DB URLs, Keycloak issuer for the *deployed* Keycloak, SendGrid sender, etc.) from a teammate or a secret store — **not** the placeholder `example.com` values currently in `.example`.
4. `cd infrastructure/terraform && terraform init && terraform plan` — read the plan, then `apply`.

The Terraform backend is GCS (`still-function-494322-d7-tfstate`), so state is shared — running `apply` will affect what everyone else sees. Always `plan` first, and never apply against `dev` without telling the team.

### 9. Secrets — what's where

| Kind | Where it lives | Committed? |
|---|---|---|
| Service env (DB URL, Keycloak URLs) | `services/*/.env` | No |
| Terraform values | `infrastructure/terraform/terraform.tfvars` | No |
| SendGrid API key, Keycloak admin client secret | **Should be** GCP Secret Manager (not yet wired — see TODO in `modules/notification_function/main.tf`) | N/A |
| Keycloak realm export | Currently undocumented | — |

Anything ending in `.env` or `.tfvars` is local-only; expect to receive those out-of-band from the team. Real production secrets belong in Secret Manager.
