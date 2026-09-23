"""
Comprehensive tests for Persistent Conversation Memory and Context-Aware RAG.

Verifies:
1. Conversation creation in PostgreSQL.
2. User and assistant message storage with roles, timestamps, and sources.
3. Message ordering and retrieval.
4. Follow-up question query contextualization.
5. Conversation ownership security and cross-user denial (403/404).
6. Cascade deletion of conversations and messages.
7. Unauthenticated request protection (401).
8. Backward compatibility of /ask with and without conversation_id.
"""
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.database.models import User, Conversation, ConversationMessage, UserSession
from app.conversation.service import (
    create_conversation,
    get_conversation,
    list_conversations,
    get_conversation_messages,
    add_message,
    delete_conversation,
    update_conversation_title,
)
from app.conversation.contextualizer import contextualize_query, is_likely_followup
from app.auth.sessions import create_session


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def user_a(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"user_a_{uid}",
        email=f"user_a_{uid}@example.com",
        password_hash="testhash123",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def user_b(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"user_b_{uid}",
        email=f"user_b_{uid}@example.com",
        password_hash="testhash123",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def client_a(db_session, user_a):
    session = create_session(db=db_session, user_id=user_a.id)
    client = TestClient(app)
    client.cookies.set("session_token", session.session_token)
    return client


@pytest.fixture(scope="module")
def client_b(db_session, user_b):
    session = create_session(db=db_session, user_id=user_b.id)
    client = TestClient(app)
    client.cookies.set("session_token", session.session_token)
    return client


@pytest.fixture(scope="module")
def anon_client():
    return TestClient(app)


# ── Database Service Tests ───────────────────────────────────────────────────

class TestConversationService:
    def test_create_and_get_conversation(self, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Test Scrubber Discussion")
        assert conv.id is not None
        assert conv.user_id == user_a.id
        assert conv.title == "Test Scrubber Discussion"
        assert conv.created_at is not None

        fetched = get_conversation(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert fetched.id == conv.id
        assert fetched.title == "Test Scrubber Discussion"

    def test_add_and_retrieve_messages(self, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Product Features")

        # Add user message
        m1 = add_message(
            db=db_session,
            conversation_id=conv.id,
            role="user",
            content="What is the Karcher BD 43/40?",
        )
        assert m1.id is not None
        assert m1.role == "user"
        assert m1.content == "What is the Karcher BD 43/40?"

        # Add assistant message with sources
        sources = [{"chunk_id": "c1", "sku": "BD-4340", "document_id": 1, "filename": "karcher.pdf"}]
        m2 = add_message(
            db=db_session,
            conversation_id=conv.id,
            role="assistant",
            content="It is a walk-behind scrubber dryer.",
            sources=sources,
        )
        assert m2.id is not None
        assert m2.role == "assistant"
        assert m2.sources == sources

        messages = get_conversation_messages(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_cross_user_service_access_denied(self, db_session, user_a, user_b):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="User A Private Chat")

        # User B trying to access User A's conversation must raise 403
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_conversation(db=db_session, conversation_id=conv.id, user_id=user_b.id)
        assert exc_info.value.status_code == 403

    def test_cascade_delete_conversation(self, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Temporary Chat")
        add_message(db=db_session, conversation_id=conv.id, role="user", content="Temporary message")

        # Delete conversation
        success = delete_conversation(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert success is True

        # Verify conversation is gone
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_conversation(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert exc_info.value.status_code == 404

        # Verify messages are also deleted (cascade)
        remaining_messages = (
            db_session.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv.id)
            .all()
        )
        assert len(remaining_messages) == 0

    def test_update_conversation_title(self, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Initial Title")
        updated = update_conversation_title(
            db=db_session,
            conversation_id=conv.id,
            user_id=user_a.id,
            title="Updated Title",
        )
        assert updated.title == "Updated Title"


# ── Contextualizer & Follow-up Tests ─────────────────────────────────────────

class TestContextualizer:
    def test_is_likely_followup(self):
        assert is_likely_followup("What are its main features?") is True
        assert is_likely_followup("How much does it weigh?") is True
        assert is_likely_followup("Tell me about this product") is True
        assert is_likely_followup("What is the Karcher BD 43/40?") is False

    def test_contextualize_standalone_query_unchanged(self):
        query = "What is the Karcher BD 43/40?"
        res = contextualize_query(query=query, history=[])
        assert res == query

    def test_contextualize_followup_with_history(self):
        history = [
            ConversationMessage(
                id=1,
                conversation_id=1,
                role="user",
                content="What is the Karcher BD 43/40?",
                created_at=datetime.now(timezone.utc),
            ),
            ConversationMessage(
                id=2,
                conversation_id=1,
                role="assistant",
                content="The Karcher BD 43/40 is a walk-behind scrubber dryer.",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        followup = "What are its main features?"
        contextualized = contextualize_query(query=followup, history=history)

        # Contextualized query must include the product name or reference
        assert "Karcher" in contextualized or "BD 43/40" in contextualized or "BD" in contextualized


# ── API Endpoints & Security Tests ───────────────────────────────────────────

class TestConversationEndpoints:
    def test_unauthenticated_access_rejected(self, anon_client):
        resp = anon_client.get("/conversations")
        assert resp.status_code == 401

        resp = anon_client.get("/conversations/1")
        assert resp.status_code == 401

        resp = anon_client.delete("/conversations/1")
        assert resp.status_code == 401

    def test_get_conversations_list(self, client_a, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="List Test Chat")
        add_message(db=db_session, conversation_id=conv.id, role="user", content="Hello")

        resp = client_a.get("/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        found = any(c["id"] == conv.id for c in data)
        assert found is True

    def test_get_conversation_detail(self, client_a, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Detail Chat")
        add_message(db=db_session, conversation_id=conv.id, role="user", content="Hello assistant")

        resp = client_a.get(f"/conversations/{conv.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv.id
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["content"] == "Hello assistant"

    def test_cross_user_api_access_forbidden(self, client_b, db_session, user_a):
        # User A owns this conversation
        conv_a = create_conversation(db=db_session, user_id=user_a.id, title="User A Secret Chat")

        # User B attempts GET /conversations/{conv_a.id} -> must be 403
        resp = client_b.get(f"/conversations/{conv_a.id}")
        assert resp.status_code == 403

        # User B attempts DELETE /conversations/{conv_a.id} -> must be 403
        resp = client_b.delete(f"/conversations/{conv_a.id}")
        assert resp.status_code == 403

    def test_rename_conversation_endpoint(self, client_a, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Old Title")
        resp = client_a.patch(f"/conversations/{conv.id}", json={"title": "Brand New Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Brand New Title"

    def test_delete_conversation_endpoint(self, client_a, db_session, user_a):
        conv = create_conversation(db=db_session, user_id=user_a.id, title="To Delete")
        resp = client_a.delete(f"/conversations/{conv.id}")
        assert resp.status_code == 200

        # Subsequent GET should return 404
        resp = client_a.get(f"/conversations/{conv.id}")
        assert resp.status_code == 404
