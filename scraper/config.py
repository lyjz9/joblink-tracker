"""Environment-backed configuration for local and hosted JobLink modes."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Production hosts can provide environment variables directly.
    def load_dotenv(*_args, **_kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


class JobLinkConfig:
    """Defaults are convenient locally and privacy-preserving in production."""

    APP_ENV = os.getenv("JOBLINK_ENV", "local").strip().casefold()
    IS_PRODUCTION = APP_ENV == "production"

    SECRET_KEY = os.getenv("JOBLINK_SECRET_KEY", "joblink-local-development-key")
    MAX_CONTENT_LENGTH = _int_env("JOBLINK_MAX_UPLOAD_MB", 12) * 1024 * 1024
    MAX_JOBS_PER_REQUEST = _int_env("JOBLINK_MAX_JOBS", 20)
    MAX_EXPORT_JOBS = _int_env("JOBLINK_MAX_EXPORT_JOBS", 100)
    MAX_WORKBOOK_UNCOMPRESSED_BYTES = _int_env(
        "JOBLINK_MAX_WORKBOOK_UNCOMPRESSED_MB", 80
    ) * 1024 * 1024
    MAX_WORKBOOK_ARCHIVE_MEMBERS = _int_env("JOBLINK_MAX_WORKBOOK_FILES", 5000)

    RATE_LIMIT_SCRAPE = _int_env("JOBLINK_RATE_LIMIT_SCRAPE", 30)
    RATE_LIMIT_EXPORT = _int_env("JOBLINK_RATE_LIMIT_EXPORT", 20)
    RATE_LIMIT_UPLOAD = _int_env("JOBLINK_RATE_LIMIT_UPLOAD", 10)
    RATE_LIMIT_FEEDBACK = _int_env("JOBLINK_RATE_LIMIT_FEEDBACK", 10)
    RATE_LIMIT_CAPTURE = _int_env("JOBLINK_RATE_LIMIT_CAPTURE", 20)
    RATE_LIMIT_JOB_CREATE = _int_env("JOBLINK_RATE_LIMIT_JOB_CREATE", 10)
    RATE_WINDOW_SECONDS = _int_env("JOBLINK_RATE_WINDOW_SECONDS", 600)

    SCRAPE_WORKERS = min(4, _int_env("JOBLINK_SCRAPE_WORKERS", 2))
    MAX_PENDING_JOBS = min(100, _int_env("JOBLINK_MAX_PENDING_JOBS", 25))
    JOB_TTL_SECONDS = _int_env("JOBLINK_JOB_TTL_SECONDS", 1800)
    SCRAPE_CAPACITY_WAIT_SECONDS = _int_env("JOBLINK_SCRAPE_CAPACITY_WAIT_SECONDS", 2)

    CAPTURE_ENABLED = _bool_env("JOBLINK_CAPTURE_ENABLED", not IS_PRODUCTION)
    EXPOSE_ISSUES = _bool_env("JOBLINK_EXPOSE_ISSUES", False)
    STORE_FULL_URLS = _bool_env("JOBLINK_STORE_FULL_URLS", not IS_PRODUCTION)
    ADMIN_TOKEN = os.getenv("JOBLINK_ADMIN_TOKEN", "").strip()
    TRUST_PROXY_HOPS = _int_env("JOBLINK_TRUST_PROXY_HOPS", 0, minimum=0)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    LOG_DIR = Path(os.getenv("JOBLINK_LOG_DIR", str(PROJECT_ROOT / "logs"))).resolve()
