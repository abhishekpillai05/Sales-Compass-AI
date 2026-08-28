from app.database.session import SessionLocal
from app.auth.sessions import create_session


db = SessionLocal()

try:

    session = create_session(
        db=db,
        user_id=1,
    )

    print("Session created successfully!")
    print("Session ID:", session.id)
    print("User ID:", session.user_id)
    print("Session Token:", session.session_token)
    print("Expires At:", session.expires_at)

finally:

    db.close()