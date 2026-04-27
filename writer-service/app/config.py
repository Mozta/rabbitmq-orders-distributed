"""Configuración del Writer Service – variables de entorno."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://orders_user:orders_pass@postgres:5432/orders_db"
    )
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    @field_validator("database_url", mode="before")
    @classmethod
    def force_asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("://", "+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"


settings = Settings()
