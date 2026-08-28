from app.database.session import SessionLocal
from app.auth.services import (
    create_user,
    authenticate_user,
)


db = SessionLocal()


try:

    # Create test user
    user = create_user(
        db=db,
        username="jagu",
        email="jagu@example.com",
        password="testpassword123",
        role="user",
    )

    print("USER CREATED")
    print(user.id)
    print(user.username)
    print(user.email)
    print(user.role)

    print("\n" + "=" * 50)
    print("LOGIN TEST")
    print("=" * 50)

    authenticated_user = authenticate_user(
        db=db,
        username="jagu",
        password="testpassword123",
    )

    if authenticated_user:
        print("LOGIN SUCCESS")
        print(
            authenticated_user.username
        )
    else:
        print("LOGIN FAILED")

finally:

    db.close()