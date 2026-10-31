# syntax=docker/dockerfile:1
# ---- stage 1: build the dashboard + approver PWA ---------------------------------------------
FROM node:22-alpine AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build:gateway   # writes ../src/mirsad/static

# ---- stage 2: runtime ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MIRSAD_HOST=0.0.0.0 MIRSAD_PORT=8700 MIRSAD_DATA_DIR=/data
RUN useradd --create-home --uid 10001 mirsad
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src/ src/
COPY demo/ demo/
COPY bench/ bench/
COPY configs/ configs/
COPY --from=web /build/src/mirsad/static/ src/mirsad/static/
RUN pip install ".[postgres]" && mkdir -p /data && chown mirsad /data
USER mirsad
VOLUME ["/data"]
EXPOSE 8700
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8700/healthz').status==200 else 1)"
CMD ["mirsad", "serve"]
