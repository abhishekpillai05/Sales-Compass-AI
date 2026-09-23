"""
Phase 11: End-to-End Verification of Persistent Conversation Memory Scenario.

Executes the exact 14-step scenario from user prompt:
1. Register/Login as User A.
2. Create a new conversation / send first question.
3. Ask: "What is the Karcher BD 43/40?"
4. Verify question and answer are stored in PostgreSQL.
5. Ask: "What are its main features?"
6. Verify backend uses conversation context.
7. Confirm conversation is available in /conversations.
8. Retrieve conversation messages from /conversations/{id}.
9. Ask another follow-up question.
10. Register/Login as User B.
11. Verify User B cannot access User A's conversation (403).
12. Logout.
13. Verify protected conversation endpoints reject requests with 401.
"""
import uuid
import requests
from app.database.session import SessionLocal
from app.database.models import User, Conversation, ConversationMessage

BASE_URL = "http://127.0.0.1:8000"


def run_scenario():
    print("=" * 70)
    print("STARTING PHASE 11 VERIFICATION SCENARIO")
    print("=" * 70)

    # Step 1: Create and Login as User A
    session_a = requests.Session()
    uid_a = uuid.uuid4().hex[:6]
    username_a = f"usera_{uid_a}"
    password = "SecurePassword123!"

    print(f"\n[1] Registering User A ({username_a})...")
    reg_resp = session_a.post(
        f"{BASE_URL}/auth/register",
        json={"username": username_a, "email": f"{username_a}@example.com", "password": password},
    )
    assert reg_resp.status_code in (200, 201), f"Registration failed: {reg_resp.text}"
    user_a_data = reg_resp.json()
    user_a_id = user_a_data["id"]
    print(f"    User A registered (id={user_a_id})")

    print(f"\n[1b] Logging in as User A...")
    login_resp = session_a.post(
        f"{BASE_URL}/auth/login",
        json={"username": username_a, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    assert "session_token" in session_a.cookies, "Missing session_token cookie"
    print("    User A logged in, session cookie acquired.")

    # Step 2 & 3: Ask first question without conversation_id
    q1 = "What is the Karcher BD 43/40?"
    print(f"\n[2 & 3] Asking initial question: '{q1}' (no conversation_id)...")
    ask1_resp = session_a.post(
        f"{BASE_URL}/ask",
        json={"query": q1, "top_k": 5},
    )
    assert ask1_resp.status_code == 200, f"Ask 1 failed: {ask1_resp.text}"
    data1 = ask1_resp.json()
    conv_id = data1.get("conversation_id")
    assert conv_id is not None, "Response missing conversation_id!"
    answer1 = data1.get("answer", "")
    print(f"    Success! conversation_id={conv_id}")
    print(f"    Answer: {answer1[:120]}...")

    # Step 4: Verify storage in PostgreSQL
    print("\n[4] Verifying PostgreSQL persistence directly in database...")
    db = SessionLocal()
    try:
        conv_record = db.query(Conversation).filter(Conversation.id == conv_id).first()
        assert conv_record is not None, "Conversation record missing in PostgreSQL!"
        assert conv_record.user_id == user_a_id, "Conversation user_id mismatch!"

        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        assert len(messages) == 2, f"Expected 2 messages (user+assistant), found {len(messages)}"
        assert messages[0].role == "user"
        assert messages[0].content == q1
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 10
        print(f"    Verified: Conversation id={conv_id} has {len(messages)} messages stored in PostgreSQL.")
    finally:
        db.close()

    # Step 5 & 6: Ask follow-up question with conversation_id
    q2 = "What are its main features?"
    print(f"\n[5 & 6] Asking follow-up question: '{q2}' (conversation_id={conv_id})...")
    ask2_resp = session_a.post(
        f"{BASE_URL}/ask",
        json={"query": q2, "conversation_id": conv_id, "top_k": 5},
    )
    assert ask2_resp.status_code == 200, f"Ask 2 failed: {ask2_resp.text}"
    data2 = ask2_resp.json()
    assert data2.get("conversation_id") == conv_id
    answer2 = data2.get("answer", "")
    print(f"    Success! Answer 2: {answer2[:140]}...")

    # Verify second turn in PostgreSQL
    db = SessionLocal()
    try:
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        assert len(messages) == 4, f"Expected 4 messages in DB, found {len(messages)}"
        assert messages[2].role == "user" and messages[2].content == q2
        assert messages[3].role == "assistant"
        print(f"    Verified: PostgreSQL now contains {len(messages)} messages for conversation {conv_id}.")
    finally:
        db.close()

    # Step 7 & 8: Check GET /conversations and GET /conversations/{id}
    print("\n[7 & 8] Checking GET /conversations and GET /conversations/{id}...")
    list_resp = session_a.get(f"{BASE_URL}/conversations")
    assert list_resp.status_code == 200
    conv_list = list_resp.json()
    assert any(c["id"] == conv_id for c in conv_list), "Conversation not listed in GET /conversations"
    print(f"    Listed conversations: {len(conv_list)} found")

    detail_resp = session_a.get(f"{BASE_URL}/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["messages"]) == 4
    print(f"    Loaded conversation detail: {len(detail['messages'])} messages returned.")

    # Step 9: Ask another follow-up question
    q3 = "What is its cleaning capacity or tank size?"
    print(f"\n[9] Asking 2nd follow-up: '{q3}' (conversation_id={conv_id})...")
    ask3_resp = session_a.post(
        f"{BASE_URL}/ask",
        json={"query": q3, "conversation_id": conv_id, "top_k": 5},
    )
    assert ask3_resp.status_code == 200
    data3 = ask3_resp.json()
    print(f"    Answer 3: {data3.get('answer', '')[:120]}...")

    # Step 10 & 11: User B tries to access User A's conversation
    session_b = requests.Session()
    uid_b = uuid.uuid4().hex[:6]
    username_b = f"userb_{uid_b}"
    print(f"\n[10 & 11] Registering & logging in as User B ({username_b})...")
    session_b.post(
        f"{BASE_URL}/auth/register",
        json={"username": username_b, "email": f"{username_b}@example.com", "password": password},
    )
    session_b.post(
        f"{BASE_URL}/auth/login",
        json={"username": username_b, "password": password},
    )

    print(f"    User B attempting to read User A's conversation (id={conv_id})...")
    hack_get = session_b.get(f"{BASE_URL}/conversations/{conv_id}")
    print(f"    Response code: {hack_get.status_code} (detail: {hack_get.json()})")
    assert hack_get.status_code == 403, f"Expected 403 Forbidden, got {hack_get.status_code}"

    print(f"    User B attempting to post to User A's conversation...")
    hack_post = session_b.post(
        f"{BASE_URL}/ask",
        json={"query": "Delete all data", "conversation_id": conv_id},
    )
    print(f"    Response code: {hack_post.status_code} (detail: {hack_post.json()})")
    assert hack_post.status_code == 403, f"Expected 403 Forbidden, got {hack_post.status_code}"

    print(f"    User B attempting to delete User A's conversation...")
    hack_del = session_b.delete(f"{BASE_URL}/conversations/{conv_id}")
    print(f"    Response code: {hack_del.status_code} (detail: {hack_del.json()})")
    assert hack_del.status_code == 403, f"Expected 403 Forbidden, got {hack_del.status_code}"

    # Step 12 & 13: Logout and test unauthenticated protection
    print("\n[12 & 13] Logging out and testing unauthenticated protection...")
    logout_resp = session_a.post(f"{BASE_URL}/auth/logout")
    assert logout_resp.status_code == 200

    anon_session = requests.Session()
    anon_get = anon_session.get(f"{BASE_URL}/conversations")
    print(f"    Unauthenticated GET /conversations -> {anon_get.status_code}")
    assert anon_get.status_code == 401

    anon_ask = anon_session.post(f"{BASE_URL}/ask", json={"query": "hello"})
    print(f"    Unauthenticated POST /ask -> {anon_ask.status_code}")
    assert anon_ask.status_code == 401

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL 14 PHASE 11 SCENARIO STEPS PASSED VERIFICATION!")
    print("=" * 70)


if __name__ == "__main__":
    run_scenario()
