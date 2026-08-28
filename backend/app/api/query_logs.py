from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.database.models import User, QueryLog
from app.database.session import SessionLocal


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.get("/query-logs")
def get_query_logs(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):

    logs = (
        db.query(QueryLog)
        .order_by(QueryLog.timestamp.desc())
        .all()
    )

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "query": log.query,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]