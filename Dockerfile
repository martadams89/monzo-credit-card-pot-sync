# Stage 1: build the Tailwind stylesheet, so the image works without running npm locally.
FROM node:22-alpine AS assets

WORKDIR /build

COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci --no-audit --no-fund

COPY app/templates ./app/templates
COPY app/static/css/src ./app/static/css/src
RUN npm run build-css

# Stage 2: the app itself.
FROM python:3.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /monzo-credit-card-pot-sync

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY wsgi.py ./
COPY app ./app
COPY --from=assets /build/app/static/css/dist ./app/static/css/dist

# The SQLite database lives here; mount a volume on it to keep your data.
RUN mkdir -p /monzo-credit-card-pot-sync/data
ENV DATABASE_URI=sqlite:////monzo-credit-card-pot-sync/data/app.db
VOLUME ["/monzo-credit-card-pot-sync/data"]

EXPOSE 1337

# Unhealthy when no sync has completed recently (see /health).
HEALTHCHECK --interval=60s --timeout=5s --start-period=5m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1337/health', timeout=4)" || exit 1

# One worker: the sync scheduler runs inside the app process, and more workers
# would each run their own copy of it. Threads keep the web UI responsive.
CMD ["gunicorn", "--bind", "0.0.0.0:1337", "--workers", "1", "--threads", "4", "--access-logfile", "-", "wsgi:app"]
