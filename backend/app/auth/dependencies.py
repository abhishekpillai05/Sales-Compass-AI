from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import User, UserSession
from app.database.session import SessionLocal
from app.auth.roles import UserRole, UserStatus

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
        # Check if the session exists in DB but is inactive
        inactive_session = (
            db.query(UserSession)
            .filter(UserSession.session_token == session_token)
            .first()
        )
        if inactive_session:
            # Preserve 403 if the user was revoked
            user = db.query(User).filter(User.id == inactive_session.user_id).first()
            if user and UserStatus.normalize(getattr(user, "status", None)) == UserStatus.REVOKED.value:
                raise HTTPException(
                    status_code=403,
                    detail="Account has been revoked. Please contact an administrator.",
                )
            raise HTTPException(
                status_code=401,
                detail="Session terminated. Your account was logged in from another device or session expired.",
            )

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

    # Check if account access has been revoked by an administrator
    if UserStatus.normalize(getattr(user, "status", None)) == UserStatus.REVOKED.value:
        session.is_active = False
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Account has been revoked. Please contact an administrator.",
        )

    return user



def require_role(*allowed_roles: str):
    normalized_allowed = set()
    for role in allowed_roles:
        normalized_allowed.add(UserRole.normalize(role))
        normalized_allowed.add(role.upper())
        normalized_allowed.add(role)

    def role_checker(
        current_user: User = Depends(get_current_user),
    ):
        user_role = UserRole.normalize(current_user.role)
        if user_role not in normalized_allowed and current_user.role not in normalized_allowed:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker