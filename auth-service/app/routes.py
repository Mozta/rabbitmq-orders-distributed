"""Rutas de autenticación: signup, login, refresh, logout, me, JWKS."""

from __future__ import annotations

import base64
import logging

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .db import async_session
from .hashing import hash_password, verify_password
from .jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_public_key,
    revoke_refresh_token,
    validate_refresh_token,
)
from .models import User
from .schemas import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger("auth-service")

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()


@router.post("/signup", response_model=SignupResponse, status_code=201)
async def signup(body: SignupRequest):
    async with async_session() as session:
        # Verificar si el email ya existe
        existing = await session.execute(
            select(User).where(User.email == body.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=body.email,
            password_hash=hash_password(body.password),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    logger.info("Usuario registrado: %s", user.email)
    return SignupResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == body.email)
        )
        user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = await create_refresh_token(user_id=user.id)

    logger.info("Login exitoso: %s", user.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    user_id = await validate_refresh_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Revocar el token usado (rotación) y emitir uno nuevo
    await revoke_refresh_token(body.refresh_token)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user_id=user.id, email=user.email)
    new_refresh_token = await create_refresh_token(user_id=user.id)

    logger.info("Token refreshed para: %s", user.email)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest):
    await revoke_refresh_token(body.refresh_token)
    logger.info("Refresh token revocado")


@router.get("/me", response_model=UserResponse)
async def me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return UserResponse(user_id=payload["sub"], email=payload["email"])


@router.get("/.well-known/jwks.json")
async def jwks():
    """Expone la clave pública RSA en formato JWKS para que otros servicios validen tokens."""
    pub_key = load_pem_public_key(get_public_key())
    numbers = pub_key.public_numbers()

    def _b64url(value: int, length: int) -> str:
        data = value.to_bytes(length, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    n_bytes = (numbers.n.bit_length() + 7) // 8

    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": _b64url(numbers.n, n_bytes),
                "e": _b64url(numbers.e, 3),
            }
        ]
    }
