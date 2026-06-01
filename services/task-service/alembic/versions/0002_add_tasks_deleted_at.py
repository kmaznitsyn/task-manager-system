"""add deleted_at to tasks

Revision ID: 0002_add_tasks_deleted_at
Revises: 0001_create_tasks
Create Date: 2026-05-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_tasks_deleted_at"
down_revision: Union[str, None] = "0001_create_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_deleted_at", table_name="tasks")
    op.drop_column("tasks", "deleted_at")
