"""Auth Service – autenticación JWT (RS256) con refresh tokens en Redis."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings  # noqa: F401
from .db import init_db
from .jwt_utils import _ensure_keys
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("auth-service")


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Inicializando base de datos...")
    await init_db()
    _ensure_keys()
    logger.info("Auth service listo")
    yield


app = FastAPI(title="Auth Service – JWT RS256", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
