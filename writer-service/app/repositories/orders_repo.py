"""Repositorio – inserción idempotente de órdenes en Postgres."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order

logger = logging.getLogger("writer-service.orders_repo")


async def upsert_order(
    session: AsyncSession,
    order_id: str,
    customer: str,
    items: list[dict],
) -> bool:
    """Inserta una orden solo si no existe previamente (idempotencia).

    Retorna True si se insertó una nueva fila, False si ya existía.
    """
    existing = await session.execute(select(Order).where(Order.order_id == order_id))
    if existing.scalar_one_or_none() is not None:
        logger.info("La orden %s ya existe – omitiendo inserción duplicada", order_id)
        return False

    order = Order(order_id=order_id, customer=customer, items=items)
    session.add(order)
    await session.commit()
    logger.info("Orden %s persistida exitosamente", order_id)
    return True
