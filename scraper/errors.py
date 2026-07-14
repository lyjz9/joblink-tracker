"""Keep web and API errors consistent and useful."""

from __future__ import annotations

from flask import current_app, g, jsonify
from werkzeug.exceptions import HTTPException


HTTP_MESSAGES = {
    400: "JobLink could not read that request.",
    404: "That page could not be found.",
    405: "That action is not available here.",
    413: "That upload is too large.",
    429: "JobLink is receiving too many requests. Wait a few minutes and try again.",
}


def register_error_handlers(app) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        status = error.code or 500
        message = HTTP_MESSAGES.get(status, "JobLink could not finish that request.")
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
        return _error_response("Something went wrong while JobLink handled that request.", 500)


def _error_response(message: str, status: int):
    payload = {"error": message}
    request_id = g.get("request_id", "")
    if request_id:
        payload["request_id"] = request_id
    return jsonify(payload), status
