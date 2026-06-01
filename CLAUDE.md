# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Monorepo for a "Task Manager" scaffold. Each top-level dir is an independent deployable / installable:

- `services/user-service`, `services/task-service`, `services/docs-service` — FastAPI apps (Python 3.13+), deployed to Cloud Run, each with its own Postgres DB, `pyproject.toml`, `alembic.ini`, and `alembic/versions`. `docs-service` handles logistics documents (Bill of Lading, manifest, proof of delivery, invoice, customs declaration) with a synchronous extraction pipeline.
- `packages/auth` — local editable package `cf-auth`. All three services depend on it via `tool.uv.sources` / `tool.poetry.dependencies` with a relative path. Edits here are picked up immediately by the services.
- `cloud-functions/notification` — GCP Cloud Function (functions-framework) triggered by Pub/Sub events from `task-service`. Has its own `requirements.txt` (not Poetry).
- `frontend/taskmanager-ui` — Angular 18 SPA using `keycloak-angular` for OIDC.
- `infrastructure/terraform` — GCP infra (modules + root `main.tf`).
- `docker-compose.yml` + `scripts/init-multiple-dbs.sh` — local Postgres (creates `users_db`, `tasks_db`, `docs_db`, `keycloak_db` in one container) and Keycloak.
- Root `pyproject.toml` / `poetry.lock` exist but are not the build unit — each service has its own. Treat root pyproject as legacy; work inside the service directory you are changing.

## Common commands

Local infra (must be running for the services to start against real Postgres/Keycloak):
```bash
docker compose up -d        # Postgres (multi-DB) + Keycloak on :8080
```

Run a service (from its directory — `app.main:app` import path assumes cwd is the service root):
```bash
cd services/user-service && uvicorn app.main:app --reload --port 8001
cd services/task-service && uvicorn app.main:app --reload --port 8002
cd services/docs-service && uvicorn app.main:app --reload --port 8003
```

Migrations are **per-service** (each service owns its schema and DB):
```bash
cd services/<svc> && alembic upgrade head
cd services/<svc> && alembic revision --autogenerate -m "message"
```

Tests:
```bash
cd services/user-service && pytest                # unit (SQLite)
cd services/user-service && pytest -m integration # spins up Postgres via testcontainers (needs Docker)
cd services/task-service && pytest
cd services/docs-service && pytest
cd cloud-functions/notification && pytest
pytest path/to/test_file.py::test_name           # single test
```

Frontend:
```bash
cd frontend/taskmanager-ui && npm start   # ng serve on :4200
cd frontend/taskmanager-ui && npm test    # karma + jasmine
cd frontend/taskmanager-ui && npm run build
```

## Architecture notes that span files

**Auth flow.** The Angular app obtains a JWT from Keycloak (`taskmanager` realm, audience `taskmanager-api`) and sends it as a bearer token. Both services validate it through the same dependency: `cf_auth.get_current_user` (in `packages/auth/src/cf_auth/deps.py`). It fetches JWKS from the Keycloak URL, caches keys (`cachetools`), and validates `iss` + `aud`. All protected endpoints inject `claims: dict = Depends(get_current_user)`; user identity is `claims["sub"]` (the Keycloak `sub`). When changing auth behavior, edit the shared package — do not duplicate per service.

**Identity model.** `user-service` does **not** own credentials. On first call to `/me`, `get_or_create_from_claims` upserts a row keyed by `keycloak_sub` (Postgres `INSERT ... ON CONFLICT DO NOTHING`, then sync email/display_name from the JWT). `task-service` does not call `user-service` for authorization — it stores `owner_sub` directly on each task and filters by it.

**Task ownership / authorization.** `task-service` deliberately returns **404** (not 403) when a caller requests another user's task — see `_owned_task_or_404` in `services/task-service/app/main.py`. Preserve this behavior; the comment explicitly notes it avoids leaking existence. `docs-service` mirrors this with `_owned_document_or_404` in `services/docs-service/app/main.py` — same rule, same reason.

**Document processing (`docs-service`).** `POST /documents` stores the raw text and metadata in status `received`. `POST /documents/{id}/process` runs a synchronous extraction stub (`app/processing.py`) — deterministic regex rules per `DocType`, no OCR/LLM. On success the row moves to `processed` with `extracted` JSON populated; on missing required fields it moves to `failed` with `failure_reason`. The stub is intentionally narrow so it can be swapped for a real extractor later without changing the API or status machine. Re-processing a `processed` document returns 409; `failed` documents can be re-tried.

**Event publishing.** `task-service` publishes `task.created` / `task.completed` to Pub/Sub topic `tasks-events`, consumed by `cloud-functions/notification`. `docs-service` publishes `document.received` / `document.processed` / `document.failed` to topic `documents-events` (no consumer yet — wire one in via TM-62 if needed). Two important properties of each service's `app/publisher.py` + `_publish_safe` in `app/main.py`:
- Publishing is **opt-in locally**: disabled unless `PUBSUB_EMULATOR_HOST` is set or `PUBSUB_ENABLED=1`. Default behavior is a log line, never a network call — so local dev works without GCP credentials.
- A Pub/Sub failure must **never** roll back a DB write. `_publish_safe` catches everything and logs. Keep this invariant in all services.

The notification function inversely re-raises on `keycloak`/`notifier` failures so Pub/Sub retries; it ack-and-drops only on malformed payloads. Don't change error-handling shape without understanding retry semantics.

**Testing strategy.**
- `user-service` has two tiers: unit tests use in-memory SQLite via `conftest.sqlite_session_factory`, which monkey-patches `get_or_create_from_claims` with a portable version because the production code uses a Postgres-specific `ON CONFLICT`. Integration tests (`-m integration`) use testcontainers Postgres and run the real Alembic migrations.
- `task-service` is unit-only against SQLite. An **autouse** fixture `stub_publisher` replaces `publish_task_event` with a spy on every test; opt out with `@pytest.mark.no_stub_publisher` if you need the real code path.
- `docs-service` follows the same pattern: SQLite-only unit tests, autouse `stub_publisher` patching `publish_document_event`, same `_ActingClient` helper for multi-user tests.
- Both services override `cf_auth.get_current_user` via `app.dependency_overrides` to inject synthetic claims — there is no real Keycloak in tests. The `_ActingClient` pattern in `task-service/tests/conftest.py` re-applies the override per request so multi-user tests don't trample each other through the global overrides dict.

**Config.** Each service has its own `app/config.py` (Pydantic `BaseSettings`, `.env` per service). The `cf-auth` package has its own `AuthSettings` reading the same Keycloak env vars (`keycloak_issuer`, `keycloak_audience`, `keycloak_jwks_url`) — keep these names in sync across `packages/auth/src/cf_auth/settings.py` and the service configs.
