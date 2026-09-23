import requests
import sys

def main():
    base_url = "http://127.0.0.1:8000"
    print("=== LIVE INTEGRATION TEST FOR ADMIN USER MANAGEMENT ===")
    
    # 1. Admin login
    admin_session = requests.Session()
    r = admin_session.post(f"{base_url}/auth/login", json={"username": "admin_test", "password": "Password123!"})
    if r.status_code != 200:
        print(f"FAILED: Admin login failed: {r.status_code} {r.text}")
        sys.exit(1)
    admin_info = r.json()
    admin_id = admin_info["id"]
    print(f"[PASS] 1. Admin login: username={admin_info['username']}, role={admin_info['role']}")

    # 2. GET /admin/users
    r = admin_session.get(f"{base_url}/admin/users")
    if r.status_code != 200:
        print(f"FAILED: GET /admin/users: {r.status_code} {r.text}")
        sys.exit(1)
    users_data = r.json()
    print(f"[PASS] 2. GET /admin/users returned total={users_data['total']} users.")
    
    salesman_user = next((u for u in users_data["users"] if u["username"] == "salesman_test"), None)
    if not salesman_user:
        print("FAILED: salesman_test not found in user list")
        sys.exit(1)
    salesman_id = salesman_user["id"]
    print(f"       Found salesman_test (id={salesman_id}, role={salesman_user['role']}, status={salesman_user['status']})")

    # 3. Promote salesman to ADMIN
    r = admin_session.patch(f"{base_url}/admin/users/{salesman_id}/role", json={"role": "ADMIN"})
    if r.status_code != 200:
        print(f"FAILED: Promote to ADMIN: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"[PASS] 3. Promoted salesman_test to ADMIN. New role: {r.json()['role']}")

    # 4. Demote salesman back to SALESMAN
    r = admin_session.patch(f"{base_url}/admin/users/{salesman_id}/role", json={"role": "SALESMAN"})
    if r.status_code != 200:
        print(f"FAILED: Demote back to SALESMAN: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"[PASS] 4. Demoted salesman_test back to SALESMAN. New role: {r.json()['role']}")

    # 5. Revoke access for salesman_test
    r = admin_session.patch(f"{base_url}/admin/users/{salesman_id}/status", json={"status": "REVOKED"})
    if r.status_code != 200:
        print(f"FAILED: Revoke access: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"[PASS] 5. Revoked access for salesman_test. New status: {r.json()['status']}")

    # 6. Verify salesman cannot log in while REVOKED
    s_client = requests.Session()
    r = s_client.post(f"{base_url}/auth/login", json={"username": "salesman_test", "password": "Password123!"})
    if r.status_code != 403:
        print(f"FAILED: Expected 403 when revoked salesman logs in, got {r.status_code}: {r.text}")
        sys.exit(1)
    print(f"[PASS] 6. Revoked user blocked at login with 403 Forbidden: {r.json()['detail']}")

    # 7. Restore access for salesman_test
    r = admin_session.patch(f"{base_url}/admin/users/{salesman_id}/status", json={"status": "ACTIVE"})
    if r.status_code != 200:
        print(f"FAILED: Restore access: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"[PASS] 7. Restored access for salesman_test. New status: {r.json()['status']}")

    # 8. Verify salesman can now log in
    r = s_client.post(f"{base_url}/auth/login", json={"username": "salesman_test", "password": "Password123!"})
    if r.status_code != 200:
        print(f"FAILED: Restored salesman login failed: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"[PASS] 8. Restored salesman successfully logged in.")

    # 9. Verify salesman cannot access /admin/users
    r = s_client.get(f"{base_url}/admin/users")
    if r.status_code != 403:
        print(f"FAILED: Expected 403 for salesman accessing /admin/users, got {r.status_code}")
        sys.exit(1)
    print(f"[PASS] 9. Salesman blocked from /admin/users with 403 Forbidden: {r.json()['detail']}")

    # 10. Safeguard: Admin cannot demote self
    r = admin_session.patch(f"{base_url}/admin/users/{admin_id}/role", json={"role": "SALESMAN"})
    if r.status_code != 400:
        print(f"FAILED: Expected 400 when admin demotes self, got {r.status_code}")
        sys.exit(1)
    print(f"[PASS] 10. Self-demotion blocked with 400 Bad Request: {r.json()['detail']}")

    # 11. Safeguard: Admin cannot revoke self
    r = admin_session.patch(f"{base_url}/admin/users/{admin_id}/status", json={"status": "REVOKED"})
    if r.status_code != 400:
        print(f"FAILED: Expected 400 when admin revokes self, got {r.status_code}")
        sys.exit(1)
    print(f"[PASS] 11. Self-revocation blocked with 400 Bad Request: {r.json()['detail']}")

    print("\nALL LIVE INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
