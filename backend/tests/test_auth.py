from datetime import timedelta
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import uvicorn

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.user import User


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


def test_auth_suite():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = Server(config=config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.5)

    base = "http://127.0.0.1:8000"
    test_email = f"test_{uuid.uuid4().hex[:8]}@safecircle.app"
    test_password = "SecurePassword123!"
    test_name = "Jane Doe Safety"
    test_phone = "+15551234567"
    created_user_id = None

    print("\n================ AUTHENTICATION TEST SUITE ================")
    try:
        # 1. Test Registration
        print("\n--- 1. Testing Registration (POST /api/v1/auth/register) ---")
        status, res = make_request(
            f"{base}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": test_name,
                "email": test_email,
                "phone_number": test_phone,
                "password": test_password,
            },
        )
        print(f"Status: {status}")
        print(f"Response: {res}")
        assert status == 201, f"Expected 201 Created, got {status}"
        assert res["email"] == test_email.lower()
        assert res["full_name"] == test_name
        assert "password" not in res, "Security violation: password returned in response!"
        assert "password_hash" not in res, "Security violation: password_hash returned in response!"
        created_user_id = res["id"]
        print("PASS: Registration successful and returns safe user profile.")

        # 2. Test Duplicate Email Rejection
        print("\n--- 2. Testing Duplicate Email Rejection ---")
        status, res = make_request(
            f"{base}/api/v1/auth/register",
            method="POST",
            data={
                "full_name": "Another Name",
                "email": test_email,
                "phone_number": "+19998887777",
                "password": "AnotherPassword456!",
            },
        )
        print(f"Status: {status}")
        print(f"Response: {res}")
        assert status == 409, f"Expected 409 Conflict for duplicate email, got {status}"
        print("PASS: Duplicate registration correctly rejected with HTTP 409.")

        # 3. Verify Password Hash in Neon Database
        print("\n--- 3. Verifying Argon2 Hash in Database ---")

        async def verify_hash():
            test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
            try:
                async with test_engine.connect() as conn:
                    stmt = select(User.password_hash).where(User.email == test_email.lower())
                    row = (await conn.execute(stmt)).fetchone()
                    assert row is not None, "User not found in database!"
                    db_hash = row[0]
                    assert db_hash != test_password, "Security violation: plaintext password found in database!"
                    assert db_hash.startswith("$argon2id$"), f"Expected Argon2id hash format, got: {db_hash[:15]}"
                    print(f"Stored hash verified as Argon2id: {db_hash[:30]}...")
            finally:
                await test_engine.dispose()

        asyncio.run(verify_hash())
        print("PASS: Password is securely hashed with Argon2id in Neon PostgreSQL.")

        # 4. Test Successful Login
        print("\n--- 4. Testing Login with Valid Credentials (POST /api/v1/auth/login) ---")
        status, res = make_request(
            f"{base}/api/v1/auth/login",
            method="POST",
            data={
                "email": test_email,
                "password": test_password,
            },
        )
        print(f"Status: {status}")
        assert status == 200, f"Expected 200 OK, got {status}"
        assert "access_token" in res, "Response missing access_token"
        assert res["token_type"] == "bearer", f"Expected bearer token type, got {res.get('token_type')}"
        access_token = res["access_token"]
        print(f"Received access token: {access_token[:25]}... (valid JWT)")
        print("PASS: Login succeeded and returned signed JWT.")

        # 5. Test Incorrect Password Rejection
        print("\n--- 5. Testing Login with Incorrect Password ---")
        status, res = make_request(
            f"{base}/api/v1/auth/login",
            method="POST",
            data={
                "email": test_email,
                "password": "WrongPassword999!",
            },
        )
        print(f"Status: {status}")
        print(f"Response: {res}")
        assert status == 401, f"Expected 401 Unauthorized for incorrect password, got {status}"
        print("PASS: Incorrect password correctly rejected with HTTP 401.")

        # 6. Test GET /api/v1/auth/me with Valid Token
        print("\n--- 6. Testing GET /api/v1/auth/me with Bearer Token ---")
        status, res = make_request(
            f"{base}/api/v1/auth/me",
            method="GET",
            token=access_token,
        )
        print(f"Status: {status}")
        print(f"Response: {res}")
        assert status == 200, f"Expected 200 OK, got {status}"
        assert res["id"] == created_user_id
        assert res["email"] == test_email.lower()
        assert "password" not in res and "password_hash" not in res
        print("PASS: /auth/me returns authenticated user's safe profile.")

        # 7. Test Missing Token Rejection
        print("\n--- 7. Testing /auth/me without Token ---")
        status, res = make_request(
            f"{base}/api/v1/auth/me",
            method="GET",
        )
        print(f"Status: {status}")
        assert status == 401, f"Expected 401 Unauthorized for missing token, got {status}"
        print("PASS: Missing token rejected with HTTP 401.")

        # 8. Test Invalid Token Rejection
        print("\n--- 8. Testing /auth/me with Invalid Token ---")
        status, res = make_request(
            f"{base}/api/v1/auth/me",
            method="GET",
            token="invalid.bogus.token.value",
        )
        print(f"Status: {status}")
        assert status == 401, f"Expected 401 Unauthorized for invalid token, got {status}"
        print("PASS: Invalid token rejected with HTTP 401.")

        # 9. Test Expired Token Rejection
        print("\n--- 9. Testing /auth/me with Expired Token ---")
        expired_token = create_access_token(
            subject=created_user_id,
            expires_delta=timedelta(seconds=-30),
        )
        status, res = make_request(
            f"{base}/api/v1/auth/me",
            method="GET",
            token=expired_token,
        )
        print(f"Status: {status}")
        print(f"Response: {res}")
        assert status == 401, f"Expected 401 Unauthorized for expired token, got {status}"
        print("PASS: Expired token rejected with HTTP 401.")

        # 10. Test Existing Health Endpoints
        print("\n--- 10. Testing Existing Health Endpoints ---")
        status, res = make_request(f"{base}/health")
        assert status == 200 and res["status"] == "healthy"
        status, res = make_request(f"{base}/api/v1/health")
        assert status == 200 and res["status"] == "healthy"
        print("PASS: Existing health endpoints remain 100% operational.")

        print("\n>>> ALL 10 AUTHENTICATION TESTS PASSED SUCCESSFULLY! <<<")

    finally:
        # Cleanup test user from live DB
        if created_user_id:

            async def cleanup():
                test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
                try:
                    async with test_engine.connect() as conn:
                        await conn.execute(delete(User).where(User.id == uuid.UUID(created_user_id)))
                        await conn.commit()
                finally:
                    await test_engine.dispose()

            asyncio.run(cleanup())
            print(f"Cleaned up test user: {test_email}")

        server.should_exit = True
        t.join(timeout=2)


if __name__ == "__main__":
    test_auth_suite()
