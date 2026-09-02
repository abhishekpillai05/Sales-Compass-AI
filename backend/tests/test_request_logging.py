"""
tests/test_request_logging.py

Phase 9 — Logging & Testing

Tests for:
  - Request ID generation and propagation (X-Request-ID header)
  - HTTP request logging middleware behaviour
  - Sensitive-data absence from logs
  - Error handling: correct status codes, no secret leakage
  - Existing endpoint accessibility (regression guard)

All tests use FastAPI TestClient with dependency overrides where live
infrastructure (DB, Qdrant) would be required.  No real network calls.
"""

import logging
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user


# ── Helper ────────────────────────────────────────────────────────────────────

def make_mock_user(role: str = "user") -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.username = f"{role}_user"
    user.email = f"{role}@test.com"
    user.role = role
    user.password_hash = "hashed"
    return user


@pytest.fixture
def client():
    """TestClient with clean dependency overrides."""
    app.dependency_overrides.clear()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client():
    """TestClient with get_current_user overridden to a mock normal user."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: make_mock_user("user")
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client():
    """TestClient with get_current_user overridden to a mock admin user."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: make_mock_user("admin")
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


# ── 1. Request ID — auto-generation ──────────────────────────────────────────

class TestRequestIDGeneration:
    """Every response must carry X-Request-ID."""

    def test_response_contains_x_request_id(self, client):
        resp = client.get("/")
        assert "x-request-id" in resp.headers, (
            "X-Request-ID must always be present in response headers"
        )

    def test_auto_generated_request_id_is_valid_uuid(self, client):
        resp = client.get("/")
        rid = resp.headers.get("x-request-id", "")
        try:
            uuid.UUID(rid)
        except ValueError:
            pytest.fail(f"Auto-generated X-Request-ID is not a valid UUID: {rid!r}")

    def test_each_request_gets_unique_id(self, client):
        r1 = client.get("/")
        r2 = client.get("/")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"], (
            "Each request must receive a distinct request ID"
        )


# ── 2. Request ID — client-supplied header propagation ───────────────────────

class TestRequestIDPropagation:
    """A client-supplied X-Request-ID must be echoed back unchanged."""

    def test_supplied_request_id_is_preserved(self, client):
        custom_id = str(uuid.uuid4())
        resp = client.get("/", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id, (
            f"Expected echoed X-Request-ID={custom_id!r}, "
            f"got {resp.headers.get('x-request-id')!r}"
        )

    def test_custom_id_survives_on_4xx(self, client):
        """Request ID must be present even on error responses."""
        custom_id = str(uuid.uuid4())
        resp = client.get("/admin/query-logs", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id

    def test_custom_id_survives_on_unauthenticated(self, client):
        custom_id = str(uuid.uuid4())
        # /ask requires auth → 401
        resp = client.post(
            "/ask",
            json={"query": "test"},
            headers={"X-Request-ID": custom_id},
        )
        assert resp.status_code == 401
        assert resp.headers.get("x-request-id") == custom_id


# ── 3. Middleware logs correct fields ─────────────────────────────────────────

class TestRequestLoggingContent:
    """Verify the middleware actually writes log records with expected fields."""

    def test_request_log_contains_method(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
            client.get("/")
        assert any("GET" in record.message for record in caplog.records), (
            "Log must include HTTP method"
        )

    def test_request_log_contains_path(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
            client.get("/")
        assert any("/" in record.message for record in caplog.records), (
            "Log must include request path"
        )

    def test_request_log_contains_status_code(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
            client.get("/")
        assert any("200" in record.message for record in caplog.records), (
            "Log must include HTTP status code"
        )

    def test_request_log_contains_duration(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
            client.get("/")
        assert any("duration" in record.message for record in caplog.records), (
            "Log must include request duration"
        )

    def test_request_log_contains_request_id(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="app.middleware.request_logging"):
            client.get("/")
        assert any("request_id" in record.message for record in caplog.records), (
            "Log must include request_id"
        )


# ── 4. Security — secrets must NOT appear in logs ────────────────────────────

class TestSensitiveDataNotLogged:
    """
    Sensitive values must never appear in log output.

    We capture logs at DEBUG level to be maximally strict.
    """

    def _all_log_messages(self, caplog) -> str:
        return " ".join(record.message for record in caplog.records)

    def test_password_not_in_logs_on_login(self, client, caplog):
        secret_password = "SuperSecret_P@ssw0rd_2024"
        with caplog.at_level(logging.DEBUG):
            client.post(
                "/auth/login",
                json={"username": "testuser", "password": secret_password},
            )
        assert secret_password not in self._all_log_messages(caplog), (
            "Plain-text password must NEVER appear in logs"
        )

    def test_password_not_in_logs_on_register(self, client, caplog):
        secret_password = "Reg!sterMe_2024"
        with caplog.at_level(logging.DEBUG):
            client.post(
                "/auth/register",
                json={
                    "username": "newuser_log_test",
                    "email": "newuser@test.com",
                    "password": secret_password,
                    "role": "user",
                },
            )
        assert secret_password not in self._all_log_messages(caplog), (
            "Plain-text password from registration must NEVER appear in logs"
        )

    def test_authorization_header_not_in_logs(self, client, caplog):
        bearer_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake"
        with caplog.at_level(logging.DEBUG):
            client.get("/auth/me", headers={"Authorization": bearer_token})
        assert bearer_token not in self._all_log_messages(caplog), (
            "Authorization header value must NEVER appear in logs"
        )

    def test_session_cookie_value_not_in_logs(self, client, caplog):
        fake_token = "totally_secret_session_token_xyz_abc_123"
        with caplog.at_level(logging.DEBUG):
            client.get("/auth/me", cookies={"session_token": fake_token})
        assert fake_token not in self._all_log_messages(caplog), (
            "Session token cookie value must NEVER appear in logs"
        )

    def test_api_key_header_not_in_logs(self, client, caplog):
        fake_key = "sk-groq-fakekeyvalue_do_not_log_this"
        with caplog.at_level(logging.DEBUG):
            client.get("/", headers={"X-API-Key": fake_key})
        assert fake_key not in self._all_log_messages(caplog), (
            "API key header value must NEVER appear in logs"
        )


# ── 5. Error handling ─────────────────────────────────────────────────────────

class TestErrorHandling:
    """Failed requests must return correct status codes without leaking secrets."""

    def test_unauthenticated_ask_returns_401(self, client):
        resp = client.post("/ask", json={"query": "test question"})
        assert resp.status_code == 401

    def test_unauthenticated_ask_has_detail_field(self, client):
        resp = client.post("/ask", json={"query": "test question"})
        assert "detail" in resp.json()

    def test_unauthenticated_ask_has_request_id(self, client):
        resp = client.post("/ask", json={"query": "test question"})
        assert "x-request-id" in resp.headers

    def test_admin_forbidden_returns_403(self, auth_client):
        resp = auth_client.get("/admin/query-logs")
        assert resp.status_code == 403

    def test_admin_forbidden_has_request_id(self, auth_client):
        resp = auth_client.get("/admin/query-logs")
        assert "x-request-id" in resp.headers

    def test_admin_forbidden_has_detail(self, auth_client):
        resp = auth_client.get("/admin/query-logs")
        assert "detail" in resp.json()

    def test_not_found_has_request_id(self, client):
        resp = client.get("/this-endpoint-does-not-exist")
        assert "x-request-id" in resp.headers

    def test_error_response_does_not_expose_database_url(self, client, caplog):
        """DATABASE_URL must never appear in any log output."""
        import os
        db_url = os.getenv("DATABASE_URL", "")
        with caplog.at_level(logging.DEBUG):
            client.get("/")
        all_messages = " ".join(r.message for r in caplog.records)
        if db_url:
            assert db_url not in all_messages, (
                "DATABASE_URL must not be logged"
            )


# ── 6. Existing endpoint regression guard ────────────────────────────────────

class TestExistingEndpointsStillWork:
    """
    Smoke check that Phase 9 additions did not break existing routing.
    Uses TestClient with dependency overrides — no live infra required.
    """

    def test_root_endpoint_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_returns_message(self, client):
        resp = client.get("/")
        assert "message" in resp.json()

    def test_auth_register_endpoint_exists(self, client):
        """POST /auth/register must be routed (400 = validation, not 404/405)."""
        resp = client.post("/auth/register", json={})
        assert resp.status_code != 404, "/auth/register must be registered"
        assert resp.status_code != 405, "/auth/register must accept POST"

    def test_auth_login_endpoint_exists(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code != 404
        assert resp.status_code != 405

    def test_auth_me_requires_auth(self, client):
        """GET /auth/me with no cookie must return 401, not 404."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_auth_logout_endpoint_exists(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code in (200, 204)

    def test_search_endpoint_exists(self, client):
        """POST /search must be routed (422 = missing body, not 404/405)."""
        resp = client.post("/search", json={})
        assert resp.status_code != 404
        assert resp.status_code != 405

    def test_upload_endpoint_exists(self, client):
        """POST /upload must be routed (422 = missing file, not 404/405)."""
        resp = client.post("/upload")
        assert resp.status_code != 404
        assert resp.status_code != 405

    def test_ask_endpoint_requires_auth(self, client):
        """POST /ask with no auth must return 401, not 404."""
        resp = client.post("/ask", json={"query": "test"})
        assert resp.status_code == 401

    def test_admin_query_logs_requires_auth(self, client):
        """GET /admin/query-logs with no auth must return 401, not 404."""
        resp = client.get("/admin/query-logs")
        assert resp.status_code == 401


# ── 7. Logging configuration ──────────────────────────────────────────────────

class TestLoggingConfiguration:
    """Verify the centralized logging module behaves correctly."""

    def test_get_logger_returns_logger(self):
        from app.logging.config import get_logger
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_name_matches(self):
        from app.logging.config import get_logger
        logger = get_logger("test.exact.name")
        assert logger.name == "test.exact.name"

    def test_configure_logging_is_idempotent(self):
        """Calling configure_logging() twice must not raise or duplicate handlers."""
        from app.logging.config import configure_logging
        configure_logging()
        configure_logging()  # second call should be a no-op

    def test_log_level_env_respected(self, monkeypatch):
        """configure_logging reads LOG_LEVEL from environment."""
        import logging as _logging
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        # Reset root handlers to force reconfiguration
        root = _logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers = []
        try:
            from app.logging import config as lc
            lc.configure_logging()
            assert root.level == _logging.WARNING
        finally:
            # Restore original handlers
            root.handlers = original_handlers
            root.setLevel(_logging.INFO)


# ── 8. Query logger preserved (Phase 7 regression) ───────────────────────────

class TestQueryLoggerPreserved:
    """Ensure Phase 7 query logging still works after Phase 9 additions."""

    def test_log_query_still_creates_record(self):
        from app.logging.query_logger import log_query

        db = MagicMock()
        db.refresh.side_effect = lambda obj: None
        captured = {}

        def fake_add(obj):
            captured["obj"] = obj

        db.add.side_effect = fake_add

        log_query(db=db, user_id=7, query="Phase 9 regression check")

        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert captured["obj"].user_id == 7
        assert captured["obj"].query == "Phase 9 regression check"

    def test_log_query_returns_object(self):
        from app.logging.query_logger import log_query

        db = MagicMock()
        db.refresh.side_effect = lambda obj: None

        result = log_query(db=db, user_id=1, query="check return")
        assert result is not None
        assert hasattr(result, "user_id")
        assert hasattr(result, "query")
