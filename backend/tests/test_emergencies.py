"""Integration and security test suite for Emergency / SOS Management."""

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
from app.models.emergency import Emergency, EmergencyStatus
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
        with urllib.request.urlopen(req, timeout=30) as resp:
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
    """Clean up test users, contacts, and emergencies using an isolated NullPool engine."""
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        for uid in test_user_ids:
            await conn.execute(delete(Emergency).where(Emergency.user_id == uid))
            await conn.execute(delete(TrustedContact).where(TrustedContact.user_id == uid))
            await conn.execute(delete(User).where(User.id == uid))
    await engine.dispose()


def run_tests():
    print("=" * 60)
    print("SafeCircle Emergency / SOS Integration & Security Test Suite")
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
        email_a = f"alice_sos_{uuid.uuid4().hex[:6]}@safecircle.app"
        pw_a = "SecretPassAlice123!"
        status, resp_a = make_request(
            f"{BASE_URL}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": "Alice SOSTester",
                "email": email_a,
                "phone_number": "+12025550111",
                "password": pw_a,
            },
        )
        assert status == 201, f"User A registration failed: {resp_a}"
        user_a_id = uuid.UUID(resp_a["id"])
        test_user_ids.append(user_a_id)

        # Login User A
        status, login_a = make_request(
            f"{BASE_URL}/api/v1/auth/login",
            method="POST",
            data={"email": email_a, "password": pw_a},
        )
        assert status == 200, f"User A login failed: {login_a}"
        token_a = login_a["access_token"]
        print(f"[OK] Registered and authenticated User A ({email_a}).")

        # 2. Register User B (for cross-user isolation tests)
        email_b = f"bob_sos_{uuid.uuid4().hex[:6]}@safecircle.app"
        pw_b = "SecretPassBob456!"
        status, resp_b = make_request(
            f"{BASE_URL}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": "Bob SOSTester",
                "email": email_b,
                "phone_number": "+12025550122",
                "password": pw_b,
            },
        )
        assert status == 201, f"User B registration failed: {resp_b}"
        user_b_id = uuid.UUID(resp_b["id"])
        test_user_ids.append(user_b_id)

        # Login User B
        status, login_b = make_request(
            f"{BASE_URL}/api/v1/auth/login",
            method="POST",
            data={"email": email_b, "password": pw_b},
        )
        assert status == 200, f"User B login failed: {login_b}"
        token_b = login_b["access_token"]
        print(f"[OK] Registered and authenticated User B ({email_b}).")

        # -------------------------------------------------------------
        # Test 1: Unauthorized Access -> 401
        # -------------------------------------------------------------
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 37.7749, "longitude": -122.4194},
        )
        assert status == 401, f"Expected 401, got {status}"
        status, _ = make_request(f"{BASE_URL}/api/v1/emergencies/active")
        assert status == 401, f"Expected 401, got {status}"
        status, _ = make_request(f"{BASE_URL}/api/v1/emergencies/")
        assert status == 401, f"Expected 401, got {status}"
        print("[OK] Unauthorized requests properly rejected with 401.")

        # -------------------------------------------------------------
        # Test 2: Input Validation (Coordinates & Accuracy) -> 422
        # -------------------------------------------------------------
        # Latitude > 90
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 90.001, "longitude": 0.0},
            token=token_a,
        )
        assert status == 422, f"Expected 422 for lat > 90, got {status}"

        # Latitude < -90
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": -90.5, "longitude": 0.0},
            token=token_a,
        )
        assert status == 422, f"Expected 422 for lat < -90, got {status}"

        # Longitude > 180
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 0.0, "longitude": 180.1},
            token=token_a,
        )
        assert status == 422, f"Expected 422 for lon > 180, got {status}"

        # Longitude < -180
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 0.0, "longitude": -180.1},
            token=token_a,
        )
        assert status == 422, f"Expected 422 for lon < -180, got {status}"

        # Negative accuracy
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 37.77, "longitude": -122.41, "location_accuracy": -5.0},
            token=token_a,
        )
        assert status == 422, f"Expected 422 for accuracy <= 0, got {status}"

        print("[OK] Invalid coordinates and non-positive accuracy properly rejected with 422.")

        # -------------------------------------------------------------
        # Test 3: Create SOS Emergency for User A -> 201
        # -------------------------------------------------------------
        sos_payload = {
            "latitude": 37.774929,
            "longitude": -122.419416,
            "location_accuracy": 8.5,
            "emergency_message": "Immediate SOS triggered! Need assistance.",
        }
        status, sos_data = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data=sos_payload,
            token=token_a,
        )
        assert status == 201, f"Create emergency failed ({status}): {sos_data}"
        emergency_1_id = sos_data["id"]
        assert sos_data["status"] == "ACTIVE"
        assert sos_data["user_id"] == str(user_a_id)
        assert abs(sos_data["latitude"] - 37.774929) < 0.0001
        assert abs(sos_data["longitude"] - (-122.419416)) < 0.0001
        assert sos_data["location_accuracy"] == 8.5
        assert sos_data["emergency_message"] == "Immediate SOS triggered! Need assistance."
        assert "created_at" in sos_data and "updated_at" in sos_data
        print(f"[OK] SOS Emergency created successfully (id={emergency_1_id}, status=ACTIVE).")

        # -------------------------------------------------------------
        # Test 4: Prevent Duplicate Active Emergencies -> 409 Conflict
        # -------------------------------------------------------------
        status, dup_resp = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={"latitude": 37.7750, "longitude": -122.4190},
            token=token_a,
        )
        assert status == 409, f"Expected 409 for duplicate active emergency, got {status}: {dup_resp}"
        print("[OK] Duplicate active emergency prevented with HTTP 409 Conflict.")

        # -------------------------------------------------------------
        # Test 5: Retrieve Active Emergency
        # -------------------------------------------------------------
        # User A has active emergency -> 200
        status, active_a = make_request(
            f"{BASE_URL}/api/v1/emergencies/active",
            token=token_a,
        )
        assert status == 200, f"Get active emergency failed: {active_a}"
        assert active_a["id"] == emergency_1_id
        assert active_a["status"] == "ACTIVE"
        print(f"[OK] Retrieved active emergency for User A (id={active_a['id']}).")

        # User B has no active emergency -> 404
        status, active_b = make_request(
            f"{BASE_URL}/api/v1/emergencies/active",
            token=token_b,
        )
        assert status == 404, f"Expected 404 for User B active emergency, got {status}"
        print("[OK] User B active emergency correctly returns 404 (isolation verified).")

        # -------------------------------------------------------------
        # Test 6: Cross-User Access Protection -> User B cannot cancel User A's emergency
        # -------------------------------------------------------------
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/{emergency_1_id}/cancel",
            method="PATCH",
            token=token_b,
        )
        assert status == 404, f"Cross-user cancel expected 404, got {status}"
        print("[OK] Cross-user cancellation blocked with 404 Not Found.")

        # -------------------------------------------------------------
        # Test 7: Cancel Emergency -> 200
        # -------------------------------------------------------------
        status, cancel_data = make_request(
            f"{BASE_URL}/api/v1/emergencies/{emergency_1_id}/cancel",
            method="PATCH",
            token=token_a,
        )
        assert status == 200, f"Cancel emergency failed: {cancel_data}"
        assert cancel_data["status"] == "CANCELLED"
        print(f"[OK] Emergency {emergency_1_id} successfully cancelled (status=CANCELLED).")

        # Verify active emergency now returns 404 for User A
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/active",
            token=token_a,
        )
        assert status == 404, f"Expected 404 after cancellation, got {status}"
        print("[OK] After cancellation, GET /active returns 404.")

        # -------------------------------------------------------------
        # Test 8: Prevent Invalid Status Transition (Cannot cancel already cancelled emergency)
        # -------------------------------------------------------------
        status, re_cancel = make_request(
            f"{BASE_URL}/api/v1/emergencies/{emergency_1_id}/cancel",
            method="PATCH",
            token=token_a,
        )
        assert status == 400, f"Expected 400 for re-cancellation, got {status}: {re_cancel}"
        print("[OK] Re-cancellation of already cancelled emergency correctly rejected with 400.")

        # -------------------------------------------------------------
        # Test 9: Create Second Emergency & Emergency History with Pagination
        # -------------------------------------------------------------
        # Now that first emergency is CANCELLED, User A can create a second emergency
        status, sos_data_2 = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            method="POST",
            data={
                "latitude": 40.712776,
                "longitude": -74.005974,
                "location_accuracy": 5.0,
                "emergency_message": "Second emergency event in New York.",
            },
            token=token_a,
        )
        assert status == 201, f"Failed to create second emergency: {sos_data_2}"
        emergency_2_id = sos_data_2["id"]
        print(f"[OK] Successfully created second emergency (id={emergency_2_id}) after previous cancellation.")

        # Retrieve full history for User A (should contain 2 emergencies)
        status, history_a = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            token=token_a,
        )
        assert status == 200, f"Get history failed: {history_a}"
        assert len(history_a) == 2, f"Expected 2 emergencies in history, got {len(history_a)}"
        # Sorted descending by created_at: newest first
        assert history_a[0]["id"] == emergency_2_id
        assert history_a[1]["id"] == emergency_1_id
        print(f"[OK] Emergency history retrieved (count={len(history_a)}, correctly ordered descending by timestamp).")

        # Test pagination: limit=1, offset=0
        status, page_1 = make_request(
            f"{BASE_URL}/api/v1/emergencies/?limit=1&offset=0",
            token=token_a,
        )
        assert status == 200 and len(page_1) == 1
        assert page_1[0]["id"] == emergency_2_id

        # Test pagination: limit=1, offset=1
        status, page_2 = make_request(
            f"{BASE_URL}/api/v1/emergencies/?limit=1&offset=1",
            token=token_a,
        )
        assert status == 200 and len(page_2) == 1
        assert page_2[0]["id"] == emergency_1_id
        print("[OK] History pagination verified (limit=1, offset=0 and offset=1).")

        # User B history must be empty
        status, history_b = make_request(
            f"{BASE_URL}/api/v1/emergencies/",
            token=token_b,
        )
        assert status == 200 and len(history_b) == 0
        print("[OK] User B history is empty (cross-user data isolation verified).")

        # Cancel emergency 2 so DB is clean
        status, _ = make_request(
            f"{BASE_URL}/api/v1/emergencies/{emergency_2_id}/cancel",
            method="PATCH",
            token=token_a,
        )
        assert status == 200

        # -------------------------------------------------------------
        # Test 10: Regression Check - Health, Auth, Contacts
        # -------------------------------------------------------------
        status_root, _ = make_request(f"{BASE_URL}/")
        assert status_root == 200
        status_health, _ = make_request(f"{BASE_URL}/health")
        assert status_health == 200
        status_v1_health, _ = make_request(f"{BASE_URL}/api/v1/health")
        assert status_v1_health == 200

        # Auth profile
        status_me, resp_me = make_request(f"{BASE_URL}/api/v1/auth/me", token=token_a)
        assert status_me == 200 and resp_me["email"] == email_a

        # Contacts CRUD regression check
        status_c_create, contact_resp = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            method="POST",
            data={"name": "SOS Contact", "phone_number": "+12025550199"},
            token=token_a,
        )
        assert status_c_create == 201

        status_c_list, contacts_list = make_request(
            f"{BASE_URL}/api/v1/contacts/",
            token=token_a,
        )
        assert status_c_list == 200 and len(contacts_list) == 1

        print("[OK] Regression checks passed: root, health, auth/me, and contacts all working seamlessly.")

        print("=" * 60)
        print("ALL EMERGENCY / SOS TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        # Cleanup test records in Neon database
        print("\nCleaning up test records from database...")
        asyncio.run(cleanup_database(test_user_ids))
        print("[OK] Database cleanup completed.")


if __name__ == "__main__":
    run_tests()
