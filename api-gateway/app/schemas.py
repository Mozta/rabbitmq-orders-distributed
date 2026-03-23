"""Esquemas Pydantic para el API Gateway (validación de entrada/salida)."""

from __future__ import annotations

from pydantic import BaseModel


class ItemIn(BaseModel):
    """Artículo dentro de una orden (SKU + cantidad)."""
    sku: str
    qty: int


class OrderIn(BaseModel):
    """Cuerpo de la petición POST /orders."""
    customer: str
    items: list[ItemIn]


class OrderCreated(BaseModel):
    """Respuesta al crear una orden (202 Accepted)."""
    order_id: str
    status: str


class OrderStatus(BaseModel):
    """Respuesta al consultar el estado de una orden (GET /orders/{id})."""
    order_id: str
    status: str
    last_update: str
    reason: str | None = None
