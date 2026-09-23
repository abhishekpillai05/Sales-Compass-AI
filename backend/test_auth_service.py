from app.database.session import SessionLocal
from app.auth.services import (
    create_user,
    authenticate_user,
)


import uuid

db = SessionLocal()

unique_id = uuid.uuid4().hex[:6]
username = f"user_{unique_id}"
email = f"user_{unique_id}@example.com"
password = "testpassword123"

try:

    # Create test user
    user = create_user(
        db=db,
        username=username,
        email=email,
        password=password,
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
        username=username,
        password=password,
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