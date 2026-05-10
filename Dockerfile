# syntax=docker/dockerfile:1.7
# Production image. Single-stage on purpose — the wheel install pulls
# everything we need; we'd save < 30 MB by going multi-stage and lose
# fast rebuilds. Revisit when the wheel grows past 200 MB.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the metadata first to maximise the dep-cache layer.
COPY pyproject.toml VERSION README.md ./
COPY service_crm ./service_crm
COPY migrations ./migrations

RUN pip install --upgrade pip && pip install ".[postgres]" gunicorn

EXPOSE 5000

# `flask db upgrade` runs from the entrypoint inside docker-compose so
# the image stays useful when run directly against an existing DB.
CMD ["gunicorn", "service_crm:create_app()", "--bind", "0.0.0.0:5000", "--workers", "4"]
