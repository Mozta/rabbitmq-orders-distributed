"""Motor síncrono de SQLAlchemy, fábrica de sesiones y seed de productos."""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Product

logger = logging.getLogger("inventory-service.db")

_POSTGRES_USER = os.getenv("POSTGRES_USER", "orders_user")
_POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "orders_pass")
_POSTGRES_DB = os.getenv("POSTGRES_DB", "orders_db")
_POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
_POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = (
    f"postgresql+psycopg2://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}"
    f"@{_POSTGRES_HOST}:{_POSTGRES_PORT}/{_POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

# Productos iniciales para demo
SEED_PRODUCTS = [
    {"sku": "LAP-001", "name": "Laptop Pro 15", "stock": 50},
    {"sku": "MON-001", "name": "Monitor 27 4K", "stock": 30},
    {"sku": "TEC-001", "name": "Teclado mecánico", "stock": 100},
    {"sku": "MOU-001", "name": "Mouse inalámbrico", "stock": 80},
]


def init_db() -> None:
    """Crea las tablas e inserta productos de ejemplo si la tabla está vacía."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        if session.query(Product).count() == 0:
            for p in SEED_PRODUCTS:
                session.add(Product(**p))
            session.commit()
            logger.info("Productos iniciales insertados: %d", len(SEED_PRODUCTS))
        else:
            logger.info("Tabla products ya contiene datos – omitiendo seed")
