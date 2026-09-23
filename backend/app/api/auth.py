from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    require_role,
)
from app.auth.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
)
from app.auth.services import (
    create_user,
    authenticate_user,
)
from app.auth.sessions import (
    create_session,
    logout_session,
)
from app.auth.roles import UserRole, UserStatus
from app.database.models import User
from app.database.session import SessionLocal
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post(
    "/register",
    response_model=UserResponse,
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):

    try:

        # Self-registration always assigns the default SALESMAN role.
        # Regular users can never elevate privileges to ADMIN during registration.
        user = create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role=UserRole.SALESMAN.value,
        )

        return user

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    user_data: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):

    user = authenticate_user(
        db=db,
        username=user_data.username,
        password=user_data.password,
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    if UserStatus.normalize(getattr(user, "status", None)) == UserStatus.REVOKED.value:
        raise HTTPException(
            status_code=403,
            detail="Account has been revoked. Please contact an administrator.",
        )

    session = create_session(
        db=db,
        user_id=user.id,
    )

    response.set_cookie(
        key="session_token",
        value=session.session_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return user

@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.post("/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):

    if session_token:

        logout_session(
            db=db,
            session_token=session_token,
        )

    response.delete_cookie(
        key="session_token",
    )

    return {
        "message": "Logged out successfully."
    }

@router.get("/admin-test")
def admin_test(
    current_user: User = Depends(
        require_role(UserRole.ADMIN.value)
    ),
):

    return {
        "message": "Welcome Admin!",
        "username": current_user.username,
    }