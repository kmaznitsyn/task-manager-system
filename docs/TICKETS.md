# Backlog — TaskManager

Ordered by dependency. Each ticket is small enough to fit in a single PR.
Prefix: **TM-**

---

## Epic 1: Local Infra & Auth Setup

### TM-1 · Bring up local infrastructure with Docker Compose
**Type:** Task · **Estimate:** 2h
**Description**
Run `docker compose up -d` and verify Postgres and Keycloak are reachable. Confirm that databases `users_db`, `tasks_db`, and `keycloak_db` exist.
**Acceptance criteria**
- [x] `docker compose ps` shows both services healthy
- [x] `psql` can connect to all three databases
- [x] Keycloak admin console reachable at `http://localhost:8080`

---

### TM-2 · Configure Keycloak realm and clients
**Type:** Task · **Estimate:** 3h
**Description**
Create realm `taskmanager` with:
- Client `taskmanager-web` (public, `Standard flow`, redirect `http://localhost:4200/*`)
- Client `taskmanager-api` (bearer-only / confidential, used as audience)
- One test user with a password
**Acceptance criteria**
- [x] Realm export committed to `keycloak/realm-export.json`
- [x] Can obtain a JWT via the frontend client from a browser
- [x] JWT contains `aud: taskmanager-api` claim

---

### TM-3 · Document environment variables
**Type:** Docs · **Estimate:** 1h
Write `.env.example` for each service. List every env var, its purpose, and default for local dev.

---

## Epic 2: Backend — Shared Auth

### TM-4 · Implement JWT verification middleware
**Type:** Feature · **Estimate:** 5h
**Depends on:** TM-2
**Description**
In `app/auth.py` (both services), replace the `501` stub with real JWKS-based verification:
1. Fetch JWKS from `keycloak_jwks_url`, cache in-memory with TTL
2. Decode with `python-jose`, verify signature, `iss`, `aud`, `exp`
3. Return claims dict from `get_current_user`
**Acceptance criteria**
- [ ] Valid token → 200
- [ ] Expired / wrong-audience / tampered token → 401
- [ ] JWKS cache refreshes on key-id miss
- [ ] Unit tests for each failure mode
**Notes**
The two services have nearly identical code — consider extracting to a shared package later (follow-up TM-22).

---

## Epic 3: User Service

### TM-5 · Define User model + Alembic migration
**Type:** Feature · **Estimate:** 3h
Columns: `id UUID pk`, `keycloak_sub TEXT unique`, `email TEXT`, `display_name TEXT`, `created_at`, `updated_at`.
**Acceptance criteria**
- [x] `alembic upgrade head` runs cleanly against `users_db`
- [x] Rollback works (`alembic downgrade -1`)

---

### TM-6 · Implement `GET /me` and first-login sync
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-4, TM-5
On every authenticated request, upsert the user row from token claims. `GET /me` returns the DB row, not the raw token.
**Acceptance criteria**
- [x] First call creates the row
- [x] Subsequent calls return the same row without duplicates
- [x] Unit + integration test (with testcontainers-postgres or equivalent)

---

### TM-7 · `PATCH /me` to update display name
**Type:** Feature · **Estimate:** 2h
Only the `display_name` field is editable. Email comes from Keycloak only.

---

## Epic 4: Task Service

### TM-8 · Define Task model + Alembic migration
**Type:** Feature · **Estimate:** 2h
Columns: `id UUID pk`, `owner_sub TEXT indexed`, `title TEXT NOT NULL`, `description TEXT`, `status ENUM('todo','doing','done')`, `due_date DATE nullable`, `created_at`, `updated_at`.

---

### TM-9 · CRUD endpoints for tasks
**Type:** Feature · **Estimate:** 6h
**Depends on:** TM-4, TM-8
Implement list / create / get / update / delete. Every query MUST filter by `owner_sub = current_user['sub']` — no cross-user access.
**Acceptance criteria**
- [x] Pydantic schemas: `TaskCreate`, `TaskUpdate`, `TaskRead`
- [x] 404 if task belongs to another user (not 403 — don't leak existence)
- [x] Pagination on list endpoint (`?limit=&offset=`)
- [x] Tests cover happy path + ownership enforcement

---

### TM-10 · Publish task events to Pub/Sub
**Type:** Feature · **Estimate:** 3h
**Depends on:** TM-9
On create and status-change-to-done, publish a message to topic `tasks-events`. In local dev, skip publishing if `PUBSUB_EMULATOR_HOST` isn't set (or just log).
**Acceptance criteria**
- [x] Message schema: `{"type": "task.created"|"task.completed", "task_id": "...", "owner_sub": "..."}`
- [x] Publish failures don't break the HTTP response (fire-and-forget, logged)

---

## Epic 5: Cloud Function — Notification

### TM-11 · Implement notification handler
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-10
For now just log a structured message. Real email is out of scope.
**Acceptance criteria**
- [x] Function runs locally via `functions-framework --target handle_task_event`
- [ ] Decoding handles malformed payloads gracefully (no uncaught exceptions)

---

### TM-12 · Deploy function via gcloud (manual smoke test)
**Type:** Chore · **Estimate:** 2h
Deploy once manually with `gcloud functions deploy` to validate the packaging. Terraform-managed deploy is TM-18.

---

## Epic 6: Frontend

### TM-13 · Bootstrap Angular app + Keycloak integration
**Type:** Feature · **Estimate:** 5h
**Depends on:** TM-2
Use `ng new` (see `frontend/README.md`). Wire up `keycloak-angular` with `APP_INITIALIZER`. Add `KeycloakAuthGuard` and a bearer-token interceptor.
**Acceptance criteria**
- [x] Visiting `/` while logged out redirects to Keycloak
- [x] After login, token appears in `Authorization` header on API calls
- [x] Logout works and clears the session

---

### TM-14 · Task list view
**Type:** Feature · **Estimate:** 5h
**Depends on:** TM-9, TM-13
Route `/tasks`. Table/list showing title, status, due date. Loading + empty states.
**Acceptance criteria**
- [x] Fetches from task-service on load
- [x] 401 triggers re-auth (handled by interceptor)

---

### TM-15 · Task create / edit form
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-14
Reactive form with validation. Inline edit or separate route — your call.

---

## Epic 7: Infrastructure (GCP)

### TM-16 · Create GCP project and Terraform state bucket
**Type:** Chore · **Estimate:** 2h
Create project, enable APIs (Cloud Run, Cloud SQL, Artifact Registry, Pub/Sub, Cloud Functions, Cloud Build). Create GCS bucket for TF state, uncomment the `backend "gcs"` block.

---

### TM-17 · Terraform: VPC connector + Cloud SQL private IP
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-16
Replace public Cloud SQL with a private-IP instance and a Serverless VPC Access connector, so Cloud Run services connect privately.

---

### TM-18 · Terraform: notification Cloud Function + Pub/Sub trigger
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-11, TM-16
Add `google_cloudfunctions2_function` with event trigger from the `tasks-events` topic. Source archive uploaded to a GCS bucket managed by Terraform.

---

### TM-19 · Lock down Cloud Run invocation - Skipped
**Type:** Security · **Estimate:** 3h
Remove `allUsers` invoker. Require authenticated identity — either a signed ID token (service-to-service) or proxy through an API gateway. Document the chosen approach in `docs/security.md`.

---

### TM-20 · Managed Keycloak deployment
**Type:** Feature · **Estimate:** 6h
Decide: Cloud Run + Cloud SQL, or external SaaS (e.g., Phase Two, Red Hat SSO). For a scaffold, Cloud Run is fine — but note the cold-start pain. Document trade-offs before committing.

---

## Epic 8: CI/CD

### TM-21 · GitHub Actions / GitLab CI pipeline
**Type:** DevOps · **Estimate:** 6h
Per service:
- [ ] Lint (ruff) + test on PR
- [ ] Build + push Docker image to Artifact Registry on merge to main
- [ ] `terraform plan` on PR, `terraform apply` on manual trigger

---

## Backlog / Nice-to-have

### TM-22 · Extract shared auth into an internal Python package
### TM-23 · OpenTelemetry instrumentation (you've looked at this before — good candidate)
### TM-24 · Rate limiting on public endpoints
### TM-25 · E2E tests with Playwright
### TM-26 · Observability: structured logging + Cloud Logging sinks

---

## Suggested order

Week 1: TM-1 → TM-4
Week 2: TM-5 → TM-10
Week 3: TM-11, TM-13 → TM-15
Week 4: TM-16 → TM-19
Later: TM-20, TM-21, backlog
