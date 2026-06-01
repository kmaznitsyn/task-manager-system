import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import now

from app import publisher
from app.config import settings
from app.database import get_db
from app.models import Document, DocStatus, DocType
from app.processing import ExtractionError, extract
from app.schemas import DocumentCreate, DocumentEvent, DocumentRead
from cf_auth import get_current_user

logger = logging.getLogger(__name__)


def _publish_safe(event: DocumentEvent) -> None:
    """Best-effort publish — must never let a Pub/Sub failure roll back the DB.

    Same invariant as task-service: status is authoritative in the DB; the
    event stream is best-effort downstream notification.
    """
    try:
        publisher.publish_document_event(event)
    except Exception:  # noqa: BLE001 — intentionally broad; log everything
        logger.exception(
            "failed to publish %s for document %s — DB state stands",
            event.type,
            event.document_id,
        )


app = FastAPI(title="Docs Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "docs-service"}


def _owned_document_or_404(
    db: Session, document_id: uuid.UUID, owner_sub: str
) -> Document:
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id, Document.owner_sub == owner_sub
        )
    )
    if doc is None:
        # 404 (not 403) — don't leak existence of other users' documents.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@app.get("/documents", response_model=list[DocumentRead])
def list_documents(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    doc_type: DocType | None = Query(default=None),
    status_: DocStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(Document)
        .where(Document.owner_sub == claims["sub"])
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if doc_type is not None:
        stmt = stmt.where(Document.doc_type == doc_type)
    if status_ is not None:
        stmt = stmt.where(Document.status == status_)
    return list(db.scalars(stmt))


@app.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentCreate,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = Document(owner_sub=claims["sub"], **body.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)

    _publish_safe(
        DocumentEvent(
            type="document.received",
            document_id=str(doc.id),
            owner_sub=doc.owner_sub,
            doc_type=doc.doc_type,
        )
    )
    return doc


@app.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _owned_document_or_404(db, document_id, claims["sub"])


@app.post("/documents/{document_id}/process", response_model=DocumentRead)
def process_document(
    document_id: uuid.UUID,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned_document_or_404(db, document_id, claims["sub"])
    if doc.status == DocStatus.processed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Document already processed")

    try:
        doc.extracted = extract(doc.doc_type, doc.raw_text)
        doc.status = DocStatus.processed
        doc.failure_reason = None
        event_type = "document.processed"
    except ExtractionError as e:
        doc.status = DocStatus.failed
        doc.failure_reason = str(e)
        event_type = "document.failed"
    doc.processed_at = now()
    db.commit()
    db.refresh(doc)

    _publish_safe(
        DocumentEvent(
            type=event_type,
            document_id=str(doc.id),
            owner_sub=doc.owner_sub,
            doc_type=doc.doc_type,
        )
    )
    return doc


@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _owned_document_or_404(db, document_id, claims["sub"])
    db.delete(doc)
    db.commit()
