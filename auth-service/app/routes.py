"""Rutas de autenticación: signup y login."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from .db import async_session
from .hashing import hash_password, verify_password
from .models import User
from .schemas import LoginRequest, SignupRequest, SignupResponse, TokenResponse
from .jwt_utils import create_access_token, create_refresh_token

logger = logging.getLogger("auth-service")

router = APIRouter(prefix="/auth", tags=["auth"])


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
