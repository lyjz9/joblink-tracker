"""Per-application runtime state and lifecycle helpers."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable

from flask import current_app

from scraper.job_queue import BackgroundJobManager


@dataclass
class RuntimeState:
    job_manager: BackgroundJobManager
    request_history: defaultdict
    request_history_lock: threading.Lock
    captures: deque
    issue_log: Path
    user_report_log: Path
    beta_feedback_log: Path
    browser_ready: bool
    browser_status: str
    shutdown_started: bool = False


def build_runtime(
    app,
    scrape: Callable[[str], dict],
    chromium_args: list[str] | None = None,
) -> RuntimeState:
    log_dir = Path(app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    browser_ready, browser_status = _browser_runtime_status(
        app.config["VERIFY_BROWSER_ON_STARTUP"],
        chromium_args=chromium_args,
    )
    manager = BackgroundJobManager(
        scrape,
        max_workers=app.config["SCRAPE_WORKERS"],
        max_pending_jobs=app.config["MAX_PENDING_JOBS"],
        ttl_seconds=app.config["JOB_TTL_SECONDS"],
        sync_wait_seconds=app.config["SCRAPE_CAPACITY_WAIT_SECONDS"],
    )
    return RuntimeState(
        job_manager=manager,
        request_history=defaultdict(deque),
        request_history_lock=threading.Lock(),
        captures=deque(maxlen=50),
        issue_log=log_dir / "extraction_issues.jsonl",
        user_report_log=log_dir / "user_reported_issues.jsonl",
        beta_feedback_log=log_dir / "beta_feedback.jsonl",
        browser_ready=browser_ready,
        browser_status=browser_status,
    )


def get_runtime() -> RuntimeState:
    return current_app.extensions["joblink_runtime"]


def begin_runtime_shutdown(app) -> None:
    runtime = app.extensions.get("joblink_runtime")
    if runtime is None or runtime.shutdown_started:
        return
    runtime.shutdown_started = True
    runtime.job_manager.begin_shutdown()


def shutdown_runtime(app, wait: bool = False) -> None:
    runtime = app.extensions.get("joblink_runtime")
    if runtime is None:
        return
    if not runtime.shutdown_started:
        begin_runtime_shutdown(app)
    runtime.job_manager.shutdown(wait=wait)


def _browser_runtime_status(
    verify: bool,
    chromium_args: list[str] | None = None,
) -> tuple[bool, str]:
    if not verify:
        return True, "not_checked"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=chromium_args or [],
            )
            browser.close()
            return True, "available"
    except Exception:
        pass
    return False, "missing"
