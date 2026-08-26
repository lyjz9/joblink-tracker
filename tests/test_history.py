from __future__ import annotations

from flask import Flask

from scraper.history import HistoryStore, create_history_blueprint


def _job(**overrides):
    job = {
        "date_applied": "08/03/2026",
        "company": "Example Company",
        "job_title": "Operations Analyst",
        "job_link": "https://example.com/jobs/123?utm_source=linkedin",
        "location": "New York, NY",
        "work_type": "Hybrid",
        "salary": "$70,000 - $80,000 per year",
        "application_portal": "Company Website",
        "source": "Company Website",
        "confidence": "High",
        "confidence_score": 95,
    }
    job.update(overrides)
    return job


def test_history_upserts_tracking_variants_without_storing_private_page_content(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")

    first = store.save_many([{
        "status": "ready",
        "job": {**_job(), "description": "Do not keep this page text", "selected": True},
    }])[0]
    second = store.save_many([{
        "status": "review",
        "job": _job(
            job_link="https://www.example.com/jobs/123?source=indeed",
            salary="$75,000 per year",
            review_issues=["salary_needs_review"],
        ),
    }])[0]

    result = store.list_entries()
    assert first["id"] == second["id"]
    assert result["total"] == 1
    assert result["all_count"] == 1
    assert result["items"][0]["status"] == "review"
    assert result["items"][0]["job"]["salary"] == "$75,000 per year"
    assert "found_on" not in result["items"][0]["job"]
    assert result["items"][0]["job"]["application_portal"] == "Company Website"
    assert "description" not in result["items"][0]["job"]
    assert "selected" not in result["items"][0]["job"]


def test_history_supports_manual_rows_search_filters_and_deletion(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    saved = store.save_many([
        {"status": "ready", "job": _job()},
        {
            "status": "ready",
            "job": _job(
                company="Hand Added LLC",
                job_title="Coordinator",
                job_link="",
                manual=True,
                confidence="Manual",
            ),
        },
    ])

    manual = store.list_entries(query="hand added", status="manual")
    assert manual["total"] == 1
    assert manual["all_count"] == 2
    assert manual["items"][0]["job"]["job_title"] == "Coordinator"
    assert store.delete_ids([saved[0]["id"]]) == 1
    assert store.list_entries()["all_count"] == 1
    assert store.clear() == 1
    assert store.list_entries()["all_count"] == 0


def test_history_routes_save_list_and_clear_rows(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_history_blueprint(store, max_items=2))

    with app.test_client() as client:
        response = client.post("/api/history", json={"job": _job(), "status": "ready"})
        assert response.status_code == 200
        assert response.get_json()["all_count"] == 1
        saved_id = response.get_json()["items"][0]["id"]

        response = client.get("/api/history?q=operations&status=ready")
        assert response.status_code == 200
        assert response.get_json()["total"] == 1

        response = client.delete("/api/history", json={"ids": [saved_id]})
        assert response.get_json() == {"deleted": 1}

        client.post("/api/history", json={"job": _job(), "status": "ready"})
        response = client.delete("/api/history", json={"all": True})
        assert response.get_json() == {"deleted": 1}


def test_history_routes_reject_invalid_payloads(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(create_history_blueprint(store, max_items=1))

    with app.test_client() as client:
        assert client.post("/api/history", json={}).status_code == 400
        assert client.get("/api/history?status=unknown").status_code == 400
        assert client.delete("/api/history", json={"ids": []}).status_code == 400
        response = client.post(
            "/api/history",
            json={"job": _job(job_link="javascript:alert(1)")},
        )
        assert response.status_code == 400


def test_history_migrates_legacy_source_to_application_portal(tmp_path):
    import json
    import sqlite3

    database = tmp_path / "history.sqlite3"
    legacy_job = _job(
        job_link="https://example.wd5.myworkdayjobs.com/job/Analyst_R123",
        source="LinkedIn",
    )
    legacy_job.pop("application_portal")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE history_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_key TEXT NOT NULL UNIQUE,
                date_applied TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                job_title TEXT NOT NULL DEFAULT '',
                job_link TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                work_type TEXT NOT NULL DEFAULT '',
                salary TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                history_status TEXT NOT NULL DEFAULT 'review',
                is_manual INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                job_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO history_entries (
                identity_key, company, job_title, job_link, source,
                history_status, created_at, updated_at, job_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-row",
                legacy_job["company"],
                legacy_job["job_title"],
                legacy_job["job_link"],
                legacy_job["source"],
                "ready",
                "2026-08-01T12:00:00+00:00",
                "2026-08-01T12:00:00+00:00",
                json.dumps(legacy_job),
            ),
        )

    store = HistoryStore(database)
    item = store.list_entries()["items"][0]["job"]
    assert "found_on" not in item
    assert item["application_portal"] == "Workday"
    assert store.list_entries(query="Workday")["total"] == 1
