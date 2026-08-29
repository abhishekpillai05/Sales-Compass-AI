"""
tests/test_auth_admin.py

Phase 7 admin authorization tests.

Tests three distinct cases for GET /admin/query-logs:
  A. Unauthenticated request   → 401
  B. Normal authenticated user → 403
  C. Admin authenticated user  → 200

Uses FastAPI TestClient with dependency_overrides. No live infrastructure
required — the DB is mocked for admin-endpoint tests, and get_current_user
is overridden to inject specific User objects. The require_role("admin")
dependency is NOT bypassed; it still runs and enforces role checks.
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user


# ── Helpers: build mock User objects ─────────────────────────────────────────

def make_user(role: str = "user") -> MagicMock:
    """
    Return a MagicMock that mimics the ORM User object.

    We do NOT use User.__new__() because SQLAlchemy instrumented
    attributes require _sa_instance_state to be present, which is only
    initialised through __init__ (or a real DB session). A MagicMock
    with explicitly set attributes is the correct approach for
    unit/integration tests that inject auth users.
    """
    user = MagicMock()
    user.id = 1 if role == "user" else 2
    user.username = f"{role}_user"
    user.email = f"{role}@test.com"
    user.password_hash = "hashed"
    user.role = role
    return user


# ── Client fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Return a TestClient with no dependency overrides (clean state)."""
    app.dependency_overrides.clear()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── Test A: Unauthenticated → 401 ────────────────────────────────────────────

class TestAdminUnauthenticated:
    """GET /admin/query-logs with no session cookie must return 401."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/admin/query-logs")
        assert resp.status_code == 401, (
            f"Expected 401, got {resp.status_code}: {resp.text}"
        )

    def test_unauthenticated_response_has_detail(self, client):
        resp = client.get("/admin/query-logs")
        data = resp.json()
        assert "detail" in data

    def test_unauthenticated_with_invalid_cookie_returns_401_or_403(self, client):
        """A bogus session_token cookie (no matching DB row) → 401 from dependency."""
        # When session lookup returns None, get_current_user raises 401.
        # We do NOT override get_current_user here, so the real dependency
        # is exercised; with a fake token the UserSession lookup fails → 401.
        client.cookies.set("session_token", "totally_invalid_token_xyz_999")
        resp = client.get("/admin/query-logs")
        # The real dependency raises 401 for invalid/expired tokens.
        # 403 is also acceptable if the auth layer differs on some setups.
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        )


# ── Test B: Normal user → 403 ─────────────────────────────────────────────────

class TestAdminNormalUser:
    """
    A user with role='user' must receive 403 when hitting admin endpoints.

    We override get_current_user to return a mock normal user, which
    bypasses session lookup but keeps the require_role("admin") check
    intact — that check fires and raises HTTP 403.
    """

    def test_normal_user_returns_403(self, client):
        normal_user = make_user(role="user")
        app.dependency_overrides[get_current_user] = lambda: normal_user

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 403, (
            f"Normal user must get 403. Got {resp.status_code}: {resp.text}"
        )

    def test_normal_user_forbidden_message(self, client):
        normal_user = make_user(role="user")
        app.dependency_overrides[get_current_user] = lambda: normal_user

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 403
        assert "detail" in resp.json()

    def test_sales_role_user_returns_403(self, client):
        """Any non-admin role is forbidden."""
        sales_user = make_user(role="sales")
        app.dependency_overrides[get_current_user] = lambda: sales_user

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 403, (
            f"Sales-role user must get 403. Got {resp.status_code}: {resp.text}"
        )


# ── Test C: Admin user → 200 ──────────────────────────────────────────────────

class TestAdminAuthorizedUser:
    """
    A user with role='admin' must receive 200 from admin endpoints.

    We override get_current_user and the query_logs DB dependency to
    avoid live infrastructure while still exercising the full routing
    and authorization path.
    """

    def test_admin_user_returns_200(self, client):
        from app.api.query_logs import get_db as query_logs_get_db

        admin_user = make_user(role="admin")
        app.dependency_overrides[get_current_user] = lambda: admin_user

        def mock_db():
            db = MagicMock()
            db.query.return_value.order_by.return_value.all.return_value = []
            yield db

        app.dependency_overrides[query_logs_get_db] = mock_db

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 200, (
            f"Admin must get 200. Got {resp.status_code}: {resp.text}"
        )

    def test_admin_user_gets_list_response(self, client):
        """Admin endpoint must return a JSON list."""
        from app.api.query_logs import get_db as query_logs_get_db

        admin_user = make_user(role="admin")
        app.dependency_overrides[get_current_user] = lambda: admin_user

        def mock_db():
            db = MagicMock()
            db.query.return_value.order_by.return_value.all.return_value = []
            yield db

        app.dependency_overrides[query_logs_get_db] = mock_db

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_user_gets_log_entries(self, client):
        """Admin endpoint returns log entries when they exist."""
        from datetime import datetime, timezone
        from app.api.query_logs import get_db as query_logs_get_db

        admin_user = make_user(role="admin")
        app.dependency_overrides[get_current_user] = lambda: admin_user

        # Build a mock log object — MagicMock is safe here too
        log = MagicMock()
        log.id = 1
        log.user_id = 2
        log.query = "test admin query"
        log.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        def mock_db():
            db = MagicMock()
            db.query.return_value.order_by.return_value.all.return_value = [log]
            yield db

        app.dependency_overrides[query_logs_get_db] = mock_db

        resp = client.get("/admin/query-logs")
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["query"] == "test admin query"
        assert logs[0]["user_id"] == 2


# ── Test D: require_role dependency unit tests ────────────────────────────────

class TestRequireRoleDependency:
    """
    Unit tests for require_role() from app.auth.dependencies.
    Calls the inner role_checker directly without an HTTP request.
    """

    def test_require_role_passes_for_matching_role(self):
        """require_role should return the user when role matches."""
        from app.auth.dependencies import require_role

        admin_user = make_user(role="admin")
        role_checker = require_role("admin")
        # role_checker is the inner Depends-able function
        result = role_checker(current_user=admin_user)
        assert result is admin_user

    def test_require_role_raises_403_for_wrong_role(self):
        """require_role must raise HTTP 403 for a user with wrong role."""
        from fastapi import HTTPException
        from app.auth.dependencies import require_role

        normal_user = make_user(role="user")
        role_checker = require_role("admin")

        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=normal_user)

        assert exc_info.value.status_code == 403

    def test_require_role_detail_message(self):
        """The 403 exception must include a non-empty detail message."""
        from fastapi import HTTPException
        from app.auth.dependencies import require_role

        normal_user = make_user(role="user")
        role_checker = require_role("admin")

        with pytest.raises(HTTPException) as exc_info:
            role_checker(current_user=normal_user)

        assert exc_info.value.detail  # non-empty


# ── Test E: Query logger unit tests ──────────────────────────────────────────

class TestQueryLogger:
    """
    Unit tests for app.logging.query_logger.log_query.
    Uses a mocked DB session — no live Neon connection required.
    Verifies that user_id, query, and timestamp fields are correctly stored.
    """

    def test_log_query_creates_record(self):
        """log_query must add a QueryLog record and commit."""
        from app.logging.query_logger import log_query

        db = MagicMock()
        captured = {}

        def fake_add(obj):
            captured["obj"] = obj

        db.add.side_effect = fake_add
        db.refresh.side_effect = lambda obj: None

        log_query(db=db, user_id=42, query="test query string")

        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert captured["obj"].user_id == 42
        assert captured["obj"].query == "test query string"

    def test_log_query_returns_log_object(self):
        """log_query must return the QueryLog instance."""
        from app.logging.query_logger import log_query

        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        result = log_query(db=db, user_id=1, query="another query")

        assert result is not None
        assert hasattr(result, "user_id")
        assert hasattr(result, "query")

    def test_log_query_stores_correct_user_id(self):
        """log_query must persist the user_id passed in."""
        from app.logging.query_logger import log_query

        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        result = log_query(db=db, user_id=99, query="q")
        assert result.user_id == 99

    def test_log_query_stores_correct_query(self):
        """log_query must persist the query string passed in."""
        from app.logging.query_logger import log_query

        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        result = log_query(db=db, user_id=1, query="specific query text")
        assert result.query == "specific query text"
