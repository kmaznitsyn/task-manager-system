import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import keycloak, publisher
from app.config import settings
from app.database import get_db
from app.keycloak import KeycloakError
from app.models import OutboxEvent, User
from app.schemas import UserOut, UsersPage
from app.users import get_or_create_from_claims
from cf_auth import get_current_user

app = FastAPI(title="User Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(KeycloakError)
def _keycloak_error_handler(_: Request, exc: KeycloakError):
    # Keycloak unreachable / misconfigured — surface as a bad-gateway, not a 500.
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def require_admin(claims: dict = Depends(get_current_user)) -> dict:
    """Allow only callers carrying the realm role ``admin``."""
    roles = claims.get("realm_access", {}).get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return claims


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}


@app.get("/admin/users", response_model=UsersPage)
def admin_list_users(
    first: int = 0,
    max: int = 20,
    search: str | None = None,
    _: dict = Depends(require_admin),
):
    max = min(max, 100)
    users = keycloak.list_users(first, max, search)
    total = keycloak.count_users(search)
    return UsersPage(users=users, total=total, first=first, max=max)


@app.delete("/admin/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: str,
    claims: dict = Depends(require_admin),
):
    if user_id == claims.get("sub"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot delete your own account"
        )
    keycloak.delete_user(user_id)


@app.get("/me", response_model=UserOut)
def me(
    claims: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_or_create_from_claims(db, claims)


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


# TODO: PATCH /users/{id}

@app.delete("/me", status_code=204)
def delete_me(claims = Depends(get_current_user), db: Session = Depends(get_db)):
  sub = claims["sub"]
  keycloak.delete_user(sub)                 # external, idempotent (404 = already gone)
  db.execute(delete(User).where(User.keycloak_sub == sub))
  db.add(OutboxEvent(topic="user-events",
                     payload={"type": "user.deleted", "sub": sub}))
  db.commit()                               # row delete + event row: one atomic commit



@app.post("/internal/outbox/flush")   # protect with OIDC like the push endpoints
def flush_outbox(db: Session = Depends(get_db)):
  rows = db.scalars(
      select(OutboxEvent)
      .where(OutboxEvent.published_at.is_(None))
      .order_by(OutboxEvent.created_at)
      .limit(100)
      .with_for_update(skip_locked=True)   # safe under multiple Cloud Run instances
  ).all()
  for ev in rows:
      publisher.publish(ev.topic, ev.payload)   # awaits future.result() — real ack
      ev.published_at = func.now()
  db.commit()