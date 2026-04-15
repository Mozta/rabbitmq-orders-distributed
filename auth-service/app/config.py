"""Configuración del Auth Service – variables de entorno."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_database_url: str = "postgresql+asyncpg://auth_user:auth_pass@postgres-auth:5432/auth_db"
    redis_url: str = "redis://redis:6379/0"

    jwt_private_key_path: str = "/app/keys/private.pem"
    jwt_public_key_path: str = "/app/keys/public.pem"
    jwt_issuer: str = "auth-service"
    jwt_algorithm: str = "RS256"

    access_token_ttl_seconds: int = 60 * 15        # 15 min
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 días

    @field_validator("auth_database_url", mode="before")
    @classmethod
    def force_asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("://", "+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"


settings = Settings()
