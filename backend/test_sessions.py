from app.database.session import SessionLocal
from app.auth.sessions import create_session


from app.database.models import User
import uuid

db = SessionLocal()

try:
    user = db.query(User).first()
    if not user:
        user = User(
            username=f"test_session_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password_hash="fakehash",
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    session = create_session(
        db=db,
        user_id=user.id,
    )

    print("Session created successfully!")
    print("Session ID:", session.id)
    print("User ID:", session.user_id)
    print("Session Token:", session.session_token)
    print("Expires At:", session.expires_at)

finally:

    db.close()