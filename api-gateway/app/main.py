"""API Gateway – punto de entrada del sistema distribuido de órdenes."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException

from .auth_middleware import fetch_jwks, require_auth
from .config import settings  # noqa: F401
from .rabbitmq_publisher import publish_order
from .redis_client import get_redis
from .schemas import OrderCreated, OrderIn, OrderStatus

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(application: FastAPI):
    await fetch_jwks()
    logger.info("API Gateway listo")
    yield


app = FastAPI(title="API Gateway – Órdenes Distribuidas", lifespan=lifespan)


# ── POST /orders (protegido) ─────────────────────────────────────────────────
@app.post("/orders", response_model=OrderCreated, status_code=202)
async def create_order(
    body: OrderIn,
    user: dict = Depends(require_auth),
    x_request_id: str | None = Header(None),
):
    request_id = x_request_id or str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user_id = user["sub"]

    logger.info(
        "Nueva orden %s de user=%s [request_id=%s]", order_id, user_id, request_id
    )

    # 1. Guardar estado inicial en Redis como RECEIVED
    r = get_redis()
    await r.hset(
        f"order:{order_id}",
        mapping={"status": "RECEIVED", "last_update": now, "user_id": user_id},
    )

    # 2. Publicar evento al exchange de RabbitMQ
    payload = {
        "order_id": order_id,
        "customer": body.customer,
        "user_id": user_id,
        "items": [item.model_dump() for item in body.items],
    }
    await publish_order(payload)

    await r.aclose()
    return OrderCreated(order_id=order_id, status="RECEIVED")


# ── GET /orders/{order_id} ────────────────────────────────────────────────────
@app.get("/orders/{order_id}", response_model=OrderStatus)
async def get_order(order_id: str):
    """Consulta el estado de una orden desde Redis."""
    r = get_redis()
    data = await r.hgetall(f"order:{order_id}")
    await r.aclose()

    if not data:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    return OrderStatus(
        order_id=order_id,
        status=data.get("status", "UNKNOWN"),
        last_update=data.get("last_update", ""),
        reason=data.get("reason"),
    )
