FROM python:3.8-slim

WORKDIR /messenger/
COPY server/requirements.txt .
RUN pip install -r requirements.txt

COPY proto/messenger.proto proto/
COPY server/server.py server/
COPY server/run.sh server/

WORKDIR /messenger/server
ENTRYPOINT ./run.sh
