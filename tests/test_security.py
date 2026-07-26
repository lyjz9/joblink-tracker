from __future__ import annotations

import io
import socket
from pathlib import Path

import pytest

from scraper.security import canonical_url_key, validate_public_url, validate_workbook_upload


def test_public_url_accepts_public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    url, error = validate_public_url("https://example.com/jobs/123")

    assert error is None
    assert url == "https://example.com/jobs/123"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "[Job](https://example.com/jobs/123?source=LinkedIn)",
            "https://example.com/jobs/123?source=LinkedIn",
        ),
        (
            "https://example.com/jobs/123?one=1&amp;two=2",
            "https://example.com/jobs/123?one=1&two=2",
        ),
        (
            "https://example.com/jobs/123\\",
            "https://example.com/jobs/123",
        ),
        (
            "\u200bhttps://example.com/jobs/123\u200b",
            "https://example.com/jobs/123",
        ),
    ],
)
def test_public_url_cleans_common_copy_paste_wrappers(monkeypatch, value, expected):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    url, error = validate_public_url(value)

    assert error is None
    assert url == expected


def test_canonical_url_key_ignores_tracking_parameters_and_linkedin_slug():
    plain = "https://www.linkedin.com/jobs/view/4443868424/"
    tracked = (
        "https://linkedin.com/jobs/view/entry-level-analyst-at-example-4443868424"
        "?utm_source=google_jobs_apply&trk=public_jobs"
    )

    assert canonical_url_key(plain) == canonical_url_key(tracked)
    assert canonical_url_key(
        "https://example.com/jobs/123?department=data&utm_source=linkedin"
    ) == canonical_url_key(
        "http://www.example.com/jobs/123/?department=data#apply"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost:5000/health",
        "http://127.0.0.1/private",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://example.com:invalid/jobs",
    ],
)
def test_public_url_rejects_unsafe_destinations(url):
    normalized, error = validate_public_url(url)

    assert normalized is None
    assert error


def test_workbook_validator_rejects_non_zip_content():
    with pytest.raises(ValueError, match="readable Excel workbook"):
        validate_workbook_upload(
            io.BytesIO(b"not an excel file"),
            "tracker.xlsx",
            max_uncompressed_bytes=1024,
            max_members=20,
        )


def test_workbook_validator_accepts_project_template():
    template = Path(__file__).resolve().parents[1] / "templates" / "linc_tracker_template.xlsx"
    with template.open("rb") as workbook:
        validate_workbook_upload(
            workbook,
            template.name,
            max_uncompressed_bytes=80 * 1024 * 1024,
            max_members=5000,
        )
