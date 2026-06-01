import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskStatus

_HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=_HEX_COLOR)


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=_HEX_COLOR)


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_sub: str
    name: str
    color: str | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus = TaskStatus.todo
    due_date: date | None = None
    labels: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    labels: list[str] | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_sub: str
    title: str
    description: str | None
    status: TaskStatus
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    labels: list[LabelRead] = []


class TaskEvent(BaseModel):
    type: Literal["task.created", "task.completed"]
    task_id: str
    owner_sub: str
