import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.models import UserSession


SESSION_EXPIRE_DAYS = 7


def create_session(
    db: Session,
    user_id: int,
):

    session_token = secrets.token_urlsafe(32)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=SESSION_EXPIRE_DAYS)
    )

    session = UserSession(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at,
        is_active=True,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session

def logout_session(
    db: Session,
    session_token: str,
):

    session = (
        db.query(UserSession)
        .filter(
            UserSession.session_token == session_token,
            UserSession.is_active == True,
        )
        .first()
    )

    if not session:
        return False

    session.is_active = False

    db.commit()

    return True