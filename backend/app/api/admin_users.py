"""
backend/app/api/admin_users.py

Admin User Management API endpoints.
Provides complete user administration capabilities restricted strictly to ADMIN users:
- List all users with search, role filter, status filter, and last login computation.
- View single user details.
- Change user role between ADMIN and SALESMAN.
- Revoke and restore user access (with immediate session invalidation).
- Strict backend safeguards preventing self-revocation, self-demotion, and last-admin lockout.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database.models import User, UserSession
from app.database.session import SessionLocal
from app.auth.dependencies import require_role
from app.auth.roles import UserRole, UserStatus
from app.auth.schemas import (
    AdminUserItem,
    AdminUserListResponse,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from app.logging.config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/admin/users",
    tags=["Admin User Management"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_user_last_login(db: Session, user_id: int):
    """Retrieve the most recent session creation time for a user."""
    res = (
        db.query(func.max(UserSession.created_at))
        .filter(UserSession.user_id == user_id)
        .scalar()
    )
    return res


def _format_admin_user_item(user: User, last_login=None) -> AdminUserItem:
    """Format User model into safe AdminUserItem."""
    return AdminUserItem(
        id=user.id,
        username=user.username,
        email=user.email,
        role=UserRole.normalize(user.role),
        status=UserStatus.normalize(getattr(user, "status", None)),
        created_at=getattr(user, "created_at", None),
        last_login=last_login,
    )


@router.get(
    "",
    response_model=AdminUserListResponse,
)
def list_users(
    search: Optional[str] = Query(default=None, description="Search by username or email"),
    role: Optional[str] = Query(default=None, description="Filter by role: ADMIN or SALESMAN"),
    status: Optional[str] = Query(default=None, description="Filter by status: ACTIVE or REVOKED"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_role(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    List all registered users with optional search and role/status filtering.
    Restricted strictly to administrators.
    """
    query = db.query(User)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
            )
        )

    if role and role.strip():
        norm_role = UserRole.normalize(role)
        query = query.filter(User.role == norm_role)

    if status and status.strip():
        norm_status = UserStatus.normalize(status)
        query = query.filter(User.status == norm_status)

    total = query.count()
    users = query.order_by(User.id.asc()).offset(offset).limit(limit).all()

    # Batch query last login for all users on this page
    user_ids = [u.id for u in users]
    last_logins_map = {}
    if user_ids:
        rows = (
            db.query(UserSession.user_id, func.max(UserSession.created_at).label("last_login"))
            .filter(UserSession.user_id.in_(user_ids))
            .group_by(UserSession.user_id)
            .all()
        )
        last_logins_map = {r.user_id: r.last_login for r in rows}

    items = [
        _format_admin_user_item(u, last_login=last_logins_map.get(u.id))
        for u in users
    ]

    logger.info(
        "admin listed users admin_id=%d total=%d returned=%d",
        current_user.id,
        total,
        len(items),
    )

    return AdminUserListResponse(users=items, total=total)


@router.get(
    "/{user_id}",
    response_model=AdminUserItem,
)
def get_user_details(
    user_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Retrieve safe user details by ID.
    Restricted strictly to administrators.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    last_login = _get_user_last_login(db, user.id)
    return _format_admin_user_item(user, last_login=last_login)


@router.patch(
    "/{user_id}/role",
    response_model=AdminUserItem,
)
def update_user_role(
    user_id: int,
    request: UpdateUserRoleRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Promote or demote a user's role.
    Safeguards:
    - Admin cannot remove their own admin privileges (self-demotion blocked).
    - Cannot demote the last active admin in the system.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_role = request.role
    current_target_role = UserRole.normalize(target_user.role)

    # 1. Prevent self-demotion
    if target_user.id == current_user.id and current_target_role == UserRole.ADMIN.value and new_role != UserRole.ADMIN.value:
        logger.warning("admin self-demotion blocked admin_id=%d", current_user.id)
        raise HTTPException(
            status_code=400,
            detail="Administrators cannot remove their own admin privileges.",
        )

    # 2. Prevent removing the last active admin
    if current_target_role == UserRole.ADMIN.value and new_role != UserRole.ADMIN.value:
        active_admin_count = (
            db.query(User)
            .filter(
                User.role == UserRole.ADMIN.value,
                User.status == UserStatus.ACTIVE.value,
            )
            .count()
        )
        if active_admin_count <= 1:
            logger.warning(
                "last active admin demotion blocked admin_id=%d target_id=%d",
                current_user.id,
                target_user.id,
            )
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last active administrator.",
            )

    target_user.role = new_role
    db.commit()
    db.refresh(target_user)

    logger.info(
        "admin updated user role admin_id=%d target_id=%d new_role=%s",
        current_user.id,
        target_user.id,
        new_role,
    )

    last_login = _get_user_last_login(db, target_user.id)
    return _format_admin_user_item(target_user, last_login=last_login)


@router.patch(
    "/{user_id}/status",
    response_model=AdminUserItem,
)
def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Revoke or restore a user's application access.
    Safeguards:
    - Admin cannot revoke their own account (self-revocation blocked).
    - Cannot revoke the last active admin in the system.
    - Revoking immediately invalidates all active sessions for the user.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_status = request.status
    current_target_role = UserRole.normalize(target_user.role)
    current_target_status = UserStatus.normalize(getattr(target_user, "status", None))

    # 1. Prevent self-revocation
    if target_user.id == current_user.id and new_status == UserStatus.REVOKED.value:
        logger.warning("admin self-revocation blocked admin_id=%d", current_user.id)
        raise HTTPException(
            status_code=400,
            detail="Administrators cannot revoke their own account.",
        )

    # 2. Prevent revoking the last active admin
    if current_target_role == UserRole.ADMIN.value and new_status == UserStatus.REVOKED.value:
        active_admin_count = (
            db.query(User)
            .filter(
                User.role == UserRole.ADMIN.value,
                User.status == UserStatus.ACTIVE.value,
            )
            .count()
        )
        if active_admin_count <= 1:
            logger.warning(
                "last active admin revocation blocked admin_id=%d target_id=%d",
                current_user.id,
                target_user.id,
            )
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke the last active administrator.",
            )

    target_user.status = new_status

    # 3. If revoking, immediately deactivate all active user sessions
    if new_status == UserStatus.REVOKED.value:
        terminated_count = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == target_user.id,
                UserSession.is_active == True,
            )
            .update({"is_active": False})
        )
        logger.info(
            "revoked user sessions terminated target_id=%d session_count=%d",
            target_user.id,
            terminated_count,
        )

    db.commit()
    db.refresh(target_user)

    logger.info(
        "admin updated user status admin_id=%d target_id=%d new_status=%s",
        current_user.id,
        target_user.id,
        new_status,
    )

    last_login = _get_user_last_login(db, target_user.id)
    return _format_admin_user_item(target_user, last_login=last_login)
