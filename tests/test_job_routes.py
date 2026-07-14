from __future__ import annotations

import time

import pytest
from flask import Flask

from scraper.job_queue import BackgroundJobManager
from scraper.job_routes import create_job_blueprint


@pytest.fixture()
def job_api(monkeypatch):
    monkeypatch.setattr(
        "scraper.job_routes.validate_public_url",
        lambda value: (str(value).strip(), None),
    )
    manager = BackgroundJobManager(
        lambda url: {
            "company": "Example Company",
            "job_title": "Analyst",
            "job_link": url,
        },
        max_workers=1,
        max_pending_jobs=2,
        ttl_seconds=30,
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(
        create_job_blueprint(
            manager,
            max_links=2,
            rate_limited=lambda _scope, _limit: False,
            create_rate_limit=10,
        )
    )
    try:
        with app.test_client() as client:
            yield client, manager
    finally:
        manager.shutdown()


def _poll(client, poll_url: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(poll_url)
        assert response.status_code == 200
        snapshot = response.get_json()
        if snapshot["status"] in {"completed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("Scrape job did not finish.")


def test_create_job_returns_pollable_results_with_application_date(job_api):
    client, _manager = job_api
    response = client.post(
        "/api/jobs",
        json={
            "urls": ["https://example.com/jobs/one", "https://example.com/jobs/two"],
            "date_applied": "2026-07-01",
        },
    )

    assert response.status_code == 202
    assert response.headers["Location"].startswith("/api/jobs/")
    snapshot = _poll(client, response.get_json()["poll_url"])
    assert snapshot["status"] == "completed"
    assert snapshot["completed"] == 2
    assert [item["result"]["date_applied"] for item in snapshot["items"]] == [
        "07/01/2026",
        "07/01/2026",
    ]


def test_create_job_deduplicates_equivalent_links(job_api):
    client, _manager = job_api
    response = client.post(
        "/api/jobs",
        json={"urls": ["https://example.com/jobs/one", "https://example.com/jobs/one/"]},
    )

    assert response.status_code == 202
    assert response.get_json()["total"] == 1


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"urls": []}, "at least one"),
        (
            {"urls": ["https://example.com/1", "https://example.com/2", "https://example.com/3"]},
            "up to 2",
        ),
        ({"urls": ["https://example.com/1"], "date_applied": "not-a-date"}, "valid application date"),
    ],
)
def test_create_job_rejects_invalid_batches(job_api, payload, message):
    client, _manager = job_api
    response = client.post("/api/jobs", json=payload)

    assert response.status_code == 400
    assert message in response.get_json()["error"].lower()


def test_unknown_job_is_not_exposed(job_api):
    client, _manager = job_api

    assert client.get("/api/jobs/not-a-real-id").status_code == 404
    assert client.delete("/api/jobs/not-a-real-id").status_code == 404
