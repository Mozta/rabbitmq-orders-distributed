"""Motor síncrono de SQLAlchemy y fábrica de sesiones para notificaciones."""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

logger = logging.getLogger("notification-service.db")

_DB_USER = os.getenv("NOTIFICATIONS_DB_USER", "notif_user")
_DB_PASSWORD = os.getenv("NOTIFICATIONS_DB_PASSWORD", "notif_pass")
_DB_NAME = os.getenv("NOTIFICATIONS_DB_NAME", "notifications_db")
_DB_HOST = os.getenv("NOTIFICATIONS_DB_HOST", "postgres-notifications")
_DB_PORT = os.getenv("NOTIFICATIONS_DB_PORT", "5432")

DATABASE_URL = (
    f"postgresql+psycopg2://{_DB_USER}:{_DB_PASSWORD}"
    f"@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Crea las tablas en la base de datos si no existen."""
    Base.metadata.create_all(bind=engine)
    logger.info("Tabla notifications lista")
