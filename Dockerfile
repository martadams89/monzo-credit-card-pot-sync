FROM python:3.14-slim-bookworm

WORKDIR /monzo-credit-card-pot-sync

COPY requirements.txt wsgi.py ./

RUN pip3 install -r requirements.txt

COPY app ./app

# Unhealthy when no sync has completed recently (see /health).
HEALTHCHECK --interval=60s --timeout=5s --start-period=5m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1337/health', timeout=4)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:1337", "wsgi:app"]