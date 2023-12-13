FROM python:3.8-slim

WORKDIR /10-practice-security/auth
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .
