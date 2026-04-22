"""Configuración del API Gateway – variables de entorno."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    auth_service_url: str = "http://auth-service:8000"
    jwt_algorithm: str = "RS256"

    class Config:
        env_file = ".env"


settings = Settings()
