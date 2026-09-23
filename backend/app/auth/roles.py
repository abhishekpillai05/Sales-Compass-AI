"""
User Roles and Normalization for Role-Based Access Control (RBAC).

Two standard roles:
- ADMIN: Complete system access (chat, search, upload, query logs, admin panel).
- SALESMAN: Restricted access (chat, search, conversations).
"""
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SALESMAN = "SALESMAN"

    @classmethod
    def normalize(cls, role: str | None) -> str:
        """
        Normalize a role string to canonical uppercase 'ADMIN' or 'SALESMAN'.
        Handles case insensitivity and maps legacy roles ('user', 'sales') to 'SALESMAN'.
        Defaults to 'SALESMAN' if missing or unrecognized.
        """
        if not role or not role.strip():
            return cls.SALESMAN.value

        cleaned = role.strip().upper()
        if cleaned in ("ADMIN",):
            return cls.ADMIN.value
        if cleaned in ("SALESMAN", "USER", "SALES"):
            return cls.SALESMAN.value

        return cls.SALESMAN.value


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"

    @classmethod
    def normalize(cls, status: str | None) -> str:
        """
        Normalize an account status string to canonical uppercase 'ACTIVE' or 'REVOKED'.
        Defaults to 'ACTIVE' if missing or unrecognized.
        """
        if not status or not status.strip():
            return cls.ACTIVE.value

        cleaned = status.strip().upper()
        if cleaned in ("REVOKED",):
            return cls.REVOKED.value

        return cls.ACTIVE.value
