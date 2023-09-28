FROM python:3.8-slim

WORKDIR /messenger/
COPY client/requirements.txt .
RUN pip install -r requirements.txt

COPY proto/messenger.proto proto/
COPY client/client.py client/
COPY client/run.sh client/

WORKDIR /messenger/client
ENTRYPOINT ./run.sh
