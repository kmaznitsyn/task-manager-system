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

Quick local dev:

```bash
docker compose up -d     # Keycloak + Postgres
cd services/user-service && uvicorn app.main:app --reload --port 8001
cd services/task-service && uvicorn app.main:app --reload --port 8002
cd frontend && npm start
```
