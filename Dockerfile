# ==============================================================================
# Estágio 1: Compilação do App Web / PWA Offline (Next.js Static Export)
# ==============================================================================
FROM node:24-alpine AS web-builder

WORKDIR /web

COPY web/package.json web/package-lock.json* ./
RUN npm ci

COPY web/ ./
RUN npm run build

# ==============================================================================
# Estágio 2: Runtime Python Stateless (FastAPI + Uvicorn + Motor RAG + PDF)
# ==============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/
COPY assets/ ./assets/
COPY data/manuais/ ./data/manuais/
COPY --from=web-builder /web/out ./web/out

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "mara_api.main:app", "--host", "0.0.0.0", "--port", "8501"]
