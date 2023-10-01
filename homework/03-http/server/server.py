import click
import logging
import mimetypes
import os
import pathlib
import socket
import subprocess
import typing as t

from dataclasses import dataclass
from socketserver import StreamRequestHandler

import http_messages
from utils import rmtree


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class HTTPServer:
    server_address: t.Tuple[str, int]
    socket: socket.socket
    server_domain: str
    working_directory: str


class HTTPHandler(StreamRequestHandler):
    server: HTTPServer

    # Use self.rfile and self.wfile to interact with the client
    # Access domain and working directory with self.server.{attr}
    def handle(self) -> None:
        logger.info(f"Handle connection from {self.client_address}")
        request = http_messages.HTTPRequest()
        request.parse_from_stream(self.rfile)
        self._process_http_request(request)

    def _process_http_request(self, request):
        response = http_messages.HTTPResponse()
        response.server = self.server.server_domain
        response.version = request.version
        response.compression = http_messages.HEADER_ACCEPT_ENCODING in request.headers
        path = pathlib.Path(self.server.working_directory + request.path)

        if (
            http_messages.HEADER_HOST in request.headers
            and self.server.server_domain
            and request.headers[http_messages.HEADER_HOST] != self.server.server_domain
        ):
            request.skip_body()
            self._reply_with_status(response, http_messages.BAD_REQUEST)

        elif request.method == http_messages.GET:
            if path.is_file():
                request.skip_body()
                response.status = http_messages.OK
                response.headers[
                    http_messages.HEADER_CONTENT_TYPE
                ] = mimetypes.guess_type(path)[0]
                response.headers[
                    http_messages.HEADER_CONTENT_LENGTH
                ] = path.stat().st_size
                with open(path, "rb") as file:
                    response.send(reciever_stream=self.wfile, sender_stream=file)
            elif path.is_dir():
                request.skip_body()
                listing = subprocess.check_output(["ls", "-la", "--time-style=+\"%Y-%m-%d %H:%M:%S\"", str(path)])
                response.status = http_messages.OK
                response.headers[
                    http_messages.HEADER_CONTENT_TYPE
                ] = http_messages.TEXT_PLAIN
                response.headers[http_messages.HEADER_CONTENT_LENGTH] = len(listing)
                response.send(reciever_stream=self.wfile, byte_content=listing)
            else:
                request.skip_body()
                self._reply_with_status(response, http_messages.NOT_FOUND)

        elif request.method == http_messages.POST:
            if path.exists():
                request.skip_body()
                self._reply_with_status(response, http_messages.CONFLICT)
            else:
                if http_messages.HEADER_CREATE_DIRECTORY in request.headers:
                    request.skip_body()
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with open(path, "wb") as file:
                        for chunk in request.get_body_chunks():
                            file.write(chunk)
                self._reply_with_status(response, http_messages.OK)

        elif request.method == http_messages.PUT:
            if not path.exists():
                request.skip_body()
                self._reply_with_status(response, http_messages.NOT_FOUND)
            if path.is_dir():
                request.skip_body()
                self._reply_with_status(response, http_messages.CONFLICT)
            else:
                with open(path, "wb") as file:
                    for chunk in request.get_body_chunks():
                        file.write(chunk)
                self._reply_with_status(response, http_messages.OK)

        elif request.method == http_messages.DELETE:
            if (
                path.is_dir()
                and http_messages.HEADER_REMOVE_DIRECTORY not in request.headers
            ):
                request.skip_body()
                self._reply_with_status(response, http_messages.NOT_ACCEPTABLE)
            elif path.is_dir():
                request.skip_body()
                rmtree(path)
                self._reply_with_status(response, http_messages.OK)
            elif path.is_file():
                request.skip_body()
                path.unlink()
                self._reply_with_status(response, http_messages.OK)
            else:
                request.skip_body()
                self._reply_with_status(response, http_messages.NOT_FOUND)

        else:
            request.skip_body()
            self._reply_with_status(response, http_messages.BAD_REQUEST)

    def _reply_with_status(self, response, status):
        reason = http_messages.HTTP_REASON_BY_STATUS[status]
        response.status = status
        response.headers[http_messages.HEADER_CONTENT_TYPE] = http_messages.TEXT_PLAIN
        response.headers[http_messages.HEADER_CONTENT_LENGTH] = len(reason)
        response.send(reciever_stream=self.wfile, byte_content=reason.encode())


@click.command()
@click.option("--host", type=str, default=os.getenv("SERVER_HOST", default="0.0.0.0"))
@click.option("--port", type=int, default=os.getenv("SERVER_PORT", default="8080"))
@click.option("--server-domain", type=str, default=os.getenv("SERVER_DOMAIN"))
@click.option(
    "--working-directory", type=str, default=os.getenv("SERVER_WORKING_DIRECTORY")
)
def main(host, port, server_domain, working_directory):
    if working_directory is None:
        exit(1)

    logger.info(
        f"Starting server on {host}:{port}, domain {server_domain}, working directory {working_directory}"
    )

    # Create a server socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set SO_REUSEADDR option
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket object to the address and port
    s.bind((host, port))
    # Start listening for incoming connections
    s.listen()

    logger.info(f"Listening at {s.getsockname()}")
    server = HTTPServer((host, port), s, server_domain, working_directory)

    while True:
        # Accept any new connection (request, client_address)
        try:
            conn, addr = s.accept()
        except OSError:
            break

        try:
            # Handle the request
            HTTPHandler(conn, addr, server)

            # Close the connection
            conn.shutdown(socket.SHUT_WR)
            conn.close()
        except Exception as e:
            logger.error(e)
            conn.close()


if __name__ == "__main__":
    main(auto_envvar_prefix="SERVER")
