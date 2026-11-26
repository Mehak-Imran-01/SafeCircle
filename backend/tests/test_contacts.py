"""Integration and security test suite for Trusted Contacts Management using standard urllib."""

import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import uvicorn

from app.core.config import settings
from app.main import app
from app.models.trusted_contact import TrustedContact
from app.models.user import User

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


class Server(uvicorn.Server):
    def install_signal_handlers(self):
        pass


def make_request(url: str, method: str = "GET", data: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    encoded_data = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed


async def cleanup_database(test_user_ids: list[uuid.UUID]):
    """Clean up test users and their cascaded contacts using an isolated NullPool engine."""
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        for uid in test_user_ids:
            await conn.execute(delete(TrustedContact).where(TrustedContact.user_id == uid))
            await conn.execute(delete(User).where(User.id == uid))
    await engine.dispose()


def run_tests():
    print("=" * 60)
    print("SafeCircle Trusted Contacts Integration & Security Test Suite")
    print("=" * 60)

    config = uvicorn.Config(app=app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")
    server = Server(config=config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server readiness
    ready = False
    for attempt in range(15):
        try:
            status, _ = make_request(f"{BASE_URL}/health")
            if status == 200:
                ready = True
                print("[OK] FastAPI server is live and responsive.")
                break
        except Exception:
            time.sleep(0.5)

    if not ready:
        print("[FAIL] Server failed to start within timeout.")
        sys.exit(1)

    test_user_ids = []

    try:
        # 1. Register User A
        email_a = f"alice_{uuid.uuid4().hex[:6]}@safecircle.app"
        pw_a = "SecretPassAlice123!"
        status, resp_a = make_request(
            f"{BASE_URL}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": "Alice ContactTester",
                "email": email_a,
                "phone_number": "+12025550101",
                "password": pw_a,
            },
        )
        assert status == 201, f"User A registration failed: {resp_a}"
        user_a_id = uuid.UUID(resp_a["id"])
        test_user_ids.append(user_a_id)
        print(f"[OK] Registered User A ({email_a})")

        # Login User A to get Token A
        status, login_a = make_request(
            f"{BASE_URL}/api/v1/auth/login",
            method="POST",
            data={"email": email_a, "password": pw_a},
        )
        assert status == 200, f"User A login failed: {login_a}"
        token_a = login_a["access_token"]
        print("[OK] User A authenticated and obtained JWT token.")

        # 2. Register User B (for cross-user isolation tests)
        email_b = f"bob_{uuid.uuid4().hex[:6]}@safecircle.app"
        pw_b = "SecretPassBob456!"
        status, resp_b = make_request(
            f"{BASE_URL}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": "Bob IntruderTester",
                "email": email_b,
                "phone_number": "+12025550102",
                "password": pw_b,
            },
        )
        assert status == 201, f"User B registration failed: {resp_b}"
        user_b_id = uuid.UUID(resp_b["id"])
        test_user_ids.append(user_b_id)
        print(f"[OK] Registered User B ({email_b})")

        # Login User B to get Token B
        status, login_b = make_request(
            f"{BASE_URL}/api/v1/auth/login",
            method="POST",
            data={"email": email_b, "password": pw_b},
        )
        assert status == 200, f"User B login failed: {login_b}"
        token_b = login_b["access_token"]
        print("[OK] User B authenticated and obtained JWT token.")

        # -------------------------------------------------------------
        # Test 1: Unauthorized Access (No Token) -> 401
        # -------------------------------------------------------------
        status, _ = make_request(f"{BASE_URL}/api/v1/contacts/")
        assert status == 401, f"Expected 401, got {status}"
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            method="POST",
            data={"name": "Sister", "phone_number": "+12025550199"},
        )
        assert status == 401, f"Expected 401, got {status}"
        print("[OK] Unauthorized requests properly rejected with 401.")

        # -------------------------------------------------------------
        # Test 2: Create Contact for User A -> 201
        # -------------------------------------------------------------
        contact_payload = {
            "name": "Jane Doe",
            "phone_number": "+12025550155",
            "relationship": "Sister",
        }
        status, contact_data = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            method="POST",
            data=contact_payload,
            token=token_a,
        )
        assert status == 201, f"Create contact failed ({status}): {contact_data}"
        contact_id = contact_data["id"]
        assert contact_data["name"] == "Jane Doe"
        assert contact_data["phone_number"] == "+12025550155"
        assert contact_data["relationship"] == "Sister"
        assert contact_data["user_id"] == str(user_a_id)
        assert "created_at" in contact_data
        print(f"[OK] Successfully created contact (id={contact_id}) for User A.")

        # Create a second contact for User A
        contact_payload_2 = {
            "name": "Dr. Sarah Smith",
            "phone_number": "+12025550166",
            "relationship": "Physician",
        }
        status, c2_data = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            method="POST",
            data=contact_payload_2,
            token=token_a,
        )
        assert status == 201, f"Create contact 2 failed: {c2_data}"
        contact_id_2 = c2_data["id"]
        print(f"[OK] Successfully created second contact (id={contact_id_2}) for User A.")

        # -------------------------------------------------------------
        # Test 3: List Contacts for User A -> 200 (Contains 2 contacts)
        # -------------------------------------------------------------
        status, contacts_list = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            token=token_a,
        )
        assert status == 200, f"List contacts failed: {contacts_list}"
        assert len(contacts_list) == 2, f"Expected 2 contacts, got {len(contacts_list)}"
        returned_ids = {c["id"] for c in contacts_list}
        assert contact_id in returned_ids and contact_id_2 in returned_ids
        print(f"[OK] Listed {len(contacts_list)} contacts for User A.")

        # Verify User B has 0 contacts
        status, list_b = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            token=token_b,
        )
        assert status == 200
        assert len(list_b) == 0, "User B should have 0 contacts"
        print("[OK] User B contact list is empty (strict isolation verified).")

        # -------------------------------------------------------------
        # Test 4: Retrieve Contact by ID -> 200
        # -------------------------------------------------------------
        status, get_single = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            token=token_a,
        )
        assert status == 200, f"Get single contact failed: {get_single}"
        assert get_single["name"] == "Jane Doe"
        print(f"[OK] Retrieved single contact {contact_id} successfully.")

        # -------------------------------------------------------------
        # Test 5: Update Contact -> 200
        # -------------------------------------------------------------
        patch_payload = {
            "name": "Jane Doe-Smith",
            "relationship": "Elder Sister",
        }
        status, updated_data = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            method="PATCH",
            data=patch_payload,
            token=token_a,
        )
        assert status == 200, f"Update contact failed: {updated_data}"
        assert updated_data["name"] == "Jane Doe-Smith"
        assert updated_data["relationship"] == "Elder Sister"
        assert updated_data["phone_number"] == "+12025550155"  # Unchanged
        print(f"[OK] Contact updated successfully: {updated_data['name']} ({updated_data['relationship']}).")

        # -------------------------------------------------------------
        # Test 6: Cross-User Protection -> User B cannot access/update/delete User A's contact
        # Must return 404 (not 403, preventing resource enumeration)
        # -------------------------------------------------------------
        # Cross-user GET
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            token=token_b,
        )
        assert status == 404, f"Cross-user GET expected 404, got {status}"

        # Cross-user PATCH
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            method="PATCH",
            data={"name": "Hacked Name"},
            token=token_b,
        )
        assert status == 404, f"Cross-user PATCH expected 404, got {status}"

        # Cross-user DELETE
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            method="DELETE",
            token=token_b,
        )
        assert status == 404, f"Cross-user DELETE expected 404, got {status}"

        print("[OK] Cross-user access strictly blocked with HTTP 404 for GET, PATCH, and DELETE.")

        # -------------------------------------------------------------
        # Test 7: Delete Contact -> 204
        # -------------------------------------------------------------
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            method="DELETE",
            token=token_a,
        )
        assert status == 204, f"Delete contact failed: {status}"
        print(f"[OK] Contact {contact_id} deleted with HTTP 204.")

        # Confirm contact is now 404 for User A
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{contact_id}",
            token=token_a,
        )
        assert status == 404, f"Expected 404 for deleted contact, got {status}"

        # List should now only have 1 contact
        status, list_after_del = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            token=token_a,
        )
        assert len(list_after_del) == 1
        print("[OK] Verified contact is deleted and list count reduced to 1.")

        # -------------------------------------------------------------
        # Test 8: Nonexistent Contact UUID -> 404
        # -------------------------------------------------------------
        fake_uuid = str(uuid.uuid4())
        status, _ = make_request(
            f"{BASE_URL}/api/v1/contacts/{fake_uuid}",
            token=token_a,
        )
        assert status == 404

        # -------------------------------------------------------------
        # Test 9: Regression Check - Health & Auth Endpoints
        # -------------------------------------------------------------
        status_root, _ = make_request(f"{BASE_URL}/")
        assert status_root == 200
        status_health, _ = make_request(f"{BASE_URL}/health")
        assert status_health == 200
        status_v1_health, _ = make_request(f"{BASE_URL}/api/v1/health")
        assert status_v1_health == 200
        status_me, resp_me = make_request(
            f"{BASE_URL}/api/v1/auth/me",
            token=token_a,
        )
        assert status_me == 200
        assert resp_me["email"] == email_a
        print("[OK] Regression checks passed: root, /health, /api/v1/health, and /api/v1/auth/me all healthy.")

        print("=" * 60)
        print("ALL TRUSTED CONTACTS & REGRESSION TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        # Cleanup test data in Neon database
        print("\nCleaning up test records from database...")
        asyncio.run(cleanup_database(test_user_ids))
        print("[OK] Database cleanup completed.")


if __name__ == "__main__":
    run_tests()
