"""Inventory Service – consumer de RabbitMQ que valida y descuenta stock."""

import json
import logging
import os

import pika

from .db import SessionLocal, init_db
from .models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("inventory-service")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


def validate_and_deduct_stock(order_id: str, items: list[dict]) -> tuple[bool, str]:
    """Valida disponibilidad y descuenta stock de forma atómica (all-or-nothing).

    Retorna (True, "") si el stock fue descontado exitosamente,
    o (False, razón) si no hay stock suficiente o el SKU no existe.
    """
    with SessionLocal() as session:
        for item in items:
            sku = item["sku"]
            qty = item.get("qty", 1)
            product = session.query(Product).filter_by(sku=sku).with_for_update().first()
            if product is None:
                session.rollback()
                reason = f"SKU {sku} no encontrado en inventario"
                logger.warning("Orden %s – %s", order_id, reason)
                return False, reason
            if product.stock < qty:
                session.rollback()
                reason = (
                    f"Stock insuficiente para SKU {sku} "
                    f"(disponible: {product.stock}, solicitado: {qty})"
                )
                logger.warning("Orden %s – %s", order_id, reason)
                return False, reason
            product.stock -= qty
            logger.info(
                "Orden %s – SKU %s: stock %d → %d",
                order_id, sku, product.stock + qty, product.stock,
            )
        session.commit()
        return True, ""


def callback(ch, method, properties, body):
    order = json.loads(body)
    order_id = order["order_id"]
    items = order["items"]
    try:
        success, reason = validate_and_deduct_stock(order_id, items)
        if success:
            event = {**order, "event": "STOCK_CONFIRMED"}
            routing_key = "order.stock_confirmed"
            logger.info("Orden %s – stock confirmado, publicando evento", order_id)
        else:
            event = {**order, "event": "STOCK_REJECTED", "reason": reason}
            routing_key = "order.stock_rejected"
            logger.info("Orden %s – stock rechazado: %s", order_id, reason)

        ch.basic_publish(
            exchange="orders",
            routing_key=routing_key,
            body=json.dumps(event).encode(),
            properties=pika.BasicProperties(content_type="application/json"),
        )
    except Exception as exc:
        logger.error("Error procesando orden %s: %s", order_id, exc)


def main() -> None:
    init_db()
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="orders", exchange_type="topic")
    result = channel.queue_declare(queue="", exclusive=True)
    channel.queue_bind(exchange="orders", queue=result.method.queue, routing_key="order.created")
    channel.basic_consume(
        queue=result.method.queue,
        on_message_callback=callback,
        auto_ack=True,
    )
    logger.info("Inventario esperando eventos...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
