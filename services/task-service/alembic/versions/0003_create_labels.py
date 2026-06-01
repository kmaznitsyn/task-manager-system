"""create labels and task_labels tables

Revision ID: 0003_create_labels
Revises: 0002_add_tasks_deleted_at
Create Date: 2026-05-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003_create_labels"
down_revision: Union[str, None] = "0002_add_tasks_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "labels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_sub", sa.String(64), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
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
        sa.UniqueConstraint("owner_sub", "name", name="uq_labels_owner_sub_name"),
    )
    op.create_index("ix_labels_owner_sub", "labels", ["owner_sub"])

    op.create_table(
        "task_labels",
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "label_id",
            UUID(as_uuid=True),
            sa.ForeignKey("labels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("task_labels")
    op.drop_index("ix_labels_owner_sub", table_name="labels")
    op.drop_table("labels")
