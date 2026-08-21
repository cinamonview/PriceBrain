# PriceBrain Cloud Run image — Gate D (no secrets baked in)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY pricebrain_app ./pricebrain_app

# Cloud Run injects PORT; bind all interfaces for container networking.
CMD ["sh", "-c", "uvicorn pricebrain_app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
