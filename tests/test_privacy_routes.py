from __future__ import annotations

import json
from pathlib import Path

import pytest

import scraper.app as app_module


@pytest.fixture()
def client(tmp_path):
    app = app_module.create_app("testing", {
        "LOG_DIR": tmp_path,
        "IS_PRODUCTION": True,
        "SECRET_KEY": "x" * 32,
        "CAPTURE_ENABLED": False,
        "EXPOSE_ISSUES": False,
        "STORE_FULL_URLS": False,
        "RATE_LIMIT_FEEDBACK": 10,
        "RATE_LIMIT_CAPTURE": 20,
        "RATE_WINDOW_SECONDS": 600,
    })
    try:
        with app.test_client() as test_client:
            yield test_client
    finally:
        app_module.shutdown_app(app)


def test_sensitive_read_endpoints_are_not_public(client):
    assert client.get("/api/issues").status_code == 404
    assert client.get("/api/captures").status_code == 404
    assert client.post("/api/capture-page", json={"text": "a visible job posting"}).status_code == 404


def test_security_headers_are_added(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "max-age=" in response.headers["Strict-Transport-Security"]


def test_reported_issue_redacts_full_urls_in_production(client, tmp_path):
    response = client.post(
        "/api/report-issue",
        json={
            "status": "review",
            "job": {
                "company": "Example Company",
                "job_title": "Analyst",
                "job_link": "https://example.com/jobs/private-query?candidate=123",
                "preferred_job_link": "https://example.com/apply/123",
                "review_issues": ["missing_location"],
            },
        },
    )

    assert response.status_code == 200
    record = json.loads((tmp_path / "user_reported_issues.jsonl").read_text(encoding="utf-8"))
    assert "url" not in record
    assert len(record["url_hash"]) == 64
    assert record["job"]["job_link"] == ""
    assert record["job"]["preferred_job_link"] == ""


def test_export_uses_a_removed_temporary_directory(client, monkeypatch):
    observed = {}

    def fake_export(_jobs, outdir):
        observed["directory"] = Path(outdir)
        output = Path(outdir) / "tracker.xlsx"
        output.write_bytes(b"xlsx test bytes")
        return str(output)

    monkeypatch.setattr(app_module, "export_jobs_to_xlsx", fake_export)
    response = client.post("/export", json=[{"company": "Example Company"}])

    assert response.status_code == 200
    assert response.data == b"xlsx test bytes"
    assert not observed["directory"].exists()
