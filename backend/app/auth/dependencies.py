from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import User, UserSession
from app.database.session import SessionLocal

from typing import Callable
def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_current_user(
    session_token: str | None = Cookie(
        default=None,
    ),
    db: Session = Depends(get_db),
):

    if not session_token:

        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
        )

    session = (
        db.query(UserSession)
        .filter(
            UserSession.session_token == session_token,
            UserSession.is_active == True,
        )
        .first()
    )

    if not session:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        )

    if session.expires_at < datetime.now(timezone.utc):

        session.is_active = False
        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again.",
        )

    user = (
        db.query(User)
        .filter(User.id == session.user_id)
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found.",
        )

    return user



def require_role(*allowed_roles: str):

    def role_checker(
        current_user: User = Depends(get_current_user),
    ):

        if current_user.role not in allowed_roles:

            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker