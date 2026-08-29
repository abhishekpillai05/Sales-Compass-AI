"""
End-to-end smoke test for SalesCompass AI Phase 1-7.

Tests the complete flow:
  register -> login -> upload -> search -> ask (skipped if no GROQ) -> query-logs

Run from: backend/ as: python smoke_test.py
"""
import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

BASE = "http://127.0.0.1:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

session = requests.Session()
results = {}
test_username = "smoketest_user_v7"
test_email = "smoketest_v7@salescompass.ai"
test_password = "SmokeTe$t2024!"

def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    msg = f"  {status} {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    results[label] = "PASS" if condition else "FAIL"
    return condition

# ── 0. Health check ───────────────────────────────────────────────────────────
print("\n=== 0. Health Check ===")
try:
    r = requests.get(f"{BASE}/", timeout=5)
    check("GET /", r.status_code == 200, r.json().get("message", ""))
    # Verify routes in OpenAPI
    r2 = requests.get(f"{BASE}/openapi.json", timeout=5)
    paths = list(r2.json().get("paths", {}).keys()) if r2.ok else []
    required_routes = ["/upload", "/search", "/auth/register", "/auth/login", "/ask", "/admin/query-logs"]
    for route in required_routes:
        found = any(p.startswith(route) for p in paths)
        check(f"Route {route} registered", found)
except Exception as e:
    check("Server reachable", False, str(e))
    print("Cannot reach server. Exiting.")
    sys.exit(1)

# ── 1. Register ───────────────────────────────────────────────────────────────
print("\n=== 1. Auth: Register ===")
try:
    r = session.post(f"{BASE}/auth/register", json={
        "username": test_username,
        "email": test_email,
        "password": test_password,
        "role": "user"
    }, timeout=30)
    if r.status_code == 200:
        check("POST /auth/register (new user)", True, f"user_id={r.json().get('id')}")
    elif r.status_code == 400 and "already" in r.text.lower():
        check("POST /auth/register (already exists - ok)", True, "user pre-exists, continuing")
    else:
        check("POST /auth/register", False, f"{r.status_code}: {r.text[:200]}")
except Exception as e:
    check("POST /auth/register", False, str(e))

# ── 2. Login ──────────────────────────────────────────────────────────────────
print("\n=== 2. Auth: Login ===")
session_token = None
try:
    r = session.post(f"{BASE}/auth/login", json={
        "username": test_username,
        "password": test_password
    }, timeout=30)
    ok = r.status_code == 200
    check("POST /auth/login (status 200)", ok, r.text[:100] if not ok else "")
    if ok:
        data = r.json()
        session_token = data.get("session_token") or data.get("token")
        # Check if cookie was set
        cookie_token = session.cookies.get("session_token")
        check("session_token in response or cookie", bool(session_token or cookie_token),
              f"token={'set' if session_token else 'not in body'}, cookie={'set' if cookie_token else 'not set'}")
        if cookie_token:
            session_token = cookie_token
        elif session_token:
            session.cookies.set("session_token", session_token)
except Exception as e:
    check("POST /auth/login", False, str(e))

# ── 3. Authenticated /auth/me ─────────────────────────────────────────────────
print("\n=== 3. Auth: /me ===")
try:
    r = session.get(f"{BASE}/auth/me", timeout=10)
    ok = r.status_code == 200
    check("GET /auth/me (authenticated)", ok,
          f"username={r.json().get('username')}" if ok else f"{r.status_code}: {r.text[:100]}")
except Exception as e:
    check("GET /auth/me", False, str(e))

# ── 4. Upload document ────────────────────────────────────────────────────────
print("\n=== 4. Phase 3+4: Upload & Index ===")
# Create a minimal test CSV
test_csv_content = b"sku,category,manufacturer,description\nTEST-001,Cleaning,Karcher,Karcher BD 43/40 walk-behind scrubber-dryer 43 litre tank\nTEST-002,Vacuum,Karcher,Karcher NT 40/1 wet and dry vacuum cleaner 40 litre\n"
chunk_count = 0
indexed_count = 0
try:
    files = {"file": ("smoke_test.csv", test_csv_content, "text/csv")}
    r = session.post(f"{BASE}/upload", files=files, timeout=60)
    ok = r.status_code == 200
    if ok:
        data = r.json()
        chunk_count = data.get("chunks_created", 0)
        indexed_count = data.get("chunks_indexed", 0)
        index_failed = data.get("chunks_index_failed", 0)
        indexing_errors = data.get("indexing_errors", [])
        check("POST /upload (status 200)", True)
        check("Phase 3: chunks created", chunk_count > 0, f"{chunk_count} chunks")
        check("Phase 4: chunks indexed to Qdrant+PG", indexed_count > 0,
              f"{indexed_count} indexed, {index_failed} failed")
        if indexing_errors:
            for ie in indexing_errors:
                print(f"    Indexing error: chunk_id={ie.get('chunk_id')} -> {ie.get('error', '')}[:200]")
    else:
        check("POST /upload", False, f"{r.status_code}: {r.text[:300]}")
except Exception as e:
    check("POST /upload", False, str(e))

# ── 5. Phase 5: Search ────────────────────────────────────────────────────────
print("\n=== 5. Phase 5: Retrieval (/search) ===")
try:
    r = session.post(f"{BASE}/search", json={
        "query": "walk-behind scrubber dryer cleaning machine",
        "top_k": 3,
        "score_threshold": 0.0
    }, timeout=30)
    ok = r.status_code == 200
    if ok:
        data = r.json()
        results_count = data.get("total_results", 0)
        check("POST /search (status 200)", True)
        check("Phase 5: results returned", results_count > 0, f"{results_count} chunks retrieved")
        if results_count > 0:
            first = data["results"][0]
            check("chunk has chunk_id", bool(first.get("chunk_id")))
            check("chunk has text", bool(first.get("text")))
            check("chunk has score", "score" in first)
    else:
        check("POST /search", False, f"{r.status_code}: {r.text[:300]}")
except Exception as e:
    check("POST /search", False, str(e))

# ── 6. Phase 5+6: /ask ────────────────────────────────────────────────────────
print("\n=== 6. Phase 5+6: Generation (/ask) ===")
groq_key = os.getenv("GROQ_API_KEY", "")
if not groq_key:
    print(f"  {SKIP} -- GROQ_API_KEY not set; skipping /ask test")
    results["POST /ask"] = "SKIP"
else:
    try:
        r = session.post(f"{BASE}/ask", json={
            "query": "What is the Karcher BD 43/40 used for?",
            "top_k": 3,
            "score_threshold": 0.0
        }, timeout=60)
        ok = r.status_code == 200
        if ok:
            data = r.json()
            check("POST /ask (status 200)", True)
            check("answer returned", bool(data.get("answer")), data.get("answer", "")[:80])
            check("sources returned", isinstance(data.get("sources"), list))
        else:
            check("POST /ask", False, f"{r.status_code}: {r.text[:300]}")
    except Exception as e:
        check("POST /ask", False, str(e))

# ── 7. Phase 7: Admin Query Logs — 3-case authorization test ─────────────────
print("\n=== 7. Phase 7: Admin Authorization (3 cases) ===")

# Case A — Unauthenticated → 401/403
try:
    anon = requests.get(f"{BASE}/admin/query-logs", timeout=10)
    check("GET /admin/query-logs unauthenticated (expect 401/403)",
          anon.status_code in (401, 403),
          f"got {anon.status_code}")
except Exception as e:
    check("GET /admin/query-logs unauthenticated", False, str(e))

# Case B — Normal authenticated user → 403
# The `session` object already holds a valid session_token for the normal user
# (smoketest_user_v7 with role='user') from the login step above.
try:
    r_normal = session.get(f"{BASE}/admin/query-logs", timeout=10)
    check("GET /admin/query-logs normal user (expect 403)",
          r_normal.status_code == 403,
          f"got {r_normal.status_code}")
except Exception as e:
    check("GET /admin/query-logs normal user (expect 403)", False, str(e))

# Case C — Admin authenticated user → 200
# Create (or reuse) an admin user and use a fresh session.
admin_session = requests.Session()
admin_username = "smoketest_admin_v7"
admin_email = "smoketest_admin_v7@salescompass.ai"
admin_password = "Adm!nSm0keT3st!"

try:
    # Register admin user (ok if already exists)
    r_reg = admin_session.post(f"{BASE}/auth/register", json={
        "username": admin_username,
        "email": admin_email,
        "password": admin_password,
        "role": "admin"
    }, timeout=30)
    admin_registered = r_reg.status_code == 200 or (
        r_reg.status_code == 400 and "already" in r_reg.text.lower()
    )
    if not admin_registered:
        check("Admin user register/exists", False, f"{r_reg.status_code}: {r_reg.text[:200]}")
    else:
        # Login as admin
        r_login = admin_session.post(f"{BASE}/auth/login", json={
            "username": admin_username,
            "password": admin_password
        }, timeout=30)
        if r_login.status_code != 200:
            check("Admin login", False, f"{r_login.status_code}: {r_login.text[:100]}")
        else:
            # Ensure cookie is in admin_session
            cookie_token = admin_session.cookies.get("session_token")
            body_token = r_login.json().get("session_token") or r_login.json().get("token")
            if not cookie_token and body_token:
                admin_session.cookies.set("session_token", body_token)

            # Hit admin endpoint as admin
            r_admin = admin_session.get(f"{BASE}/admin/query-logs", timeout=15)
            check("GET /admin/query-logs admin user (expect 200)",
                  r_admin.status_code == 200,
                  f"got {r_admin.status_code}, logs={len(r_admin.json()) if r_admin.ok else 'N/A'}")

            # Confirm query logs are visible to admin after /ask
            if r_admin.ok:
                logs = r_admin.json()
                check("admin/query-logs returns list",
                      isinstance(logs, list),
                      f"{len(logs)} entries")

            # Logout admin
            admin_session.post(f"{BASE}/auth/logout", timeout=10)

except Exception as e:
    check("GET /admin/query-logs admin user (expect 200)", False, str(e))

# ── 8. Logout ─────────────────────────────────────────────────────────────────
print("\n=== 8. Auth: Logout ===")
try:
    r = session.post(f"{BASE}/auth/logout", timeout=10)
    check("POST /auth/logout", r.status_code in (200, 204),
          f"status={r.status_code}")
except Exception as e:
    check("POST /auth/logout", False, str(e))

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n=== Smoke Test Summary ===")
passed = sum(1 for v in results.values() if v == "PASS")
failed = sum(1 for v in results.values() if v == "FAIL")
skipped = sum(1 for v in results.values() if v == "SKIP")

for name, status in results.items():
    icon = "[OK]" if status == "PASS" else ("[SKIP]" if status == "SKIP" else "[!!]")
    print(f"  {icon} {name}: {status}")

print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
print("Overall:", "PASS" if failed == 0 else "FAIL")
sys.exit(0 if failed == 0 else 1)
