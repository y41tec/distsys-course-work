import copy
import json
import logging
import os
import random
import threading
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict

import grpc
import google.protobuf.json_format  # ParseDict, MessageToDict
import google.protobuf.empty_pb2  # Empty
import messenger_pb2
import messenger_pb2_grpc


class PostBox:
    def __init__(self):
        self._messages: List[Dict] = []
        self._lock = threading.Lock()

    def collect_messages(self) -> List[Dict]:
        with self._lock:
            messages = copy.deepcopy(self._messages)
            self._messages = []
        return messages

    def put_message(self, message: Dict):
        with self._lock:
            self._messages.append(message)


class MessageHandler(BaseHTTPRequestHandler):
    _stub = None
    _postbox: PostBox

    def _read_content(self):
        content_length = int(self.headers['Content-Length'])
        bytes_content = self.rfile.read(content_length)
        return bytes_content.decode('ascii')

    # noinspection PyPep8Naming
    def do_POST(self):
        if self.path == '/sendMessage':
            response = self._send_message(self._read_content())
        elif self.path == '/getAndFlushMessages':
            response = self._get_messages()
        else:
            self.send_error(HTTPStatus.NOT_IMPLEMENTED)
            self.end_headers()
            return

        response_bytes = json.dumps(response).encode('ascii')
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def _send_message(self, content: str) -> dict:
        json_request = json.loads(content)
        data = google.protobuf.json_format.ParseDict(json_request, messenger_pb2.Data())
        ack = self._stub.SendMessage(data)
        return google.protobuf.json_format.MessageToDict(ack)

    def _get_messages(self) -> List[dict]:
        return self._postbox.collect_messages()


def consume_messages(stub, postbox):
    for message in stub.ReadMessages(google.protobuf.empty_pb2.Empty()):
        postbox.put_message(google.protobuf.json_format.MessageToDict(message))


def main():
    grpc_server_address = os.environ.get('MESSENGER_SERVER_ADDR')
    channel = grpc.insecure_channel(grpc_server_address)
    stub = messenger_pb2_grpc.MessengerServerStub(channel)

    # A list of messages obtained from the server-py but not yet requested by the user to be shown
    # (via the http's /getAndFlushMessages).
    postbox = PostBox()
    consumer_thread = threading.Thread(target=consume_messages, args=[stub, postbox])
    consumer_thread.start()

    # Pass the stub and the postbox to the HTTP server.
    # Dirty, but this simple http server doesn't provide interface
    # for passing arguments to the handler c-tor.
    MessageHandler._stub = stub
    MessageHandler._postbox = postbox

    http_port = os.environ.get('MESSENGER_HTTP_PORT')
    http_server_address = ('0.0.0.0', int(http_port))

    # NB: handler_class is instantiated for every http request. Do not store any inter-request state in it.
    httpd = HTTPServer(http_server_address, MessageHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    logging.basicConfig()
    main()
