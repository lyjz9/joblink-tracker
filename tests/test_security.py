from __future__ import annotations

import io
import socket
from pathlib import Path

import pytest

from scraper.security import validate_public_url, validate_workbook_upload


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
