from __future__ import annotations

import threading
import time

import pytest

from scraper.job_queue import (
    BackgroundJobManager,
    JobNotFound,
    JobQueueFull,
    ScrapeCapacityFull,
)


def _wait_for(manager: BackgroundJobManager, job_id: str, status: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = manager.snapshot(job_id)
        if snapshot["status"] == status:
            return snapshot
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not reach {status}.")


def test_background_jobs_never_exceed_worker_limit():
    lock = threading.Lock()
    active = 0
    peak = 0

    def scrape(url):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return {"job_link": url, "job_title": "Analyst"}

    manager = BackgroundJobManager(scrape, max_workers=2, max_pending_jobs=6)
    try:
        job = manager.submit([f"https://example.com/jobs/{index}" for index in range(6)])
        _wait_for(manager, job["job_id"], "completed")
        assert peak == 2
    finally:
        manager.shutdown()


def test_queue_rejects_more_than_the_configured_active_jobs():
    started = threading.Event()
    release = threading.Event()

    def scrape(url):
        started.set()
        release.wait(timeout=2)
        return {"job_link": url}

    manager = BackgroundJobManager(scrape, max_workers=1, max_pending_jobs=1)
    try:
        manager.submit(["https://example.com/jobs/one"])
        assert started.wait(timeout=1)
        with pytest.raises(JobQueueFull):
            manager.submit(["https://example.com/jobs/two"])
    finally:
        release.set()
        manager.shutdown()


def test_queued_job_can_be_cancelled_before_scraping():
    started = threading.Event()
    release = threading.Event()
    scraped = []

    def scrape(url):
        scraped.append(url)
        if url.endswith("one"):
            started.set()
            release.wait(timeout=2)
        return {"job_link": url}

    manager = BackgroundJobManager(scrape, max_workers=1, max_pending_jobs=2)
    try:
        first = manager.submit(["https://example.com/jobs/one"])
        assert started.wait(timeout=1)
        second = manager.submit(["https://example.com/jobs/two"])

        cancelled = manager.cancel(second["job_id"])

        assert cancelled["status"] == "cancelled"
        assert cancelled["items"][0]["status"] == "cancelled"
        release.set()
        _wait_for(manager, first["job_id"], "completed")
        assert scraped == ["https://example.com/jobs/one"]
    finally:
        release.set()
        manager.shutdown()


def test_completed_jobs_expire_after_ttl():
    now = [100.0]
    manager = BackgroundJobManager(
        lambda url: {"job_link": url},
        max_workers=1,
        ttl_seconds=5,
        clock=lambda: now[0],
    )
    try:
        job = manager.submit(["https://example.com/jobs/one"])
        _wait_for(manager, job["job_id"], "completed")
        now[0] += 5
        with pytest.raises(JobNotFound):
            manager.snapshot(job["job_id"])
    finally:
        manager.shutdown()


def test_sync_scrape_shares_the_background_capacity_limit():
    started = threading.Event()
    release = threading.Event()

    def scrape(url):
        started.set()
        release.wait(timeout=2)
        return {"job_link": url}

    manager = BackgroundJobManager(
        scrape,
        max_workers=1,
        sync_wait_seconds=0,
    )
    worker = threading.Thread(
        target=manager.run_sync,
        args=("https://example.com/jobs/one",),
    )
    try:
        worker.start()
        assert started.wait(timeout=1)
        with pytest.raises(ScrapeCapacityFull):
            manager.run_sync("https://example.com/jobs/two")
    finally:
        release.set()
        worker.join(timeout=2)
        manager.shutdown()
