"""Environment-backed configuration for local and hosted Linc modes."""

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
    SCRAPE_PAGE_TIMEOUT_MS = _int_env("JOBLINK_SCRAPE_PAGE_TIMEOUT_SECONDS", 60) * 1000
    CHROMIUM_DISABLE_DEV_SHM_USAGE = _bool_env(
        "JOBLINK_CHROMIUM_DISABLE_DEV_SHM_USAGE", IS_PRODUCTION
    )

    CAPTURE_ENABLED = _bool_env("JOBLINK_CAPTURE_ENABLED", not IS_PRODUCTION)
    EXPOSE_ISSUES = _bool_env("JOBLINK_EXPOSE_ISSUES", False)
    STORE_FULL_URLS = _bool_env("JOBLINK_STORE_FULL_URLS", not IS_PRODUCTION)
    ADMIN_TOKEN = os.getenv("JOBLINK_ADMIN_TOKEN", "").strip()
    TRUST_PROXY_HOPS = _int_env("JOBLINK_TRUST_PROXY_HOPS", 0, minimum=0)

    JSON_LOGS = _bool_env("JOBLINK_JSON_LOGS", IS_PRODUCTION)
    REQUEST_LOGGING = _bool_env("JOBLINK_REQUEST_LOGGING", True)
    LOG_LEVEL = os.getenv("JOBLINK_LOG_LEVEL", "INFO").strip().upper()
    VERIFY_BROWSER_ON_STARTUP = _bool_env(
        "JOBLINK_VERIFY_BROWSER_ON_STARTUP", IS_PRODUCTION
    )
    REGISTER_ATEXIT = True

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    LOG_DIR = Path(os.getenv("JOBLINK_LOG_DIR", str(PROJECT_ROOT / "logs"))).resolve()


class LocalConfig(JobLinkConfig):
    APP_ENV = "local"
    IS_PRODUCTION = False
    CAPTURE_ENABLED = _bool_env("JOBLINK_CAPTURE_ENABLED", True)
    STORE_FULL_URLS = _bool_env("JOBLINK_STORE_FULL_URLS", True)
    JSON_LOGS = _bool_env("JOBLINK_JSON_LOGS", False)
    VERIFY_BROWSER_ON_STARTUP = _bool_env("JOBLINK_VERIFY_BROWSER_ON_STARTUP", False)
    CHROMIUM_DISABLE_DEV_SHM_USAGE = _bool_env(
        "JOBLINK_CHROMIUM_DISABLE_DEV_SHM_USAGE", False
    )
    SESSION_COOKIE_SECURE = False


class TestingConfig(LocalConfig):
    APP_ENV = "testing"
    TESTING = True
    CAPTURE_ENABLED = False
    STORE_FULL_URLS = False
    REQUEST_LOGGING = False
    VERIFY_BROWSER_ON_STARTUP = False
    REGISTER_ATEXIT = False


class ProductionConfig(JobLinkConfig):
    APP_ENV = "production"
    IS_PRODUCTION = True
    CAPTURE_ENABLED = _bool_env("JOBLINK_CAPTURE_ENABLED", False)
    STORE_FULL_URLS = _bool_env("JOBLINK_STORE_FULL_URLS", False)
    JSON_LOGS = _bool_env("JOBLINK_JSON_LOGS", True)
    VERIFY_BROWSER_ON_STARTUP = _bool_env("JOBLINK_VERIFY_BROWSER_ON_STARTUP", True)
    CHROMIUM_DISABLE_DEV_SHM_USAGE = _bool_env(
        "JOBLINK_CHROMIUM_DISABLE_DEV_SHM_USAGE", True
    )
    SESSION_COOKIE_SECURE = True


CONFIG_BY_ENVIRONMENT = {
    "local": LocalConfig,
    "development": LocalConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_for_environment(environment: str | None = None):
    name = str(environment or os.getenv("JOBLINK_ENV", "local")).strip().casefold()
    try:
        return CONFIG_BY_ENVIRONMENT[name]
    except KeyError as exc:
        choices = ", ".join(sorted(CONFIG_BY_ENVIRONMENT))
        raise RuntimeError(f"JOBLINK_ENV must be one of: {choices}.") from exc
