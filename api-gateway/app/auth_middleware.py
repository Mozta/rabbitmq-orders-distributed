"""Middleware de autenticación JWT para el API Gateway.

Descarga la clave pública del auth-service (JWKS) al arrancar,
y valida el Bearer token en rutas protegidas.
"""

from __future__ import annotations

import logging

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

logger = logging.getLogger("api-gateway")

bearer_scheme = HTTPBearer(auto_error=False)

# Clave pública cacheada en memoria
_public_key = None


async def fetch_jwks() -> None:
    """Descarga JWKS del auth-service y cachea la clave pública RSA."""
    global _public_key
    url = f"{settings.auth_service_url}/auth/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
        jwks = resp.json()
        key_data = jwks["keys"][0]
        _public_key = RSAAlgorithm.from_jwk(key_data)
        logger.info("JWKS cargado desde %s", url)
    except Exception as exc:
        logger.error("No se pudo cargar JWKS desde %s: %s", url, exc)
        raise


def get_public_key():
    if _public_key is None:
        raise HTTPException(status_code=503, detail="Auth public key not loaded")
    return _public_key


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Dependency de FastAPI que valida JWT y retorna el payload.

    Uso en endpoints:
        @app.post("/orders")
        async def create_order(user: dict = Depends(require_auth)):
            user_id = user["sub"]
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_public_key(),
            algorithms=[settings.jwt_algorithm],
            issuer="auth-service",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload
