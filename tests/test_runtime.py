from __future__ import annotations

import json

import pytest

import scraper.app as app_module
from scraper.runtime import get_runtime


def _testing_app(tmp_path, **overrides):
    return app_module.create_app("testing", {"LOG_DIR": tmp_path, **overrides})


def test_app_factory_keeps_runtime_state_isolated(tmp_path):
    first = _testing_app(tmp_path / "first")
    second = _testing_app(tmp_path / "second")
    try:
        with first.app_context():
            first_runtime = get_runtime()
        with second.app_context():
            second_runtime = get_runtime()

        assert first_runtime is not second_runtime
        assert first_runtime.job_manager is not second_runtime.job_manager
        assert first_runtime.issue_log.parent != second_runtime.issue_log.parent
    finally:
        app_module.shutdown_app(first)
        app_module.shutdown_app(second)


def test_production_rejects_a_placeholder_secret(tmp_path):
    with pytest.raises(RuntimeError, match="JOBLINK_SECRET_KEY"):
        app_module.create_app("production", {
            "LOG_DIR": tmp_path,
            "SECRET_KEY": "replace-me",
            "VERIFY_BROWSER_ON_STARTUP": False,
        })


def test_production_uses_secure_privacy_defaults(tmp_path):
    app = app_module.create_app("production", {
        "LOG_DIR": tmp_path,
        "SECRET_KEY": "x" * 32,
        "VERIFY_BROWSER_ON_STARTUP": False,
        "REGISTER_ATEXIT": False,
    })
    try:
        assert app.config["IS_PRODUCTION"] is True
        assert app.config["CAPTURE_ENABLED"] is False
        assert app.config["STORE_FULL_URLS"] is False
        assert app.config["SESSION_COOKIE_SECURE"] is True
        assert app.config["JSON_LOGS"] is True
    finally:
        app_module.shutdown_app(app)


def test_readiness_fails_after_shutdown_begins(tmp_path):
    app = _testing_app(tmp_path)
    try:
        with app.test_client() as client:
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 200
            app_module.begin_shutdown(app)
            response = client.get("/ready")

        assert response.status_code == 503
        assert response.get_json()["checks"]["queue"] == "shutting_down"
    finally:
        app_module.shutdown_app(app)


def test_central_error_response_has_request_id_without_details(tmp_path, capsys):
    app = _testing_app(tmp_path, JSON_LOGS=True)

    def boom():
        raise RuntimeError("private technical detail")

    app.add_url_rule("/boom", view_func=boom)
    try:
        with app.test_client() as client:
            response = client.get("/boom", headers={"X-Request-ID": "request_12345"})

        assert response.status_code == 500
        assert response.headers["X-Request-ID"] == "request_12345"
        assert response.get_json() == {
            "error": "The server could not complete this request.",
            "request_id": "request_12345",
        }
        assert b"private technical detail" not in response.data
        assert "private technical detail" not in capsys.readouterr().out
    finally:
        app_module.shutdown_app(app)


def test_json_request_logs_exclude_query_strings(tmp_path, capsys):
    app = _testing_app(
        tmp_path,
        JSON_LOGS=True,
        REQUEST_LOGGING=True,
    )
    try:
        with app.test_client() as client:
            response = client.get("/missing?candidate=private-value")
        output = capsys.readouterr().out

        assert response.status_code == 404
        assert "private-value" not in output
        records = [json.loads(line) for line in output.splitlines() if line.strip()]
        request_record = next(record for record in records if record.get("event") == "request_completed")
        assert request_record["path"] == "/missing"
        assert request_record["status_code"] == 404
    finally:
        app_module.shutdown_app(app)


def test_scrape_timeout_and_chromium_args_are_forwarded(monkeypatch, tmp_path):
    observed = {}

    def fake_browser_scrape(url, timeout, launch_args):
        observed.update(url=url, timeout=timeout, launch_args=launch_args)
        return {
            "company": "Example Company",
            "job_title": "Analyst",
            "location": "New York, NY",
            "work_type": "n/a",
            "salary": "n/a",
            "source": "Company Website",
            "job_link": url,
        }

    monkeypatch.setattr(app_module, "parse_job_with_browser", fake_browser_scrape)
    result = app_module._scrape_url(
        "https://example.com/jobs/one",
        page_timeout_ms=17000,
        chromium_args=["--disable-dev-shm-usage"],
        issue_log=tmp_path / "issues.jsonl",
    )

    assert result["company"] == "Example Company"
    assert observed == {
        "url": "https://example.com/jobs/one",
        "timeout": 17000,
        "launch_args": ["--disable-dev-shm-usage"],
    }
