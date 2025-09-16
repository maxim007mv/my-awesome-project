# Simple production Dockerfile for the API (server.py)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY server.py ./

# Env vars expected at runtime:
# - TG_BOT_TOKEN
# - TG_CHAT_ID
# - TG_INBOUND_SECRET (optional)
# - ALLOW_ORIGINS (optional, e.g. https://tennisgo.netlify.app)

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

