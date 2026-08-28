from sqlalchemy.orm import Session

from app.database.models import QueryLog


def log_query(
    db: Session,
    user_id: int,
    query: str,
):
    query_log = QueryLog(
        user_id=user_id,
        query=query,
    )

    db.add(query_log)

    db.commit()

    db.refresh(query_log)

    return query_log