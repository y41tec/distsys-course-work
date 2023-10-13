import logging
import os
import pika
import threading
import time

from flask import Flask, request
from loguru import logger
from typing import List, Optional


class Server:
    def __init__(self, host, port):
        self._counter = 0
        self._processed_images = []
        self.init_task_queue(host, port)
        self.init_callback_queue(host, port)

    def init_task_queue(self, host, port):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port)
        )
        self._task_channel = connection.channel()
        self._task_channel.queue_declare(queue="task_queue", durable=True)
        self._task_channel.confirm_delivery()

    def init_callback_queue(self, host, port):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port)
        )
        channel = connection.channel()
        callback_queue = channel.queue_declare(
            queue="callback_queue", durable=True, exclusive=True
        )
        self._callback_queue = callback_queue.method.queue
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=self._callback_queue,
            on_message_callback=self._callback,
        )
        consumer_thread = threading.Thread(target=channel.start_consuming)
        consumer_thread.start()

    def _callback(self, ch, method, properties, body):
        try:
            image_id = int(body.decode())
            self._processed_images.append(image_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Server recieved {image_id}.")
        except Exception as e:
            logger.info(f"Server failed to recieve {image_id} due to {e}.")

    def store_image(self, image: str) -> int:
        image_id = self._counter
        self._counter += 1
        while True:
            try:
                self._task_channel.basic_publish(
                    exchange="",
                    routing_key="task_queue",
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        reply_to=self._callback_queue,
                    ),
                    body=f"{image} {image_id}",
                )
                logger.info(f"Added {image_id} to task queue.")
                return image_id
            except Exception as e:
                logger.info(f"Retransmit {image_id} due to {e}.")
                time.sleep(1)

    def get_processed_images(self) -> List[int]:
        try:
            return self._processed_images
        except Exception as e:
            logger.info(f"Failed to get list of processed images due to {e}.")

    def get_image_description(self, image_id: str) -> Optional[str]:
        try:
            with open(f"{os.getenv('DATA_DIR')}/{image_id}.txt", "r") as file:
                return file.read()
        except Exception as e:
            logger.info(f"Failed to get description of {image_id} due to {e}.")


def create_app() -> Flask:
    """
    Create flask application
    """
    app = Flask(__name__)

    server = Server(host=os.getenv("RABBITMQ_HOST"), port=os.getenv("RABBITMQ_PORT"))

    @app.route(os.getenv("IMAGES_ENDPOINT"), methods=["POST"])
    def add_image():
        body = request.get_json(force=True)
        image_id = server.store_image(body["image_url"])
        return {"image_id": image_id}

    @app.route(os.getenv("IMAGES_ENDPOINT"), methods=["GET"])
    def get_image_ids():
        image_ids = server.get_processed_images()
        return {"image_ids": image_ids}

    @app.route(f"{os.getenv('IMAGES_ENDPOINT')}/<string:image_id>", methods=["GET"])
    def get_processing_result(image_id):
        result = server.get_image_description(image_id)
        if result is None:
            return "Image not found.", 404
        else:
            return {"description": result}

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig()
    app.run(host=os.getenv("WEB_HOST"), port=os.getenv("WEB_PORT"))
