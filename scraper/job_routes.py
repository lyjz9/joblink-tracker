"""Flask routes for small background scraping batches."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request, url_for

from scraper.job_queue import BackgroundJobManager, JobNotFound, JobQueueFull
from scraper.security import validate_public_url


def create_job_blueprint(
    manager: BackgroundJobManager,
    *,
    max_links: int,
    rate_limited,
    create_rate_limit: int,
) -> Blueprint:
    blueprint = Blueprint("scrape_jobs", __name__, url_prefix="/api/jobs")

    @blueprint.post("")
    def create_job():
        if rate_limited("create-job", create_rate_limit):
            return jsonify({"error": "Too many batches were submitted. Wait a few minutes and try again."}), 429

        payload = request.get_json(silent=True) or {}
        raw_urls = payload.get("urls")
        if not isinstance(raw_urls, list) or not raw_urls:
            return jsonify({"error": "Add at least one job link."}), 400
        if len(raw_urls) > max_links:
            return jsonify({"error": f"Process up to {max_links} links at a time."}), 400

        urls = []
        seen = set()
        for index, raw_url in enumerate(raw_urls, start=1):
            url, error = validate_public_url(raw_url)
            if error:
                return jsonify({"error": f"Link {index}: {error}"}), 400
            key = url.rstrip("/").casefold()
            if key not in seen:
                seen.add(key)
                urls.append(url)

        date_applied, date_error = _normalize_date(payload.get("date_applied"))
        if date_error:
            return jsonify({"error": date_error}), 400

        try:
            snapshot = manager.submit(urls, date_applied)
        except JobQueueFull:
            return jsonify({"error": "JobLink is busy with another batch. Wait for it to finish, then try again."}), 503

        snapshot["poll_url"] = url_for("scrape_jobs.job_status", job_id=snapshot["job_id"])
        response = jsonify(snapshot)
        response.status_code = 202
        response.headers["Location"] = snapshot["poll_url"]
        response.headers["Retry-After"] = "1"
        return response

    @blueprint.get("/<job_id>")
    def job_status(job_id: str):
        try:
            return jsonify(manager.snapshot(job_id))
        except JobNotFound:
            return jsonify({"error": "This batch is no longer available. Submit the links again."}), 404

    @blueprint.delete("/<job_id>")
    def cancel_job(job_id: str):
        try:
            return jsonify(manager.cancel(job_id))
        except JobNotFound:
            return jsonify({"error": "This batch is no longer available. Submit the links again."}), 404

    return blueprint


def _normalize_date(value) -> tuple[str, str | None]:
    text = str(value or "").strip()
    if not text:
        return "", None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%m/%d/%Y"), None
        except ValueError:
            pass
    return "", "Choose a valid application date."
