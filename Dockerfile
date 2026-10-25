# SnapSumbong API — production image
#
# Not built on the production server: GitHub Actions (.github/workflows/)
# builds this and pushes it to ghcr.io/charles101005/snapsumbong-api,
# which the EC2 host pulls via docker compose.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is used by the HEALTHCHECK below
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

# Liveness probe. Sends the real DOMAIN (Django rejects unknown hosts with
# 400 DisallowedHost) and X-Forwarded-Proto so SECURE_SSL_REDIRECT does not
# answer with a 301. DOMAIN comes in via env_file (.env) — compose requires it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS -H "Host: ${DOMAIN:-localhost}" -H "X-Forwarded-Proto: https" http://localhost:8000/health/ || exit 1

ENTRYPOINT ["./entrypoint.sh"]
