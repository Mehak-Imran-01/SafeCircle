import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine


async def test_live_connection():
    print("\n--- Testing Live Database Connection (SELECT 1) ---")
    # Verify driver without printing credentials
    scheme = settings.async_database_url.split("://")[0]
    print(f"Using driver: {scheme}://***")

    try:
        async with engine.connect() as conn:
            # Execute SELECT 1
            res_scalar = await conn.execute(text("SELECT 1"))
            val = res_scalar.scalar()
            assert val == 1, f"Expected 1, got {val}"
            print("Successfully executed 'SELECT 1'. Result: 1")

            # Check database and PostgreSQL version (non-sensitive)
            meta_res = await conn.execute(
                text("SELECT current_database(), split_part(version(), ' ', 1), split_part(version(), ' ', 2)")
            )
            row = meta_res.fetchone()
            if row:
                print(f"Connected Database Name: {row[0]}")
                print(f"Database Server: {row[1]} {row[2]}")

        print("PASS: Live database connection verified successfully!")
        return True
    except Exception as e:
        print(f"FAILED: Connection error: {type(e).__name__}: {e}")
        return False
    finally:
        await engine.dispose()
        print("Engine pool disposed cleanly.")


def main():
    success = asyncio.run(test_live_connection())
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
