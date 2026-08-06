# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache \
    HF_HOME=/opt/huggingface
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install . \
    && mkdir -p "$TIKTOKEN_CACHE_DIR" \
    && /opt/venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" \
    && /opt/venv/bin/python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding(model_name='Qdrant/bm25')"

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache \
    HF_HOME=/opt/huggingface

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/tiktoken-cache /opt/tiktoken-cache
COPY --from=builder /opt/huggingface /opt/huggingface
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini pyproject.toml ./
RUN mkdir -p /data/uploads /data/celerybeat && chown -R app:app /data /app /opt/tiktoken-cache /opt/huggingface

USER app
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=3)"]
CMD ["python", "-m", "app.run_api"]
