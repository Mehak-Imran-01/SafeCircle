from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "SafeCircle Backend API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    DOCS_URL: str = "/api/docs"
    OPENAPI_URL: str = "/api/openapi.json"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/safecircle_dev"

    # JWT Authentication Configuration
    JWT_SECRET_KEY: str = "dev-insecure-secret-key-change-in-production-safecircle-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    @property
    def async_database_url(self) -> str:
        """Ensure database URL uses asyncpg driver and handles PostgreSQL/Neon conventions."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]

        # Clean query parameters for asyncpg compatibility
        parsed = urlparse(url)
        if parsed.query:
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            # asyncpg expects 'ssl' rather than 'sslmode'
            if "sslmode" in query_params:
                sslmode_val = query_params.pop("sslmode")[0]
                if sslmode_val in ("require", "verify-ca", "verify-full"):
                    query_params["ssl"] = ["require"]
            # Remove libpq-only parameters not supported as kwargs in asyncpg.connect()
            for unsupported in ("channel_binding", "gssencmode", "target_session_attrs"):
                query_params.pop(unsupported, None)

            new_query = urlencode([(k, v) for k, vs in query_params.items() for v in vs])
            url = urlunparse(parsed._replace(query=new_query))

        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
