import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keycloak_sub: str
    email: EmailStr
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class KeycloakUserOut(BaseModel):
    """A user as returned by the Keycloak Admin API (camelCase mapped to snake)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    username: str
    email: str | None = None
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    enabled: bool = True
    created_timestamp: int | None = Field(default=None, alias="createdTimestamp")


class UsersPage(BaseModel):
    users: list[KeycloakUserOut]
    total: int
    first: int
    max: int
