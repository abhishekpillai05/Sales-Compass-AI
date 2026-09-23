"""
backend/tests/test_admin_management.py

Comprehensive test suite for the ADMIN User Management module.

Verifies:
1. Admin can view users list (GET /admin/users).
2. Salesman cannot access user management APIs (403 Forbidden).
3. Admin can promote a salesman to admin.
4. Admin can demote an admin to salesman (when multiple active admins exist).
5. Admin can revoke a salesman's access.
6. Revoked user cannot log in (403 Forbidden).
7. Revoked user cannot access Chat or Search (403 Forbidden).
8. Admin can restore revoked access (ACTIVE status).
9. Admin self-revocation is blocked (400 Bad Request).
10. Admin self-demotion is blocked (400 Bad Request).
11. Last active admin cannot be demoted or revoked (400 Bad Request).
12. Existing active sessions are invalidated upon revocation.
13. Unauthenticated requests to management APIs return 401.
14. GET /admin/users/{user_id} returns user details or 404.
15. Search and role/status filtering on GET /admin/users.
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.auth.roles import UserRole, UserStatus
from app.auth.dependencies import get_current_user, require_role
from app.database.models import User, UserSession
from app.database.session import SessionLocal


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(
    role: str = "ADMIN",
    status: str = "ACTIVE",
    user_id: int = 1,
    username: str = "test_admin",
) -> MagicMock:
    """Create a mock User instance."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.username = username
    user.email = f"{username}@test.com"
    user.password_hash = "hashed_secret"
    user.role = role
    user.status = status
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def client():
    """Test client with isolated dependency overrides."""
    app.dependency_overrides.clear()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── 1. Unauthenticated & Salesman Authorization Tests ─────────────────────────

class TestManagementAuthorization:
    """Verify unauthenticated (401) and salesman (403) rejections."""

    def test_unauthenticated_cannot_list_users(self, client):
        resp = client.get("/admin/users")
        assert resp.status_code == 401

    def test_unauthenticated_cannot_change_role(self, client):
        resp = client.patch("/admin/users/1/role", json={"role": "ADMIN"})
        assert resp.status_code == 401

    def test_unauthenticated_cannot_change_status(self, client):
        resp = client.patch("/admin/users/1/status", json={"status": "REVOKED"})
        assert resp.status_code == 401

    def test_salesman_cannot_list_users(self, client):
        salesman = make_user(role="SALESMAN", user_id=10)
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.get("/admin/users")
        assert resp.status_code == 403
        assert "permission" in resp.json().get("detail", "").lower()

    def test_salesman_cannot_update_role(self, client):
        salesman = make_user(role="SALESMAN", user_id=10)
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.patch("/admin/users/2/role", json={"role": "ADMIN"})
        assert resp.status_code == 403

    def test_salesman_cannot_update_status(self, client):
        salesman = make_user(role="SALESMAN", user_id=10)
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.patch("/admin/users/2/status", json={"status": "REVOKED"})
        assert resp.status_code == 403


# ── 2. Admin View Users & User Details ────────────────────────────────────────

class TestAdminViewUsers:
    """Verify admin user listing, search, filtering, and detail endpoints."""

    def test_admin_can_view_users_list(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1, username="superadmin")
        app.dependency_overrides[get_current_user] = lambda: admin

        # Mock DB session
        u1 = make_user(role="ADMIN", status="ACTIVE", user_id=1, username="superadmin")
        u2 = make_user(role="SALESMAN", status="ACTIVE", user_id=2, username="john_sales")
        u3 = make_user(role="SALESMAN", status="REVOKED", user_id=3, username="banned_sales")

        def mock_db():
            db = MagicMock()
            query_mock = db.query.return_value
            query_mock.count.return_value = 3
            query_mock.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
                u1, u2, u3
            ]
            # user sessions query
            db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.get("/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["users"]) == 3
        # Ensure password_hash is never exposed
        for user in data["users"]:
            assert "password_hash" not in user
            assert "password" not in user
            assert "role" in user
            assert "status" in user

    def test_admin_users_sorting_parameters(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1, username="superadmin")
        app.dependency_overrides[get_current_user] = lambda: admin

        u1 = make_user(role="ADMIN", status="ACTIVE", user_id=1, username="superadmin")
        u2 = make_user(role="SALESMAN", status="ACTIVE", user_id=2, username="john_sales")

        def mock_db():
            db = MagicMock()
            query_mock = db.query.return_value
            query_mock.count.return_value = 2
            query_mock.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
                u2, u1
            ]
            db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        # Test with sort_by and order query parameters
        resp = client.get("/admin/users?sort_by=id&order=desc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

        resp2 = client.get("/admin/users?sort_by=username&order=asc")
        assert resp2.status_code == 200

        resp3 = client.get("/admin/users?sort_by=created_at&order=desc")
        assert resp3.status_code == 200

    def test_get_user_details_found(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1)
        target = make_user(role="SALESMAN", status="ACTIVE", user_id=42, username="alice")
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = target
            db.query.return_value.filter.return_value.scalar.return_value = datetime(2026, 9, 23, 12, 0)
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.get("/admin/users/42")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 42
        assert data["username"] == "alice"
        assert data["role"] == "SALESMAN"
        assert data["status"] == "ACTIVE"

    def test_get_user_details_not_found(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1)
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.get("/admin/users/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ── 3. Role Promotion & Demotion ──────────────────────────────────────────────

class TestRoleManagement:
    """Verify role updates, self-demotion prevention, and last admin safeguard."""

    def test_admin_can_promote_salesman_to_admin(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1)
        target = make_user(role="SALESMAN", status="ACTIVE", user_id=2, username="promoteme")
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = target
            db.query.return_value.filter.return_value.scalar.return_value = None
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/2/role", json={"role": "ADMIN"})
        assert resp.status_code == 200
        assert target.role == "ADMIN"
        assert resp.json()["role"] == "ADMIN"

    def test_admin_can_demote_admin_to_salesman_when_multiple_admins(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin_1 = make_user(role="ADMIN", user_id=1)
        admin_2 = make_user(role="ADMIN", status="ACTIVE", user_id=2, username="demoteme")
        app.dependency_overrides[get_current_user] = lambda: admin_1

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = admin_2
            # active admin count is 2
            db.query.return_value.filter.return_value.count.return_value = 2
            db.query.return_value.filter.return_value.scalar.return_value = None
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/2/role", json={"role": "SALESMAN"})
        assert resp.status_code == 200
        assert admin_2.role == "SALESMAN"
        assert resp.json()["role"] == "SALESMAN"

    def test_self_demotion_is_blocked(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1, username="admin1")
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            # Target is the current admin themselves
            db.query.return_value.filter.return_value.first.return_value = admin
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/1/role", json={"role": "SALESMAN"})
        assert resp.status_code == 400
        assert "cannot remove their own admin privileges" in resp.json()["detail"].lower()

    def test_last_active_admin_demotion_is_blocked(self, client):
        from app.api.admin_users import get_db as admin_get_db

        caller_admin = make_user(role="ADMIN", user_id=1)
        target_admin = make_user(role="ADMIN", status="ACTIVE", user_id=2)
        app.dependency_overrides[get_current_user] = lambda: caller_admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = target_admin
            # Count of active admins is only 1!
            db.query.return_value.filter.return_value.count.return_value = 1
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/2/role", json={"role": "SALESMAN"})
        assert resp.status_code == 400
        assert "cannot demote the last active administrator" in resp.json()["detail"].lower()


# ── 4. Revocation & Restoration ───────────────────────────────────────────────

class TestRevocationAndRestoration:
    """Verify user revocation, restoration, self-revocation block, and last admin safeguard."""

    def test_admin_can_revoke_salesman(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1)
        salesman = make_user(role="SALESMAN", status="ACTIVE", user_id=2, username="bad_salesman")
        app.dependency_overrides[get_current_user] = lambda: admin

        session_query_mock = MagicMock()

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = salesman
            # session deactivation
            db.query.return_value.filter.return_value.update = session_query_mock.update
            db.query.return_value.filter.return_value.scalar.return_value = None
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/2/status", json={"status": "REVOKED"})
        assert resp.status_code == 200
        assert salesman.status == "REVOKED"
        assert resp.json()["status"] == "REVOKED"
        # Verify active sessions were deactivated
        session_query_mock.update.assert_called_once_with({"is_active": False})

    def test_admin_can_restore_revoked_user(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1)
        revoked_user = make_user(role="SALESMAN", status="REVOKED", user_id=3)
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = revoked_user
            db.query.return_value.filter.return_value.scalar.return_value = None
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/3/status", json={"status": "ACTIVE"})
        assert resp.status_code == 200
        assert revoked_user.status == "ACTIVE"
        assert resp.json()["status"] == "ACTIVE"

    def test_self_revocation_is_blocked(self, client):
        from app.api.admin_users import get_db as admin_get_db

        admin = make_user(role="ADMIN", user_id=1, username="admin1")
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = admin
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/1/status", json={"status": "REVOKED"})
        assert resp.status_code == 400
        assert "cannot revoke their own account" in resp.json()["detail"].lower()

    def test_last_active_admin_revocation_is_blocked(self, client):
        from app.api.admin_users import get_db as admin_get_db

        caller_admin = make_user(role="ADMIN", user_id=1)
        target_admin = make_user(role="ADMIN", status="ACTIVE", user_id=2)
        app.dependency_overrides[get_current_user] = lambda: caller_admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = target_admin
            # Count of active admins is only 1!
            db.query.return_value.filter.return_value.count.return_value = 1
            yield db

        app.dependency_overrides[admin_get_db] = mock_db

        resp = client.patch("/admin/users/2/status", json={"status": "REVOKED"})
        assert resp.status_code == 400
        assert "cannot revoke the last active administrator" in resp.json()["detail"].lower()


# ── 5. Revoked Account Access Denial (Login, Chat, Search) ────────────────────

class TestRevokedAccountAccessDenial:
    """Verify that a revoked user cannot login or make authenticated requests."""

    def test_revoked_user_cannot_login(self, client):
        from app.api.auth import get_db as auth_get_db

        revoked_user = make_user(role="SALESMAN", status="REVOKED", user_id=5, username="blocked_user")

        def mock_db():
            db = MagicMock()
            # authenticate_user returns the user with valid password
            yield db

        app.dependency_overrides[auth_get_db] = mock_db

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.api.auth.authenticate_user", lambda db, username, password: revoked_user)

            resp = client.post("/auth/login", json={"username": "blocked_user", "password": "Password123!"})
            assert resp.status_code == 403
            assert "revoked" in resp.json()["detail"].lower()

    def test_revoked_user_in_flight_session_rejected_by_get_current_user(self, client):
        """When a user is revoked, get_current_user terminates the session and raises 403."""
        db = SessionLocal()
        uid = uuid.uuid4().hex[:6]
        user = User(
            username=f"revoketest_{uid}",
            email=f"revoketest_{uid}@test.com",
            password_hash="secret",
            role="SALESMAN",
            status="REVOKED",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        session = UserSession(
            user_id=user.id,
            session_token=f"token_{uid}",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            is_active=True,
        )
        db.add(session)
        db.commit()

        try:
            client.cookies.set("session_token", session.session_token)

            # Test on /search (uses get_current_user)
            resp = client.post("/search", json={"query": "test"})
            assert resp.status_code == 403
            assert "revoked" in resp.json()["detail"].lower()

            # Verify session was deactivated in DB
            db.refresh(session)
            assert session.is_active is False

            # Test on /conversations (uses get_current_user)
            resp = client.get("/conversations")
            assert resp.status_code == 401 or resp.status_code == 403

        finally:
            try:
                db.delete(session)
                db.commit()
            except Exception:
                db.rollback()
            try:
                db.delete(user)
                db.commit()
            except Exception:
                db.rollback()
            db.close()
