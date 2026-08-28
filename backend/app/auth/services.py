from sqlalchemy.orm import Session

from app.database.models import User
from app.auth.security import (
    hash_password,
    verify_password,
)


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    role: str = "user",
) -> User:
    """
    Create a new user after checking
    for duplicate username and email.
    """

    existing_username = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_username:
        raise ValueError(
            "Username already exists."
        )

    existing_email = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_email:
        raise ValueError(
            "Email already exists."
        )

    password_hash = hash_password(
        password
    )

    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        role=role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    """
    Authenticate a user using username
    and password.
    """

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user:
        return None

    is_valid = verify_password(
        password,
        user.password_hash,
    )

    if not is_valid:
        return None

    return user