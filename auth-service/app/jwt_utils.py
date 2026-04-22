"""Generación y validación de tokens JWT (RS256) + refresh tokens en Redis."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .config import settings

logger = logging.getLogger("auth-service")

# ── Claves RSA ─────────────────────────────────────────────────────────────────

_private_key: bytes | None = None
_public_key: bytes | None = None


def _ensure_keys() -> None:
    """Genera o carga el par RSA desde disco."""
    global _private_key, _public_key

    priv_path = Path(settings.jwt_private_key_path)
    pub_path = Path(settings.jwt_public_key_path)

    if priv_path.exists() and pub_path.exists():
        _private_key = priv_path.read_bytes()
        _public_key = pub_path.read_bytes()
        logger.info("Claves RSA cargadas desde disco")
        return

    # Generar nuevo par
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    _private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Persistir en disco
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(_private_key)
    pub_path.write_bytes(_public_key)
    os.chmod(priv_path, 0o600)

    logger.info("Par RSA generado y persistido en %s", priv_path.parent)


def get_private_key() -> bytes:
    if _private_key is None:
        _ensure_keys()
    return _private_key  # type: ignore[return-value]


def get_public_key() -> bytes:
    if _public_key is None:
        _ensure_keys()
    return _public_key  # type: ignore[return-value]


# ── Access Token (JWT RS256) ───────────────────────────────────────────────────


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, get_private_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decodifica y valida un access token. Lanza jwt.PyJWTError si es inválido."""
    return jwt.decode(
        token,
        get_public_key(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
    )


# ── Refresh Token (almacenado en Redis) ───────────────────────────────────────


async def create_refresh_token(user_id: str) -> str:
    """Genera un refresh token opaco, lo guarda en Redis con TTL."""
    from .redis_client import get_redis

    token_id = str(uuid.uuid4())
    r = get_redis()
    await r.set(
        f"refresh:{token_id}",
        user_id,
        ex=settings.refresh_token_ttl_seconds,
    )
    await r.aclose()
    return token_id


async def validate_refresh_token(token_id: str) -> str | None:
    """Valida un refresh token. Retorna user_id o None si expiró/revocado."""
    from .redis_client import get_redis

    r = get_redis()
    user_id = await r.get(f"refresh:{token_id}")
    await r.aclose()
    return user_id


async def revoke_refresh_token(token_id: str) -> None:
    """Revoca un refresh token eliminándolo de Redis."""
    from .redis_client import get_redis

    r = get_redis()
    await r.delete(f"refresh:{token_id}")
    await r.aclose()
