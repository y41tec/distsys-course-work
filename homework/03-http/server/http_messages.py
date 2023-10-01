import dataclasses
import gzip
import typing as t

CHUNKSIZE = 1024


class HTTPRequest:
    def __init__(self):
        self.method: str = ""
        self.path: str = ""
        self.version: str = ""
        self.parameters: t.Dict[str, str] = {}
        self.headers: t.Dict[str, str] = {}
        self._stream = None

    def parse_from_stream(self, stream):
        try:
            self._stream = stream
            self._parse_startline()
            self._parse_headerline()
        except Exception as e:
            self._stream = None
            print(e)

    def _parse_startline(self):
        line = self._stream.readline()
        self.method, self.path, self.version = line.decode().strip().split()

    def _parse_headerline(self):
        while True:
            line = self._stream.readline()
            if line == CRLF:
                return
            key, value = line.decode().strip().split(": ")
            self.headers[key] = int(value) if key == HEADER_CONTENT_LENGTH else value

    def skip_body(self):
        for _ in self.get_body_chunks():
            continue

    def get_body_chunks(self):
        if self._stream and HEADER_CONTENT_LENGTH in self.headers:
            while self.headers[HEADER_CONTENT_LENGTH] > 0:
                yield self._stream.read(
                    min(self.headers[HEADER_CONTENT_LENGTH], CHUNKSIZE)
                )
                self.headers[HEADER_CONTENT_LENGTH] -= CHUNKSIZE


class HTTPResponse:
    def __init__(self):
        self.server: str = ""
        self.version: str = ""
        self.status: str = ""
        self.compression: bool = False
        self.headers: t.Dict[str, str] = {}

    def send(self, reciever_stream, byte_content=None, sender_stream=None):
        reciever_stream.write(self._to_bytes())
        reciever_stream.write(CRLF)
        if byte_content:
            reciever_stream.write(gzip.compress(byte_content) if self.compression else byte_content)
        else:
            reciever_stream.write(gzip.compress(sender_stream.read()) if self.compression else sender_stream.read())

    def _to_bytes(self):
        response_lines = [
            f"{self.version} {self.status} {HTTP_REASON_BY_STATUS[self.status]}\r\n",
            f"{HEADER_CONTENT_TYPE}: text/html\r\n",
            f"{HEADER_CONTENT_LENGTH}: {self.headers[HEADER_CONTENT_LENGTH]}\r\n",
            f"{HEADER_SERVER}: {self.server}\r\n",
        ]
        if self.compression:
            response_lines.append(f"{HEADER_CONTENT_ENCODING}: {GZIP}\r\n",)
        return ("".join(response_lines)).encode()


# Common HTTP strings and constants


CR = b"\r"
LF = b"\n"
CRLF = CR + LF

HTTP_VERSION = "1.1"

OPTIONS = "OPTIONS"
GET = "GET"
HEAD = "HEAD"
POST = "POST"
PUT = "PUT"
DELETE = "DELETE"

METHODS = [
    OPTIONS,
    GET,
    HEAD,
    POST,
    PUT,
    DELETE,
]

HEADER_HOST = "Host"
HEADER_CONTENT_LENGTH = "Content-Length"
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_CONTENT_ENCODING = "Content-Encoding"
HEADER_ACCEPT_ENCODING = "Accept-Encoding"
HEADER_CREATE_DIRECTORY = "Create-Directory"
HEADER_SERVER = "Server"
HEADER_REMOVE_DIRECTORY = "Remove-Directory"

GZIP = "gzip"

TEXT_PLAIN = "text/plain"
APPLICATION_OCTET_STREAM = "application/octet-stream"
APPLICATION_GZIP = "application/gzip"

OK = "200"
BAD_REQUEST = "400"
NOT_FOUND = "404"
METHOD_NOT_ALLOWED = "405"
NOT_ACCEPTABLE = "406"
CONFLICT = "409"

HTTP_REASON_BY_STATUS = {
    "100": "Continue",
    "101": "Switching Protocols",
    "200": "OK",
    "201": "Created",
    "202": "Accepted",
    "203": "Non-Authoritative Information",
    "204": "No Content",
    "205": "Reset Content",
    "206": "Partial Content",
    "300": "Multiple Choices",
    "301": "Moved Permanently",
    "302": "Found",
    "303": "See Other",
    "304": "Not Modified",
    "305": "Use Proxy",
    "307": "Temporary Redirect",
    "400": "Bad Request",
    "401": "Unauthorized",
    "402": "Payment Required",
    "403": "Forbidden",
    "404": "Not Found",
    "405": "Method Not Allowed",
    "406": "Not Acceptable",
    "407": "Proxy Authentication Required",
    "408": "Request Time-out",
    "409": "Conflict",
    "410": "Gone",
    "411": "Length Required",
    "412": "Precondition Failed",
    "413": "Request Entity Too Large",
    "414": "Request-URI Too Large",
    "415": "Unsupported Media Type",
    "416": "Requested range not satisfiable",
    "417": "Expectation Failed",
    "500": "Internal Server Error",
    "501": "Not Implemented",
    "502": "Bad Gateway",
    "503": "Service Unavailable",
    "504": "Gateway Time-out",
    "505": "HTTP Version not supported",
}
