import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserOut
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}


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
