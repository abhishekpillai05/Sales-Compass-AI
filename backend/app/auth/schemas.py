from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from app.auth.roles import UserRole, UserStatus


class UserRegister(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    email: EmailStr

    password: str = Field(
        min_length=6,
    )

    role: str = "SALESMAN"


class UserLogin(BaseModel):

    username: str

    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str | None) -> str:
        return UserRole.normalize(v)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: str | None) -> str:
        return UserStatus.normalize(v)


class AdminUserItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str | None) -> str:
        return UserRole.normalize(v)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: str | None) -> str:
        return UserStatus.normalize(v)


class AdminUserListResponse(BaseModel):
    users: List[AdminUserItem]
    total: int


class UpdateUserRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        normalized = UserRole.normalize(v)
        if normalized not in (UserRole.ADMIN.value, UserRole.SALESMAN.value):
            raise ValueError(f"Invalid role '{v}'. Allowed roles: ADMIN, SALESMAN.")
        return normalized


class UpdateUserStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        cleaned = v.strip().upper() if v else ""
        if cleaned not in (UserStatus.ACTIVE.value, UserStatus.REVOKED.value):
            raise ValueError(f"Invalid status '{v}'. Allowed statuses: ACTIVE, REVOKED.")
        return cleaned