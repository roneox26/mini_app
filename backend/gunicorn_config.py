"""Gunicorn configuration for production deployment."""
import multiprocessing
import os

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
backlog = 2048

# Worker processes
# For high traffic: workers = (2 * cpu_count) + 1
workers = int(os.getenv("GUNICORN_WORKERS", (multiprocessing.cpu_count() * 2) + 1))
worker_class = "sync"  # Can use "gevent" or "eventlet" for async if needed
worker_connections = 1000
max_requests = 1000  # Recycle workers to prevent memory leaks
max_requests_jitter = 50
timeout = 60  # Request timeout in seconds

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Graceful shutdown
graceful_timeout = 30
keep_alive = 5

# SSL configuration (uncomment if using HTTPS)
# keyfile = "/path/to/keyfile.key"
# certfile = "/path/to/certfile.crt"
# ca_certs = "/path/to/ca_certs.crt"

# Performance tuning
daemon = False
pidfile = None
preload_app = True  # Load app before forking workers

# Callbacks
def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[Gunicorn] Starting with {workers} workers")

def when_ready(server):
    """Called when the server is ready to serve requests."""
    print(f"[Gunicorn] Server is ready. Listening on {bind}")

def on_exit(server):
    """Called just before exiting."""
    print("[Gunicorn] Server exiting")
