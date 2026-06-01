"""create documents table

Revision ID: 0001_create_documents
Revises:
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_create_documents"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


doc_type = sa.Enum(
    "bill_of_lading",
    "manifest",
    "proof_of_delivery",
    "invoice",
    "customs_declaration",
    name="doc_type",
)
doc_status = sa.Enum(
    "received", "processing", "processed", "failed", name="doc_status"
)


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_sub", sa.String(64), nullable=False),
        sa.Column("doc_type", doc_type, nullable=False),
        sa.Column("reference_number", sa.String(128), nullable=False),
        sa.Column("shipment_ref", sa.String(128), nullable=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column(
            "status",
            doc_status,
            nullable=False,
            server_default="received",
        ),
        sa.Column("extracted", JSONB, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_owner_sub", "documents", ["owner_sub"])


def downgrade() -> None:
    op.drop_index("ix_documents_owner_sub", table_name="documents")
    op.drop_table("documents")
    sa.Enum(name="doc_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="doc_type").drop(op.get_bind(), checkfirst=True)
