import logging
import os
import pika
import time

from loguru import logger
from caption import get_image_caption


def callback(channel, method, properties, body):
    try:
        image, image_id = body.decode().split()
        logger.info(f"Worker received {image_id}.")
        with open(f"/data/{image_id}.txt", "w") as file:
            file.write(get_image_caption(image))

        channel.basic_publish(
            exchange="",
            routing_key=properties.reply_to,
            body=image_id,
        )
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Worker processed {image_id}.")
    except Exception as e:
        logger.info(f"Worker failed to process {image_id} due to {e}.")


if __name__ == "__main__":
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.getenv("RABBITMQ_HOST"), port=os.getenv("RABBITMQ_PORT")
        )
    )
    channel = connection.channel()

    channel.queue_declare(queue="task_queue", durable=True)
    logger.info("Worker waiting for messages.")

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="task_queue", on_message_callback=callback)
    channel.start_consuming()
