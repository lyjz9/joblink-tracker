"""Gunicorn settings for the single-process in-memory queue deployment."""

import os


bind = f"0.0.0.0:{os.getenv('PORT', '7860')}"
workers = 1
worker_class = "gthread"
threads = max(2, min(8, int(os.getenv("JOBLINK_HTTP_THREADS", "4"))))
timeout = 120
graceful_timeout = 45
keepalive = 5
preload_app = False
accesslog = None
errorlog = "-"
capture_output = True


def worker_int(worker):
    app = getattr(worker, "wsgi", None)
    if app is not None:
        from scraper.app import begin_shutdown

        begin_shutdown(app)


def worker_abort(worker):
    app = getattr(worker, "wsgi", None)
    if app is not None:
        from scraper.app import begin_shutdown

        begin_shutdown(app)


def worker_exit(_server, worker):
    app = getattr(worker, "wsgi", None)
    if app is not None:
        from scraper.app import shutdown_app

        shutdown_app(app, wait=False)
