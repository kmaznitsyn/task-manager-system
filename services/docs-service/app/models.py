import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocType(str, enum.Enum):
    bill_of_lading = "bill_of_lading"
    manifest = "manifest"
    proof_of_delivery = "proof_of_delivery"
    invoice = "invoice"
    customs_declaration = "customs_declaration"


class DocStatus(str, enum.Enum):
    received = "received"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_sub: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, name="doc_type", native_enum=True), nullable=False
    )
    reference_number: Mapped[str] = mapped_column(String(128), nullable=False)
    shipment_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status", native_enum=True),
        nullable=False,
        default=DocStatus.received,
        server_default=DocStatus.received.value,
    )
    extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
