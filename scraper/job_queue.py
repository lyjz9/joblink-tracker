"""Bounded in-process background jobs for browser-backed extraction."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
import secrets
import threading
import time
from typing import Callable


TERMINAL_STATES = {"completed", "cancelled"}


class JobNotFound(KeyError):
    pass


class JobQueueFull(RuntimeError):
    pass


class ScrapeCapacityFull(RuntimeError):
    pass


class BackgroundJobManager:
    """Run small scrape batches with fixed browser concurrency and bounded backlog."""

    def __init__(
        self,
        scrape: Callable[[str], dict],
        *,
        max_workers: int = 2,
        max_pending_jobs: int = 25,
        ttl_seconds: int = 1800,
        sync_wait_seconds: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._scrape = scrape
        self._max_workers = max(1, min(4, int(max_workers)))
        self._max_pending_jobs = max(1, int(max_pending_jobs))
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._sync_wait_seconds = max(0, int(sync_wait_seconds))
        self._clock = clock
        self._lock = threading.RLock()
        self._capacity = threading.BoundedSemaphore(self._max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="joblink-scrape",
        )
        self._jobs: dict[str, dict] = {}
        self._futures: dict[str, list[Future]] = {}
        self._accepting = True
        self._shutdown_complete = False

    def submit(self, urls: list[str], date_applied: str = "") -> dict:
        if not urls:
            raise ValueError("At least one job link is required.")

        with self._lock:
            if not self._accepting:
                raise JobQueueFull("The scraper is shutting down.")
            self._remove_expired_locked()
            active = sum(
                job["status"] not in TERMINAL_STATES
                for job in self._jobs.values()
            )
            if active >= self._max_pending_jobs:
                raise JobQueueFull("The scrape queue is full.")

            job_id = secrets.token_urlsafe(24)
            now = self._clock()
            self._jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "date_applied": date_applied,
                "created_at": now,
                "updated_at": now,
                "finished_at": None,
                "cancel_requested": False,
                "items": [
                    {"url": url, "status": "queued", "result": None}
                    for url in urls
                ],
            }
            self._futures[job_id] = [
                self._executor.submit(self._run_item, job_id, index)
                for index in range(len(urls))
            ]
            return self._snapshot_locked(job_id)

    def snapshot(self, job_id: str) -> dict:
        with self._lock:
            self._remove_expired_locked()
            if job_id not in self._jobs:
                raise JobNotFound(job_id)
            return self._snapshot_locked(job_id)

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            self._remove_expired_locked()
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            if job["status"] in TERMINAL_STATES:
                return self._snapshot_locked(job_id)

            job["cancel_requested"] = True
            self._cancel_pending_locked(job_id, job)
            return self._snapshot_locked(job_id)

    def run_sync(self, url: str) -> dict:
        with self._lock:
            if not self._accepting:
                raise ScrapeCapacityFull("The scraper is shutting down.")
        acquired = self._capacity.acquire(timeout=self._sync_wait_seconds)
        if not acquired:
            raise ScrapeCapacityFull("All scraper workers are busy.")
        try:
            with self._lock:
                if not self._accepting:
                    raise ScrapeCapacityFull("The scraper is shutting down.")
            return self._scrape(url)
        finally:
            self._capacity.release()

    @property
    def is_accepting(self) -> bool:
        with self._lock:
            return self._accepting

    def begin_shutdown(self) -> None:
        with self._lock:
            if not self._accepting:
                return
            self._accepting = False
            for job_id, job in self._jobs.items():
                if job["status"] in TERMINAL_STATES:
                    continue
                job["cancel_requested"] = True
                self._cancel_pending_locked(job_id, job)

    def stats(self) -> dict:
        with self._lock:
            self._remove_expired_locked()
            active = sum(job["status"] not in TERMINAL_STATES for job in self._jobs.values())
            return {
                "workers": self._max_workers,
                "active_jobs": active,
                "retained_jobs": len(self._jobs),
                "queue_limit": self._max_pending_jobs,
                "accepting": self._accepting,
            }

    def shutdown(self, wait: bool = True) -> None:
        self.begin_shutdown()
        with self._lock:
            if self._shutdown_complete:
                return
            self._shutdown_complete = True
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _run_item(self, job_id: str, index: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] == "cancelled":
                return
            if job["cancel_requested"]:
                job["items"][index]["status"] = "cancelled"
                job["updated_at"] = self._clock()
                self._finalize_if_settled_locked(job)
                return
            job["status"] = "running"
            item = job["items"][index]
            item["status"] = "running"
            job["updated_at"] = self._clock()
            url = item["url"]
            date_applied = job["date_applied"]

        try:
            self._capacity.acquire()
            try:
                result = self._scrape(url)
            finally:
                self._capacity.release()
            if not isinstance(result, dict):
                result = {"error": "The scraper returned an unreadable result."}
        except Exception:
            result = {"error": "The scraper could not process this job page."}

        result = dict(result)
        result.setdefault("job_link", url)
        if date_applied:
            result["date_applied"] = date_applied

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            item = job["items"][index]
            item["result"] = result
            item["status"] = "failed" if result.get("error") else "completed"
            job["updated_at"] = self._clock()
            self._finalize_if_settled_locked(job)

    def _finalize_if_settled_locked(self, job: dict) -> None:
        if any(item["status"] in {"queued", "running"} for item in job["items"]):
            return
        job["status"] = "cancelled" if job["cancel_requested"] else "completed"
        job["finished_at"] = self._clock()
        job["updated_at"] = job["finished_at"]

    def _cancel_pending_locked(self, job_id: str, job: dict) -> None:
        for index, future in enumerate(self._futures.get(job_id, [])):
            if future.cancel() and job["items"][index]["status"] == "queued":
                job["items"][index]["status"] = "cancelled"
        job["updated_at"] = self._clock()
        self._finalize_if_settled_locked(job)

    def _snapshot_locked(self, job_id: str) -> dict:
        job = self._jobs[job_id]
        items = deepcopy(job["items"])
        processed = sum(item["status"] in {"completed", "failed"} for item in items)
        return {
            "job_id": job["id"],
            "status": job["status"],
            "total": len(items),
            "processed": processed,
            "completed": sum(item["status"] == "completed" for item in items),
            "failed": sum(item["status"] == "failed" for item in items),
            "items": items,
        }

    def _remove_expired_locked(self) -> None:
        now = self._clock()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job["status"] in TERMINAL_STATES
            and job["finished_at"] is not None
            and now - job["finished_at"] >= self._ttl_seconds
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)
            self._futures.pop(job_id, None)
