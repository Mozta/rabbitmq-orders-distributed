"""Publicador de eventos de órdenes al exchange de RabbitMQ."""

from __future__ import annotations

import json
import logging

import aio_pika

from .config import settings

logger = logging.getLogger("api-gateway.publisher")


async def publish_order(payload: dict) -> None:
    """Publica un evento order.created al exchange fanout 'orders'."""
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "orders", aio_pika.ExchangeType.TOPIC
        )
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
        )
        await exchange.publish(message, routing_key="order.created")
        logger.info("Evento publicado: order_id=%s", payload.get("order_id"))
