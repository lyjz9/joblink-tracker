"""Centralized JSON error responses for web and API failures."""

from __future__ import annotations

from flask import current_app, g, jsonify
from werkzeug.exceptions import HTTPException


HTTP_MESSAGES = {
    400: "The request could not be read.",
    404: "The requested page was not found.",
    405: "That action is not allowed for this endpoint.",
    413: "The upload is larger than the allowed limit.",
    429: "Too many requests. Wait a few minutes and try again.",
}


def register_error_handlers(app) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        status = error.code or 500
        message = HTTP_MESSAGES.get(status, "The request could not be completed.")
        return _error_response(message, status)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        current_app.logger.exception(
            "unhandled_exception",
            extra={
                "event": "unhandled_exception",
                "request_id": g.get("request_id", ""),
                "error_type": type(error).__name__,
            },
        )
        return _error_response("The server could not complete this request.", 500)


def _error_response(message: str, status: int):
    payload = {"error": message}
    request_id = g.get("request_id", "")
    if request_id:
        payload["request_id"] = request_id
    return jsonify(payload), status
