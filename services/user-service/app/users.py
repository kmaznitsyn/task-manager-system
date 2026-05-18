from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import User


def get_or_create_from_claims(db: Session, claims: dict) -> User:
    sub = claims["sub"]
    email = claims.get("email") or f"{sub}@unknown.local"
    display_name = claims.get("name") or claims.get("preferred_username")

    # INSERT ... ON CONFLICT DO NOTHING — concurrency-safe first-login provisioning.
    stmt = (
        insert(User)
        .values(keycloak_sub=sub, email=email, display_name=display_name)
        .on_conflict_do_nothing(index_elements=["keycloak_sub"])
    )
    db.execute(stmt)
    db.commit()

    user = db.scalar(select(User).where(User.keycloak_sub == sub))

    # Keep email / display_name in sync with Keycloak on subsequent logins.
    changed = False
    if claims.get("email") and user.email != claims["email"]:
        user.email = claims["email"]
        changed = True
    if display_name and user.display_name != display_name:
        user.display_name = display_name
        changed = True
    if changed:
        db.commit()
        db.refresh(user)

    return user
