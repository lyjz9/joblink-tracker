"""Privacy-safe application and request logging."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
import secrets
import sys
import time
import traceback

from flask import g, request


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
EXTRA_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "environment",
    "browser_status",
    "error_type",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value not in (None, ""):
                payload[field] = value
        if record.exc_info:
            payload["stack"] = [
                f"{frame.filename}:{frame.lineno}:{frame.name}"
                for frame in traceback.extract_tb(record.exc_info[2])[-12:]
            ]
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(app) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if app.config["JSON_LOGS"]:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(getattr(logging, app.config["LOG_LEVEL"], logging.INFO))
    app.logger.propagate = False


def register_request_logging(app) -> None:
    @app.before_request
    def start_request_log():
        supplied = request.headers.get("X-Request-ID", "")
        g.request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else secrets.token_hex(8)
        g.request_started_at = time.monotonic()

    @app.after_request
    def finish_request_log(response):
        response.headers["X-Request-ID"] = g.get("request_id", secrets.token_hex(8))
        if not app.config["REQUEST_LOGGING"] or request.path in {"/health", "/ready"}:
            return response
        duration_ms = round((time.monotonic() - g.request_started_at) * 1000, 1)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        app.logger.log(
            level,
            "request_completed",
            extra={
                "event": "request_completed",
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
