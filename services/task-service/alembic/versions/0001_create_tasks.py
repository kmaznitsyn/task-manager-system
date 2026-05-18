"""create tasks table

Revision ID: 0001_create_tasks
Revises:
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001_create_tasks"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_status = sa.Enum("todo", "doing", "done", name="task_status")


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_sub", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            task_status,
            nullable=False,
            server_default="todo",
        ),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tasks_owner_sub", "tasks", ["owner_sub"])


def downgrade() -> None:
    op.drop_index("ix_tasks_owner_sub", table_name="tasks")
    op.drop_table("tasks")
    sa.Enum(name="task_status").drop(op.get_bind(), checkfirst=True)
