"""Notification Service – consumer de RabbitMQ que envía confirmaciones."""

import json
import logging
import os

import pika

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger("notification-service")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


def callback(ch, method, properties, body):
    order = json.loads(body)
    event = order.get("event", "")
    if event == "STOCK_CONFIRMED":
        # TODO: implementar envío real de notificación (email, SMS, push, etc.)
        logger.info(
            "Notificación: confirmación enviada al cliente '%s' para orden %s",
            order["customer"],
            order["order_id"],
        )
    elif event == "STOCK_REJECTED":
        # TODO: implementar envío real de notificación de rechazo
        logger.info(
            "Notificación: orden %s rechazada para cliente '%s' – %s",
            order["order_id"],
            order["customer"],
            order.get("reason", ""),
        )


def main() -> None:
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="orders", exchange_type="topic")
    result = channel.queue_declare(queue="", exclusive=True)
    channel.queue_bind(
        exchange="orders",
        queue=result.method.queue,
        routing_key="order.stock_confirmed",
    )
    channel.queue_bind(
        exchange="orders", queue=result.method.queue, routing_key="order.stock_rejected"
    )
    channel.basic_consume(
        queue=result.method.queue,
        on_message_callback=callback,
        auto_ack=True,
    )
    logger.info("Notificaciones esperando eventos...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
