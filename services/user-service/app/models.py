import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keycloak_sub: Mapped[str] = mapped_column(String(64), unique=True,
                                              index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True,
                                       index=True)
    display_name: Mapped[str | None] = mapped_column(String(120),
                                                     nullable=True)
    # is_active: Mapped[bool] = mapped_column(Boolean, default=True,
    #                                         nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )