# Active Development Backlog — TaskManager

Follow-up work after the initial scaffold (see `INITIAL-TICKETS.md`).
Focus: **backend hardening + product features**, frontend polish, and the
slice of CI/CD / infra / Keycloak that the backend work actually depends on.

Prefix: **TM-** (continues numbering from `INITIAL-TICKETS.md`)

Conventions
- Every ticket fits in a single PR.
- AC are testable. If you can't write a test for it, the AC is wrong.
- "Backend" tickets must keep the invariants from `CLAUDE.md`:
  - `_owned_task_or_404` returns **404**, never 403.
  - `_publish_safe` never fails the HTTP response on Pub/Sub errors.
  - `cf-auth` is the single source of truth — no per-service JWT code.

---

## Epic A — Task Service: feature breadth

### TM-28 · Soft-delete + restore for tasks
**Type:** Feature · **Estimate:** 5h
**Description**
Today `DELETE /tasks/{id}` hard-deletes. Replace with soft-delete to support undo and accidental-delete recovery.
- Add nullable `deleted_at TIMESTAMPTZ` column + partial index `WHERE deleted_at IS NULL`.
- All read queries filter `deleted_at IS NULL` by default.
- New endpoint `POST /tasks/{id}/restore` (404 if not owned, 409 if not deleted).
- New query param `GET /tasks?include_deleted=true` (owner only).
- Soft-deleted tasks remain owned by `owner_sub`; ownership rules unchanged.
**Acceptance criteria**
- [x] Alembic migration up/down clean
- [x] DELETE returns 204 and the task no longer appears in `GET /tasks`
- [x] Restore returns 200 + the task reappears
- [x] Cross-user restore returns 404 (consistency with read rules)
- [x] Unit tests cover all four paths

---

### TM-29 · Task labels (many-to-many tagging)
**Type:** Feature · **Estimate:** 8h
**Description**
Users group tasks by free-form labels (`#work`, `#urgent`). Per-owner namespace — two users can both have a label called `work` without collision.
- Tables: `labels (id, owner_sub, name, color, created_at)` with unique `(owner_sub, lower(name))`; `task_labels (task_id, label_id)` PK both.
- Endpoints: `GET/POST/DELETE /labels`, `PUT /tasks/{id}/labels` (replace set).
- `GET /tasks?label=work&label=urgent` filters tasks that have **all** given labels.
- `TaskRead` includes `labels: list[LabelRead]`.
**Acceptance criteria**
- [ ] Creating a label that already exists for the same user → 409
- [ ] Other users' labels are invisible (404 on direct GET)
- [ ] Deleting a label removes the join rows but not the tasks
- [ ] Tests cover the AND-filter semantics

---

### TM-30 · Task search + advanced filters
**Type:** Feature · **Estimate:** 6h
**Depends on:** TM-29
Today `GET /tasks` only paginates. Add:
- `?q=<text>` — case-insensitive `ILIKE` on `title` and `description`.
- `?status=todo,doing` — comma-separated multi-status.
- `?due_before=YYYY-MM-DD`, `?due_after=YYYY-MM-DD`.
- `?sort=due_date|created_at|title`, `?order=asc|desc`.
- Response envelope: `{items, total, limit, offset}` — currently the list is bare; introduce this gently with a feature flag header (`X-API-Envelope: 1`) to avoid breaking the frontend until TM-41.
**Acceptance criteria**
- [ ] Each filter has its own test
- [ ] SQL EXPLAIN shows index usage (add a GIN/`pg_trgm` index on title in the same migration)
- [ ] Frontend keeps working without the envelope header

---

### TM-31 · Bulk task operations
**Type:** Feature · **Estimate:** 4h
`POST /tasks/bulk` with body `{action: "complete"|"delete"|"set_status", ids: [uuid], status?: "done"}`.
- Ownership filter applied per-id; non-owned ids are silently ignored (consistent with the 404 rule — don't leak existence).
- Returns `{updated: int, ignored: int}`.
- For `complete`, publishes one `task.completed` per affected row (still through `_publish_safe`).
**Acceptance criteria**
- [ ] Atomic in a single transaction
- [ ] Mixed owner/non-owner ids → only owned rows touched
- [ ] Test asserts the publisher spy received the right number of events

---

### TM-32 · Task activity log (audit trail)
**Type:** Feature · **Estimate:** 6h
Append-only `task_events (id, task_id, actor_sub, kind, payload_jsonb, at)` capturing create / update (with diff) / status change / restore / delete.
- New endpoint `GET /tasks/{id}/activity` (owner only).
- Writes happen in the same DB transaction as the change — losing the audit row should fail the request.
- Pub/Sub publishing remains separate (out-of-tx, `_publish_safe`).
**Acceptance criteria**
- [ ] Update produces a diff payload (only changed fields)
- [ ] Activity is ordered newest-first, paginated
- [ ] Failing the audit insert rolls back the task change (verify with a forced exception in a test)

---

## Epic B — Cross-cutting backend hardening

### TM-33 · Structured request logging + correlation IDs
**Type:** Feature · **Estimate:** 4h
- Middleware reads `X-Request-ID`; if absent, generate UUID4. Echo it on the response.
- All log lines emitted within the request carry `request_id`, `user_sub` (if authenticated), `route`, `status`, `duration_ms`.
- JSON formatter (`python-json-logger`) in non-dev environments; pretty in local.
- Apply in **both** services and in the notification Cloud Function (propagate `request_id` from Pub/Sub attributes).
**Acceptance criteria**
- [ ] A request with a custom `X-Request-ID` appears with that id in logs end-to-end (service → Pub/Sub → function)
- [ ] No log line in prod mode is non-JSON
- [ ] Tests assert the middleware sets `request.state.request_id`

---

### TM-34 · Standardized error envelope (RFC 7807 Problem+JSON)
**Type:** Feature · **Estimate:** 4h
Today errors are FastAPI defaults (`{"detail": "..."}`). Move to `application/problem+json`:
```json
{ "type": "https://errors.taskmanager/validation", "title": "Validation failed",
  "status": 422, "detail": "...", "instance": "/tasks", "errors": [...] }
```
- Global exception handler for `HTTPException` and `RequestValidationError`.
- `instance` is the request path; never echo raw user input.
- Update `cf-auth` to raise the same shape on 401.
**Acceptance criteria**
- [ ] Existing tests updated; new test for every status code we emit
- [ ] OpenAPI schema documents the error shape
- [ ] Frontend interceptor (TM-44) keys off `type`, not free-text

---

### TM-35 · Per-user rate limiting on write endpoints
**Type:** Feature · **Estimate:** 5h
Protect against accidental hot loops from the SPA and abuse. Token bucket keyed by `sub`.
- 60 writes/min default; configurable per env via `RATE_LIMIT_WRITES_PER_MIN`.
- 429 with `Retry-After` header and the problem+json envelope.
- Storage: in-process (`cachetools`) for now; note "Redis swap when we scale horizontally" as a follow-up.
- Applies to POST/PUT/PATCH/DELETE; reads unaffected.
**Acceptance criteria**
- [ ] Synthetic test trips the limit and recovers after the window
- [ ] `GET` requests are never throttled
- [ ] Anonymous (no auth) → still 401, never 429 (auth check runs first)

---

### TM-36 · Pub/Sub dead-letter queue + retry policy
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-11
Notification function currently re-raises on infra failure (relies on subscription retry) but there is no DLQ. Add one in Terraform + harden the consumer.
- `tasks-events-dlq` topic; subscription `max_delivery_attempts=5`, backoff 10s→600s.
- Function: structured log on every retry attempt (`delivery_attempt` from message metadata).
- Add a malformed-payload test (asserts ack-and-drop, never DLQ).
**Acceptance criteria**
- [ ] Forcing a permanent failure in a local emulator pushes the message to the DLQ after 5 tries
- [ ] Malformed payload is logged at WARN and acked
- [ ] Runbook entry in `docs/runbooks/pubsub-dlq.md` for draining the DLQ

---

### TM-37 · API versioning (`/api/v1`)
**Type:** Refactor · **Estimate:** 5h
All current routes are unversioned. Move to `/api/v1/...` to unblock future breaking changes without a giant migration later.
- Both services mount the existing router at `/api/v1`.
- Keep unversioned routes for 1 release with `Deprecation` + `Sunset` headers.
- Update frontend env (TM-41 will use the new path).
- OpenAPI `servers` block lists `/api/v1` as the canonical base.
**Acceptance criteria**
- [ ] Both routes return identical responses during the deprecation window
- [ ] An e2e smoke test hits `/api/v1/tasks`
- [ ] Deprecation header shows up on every legacy response

---

### TM-38 · GDPR — `DELETE /me` account deletion
**Type:** Feature · **Estimate:** 6h
User-initiated account deletion. Hard delete from `user-service` + cascade tasks via owner_sub.
- `DELETE /me` on user-service: deletes the row, publishes `user.deleted` event (`{sub}`).
- `task-service` subscribes (new subscription on `tasks-events` is wrong — make a separate topic `user-events`) and hard-deletes all tasks for that sub.
- Soft-deleted tasks are also purged.
- Activity log rows for deleted tasks are dropped (no orphan PII).
**Acceptance criteria**
- [ ] User row gone; tasks gone; activity rows gone — verified by integration test
- [ ] Idempotent: replaying the event doesn't error
- [ ] Documented in `docs/data-retention.md`

---

### TM-39 · Index audit + N+1 review for `/tasks`
**Type:** Chore · **Estimate:** 4h
`GET /tasks` with labels (TM-29) and filters (TM-30) is the hot read path.
- Add composite index `(owner_sub, deleted_at, status, due_date)` informed by EXPLAIN on a 10k-row seed.
- Replace the labels-per-task fetch loop with a single `selectinload` (or one-query CTE).
- Add a `pytest --benchmark` test with the seed; record baseline in `docs/perf-baseline.md`.
**Acceptance criteria**
- [ ] `EXPLAIN ANALYZE` of the worst filter combination uses index, no Seq Scan
- [ ] Query count for a 50-task list ≤ 2 (assert with `sqlalchemy.event`)

---

## Epic C — Frontend

### TM-40 · Task detail route + edit/delete
**Type:** Feature · **Estimate:** 5h
**Depends on:** TM-14
Route `/tasks/:id`. Reuses the form from TM-15 in edit mode. Delete with confirm dialog → uses TM-28 soft-delete; toast offers "Undo" that calls `/restore`.
**Acceptance criteria**
- [ ] Deep link `/tasks/<uuid>` works after a hard refresh (SPA rewrite from TM-27)
- [ ] 404 from the API → "Task not found" empty state (don't crash the route)

---

### TM-41 · Task list filters + search UI
**Type:** Feature · **Estimate:** 6h
**Depends on:** TM-30
Filter bar above the list: search box, status multi-select chips, due-date range picker, label filter (TM-42), sort dropdown.
- State synced to query params (`/tasks?q=...&status=todo,doing`) so filters are shareable and survive reload.
- Debounce search input by 300ms.
- Loading state for the list while filters change; never blank-flash.
**Acceptance criteria**
- [ ] Browser back/forward replays filter state
- [ ] Clearing all filters resets to default and removes query params
- [ ] Component tests for query-param sync

---

### TM-42 · Labels management UI
**Type:** Feature · **Estimate:** 5h
**Depends on:** TM-29
- `/labels` settings page: list, create (name + color picker), rename, delete.
- Inline label chip selector on the task form (TM-15) and task detail (TM-40).
- Optimistic add/remove with rollback on 4xx.
**Acceptance criteria**
- [ ] Deleting a label that's attached to N tasks asks for confirmation that mentions N
- [ ] Color contrast on chips meets WCAG AA (test with a known palette)

---

### TM-43 · Profile page
**Type:** Feature · **Estimate:** 3h
**Depends on:** TM-7
Route `/profile`. Shows email (read-only, from Keycloak), display name (editable, calls `PATCH /me`), account-created date.
- "Delete my account" button at the bottom — gated behind a typed-confirmation modal — calls TM-38.
**Acceptance criteria**
- [ ] PATCH success shows a toast and updates the header username without reload
- [ ] Account deletion logs the user out and lands on the Keycloak login page

---

### TM-44 · Global error/toast system + HTTP interceptor
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-34
- Snackbar service (Angular Material or roll a small component).
- HTTP interceptor maps RFC 7807 errors to toasts (`title` + `detail`), with i18n hooks for known `type` URIs.
- 401 → silent re-auth via Keycloak (already handled by `keycloak-angular`); never toast.
- 429 → toast "Slow down — try again in N seconds" (read `Retry-After`).
**Acceptance criteria**
- [ ] Unit test for the interceptor mapping each status code
- [ ] No two toasts stack for the same `request_id`

---

### TM-45 · Skeleton loaders + empty/error states
**Type:** Polish · **Estimate:** 3h
Replace spinners on `/tasks`, `/tasks/:id`, `/labels`, `/profile` with skeleton placeholders. Add proper empty states ("No tasks yet — create one") and error states with a Retry button (calls the same observable).
**Acceptance criteria**
- [ ] No layout shift between skeleton and loaded state (same heights)
- [ ] Slow-3G throttled test in DevTools shows skeletons within 100ms

---

### TM-46 · Frontend bundle + lazy routes
**Type:** Performance · **Estimate:** 3h
Audit `npm run build --configuration=production`. Lazy-load `/labels` and `/profile`. Target initial JS < 250 KB gzipped.
**Acceptance criteria**
- [ ] `source-map-explorer` report committed to `docs/perf-baseline.md`
- [ ] Lighthouse Performance ≥ 90 on a cold load against the prod build

---

## Epic D — CI/CD, Infra, Keycloak (focused slice)

### TM-47 · GitHub Actions: per-service path-filtered pipelines
**Type:** DevOps · **Estimate:** 5h
**Depends on:** TM-21
Current pipeline (when built in TM-21) runs everything for every PR. Split into reusable workflows per service with `paths:` filters so touching the frontend doesn't run Python tests and vice-versa.
- `.github/workflows/ci-user-service.yml`, `ci-task-service.yml`, `ci-notification.yml`, `ci-frontend.yml`, `ci-terraform.yml`.
- Shared composite action for "setup Python + uv + cache".
- Concurrency group per branch+workflow cancels superseded runs.
**Acceptance criteria**
- [ ] PR that only edits `frontend/` triggers exactly one workflow
- [ ] PR that edits `packages/auth/` triggers both service workflows (shared dep)
- [ ] Workflow duration on a no-op PR < 60s

---

### TM-48 · Multi-environment Terraform (Dev / Test / Prod)
**Type:** Infrastructure · **Estimate:** 8h
**Depends on:** TM-16
Today there's one root `main.tf`. Restructure for env separation per the JD's "clean Dev/Test/Prod separation".
- `infrastructure/terraform/environments/{dev,test,prod}/` each with its own backend bucket prefix + `terraform.tfvars`.
- Shared modules unchanged; envs are thin compositions.
- Prod has stricter values: `deletion_protection=true` on Cloud SQL, no public IP, min-instances ≥ 1 for Cloud Run.
- CI: `terraform plan` runs against the env matching the PR's target branch (`develop` → dev, `main` → prod).
**Acceptance criteria**
- [ ] `terraform apply` in dev does not touch prod state (proven with `terraform state list`)
- [ ] Documented promotion flow in `docs/runbooks/promote-to-prod.md`
- [ ] At least one resource has env-specific config (e.g., Cloud SQL tier)

---

### TM-49 · Secret Manager for service config
**Type:** Security · **Estimate:** 4h
**Depends on:** TM-48
Move DB passwords and Keycloak client secrets out of `.env` / `terraform.tfvars` into GCP Secret Manager.
- Terraform creates `google_secret_manager_secret` per secret per env.
- Cloud Run services receive them as env vars via `value_source.secret_key_ref`.
- Local dev still reads `.env` (Pydantic settings) — no code change in `app/config.py`.
**Acceptance criteria**
- [ ] No plaintext secret in any tfvars file under version control
- [ ] Service starts in Cloud Run with secrets resolved (verified via `gcloud run services describe`)
- [ ] `pre-commit` hook (gitleaks or detect-secrets) catches new plaintext secrets

---

### TM-50 · Keycloak role-based authorization (admin vs user)
**Type:** Security · **Estimate:** 6h
**Depends on:** TM-4
Today every authenticated user can hit every endpoint. Introduce roles for future admin features (e.g., bulk export of all tasks for support).
- Realm roles: `task-user` (default), `task-admin`.
- `cf-auth` exposes `require_role("task-admin")` dependency.
- Add one admin-only endpoint as proof: `GET /admin/users` on user-service (returns paginated user list).
- Token role check uses `realm_access.roles`; 403 (not 404) is acceptable here because the endpoint's existence isn't sensitive.
**Acceptance criteria**
- [ ] User without role → 403 with problem+json
- [ ] Realm export updated with both roles + a test admin user
- [ ] Tests cover both allow and deny paths

---

## Epic E — Logistics documents (docs-service)

`services/docs-service` + frontend `/documents` were scaffolded with the minimum
necessary slice: per-owner CRUD, a deterministic regex-based extraction stub
(`app/processing.py`), and Pub/Sub on `documents-events`. These tickets harden
and extend that slice. Same invariants as the other services apply:
- `_owned_document_or_404` returns **404**, never 403.
- `_publish_safe` never fails the HTTP response on Pub/Sub errors.
- `cf-auth` is still the single source of truth for JWT validation.

---

### TM-59 · docs-service: integration tests on real Postgres
**Type:** Chore · **Estimate:** 3h
The service is unit-tested against SQLite only — the `JSONB` column for `extracted`
falls back to `JSON` and the native enums to `VARCHAR`, so the SQLite test path
does not exercise the actual production schema.
- Add a `-m integration` tier mirroring `user-service`: testcontainers Postgres,
  Alembic `upgrade head`, real `JSONB` round-trip on `extracted`.
- Cover the doc_type enum and the `failed → processed` re-run path against Postgres.
**Acceptance criteria**
- [ ] `pytest -m integration` green against a containerised Postgres
- [ ] One assertion that `extracted` is queryable via a `JSONB` operator (`->>`)
- [ ] Migration up/down clean (verify with `alembic downgrade -1 && upgrade head`)

---

### TM-60 · Async background processing
**Type:** Feature · **Estimate:** 6h
**Depends on:** TM-59
Today `POST /documents/{id}/process` blocks the request thread while the (cheap)
extractor runs. A real OCR/LLM pipeline can take seconds — make processing async
without changing the public API surface.
- `POST /documents` → row in `received`. **Background worker** (FastAPI
  `BackgroundTasks` for the first step; pluggable Cloud Tasks/Pub/Sub-driven worker
  for prod) picks it up, flips to `processing`, runs extraction, lands in
  `processed` / `failed`.
- Keep `POST /documents/{id}/process` as a manual re-trigger (idempotent: 409 if
  already `processed`, allowed from `failed` or `received`).
- Add `?status=processing` filter to `GET /documents` for the UI to poll.
**Acceptance criteria**
- [ ] Creating a document returns 201 immediately, never blocks on extraction
- [ ] A test inserts a `received` doc, runs the worker tick, asserts terminal status
- [ ] Status transitions are documented in `docs-service/README.md`

---

### TM-61 · Pluggable extractor backend (OCR / LLM)
**Type:** Feature · **Estimate:** 8h
**Depends on:** TM-60
`app/processing.py` is a deterministic regex stub on purpose. Lift it behind an
interface so it can be swapped for a real extractor.
- `Extractor` protocol: `extract(doc_type, raw_text | raw_bytes) -> dict`.
- Two implementations shipped: `RegexExtractor` (current behaviour, default in dev
  and tests) and `VertexAIExtractor` (uses Vertex AI / Document AI, gated by
  `EXTRACTOR_BACKEND=vertex`).
- Add a `mime_type` column + `raw_bytes` storage (GCS reference, not blob in
  Postgres) for binary uploads — `raw_text` stays for paste-in flow.
- No-op for SQLite tests: backend defaults to `regex`.
**Acceptance criteria**
- [ ] Switching `EXTRACTOR_BACKEND` does not require code changes outside `processing/`
- [ ] Existing tests still green with `regex` default
- [ ] Vertex backend behind a feature flag; not exercised in CI

---

### TM-62 · `notification` Cloud Function subscribes to `documents-events`
**Type:** Feature · **Estimate:** 3h
**Depends on:** TM-36
`docs-service` publishes `document.processed` / `document.failed` but nothing
consumes them. Reuse the existing notification function so the user gets the same
email/in-app channel as for tasks.
- Add a second Pub/Sub trigger in Terraform: subscription on `documents-events`
  → same Cloud Function entry point with a `kind=document` discriminator.
- Function distinguishes payload shape by `type` (already `document.*` vs `task.*`).
- Malformed payloads: ack-and-drop (same policy as today). Real failures: re-raise
  for retry. Don't change the retry/DLQ contract.
**Acceptance criteria**
- [ ] Local emulator: publishing `document.processed` invokes the function with
      a `document_id` in the payload
- [ ] Function tests cover both event families
- [ ] DLQ (TM-36) catches a malformed `document.*` event after 5 tries

---

### TM-63 · Frontend: document detail route + re-process / extracted view
**Type:** Feature · **Estimate:** 4h
**Depends on:** TM-60
Today `/documents` is one list view; the extracted fields are shown inline in
each row's card, which is OK for two or three documents but cramped at scale.
- Route `/documents/:id`: full extracted fields, raw text (collapsed), audit
  metadata, status timeline.
- Re-process button calls `POST /documents/{id}/process`; UI optimistically flips
  status to `processing` and polls via `?status=processing` until terminal.
- Delete moves to a confirmation modal (matches the `confirm()` removal in TM-40).
**Acceptance criteria**
- [ ] Deep link `/documents/<uuid>` works after a hard refresh
- [ ] 404 from API → empty-state "Document not found", route does not crash
- [ ] Polling stops as soon as status is `processed` or `failed`

---

### TM-64 · File upload (PDF / image) instead of paste-in `raw_text`
**Type:** Feature · **Estimate:** 6h
**Depends on:** TM-61
Real users have PDFs and scans, not pre-OCR'd text. Add binary upload.
- Frontend: `<input type="file">` on the create form, drag-and-drop zone.
  Multipart POST to `/documents` with `file` field + JSON metadata.
- Backend: upload goes to a GCS bucket per env (`docs-uploads-<env>`), DB stores
  the GCS URI in a new `source_uri` column.
- `RegexExtractor` keeps reading `raw_text`; `VertexAIExtractor` (TM-61) reads
  bytes from GCS.
- Size limit 10 MB enforced at the API gateway; problem+json (TM-34) on overflow.
**Acceptance criteria**
- [ ] Uploading a PDF returns 201 with `source_uri` set, `raw_text` empty
- [ ] Bucket has a 30-day lifecycle rule (defined in Terraform)
- [ ] Tests cover happy path + oversize rejection

---

## Backlog / Nice-to-have (post-MVP)

- **TM-51** OpenTelemetry tracing across services + Cloud Trace export
- **TM-52** Load test with `k6` against staging; publish baseline + alert thresholds
- **TM-53** Cloud Monitoring dashboards + alerting policies (latency p95, error rate, DLQ depth)
- **TM-54** Playwright e2e suite running in CI against an ephemeral env
- **TM-55** Cloud SQL PITR + automated restore drill (quarterly runbook)
- **TM-56** i18n (de/en) on the frontend
- **TM-57** Dark mode + system-preference detection
- **TM-58** Replace in-process rate limit (TM-35) with Redis/Memorystore when scaling out

---

## Suggested order

Sprint 1 (backend foundations): TM-33, TM-34, TM-37 → unlocks everything else
Sprint 2 (features): TM-28, TM-29, TM-30, TM-32
Sprint 3 (frontend catch-up): TM-40, TM-41, TM-42, TM-44
Sprint 4 (hardening + ops): TM-35, TM-36, TM-39, TM-47
Sprint 5 (env separation): TM-48, TM-49, TM-50
Sprint 6 (docs-service): TM-59, TM-60, TM-62, TM-63 (TM-61 + TM-64 follow once a real extractor is selected)
