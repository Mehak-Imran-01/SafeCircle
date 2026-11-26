import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import engine


async def verify_user_table():
    print("\n--- Verifying 'users' Table in Neon PostgreSQL ---")
    async with engine.connect() as conn:
        # Check table existence
        tbl_res = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users'"
            )
        )
        assert tbl_res.scalar() == "users", "Table 'users' does not exist in 'public' schema!"
        print("PASS: 'users' table exists in public schema.")

        # Check columns
        col_res = await conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' "
                "ORDER BY ordinal_position"
            )
        )
        columns = col_res.fetchall()
        col_dict = {col[0]: (col[1], col[2], col[3]) for col in columns}
        print("\nColumns found in 'users' table:")
        for name, info in col_dict.items():
            print(f"  - {name}: type={info[0]}, nullable={info[1]}, default={info[2]}")

        # Required fields check
        required_cols = [
            "id",
            "full_name",
            "email",
            "phone_number",
            "password_hash",
            "is_active",
            "created_at",
            "updated_at",
        ]
        for col in required_cols:
            assert col in col_dict, f"Missing required column: {col}"
        print(f"\nPASS: All {len(required_cols)} required columns present.")

        # Check unique index on email
        idx_res = await conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = 'users' AND indexname = 'ix_users_email'"
            )
        )
        idx_row = idx_res.fetchone()
        assert idx_row is not None, "Unique index 'ix_users_email' not found!"
        print(f"PASS: Unique index verified: {idx_row[0]} ({idx_row[1]})")

    await engine.dispose()
    print("\n>>> USER TABLE VERIFICATION SUCCESSFUL! <<<")


def main():
    asyncio.run(verify_user_table())


if __name__ == "__main__":
    main()
