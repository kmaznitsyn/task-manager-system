import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import publisher
from app.config import settings
from app.database import get_db
from app.models import Label, Task, TaskStatus
from app.schemas import LabelRead, TaskCreate, TaskEvent, TaskRead, TaskUpdate
from cf_auth import get_current_user
from sqlalchemy.sql.functions import now

logger = logging.getLogger(__name__)


def _publish_safe(event: TaskEvent) -> None:
    """Best-effort publish — must never let a Pub/Sub failure roll back the DB."""
    try:
        publisher.publish_task_event(event)
    except Exception:  # noqa: BLE001  — intentionally broad; log everything
        logger.exception(
            "failed to publish %s for task %s — DB state stands",
            event.type,
            event.task_id,
        )

app = FastAPI(title="Task Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "task-service"}


@app.get("/labels", response_model=list[LabelRead])
def list_labels(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The caller's existing labels, alphabetised — used to power autocomplete
    on the task form."""
    stmt = (
        select(Label).where(Label.owner_sub == claims["sub"]).order_by(Label.name)
    )
    return list(db.scalars(stmt))


def _resolve_labels(db: Session, owner_sub: str, names: list[str]) -> list[Label]:
    """Map a list of label *names* to this owner's Label rows, creating any
    that don't exist yet. Names are trimmed and de-duplicated (case-insensitive)
    so the same label can't be attached twice."""
    resolved: list[Label] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        label = db.scalar(
            select(Label).where(Label.owner_sub == owner_sub, Label.name == name)
        )
        if label is None:
            label = Label(owner_sub=owner_sub, name=name)
            db.add(label)
        resolved.append(label)
    return resolved


def _owned_task_or_404(db: Session, task_id: uuid.UUID, owner_sub: str) -> Task:
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.owner_sub == owner_sub, Task.deleted_at.is_(None))
    )
    if task is None:
        # 404 (not 403) — don't leak existence of other users' tasks.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(Task)
        .where(Task.owner_sub == claims["sub"])
        .order_by(Task.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_ is not None:
        stmt = stmt.where(Task.status == status_)
    return list(db.scalars(stmt))


@app.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = body.model_dump(exclude={"labels"})
    task = Task(owner_sub=claims["sub"], **data)
    task.labels = _resolve_labels(db, claims["sub"], body.labels)
    db.add(task)
    db.commit()
    db.refresh(task)

    _publish_safe(
        TaskEvent(
            type="task.created",
            task_id=str(task.id),
            owner_sub=task.owner_sub,
        )
    )
    return task


@app.get("/tasks/deleted", response_model=list[TaskRead])
def list_deleted_tasks(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(Task)
        .where(Task.owner_sub == claims["sub"], Task.deleted_at.isnot(None))
        .execution_options(include_deleted=True)
        .order_by(Task.deleted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _owned_task_or_404(db, task_id, claims["sub"])


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _owned_task_or_404(db, task_id, claims["sub"])
    previous_status = task.status

    changes = body.model_dump(exclude_unset=True)
    label_names = changes.pop("labels", None)
    for field, value in changes.items():
        setattr(task, field, value)
    if label_names is not None:
        task.labels = _resolve_labels(db, claims["sub"], label_names)
    db.commit()
    db.refresh(task)

    if (
        task.status == TaskStatus.done
        and previous_status != TaskStatus.done
    ):
        _publish_safe(
            TaskEvent(
                type="task.completed",
                task_id=str(task.id),
                owner_sub=task.owner_sub,
            )
        )
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _owned_task_or_404(db, task_id, claims["sub"])
    task.deleted_at = now()
    db.commit()


@app.post("/tasks/{task_id}/restore", response_model=TaskRead)
def restore_task(
  task_id: uuid.UUID,
  claims: dict = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  task = db.scalar(
      select(Task)
      .where(Task.id == task_id, Task.owner_sub == claims["sub"])
      .execution_options(include_deleted=True)
  )
  if task is None:
      # 404 (not 403) — same existence-hiding policy as _owned_task_or_404
      raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
  if task.deleted_at is None:
      raise HTTPException(status.HTTP_409_CONFLICT, "Task is not deleted")
  task.deleted_at = None
  db.commit()
  db.refresh(task)
  return task