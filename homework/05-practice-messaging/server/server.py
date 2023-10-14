import logging
import os
import pika
import threading
import time

from flask import Flask, request
from loguru import logger
from typing import List, Optional


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT")

WEB_HOST = os.getenv("WEB_HOST")
WEB_PORT = os.getenv("WEB_PORT")
IMAGES_ENDPOINT = os.getenv("IMAGES_ENDPOINT", "/api/v1.0/images")
DATA_DIR = os.getenv("DATA_DIR")


class Server:
    def __init__(self, host, port):
        self._counter = 0
        self._lock = threading.Lock()

        self._pending_images = {}
        self._processed_images = []

        self._host = host
        self._port = port

        self.init_callback_queue()
        self.init_task_queue()

    def init_task_queue(self):
        logger.info("Initializing task queue.")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host, port=self._port)
        )
        self._task_channel = connection.channel()
        self._task_channel.queue_declare(queue="task_queue")
        publisher_thread = threading.Thread(target=self.start_publishing)
        publisher_thread.start()

    def start_publishing(self):
        while True:
            time.sleep(0.2)
            try:
                with self._lock:
                    image_id, image = list(self._pending_images.items())[0]
                    self._task_channel.basic_publish(
                        exchange="",
                        routing_key="task_queue",
                        properties=pika.BasicProperties(
                            reply_to=self._callback_queue,
                        ),
                        body=f"{image} {image_id}",
                    )
                    logger.info(f"Server published {image_id}.")
            except Exception as e:
                logger.info(f"Server failed to publish due to {e}.")

    def init_callback_queue(self):
        logger.info("Initializing callback queue.")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self._host, port=self._port)
        )
        channel = connection.channel()
        callback_queue = channel.queue_declare(queue="callback_queue", exclusive=True)
        self._callback_queue = callback_queue.method.queue
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=self._callback_queue,
            on_message_callback=self._on_worker_message,
        )
        consumer_thread = threading.Thread(target=channel.start_consuming)
        consumer_thread.start()

    def _on_worker_message(self, channel, method, properties, body):
        try:
            image_id = int(body.decode())
            with self._lock:
                self._processed_images.append(image_id)
                self._pending_images.pop(image_id, None)

            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Server recieved {image_id}.")
        except Exception as e:
            logger.info(f"Server failed to recieve {image_id} due to {e}.")

    def store_image(self, image: str) -> int:
        image_id = self._counter
        with self._lock:
            self._pending_images[image_id] = image
            self._counter += 1

        logger.info(f"Added {image_id} to task queue.")
        return image_id

    def get_processed_images(self) -> List[int]:
        try:
            with self._lock:
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

    server = Server(host=RABBITMQ_HOST, port=RABBITMQ_PORT)

    @app.route(IMAGES_ENDPOINT, methods=["POST"])
    def add_image():
        body = request.get_json(force=True)
        image_id = server.store_image(body["image_url"])
        return {"image_id": image_id}

    @app.route(IMAGES_ENDPOINT, methods=["GET"])
    def get_image_ids():
        image_ids = server.get_processed_images()
        return {"image_ids": image_ids}

    @app.route(f"{IMAGES_ENDPOINT}/<string:image_id>", methods=["GET"])
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
    app.run(host=WEB_HOST, port=WEB_PORT)
