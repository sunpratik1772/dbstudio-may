# syntax=docker/dockerfile:1.6
#
# dbSherpa backend container.
#
# Design goals:
#   * Runs on Cloud Run (listens on $PORT, single non-root process).
#   * Fast cold start — dependencies baked into the image, no pip install
#     at boot.
#   * Stateless — all writable paths redirected to `/tmp` via env vars,
#     so multiple instances can scale independently.
#
# Build locally:
#   docker build -t dbsherpa-backend -f backend/Dockerfile backend
#
# Run locally:
#   docker run --rm -p 8080:8080 -e GEMINI_API_KEY=$GEMINI_API_KEY dbsherpa-backend
#
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# System deps: libgomp for pandas, tini for clean signal handling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps ---------------------------------------------------------
# Copy just requirements first so the dep layer is cached across code
# changes — a 3-line router edit doesn't invalidate the pip install.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# --- App source ----------------------------------------------------------
COPY . ./

# Create a non-root user and hand it the writable paths we redirect
# runtime state into. Keeps the container surface minimal.
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /tmp/dbsherpa/workflows /tmp/dbsherpa/drafts /tmp/dbsherpa/output \
    && chown -R app:app /app /tmp/dbsherpa
USER app

# Redirect writable dirs to /tmp so the read-only image is never mutated.
ENV DBSHERPA_WORKFLOWS_DIR=/tmp/dbsherpa/workflows \
    DBSHERPA_DRAFTS_DIR=/tmp/dbsherpa/drafts \
    DBSHERPA_OUTPUT_DIR=/tmp/dbsherpa/output

EXPOSE 8080

# tini → uvicorn. Single worker is the Cloud Run default; scale by
# bumping `--concurrency` on the service, not the process count.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level info"]
