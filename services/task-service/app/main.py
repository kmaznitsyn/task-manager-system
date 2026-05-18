import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import publisher
from app.config import settings
from app.database import get_db
from app.models import Task, TaskStatus
from app.schemas import TaskCreate, TaskEvent, TaskRead, TaskUpdate
from cf_auth import get_current_user

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


def _owned_task_or_404(db: Session, task_id: uuid.UUID, owner_sub: str) -> Task:
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.owner_sub == owner_sub)
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
    task = Task(owner_sub=claims["sub"], **body.model_dump())
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
    for field, value in changes.items():
        setattr(task, field, value)
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
    db.delete(task)
    db.commit()
