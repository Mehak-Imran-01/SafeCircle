import inspect
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.db.base import Base
from app.db.session import async_session_factory, engine, get_db


def test_settings_database_url():
    print("\n--- 1. Testing DATABASE_URL in Settings ---")
    assert hasattr(settings, "DATABASE_URL"), "settings missing DATABASE_URL"
    assert hasattr(settings, "async_database_url"), "settings missing async_database_url property"
    print(f"DATABASE_URL configured: {bool(settings.DATABASE_URL)}")
    print(f"async_database_url scheme: {settings.async_database_url.split('://')[0]}://...")
    assert settings.async_database_url.startswith("postgresql+asyncpg://"), (
        f"Expected postgresql+asyncpg driver, got: {settings.async_database_url.split('://')[0]}"
    )
    print("PASS: Settings DATABASE_URL correctly configured with asyncpg driver.")


def test_sqlalchemy_base_and_session():
    print("\n--- 2. Testing SQLAlchemy Base and Session Factory ---")
    assert hasattr(Base, "metadata"), "Base has no metadata"
    print("Base.metadata exists:", Base.metadata)
    assert engine is not None, "engine is None"
    assert async_session_factory is not None, "async_session_factory is None"
    assert inspect.isasyncgenfunction(get_db), "get_db must be an async generator function"
    print("PASS: Base, engine, async_session_factory, and get_db dependency verified.")


def test_alembic_configuration():
    print("\n--- 3. Testing Alembic Configuration ---")
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    assert os.path.exists(alembic_ini_path), f"alembic.ini not found at {alembic_ini_path}"
    alembic_cfg = Config(alembic_ini_path)
    script = ScriptDirectory.from_config(alembic_cfg)
    print(f"Alembic ScriptDirectory loaded: {script.dir}")
    print("PASS: Alembic config and script directory validated.")


def main():
    try:
        test_settings_database_url()
        test_sqlalchemy_base_and_session()
        test_alembic_configuration()
        print("\n>>> ALL DATABASE FOUNDATION TESTS PASSED! <<<")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
