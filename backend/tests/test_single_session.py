"""
tests/test_single_session.py

Tests for Option A: Single Active Session (Single Device / Last Login Wins).
Verifies that:
1. A user logging in gets an active session.
2. A subsequent login by the same user automatically terminates (deactivates) the prior session.
3. The old session is rejected with HTTP 401 informing the user that another device logged in.
4. The new session functions normally.
5. Logins by different users do not interfere with each other's active sessions.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.database.models import User, UserSession
from app.auth.services import hash_password


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_users(db_session):
    """Create two test users for single session verification."""
    uid = uuid.uuid4().hex[:6]
    pw_hash = hash_password("Password123!")

    user1 = User(
        username=f"rep_alpha_{uid}",
        email=f"alpha_{uid}@test.com",
        password_hash=pw_hash,
        role="SALESMAN",
        status="ACTIVE",
    )
    user2 = User(
        username=f"rep_beta_{uid}",
        email=f"beta_{uid}@test.com",
        password_hash=pw_hash,
        role="SALESMAN",
        status="ACTIVE",
    )
    db_session.add_all([user1, user2])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)

    yield user1, user2

    # Cleanup
    try:
        db_session.query(UserSession).filter(UserSession.user_id.in_([user1.id, user2.id])).delete()
        db_session.query(User).filter(User.id.in_([user1.id, user2.id])).delete()
        db_session.commit()
    except Exception:
        pass


class TestSingleActiveSession:
    def test_single_active_session_enforcement(self, client, db_session, test_users):
        user1, _ = test_users

        # 1. Device 1 logs in
        login_payload = {"username": user1.username, "password": "Password123!"}
        resp1 = client.post("/auth/login", json=login_payload)
        assert resp1.status_code == 200
        token_device1 = resp1.cookies.get("session_token")
        assert token_device1 is not None

        # Verify session 1 is active in DB
        s1 = db_session.query(UserSession).filter(UserSession.session_token == token_device1).first()
        assert s1 is not None
        assert s1.is_active is True

        # Device 1 can access /auth/me
        client.cookies.set("session_token", token_device1)
        me_resp1 = client.get("/auth/me")
        assert me_resp1.status_code == 200
        assert me_resp1.json()["username"] == user1.username

        # 2. Device 2 logs in with the SAME user credentials
        resp2 = client.post("/auth/login", json=login_payload)
        assert resp2.status_code == 200
        token_device2 = resp2.cookies.get("session_token")
        assert token_device2 is not None
        assert token_device2 != token_device1

        # Verify in DB: Session 1 is now DEACTIVATED (is_active = False), Session 2 is ACTIVE
        db_session.refresh(s1)
        assert s1.is_active is False, "Previous session was not deactivated upon new login!"

        s2 = db_session.query(UserSession).filter(UserSession.session_token == token_device2).first()
        assert s2 is not None
        assert s2.is_active is True

        # 3. Device 1 attempts to use the old session token -> MUST BE REJECTED with 401
        client.cookies.set("session_token", token_device1)
        stale_resp = client.get("/auth/me")
        assert stale_resp.status_code == 401
        assert "another device" in stale_resp.json()["detail"].lower()

        # 4. Device 2 uses the new session token -> MUST SUCCEED with 200
        client.cookies.set("session_token", token_device2)
        active_resp = client.get("/auth/me")
        assert active_resp.status_code == 200
        assert active_resp.json()["username"] == user1.username

    def test_different_users_do_not_invalidate_each_other(self, client, db_session, test_users):
        user1, user2 = test_users

        # User 1 logs in
        resp1 = client.post("/auth/login", json={"username": user1.username, "password": "Password123!"})
        assert resp1.status_code == 200
        token1 = resp1.cookies.get("session_token")

        # User 2 logs in
        resp2 = client.post("/auth/login", json={"username": user2.username, "password": "Password123!"})
        assert resp2.status_code == 200
        token2 = resp2.cookies.get("session_token")

        # User 1's session should STILL be active
        s1 = db_session.query(UserSession).filter(UserSession.session_token == token1).first()
        assert s1.is_active is True

        # User 2's session should also be active
        s2 = db_session.query(UserSession).filter(UserSession.session_token == token2).first()
        assert s2.is_active is True

        # Both can access /auth/me
        client.cookies.set("session_token", token1)
        assert client.get("/auth/me").status_code == 200

        client.cookies.set("session_token", token2)
        assert client.get("/auth/me").status_code == 200

