"""Gunicorn configuration file."""

import os
import multiprocessing

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_connections = 1000
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Debug config
reload = os.getenv("FLASK_ENV", "production") == "development"
reload_extra_files = []
spew = False

# Server mechanics
chdir = '/app'
daemon = False
raw_env = []
pidfile = None
umask = 0
user = os.getenv("GUNICORN_USER", None)
group = os.getenv("GUNICORN_GROUP", None)
tmp_upload_dir = None

# Error handling
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# When using a reverse proxy - FIX: Using the string directly instead of splitting
forwarded_allow_ips = os.getenv("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Pre-load the app to catch syntax errors
preload_app = False

# Use /dev/shm for worker heartbeat directory to avoid disk I/O
worker_tmp_dir = "/dev/shm"

# Configuration hooks
def on_starting(server):
    """Log when the server is starting."""
    server.log.info("Gunicorn server is starting")

def post_worker_init(worker):
    """Log when a worker is initialized."""
    worker.log.info(f"Worker {worker.pid} initialized")

def worker_exit(server, worker):
    """Log when a worker exits."""
    server.log.info(f"Worker {worker.pid} exited")
