"""Writer Service – consumer de RabbitMQ que persiste órdenes en Postgres."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import aio_pika

from .config import settings
from .db import async_session, init_db
from .redis_client import get_redis
from .repositories.orders_repo import upsert_order

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger("writer-service")


async def handle_order(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        body = json.loads(message.body)
        order_id = body["order_id"]
        event = body.get("event", "")
        now = datetime.now(timezone.utc).isoformat()
        r = get_redis()
        try:
            if event == "STOCK_CONFIRMED":
                async with async_session() as session:
                    await upsert_order(
                        session,
                        order_id=order_id,
                        customer=body["customer"],
                        items=body["items"],
                    )
                await r.hset(
                    f"order:{order_id}",
                    mapping={"status": "PERSISTED", "last_update": now},
                )
                logger.info("Orden %s persistida", order_id)
            elif event == "STOCK_REJECTED":
                reason = body.get("reason", "Stock insuficiente")
                await r.hset(
                    f"order:{order_id}",
                    mapping={
                        "status": "REJECTED",
                        "last_update": now,
                        "reason": reason,
                    },
                )
                logger.info("Orden %s rechazada: %s", order_id, reason)
        except Exception as exc:
            await r.hset(
                f"order:{order_id}",
                mapping={"status": "FAILED", "last_update": now},
            )
            logger.error("Error procesando orden %s: %s", order_id, exc)
        finally:
            await r.aclose()


async def main() -> None:
    await init_db()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("orders", aio_pika.ExchangeType.TOPIC)
        queue = await channel.declare_queue("", exclusive=True)
        await queue.bind(exchange, routing_key="order.stock_confirmed")
        await queue.bind(exchange, routing_key="order.stock_rejected")
        logger.info("Writer esperando eventos...")
        await queue.consume(handle_order)
        await asyncio.Future()  # mantener el loop corriendo


if __name__ == "__main__":
    asyncio.run(main())
