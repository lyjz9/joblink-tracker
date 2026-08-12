"""Local SQLite storage for durable job-result history."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request

from scraper.security import canonical_url_key
from scraper.source_tracking import enrich_source_tracking


HISTORY_STATUSES = {"ready", "review", "error", "manual"}
HISTORY_JOB_KEYS = {
    "date_applied",
    "company",
    "job_title",
    "job_link",
    "status",
    "location",
    "work_type",
    "salary",
    "follow_up",
    "found_on",
    "application_portal",
    "source",
    "error",
    "preferred_job_link",
    "preferred_job_link_note",
    "review_issues",
    "review_notes",
    "review_details",
    "field_options",
    "source_reliability",
    "source_reliability_label",
    "source_reliability_note",
    "confidence",
    "confidence_score",
    "manual",
}
LONG_TEXT_KEYS = {"error", "review_notes", "source_reliability_note"}
URL_KEYS = {"job_link", "preferred_job_link"}


class HistoryStore:
    """Persist the latest visible result for each canonical job link."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS history_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identity_key TEXT NOT NULL UNIQUE,
                    date_applied TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    job_title TEXT NOT NULL DEFAULT '',
                    job_link TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    work_type TEXT NOT NULL DEFAULT '',
                    salary TEXT NOT NULL DEFAULT '',
                    found_on TEXT NOT NULL DEFAULT '',
                    application_portal TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    history_status TEXT NOT NULL DEFAULT 'review',
                    is_manual INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    job_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS history_entries_updated_idx
                    ON history_entries(updated_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS history_entries_status_idx
                    ON history_entries(history_status, updated_at DESC);
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(history_entries)")
            }
            if "found_on" not in columns:
                connection.execute(
                    "ALTER TABLE history_entries ADD COLUMN found_on TEXT NOT NULL DEFAULT ''"
                )
            if "application_portal" not in columns:
                connection.execute(
                    "ALTER TABLE history_entries ADD COLUMN application_portal TEXT NOT NULL DEFAULT ''"
                )
            self._backfill_source_tracking(connection)
            connection.execute("PRAGMA user_version = 2")

    @staticmethod
    def _backfill_source_tracking(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, job_link, found_on, application_portal, source, job_json
            FROM history_entries
            WHERE found_on = '' OR application_portal = ''
            """
        ).fetchall()
        for row in rows:
            try:
                job = json.loads(row["job_json"])
            except (TypeError, json.JSONDecodeError):
                job = {}
            if not isinstance(job, dict):
                job = {}
            job.setdefault("job_link", row["job_link"])
            job.setdefault("source", row["source"])
            if row["found_on"]:
                job.setdefault("found_on", row["found_on"])
            if row["application_portal"]:
                job.setdefault("application_portal", row["application_portal"])
            tracked = enrich_source_tracking(job, row["job_link"])
            connection.execute(
                """
                UPDATE history_entries
                SET found_on = ?, application_portal = ?, source = ?, job_json = ?
                WHERE id = ?
                """,
                (
                    tracked["found_on"],
                    tracked["application_portal"],
                    tracked["source"],
                    json.dumps(tracked, ensure_ascii=True, separators=(",", ":")),
                    row["id"],
                ),
            )

    def save_many(self, items: list[dict]) -> list[dict]:
        saved = []
        now = _utc_timestamp()
        with self._write_lock, self._connect() as connection:
            for item in items:
                raw_job = item.get("job") if isinstance(item, dict) else None
                if not isinstance(raw_job, dict):
                    raise ValueError("Each history item must include a job row.")
                job = _sanitize_job(raw_job)
                history_status = _history_status(job, item.get("status"))
                identity_key = _identity_key(job)
                job_json = json.dumps(job, ensure_ascii=True, separators=(",", ":"))
                connection.execute(
                    """
                    INSERT INTO history_entries (
                        identity_key, date_applied, company, job_title, job_link,
                        location, work_type, salary, found_on, application_portal,
                        source, history_status, is_manual, created_at, updated_at,
                        job_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(identity_key) DO UPDATE SET
                        date_applied = excluded.date_applied,
                        company = excluded.company,
                        job_title = excluded.job_title,
                        job_link = excluded.job_link,
                        location = excluded.location,
                        work_type = excluded.work_type,
                        salary = excluded.salary,
                        found_on = excluded.found_on,
                        application_portal = excluded.application_portal,
                        source = excluded.source,
                        history_status = excluded.history_status,
                        is_manual = excluded.is_manual,
                        updated_at = excluded.updated_at,
                        job_json = excluded.job_json
                    """,
                    (
                        identity_key,
                        job.get("date_applied", ""),
                        job.get("company", ""),
                        job.get("job_title", ""),
                        job.get("job_link", ""),
                        job.get("location", ""),
                        job.get("work_type", ""),
                        job.get("salary", ""),
                        job.get("found_on", ""),
                        job.get("application_portal", ""),
                        job.get("source", ""),
                        history_status,
                        int(bool(job.get("manual"))),
                        now,
                        now,
                        job_json,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM history_entries WHERE identity_key = ?",
                    (identity_key,),
                ).fetchone()
                saved.append(_row_to_entry(row))
        return saved

    def list_entries(
        self,
        *,
        query: str = "",
        status: str = "all",
        limit: int = 500,
        offset: int = 0,
    ) -> dict:
        clauses = []
        parameters: list[object] = []
        if status != "all":
            clauses.append("history_status = ?")
            parameters.append(status)
        if query:
            pattern = f"%{_escape_like(query)}%"
            clauses.append(
                "(" + " OR ".join(
                    f"{column} LIKE ? ESCAPE '\\' COLLATE NOCASE"
                    for column in (
                        "company", "job_title", "location", "work_type",
                        "salary", "found_on", "application_portal", "source",
                        "job_link", "date_applied",
                    )
                ) + ")"
            )
            parameters.extend([pattern] * 10)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM history_entries{where}",
                parameters,
            ).fetchone()[0]
            all_count = connection.execute(
                "SELECT COUNT(*) FROM history_entries"
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM history_entries{where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
        return {
            "items": [_row_to_entry(row) for row in rows],
            "total": total,
            "all_count": all_count,
            "limit": limit,
            "offset": offset,
        }

    def delete_ids(self, ids: list[int]) -> int:
        unique_ids = sorted(set(ids))
        if not unique_ids:
            return 0
        placeholders = ",".join("?" for _ in unique_ids)
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM history_entries WHERE id IN ({placeholders})",
                unique_ids,
            )
        return cursor.rowcount

    def clear(self) -> int:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM history_entries")
        return cursor.rowcount

    def count(self) -> int:
        with self._connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM history_entries"
            ).fetchone()[0]


def create_history_blueprint(store: HistoryStore, *, max_items: int) -> Blueprint:
    blueprint = Blueprint("history", __name__, url_prefix="/api/history")

    @blueprint.get("")
    def list_history():
        query = str(request.args.get("q") or "").strip()[:200]
        status = str(request.args.get("status") or "all").strip().casefold()
        if status != "all" and status not in HISTORY_STATUSES:
            return jsonify({"error": "Choose a valid history status."}), 400
        limit = _bounded_integer(request.args.get("limit"), default=500, minimum=1, maximum=1000)
        offset = _bounded_integer(request.args.get("offset"), default=0, minimum=0, maximum=1_000_000)
        return jsonify(store.list_entries(query=query, status=status, limit=limit, offset=offset))

    @blueprint.post("")
    def save_history():
        payload = request.get_json(silent=True) or {}
        if isinstance(payload.get("items"), list):
            items = payload["items"]
        elif isinstance(payload.get("job"), dict):
            items = [payload]
        else:
            return jsonify({"error": "Add at least one job row to history."}), 400
        if not items or len(items) > max_items:
            return jsonify({"error": f"Save up to {max_items} history rows at a time."}), 400
        try:
            saved = store.save_many(items)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({
            "items": saved,
            "saved": len(saved),
            "all_count": store.count(),
        })

    @blueprint.delete("")
    def delete_history():
        payload = request.get_json(silent=True) or {}
        if payload.get("all") is True:
            return jsonify({"deleted": store.clear()})
        raw_ids = payload.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 1000:
            return jsonify({"error": "Choose one or more history rows to delete."}), 400
        try:
            ids = [int(value) for value in raw_ids if int(value) > 0]
        except (TypeError, ValueError):
            return jsonify({"error": "History row IDs must be valid numbers."}), 400
        if not ids:
            return jsonify({"error": "Choose one or more history rows to delete."}), 400
        return jsonify({"deleted": store.delete_ids(ids)})

    return blueprint


def _sanitize_job(raw_job: dict) -> dict:
    job = {}
    for key in HISTORY_JOB_KEYS:
        if key not in raw_job:
            continue
        value = raw_job[key]
        if key == "manual":
            job[key] = bool(value)
        elif key == "confidence_score":
            try:
                job[key] = max(0, min(100, int(float(value))))
            except (TypeError, ValueError):
                continue
        elif key == "review_issues" and isinstance(value, list):
            job[key] = [_bounded_text(item, 100) for item in value[:20] if _bounded_text(item, 100)]
        elif key == "review_details" and isinstance(value, list):
            job[key] = [
                {
                    item_key: _bounded_text(item.get(item_key), 500)
                    for item_key in ("code", "label", "action")
                    if item.get(item_key)
                }
                for item in value[:20]
                if isinstance(item, dict)
            ]
        elif key == "field_options" and isinstance(value, dict):
            job[key] = {
                _bounded_text(field, 50): [
                    _bounded_text(option, 500)
                    for option in options[:5]
                    if _bounded_text(option, 500)
                ]
                for field, options in list(value.items())[:10]
                if isinstance(options, list) and _bounded_text(field, 50)
            }
        elif key == "source_reliability" and isinstance(value, dict):
            job[key] = {
                item_key: _bounded_text(value.get(item_key), 500)
                for item_key in ("level", "note")
                if value.get(item_key)
            }
        else:
            limit = 4096 if key in URL_KEYS else 2000 if key in LONG_TEXT_KEYS else 500
            text = _bounded_text(value, limit)
            if text:
                job[key] = text

    link = job.get("job_link", "")
    if link and not _http_url(link):
        raise ValueError("History can only save complete http:// or https:// job links.")
    preferred = job.get("preferred_job_link", "")
    if preferred and not _http_url(preferred):
        job.pop("preferred_job_link", None)
    if not link and not (job.get("company") and job.get("job_title")):
        raise ValueError("A history row needs a job link or a company and job title.")
    return enrich_source_tracking(job, link)


def _history_status(job: dict, supplied: object) -> str:
    if job.get("error"):
        return "error"
    status = str(supplied or "").strip().casefold()
    if status == "review" or job.get("review_issues") or job.get("review_notes"):
        return "review"
    if job.get("manual") or str(job.get("confidence", "")).casefold() == "manual":
        return "manual"
    return status if status in HISTORY_STATUSES else "ready"


def _identity_key(job: dict) -> str:
    link = job.get("job_link", "")
    if link:
        return f"url:{canonical_url_key(link)}"
    fields = "\n".join(
        str(job.get(key, "")).strip().casefold()
        for key in ("date_applied", "company", "job_title", "location")
    )
    return "manual:" + hashlib.sha256(fields.encode("utf-8")).hexdigest()


def _row_to_entry(row: sqlite3.Row) -> dict:
    try:
        job = json.loads(row["job_json"])
    except (TypeError, json.JSONDecodeError):
        job = {}
    row_keys = set(row.keys())
    if not job.get("found_on") and "found_on" in row_keys:
        job["found_on"] = row["found_on"]
    if not job.get("application_portal") and "application_portal" in row_keys:
        job["application_portal"] = row["application_portal"]
    if not job.get("source") and "source" in row_keys:
        job["source"] = row["source"]
    job = enrich_source_tracking(job, job.get("job_link"))
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["history_status"],
        "job": job,
    }


def _http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _bounded_text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _bounded_integer(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
