"""Auth Service – autenticación JWT (RS256) con refresh tokens en Redis."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import settings  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("auth-service")

app = FastAPI(title="Auth Service – JWT RS256")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
