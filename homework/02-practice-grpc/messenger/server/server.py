import logging
import os
import queue
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import grpc
import messenger_pb2
import messenger_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp


class MessengerServer(messenger_pb2_grpc.MessengerServerServicer):
    def __init__(self):
        self._stream_lock = Lock()
        self._streams = []

    def SendMessage(self, request, context):
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        with self._stream_lock:
            for stram in self._streams:
                stram.put(messenger_pb2.Message(author=request.author, text=request.text, sendTime=timestamp))
        return messenger_pb2.Ack(sendTime=timestamp)

    def ReadMessages(self, request, context):
        new_stream = queue.SimpleQueue()
        with self._stream_lock:
            self._streams.append(new_stream)
        while True:
            yield new_stream.get()


def serve():
    server = grpc.server(ThreadPoolExecutor())
    messenger_pb2_grpc.add_MessengerServerServicer_to_server(MessengerServer(), server)
    server.add_insecure_port("0.0.0.0:" + os.environ.get("MESSENGER_SERVER_PORT"))
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig()
    serve()
