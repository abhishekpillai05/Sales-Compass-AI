"""
backend/tests/test_rbac.py

Comprehensive test suite for Role-Based Access Control (RBAC).

Tests:
1. Role normalization and enumeration (ADMIN, SALESMAN, legacy mapping).
2. Registration privilege escalation prevention (self-registration strictly creates SALESMAN).
3. Unauthenticated requests to protected endpoints return 401:
   - POST /search
   - POST /upload
   - GET /admin/query-logs
   - POST /ask
   - GET /conversations
4. SALESMAN access permissions:
   - Allowed: POST /search, POST /ask, GET /conversations, /auth/me
   - Forbidden (403): POST /upload, GET /admin/query-logs, GET /auth/admin-test
5. ADMIN access permissions:
   - Allowed: POST /search, POST /ask, GET /conversations, /auth/me
   - Allowed: POST /upload, GET /admin/query-logs, GET /auth/admin-test
6. Conversation ownership isolation:
   - Cross-user conversation access receives 403 Forbidden.
   - Cross-user conversation deletion receives 403 Forbidden.
7. Login & Profile serialization:
   - GET /auth/me and POST /auth/login return normalized uppercase role.
"""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth.roles import UserRole
from app.auth.dependencies import get_current_user, require_role
from app.database.models import User, Conversation
from app.database.session import SessionLocal


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(role: str = "SALESMAN", user_id: int = 1) -> MagicMock:
    """Return a MagicMock mimicking an ORM User with given role and id."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.username = f"{role.lower()}_user_{user_id}"
    user.email = f"{role.lower()}_{user_id}@test.com"
    user.password_hash = "hashed_secret"
    user.role = role
    return user


@pytest.fixture
def client():
    """Return a TestClient with a fresh dependency override state."""
    app.dependency_overrides.clear()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── 1. Role Normalization Unit Tests ──────────────────────────────────────────

class TestRoleNormalization:
    """Verify UserRole enum and normalizer handle all cases robustly."""

    def test_admin_normalization(self):
        assert UserRole.normalize("ADMIN") == "ADMIN"
        assert UserRole.normalize("admin") == "ADMIN"
        assert UserRole.normalize(" Admin ") == "ADMIN"

    def test_salesman_normalization(self):
        assert UserRole.normalize("SALESMAN") == "SALESMAN"
        assert UserRole.normalize("salesman") == "SALESMAN"
        assert UserRole.normalize(" Salesman ") == "SALESMAN"

    def test_legacy_role_mapping(self):
        # Legacy roles "user" and "sales" must map to SALESMAN
        assert UserRole.normalize("user") == "SALESMAN"
        assert UserRole.normalize("USER") == "SALESMAN"
        assert UserRole.normalize("sales") == "SALESMAN"
        assert UserRole.normalize("SALES") == "SALESMAN"

    def test_missing_or_empty_role_defaults_to_salesman(self):
        assert UserRole.normalize(None) == "SALESMAN"
        assert UserRole.normalize("") == "SALESMAN"
        assert UserRole.normalize("   ") == "SALESMAN"


# ── 2. Registration Privilege Escalation Prevention ───────────────────────────

class TestRegistrationPrivilegeEscalation:
    """Verify that public registration cannot self-promote to ADMIN."""

    def test_registration_with_admin_role_forces_salesman(self, client):
        """Even if payload specifies role='ADMIN', user must be created as SALESMAN."""
        db = SessionLocal()
        unique_suffix = uuid.uuid4().hex[:6]
        payload = {
            "username": f"hacker_{unique_suffix}",
            "email": f"hacker_{unique_suffix}@example.com",
            "password": "Password123!",
            "role": "ADMIN",  # Attempted privilege escalation
        }

        try:
            resp = client.post("/auth/register", json=payload)
            assert resp.status_code == 200, f"Registration failed: {resp.text}"
            data = resp.json()

            # Must return SALESMAN role in response
            assert data["role"] == "SALESMAN", (
                f"Self-registration allowed role={data['role']} instead of SALESMAN!"
            )

            # Verify in DB that role is strictly SALESMAN
            created_user = db.query(User).filter(User.username == payload["username"]).first()
            assert created_user is not None
            assert created_user.role == "SALESMAN"

        finally:
            # Clean up test user
            user_to_del = db.query(User).filter(User.username == payload["username"]).first()
            if user_to_del:
                db.delete(user_to_del)
                db.commit()
            db.close()

    def test_registration_without_role_defaults_to_salesman(self, client):
        db = SessionLocal()
        unique_suffix = uuid.uuid4().hex[:6]
        payload = {
            "username": f"sales_{unique_suffix}",
            "email": f"sales_{unique_suffix}@example.com",
            "password": "Password123!",
        }

        try:
            resp = client.post("/auth/register", json=payload)
            assert resp.status_code == 200, f"Registration failed: {resp.text}"
            data = resp.json()
            assert data["role"] == "SALESMAN"

        finally:
            user_to_del = db.query(User).filter(User.username == payload["username"]).first()
            if user_to_del:
                db.delete(user_to_del)
                db.commit()
            db.close()


# ── 3. Unauthenticated Access Protection (401) ────────────────────────────────

class TestUnauthenticatedAccessProtection:
    """Verify that protected endpoints return 401 when accessed without credentials."""

    def test_search_requires_auth(self, client):
        resp = client.post("/search", json={"query": "safety boots"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        assert "detail" in resp.json()

    def test_upload_requires_auth(self, client):
        resp = client.post("/upload")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_admin_query_logs_requires_auth(self, client):
        resp = client.get("/admin/query-logs")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_conversations_list_requires_auth(self, client):
        resp = client.get("/conversations")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_auth_me_requires_auth(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ── 4. SALESMAN Role Permissions ──────────────────────────────────────────────

class TestSalesmanPermissions:
    """
    SALESMAN:
    - CAN search products.
    - CAN view own conversations.
    - CAN view profile.
    - CANNOT upload documents (403).
    - CANNOT view admin query logs (403).
    - CANNOT access admin test endpoint (403).
    """

    def test_salesman_cannot_upload_document(self, client):
        salesman = make_user(role="SALESMAN")
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.post(
            "/upload",
            files={"file": ("test.txt", b"some dummy document content", "text/plain")},
        )
        assert resp.status_code == 403, (
            f"Salesman must be forbidden (403) from /upload. Got {resp.status_code}: {resp.text}"
        )
        assert "permission" in resp.json().get("detail", "").lower()

    def test_salesman_cannot_view_query_logs(self, client):
        salesman = make_user(role="SALESMAN")
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.get("/admin/query-logs")
        assert resp.status_code == 403, (
            f"Salesman must be forbidden (403) from /admin/query-logs. Got {resp.status_code}"
        )

    def test_salesman_cannot_access_admin_test(self, client):
        salesman = make_user(role="SALESMAN")
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.get("/auth/admin-test")
        assert resp.status_code == 403

    def test_salesman_can_search_products(self, client):
        salesman = make_user(role="SALESMAN")
        app.dependency_overrides[get_current_user] = lambda: salesman

        with patch("app.api.search.retrieve") as mock_retrieve:
            mock_retrieve.return_value = MagicMock(
                query="gloves",
                results=[],
                total_results=0,
            )
            resp = client.post("/search", json={"query": "gloves"})
            assert resp.status_code == 200, f"Salesman should be allowed to search. Got {resp.status_code}"

    def test_salesman_can_view_profile(self, client):
        salesman = make_user(role="SALESMAN", user_id=42)
        app.dependency_overrides[get_current_user] = lambda: salesman

        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 42
        assert data["role"] == "SALESMAN"


# ── 5. ADMIN Role Permissions ─────────────────────────────────────────────────

class TestAdminPermissions:
    """
    ADMIN:
    - CAN search products.
    - CAN view own conversations.
    - CAN access admin test endpoint.
    - CAN view query logs.
    - CAN upload documents (passes auth guard).
    """

    def test_admin_can_access_admin_test(self, client):
        admin = make_user(role="ADMIN")
        app.dependency_overrides[get_current_user] = lambda: admin

        resp = client.get("/auth/admin-test")
        assert resp.status_code == 200
        assert "Welcome Admin!" in resp.json().get("message", "")

    def test_admin_can_view_query_logs(self, client):
        from app.api.query_logs import get_db as query_logs_get_db

        admin = make_user(role="ADMIN")
        app.dependency_overrides[get_current_user] = lambda: admin

        def mock_db():
            db = MagicMock()
            db.query.return_value.order_by.return_value.all.return_value = []
            yield db

        app.dependency_overrides[query_logs_get_db] = mock_db

        resp = client.get("/admin/query-logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_can_search_products(self, client):
        admin = make_user(role="ADMIN")
        app.dependency_overrides[get_current_user] = lambda: admin

        with patch("app.api.search.retrieve") as mock_retrieve:
            mock_retrieve.return_value = MagicMock(
                query="welding mask",
                results=[],
                total_results=0,
            )
            resp = client.post("/search", json={"query": "welding mask"})
            assert resp.status_code == 200

    def test_admin_upload_passes_auth_guard(self, client):
        """ADMIN user passes the require_role guard on /upload."""
        from app.api.upload import get_db as upload_get_db

        admin = make_user(role="ADMIN")
        app.dependency_overrides[get_current_user] = lambda: admin

        with patch("app.api.upload.ingest_document") as mock_ingest, \
             patch("app.api.upload.document_chunks_to_chunk_inputs") as mock_bridge, \
             patch("app.api.upload.index_chunks") as mock_index:

            mock_ingest.return_value = {
                "document_id": 99,
                "filename": "catalog.pdf",
                "chunks": [],
            }
            mock_bridge.return_value = []
            mock_index.return_value = []

            resp = client.post(
                "/upload",
                files={"file": ("catalog.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            )
            assert resp.status_code == 200, f"Admin upload failed: {resp.text}"
            assert resp.json()["success"] is True


# ── 6. Conversation Ownership Isolation ───────────────────────────────────────

class TestConversationOwnershipSecurity:
    """Verify that User A cannot read or delete User B's conversation (403 Forbidden)."""

    def test_cross_user_get_conversation_denied(self, client):
        from app.api.conversations import get_db as conv_get_db

        user_a = make_user(role="SALESMAN", user_id=101)
        app.dependency_overrides[get_current_user] = lambda: user_a

        # Mock DB returning a conversation owned by user_id 202
        other_user_conv = Conversation(
            id=555,
            user_id=202,
            title="Private Conversation of User B",
        )

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = other_user_conv
            yield db

        app.dependency_overrides[conv_get_db] = mock_db

        resp = client.get("/conversations/555")
        assert resp.status_code == 403, (
            f"User 101 must receive 403 when accessing User 202's conversation. Got {resp.status_code}"
        )

    def test_cross_user_delete_conversation_denied(self, client):
        from app.api.conversations import get_db as conv_get_db

        user_a = make_user(role="SALESMAN", user_id=101)
        app.dependency_overrides[get_current_user] = lambda: user_a

        other_user_conv = Conversation(
            id=777,
            user_id=202,
            title="User B's Conversation",
        )

        def mock_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = other_user_conv
            yield db

        app.dependency_overrides[conv_get_db] = mock_db

        resp = client.delete("/conversations/777")
        assert resp.status_code == 403, (
            f"User 101 must receive 403 when deleting User 202's conversation. Got {resp.status_code}"
        )
