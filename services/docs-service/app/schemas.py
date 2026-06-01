import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocStatus, DocType


class DocumentCreate(BaseModel):
    doc_type: DocType
    reference_number: str = Field(min_length=1, max_length=128)
    shipment_ref: str | None = Field(default=None, max_length=128)
    raw_text: str = Field(min_length=1)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_sub: str
    doc_type: DocType
    reference_number: str
    shipment_ref: str | None
    raw_text: str
    status: DocStatus
    extracted: dict | None
    failure_reason: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentEvent(BaseModel):
    type: Literal["document.received", "document.processed", "document.failed"]
    document_id: str
    owner_sub: str
    doc_type: DocType
