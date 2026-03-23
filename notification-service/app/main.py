"""Notification Service – consumer de RabbitMQ que persiste y envía notificaciones."""

import json
import logging
import os

import pika

from .db import SessionLocal, init_db
from .models import Notification

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("notification-service")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


def save_notification(order_id: str, customer: str, event_type: str, message: str, reason: str | None = None) -> None:
    """Persiste una notificación en la base de datos."""
    with SessionLocal() as session:
        notification = Notification(
            order_id=order_id,
            customer=customer,
            event_type=event_type,
            message=message,
            reason=reason,
        )
        session.add(notification)
        session.commit()
        logger.info("Notificación guardada en BD para orden %s", order_id)


def callback(ch, method, properties, body):
    order = json.loads(body)
    event = order.get("event", "")
    order_id = order["order_id"]
    customer = order["customer"]

    if event == "STOCK_CONFIRMED":
        message = f"Orden {order_id} confirmada para cliente '{customer}'"
        # TODO: implementar envío real de notificación (email, SMS, push, etc.)
        logger.info("Notificación: confirmación enviada al cliente '%s' para orden %s", customer, order_id)
        save_notification(order_id, customer, event, message)

    elif event == "STOCK_REJECTED":
        reason = order.get("reason", "")
        message = f"Orden {order_id} rechazada para cliente '{customer}'"
        # TODO: implementar envío real de notificación de rechazo
        logger.info("Notificación: orden %s rechazada para cliente '%s' – %s", order_id, customer, reason)
        save_notification(order_id, customer, event, message, reason)


def main() -> None:
    init_db()
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="orders", exchange_type="topic")
    result = channel.queue_declare(queue="", exclusive=True)
    channel.queue_bind(exchange="orders", queue=result.method.queue, routing_key="order.stock_confirmed")
    channel.queue_bind(exchange="orders", queue=result.method.queue, routing_key="order.stock_rejected")
    channel.basic_consume(
        queue=result.method.queue,
        on_message_callback=callback,
        auto_ack=True,
    )
    logger.info("Notificaciones esperando eventos...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
