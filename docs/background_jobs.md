# Background Scraping Jobs

When you submit several links, JobLink works through them in the background. The page checks in for progress and adds each finished result to the table as soon as it is ready.

## API

- `POST /api/jobs` accepts `urls` and an optional `date_applied`. It returns `202 Accepted`, a job ID, and the URL used to check progress.
- `GET /api/jobs/<job_id>` returns the latest status, counts, and result for each link.
- `DELETE /api/jobs/<job_id>` cancels work that has not started. A page already being read is allowed to finish.
- `POST /scrape` still handles one-link retries and the Excel/VBA workflow. It uses the same scraper capacity.

Jobs live only in the running app's memory and expire after `JOBLINK_JOB_TTL_SECONDS`. Uploaded workbooks never enter this queue.

## Limits

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `JOBLINK_SCRAPE_WORKERS` | `2` | Browser pages JobLink may read at the same time; capped at 4. |
| `JOBLINK_MAX_PENDING_JOBS` | `25` | Batches that may be queued or running. |
| `JOBLINK_JOB_TTL_SECONDS` | `1800` | How long finished or cancelled jobs remain available. |
| `JOBLINK_SCRAPE_CAPACITY_WAIT_SECONDS` | `2` | How long a one-link retry waits for an open scraper slot. |
| `JOBLINK_RATE_LIMIT_JOB_CREATE` | `10` | Batches one client may submit during a rate-limit window. |

The existing `JOBLINK_MAX_JOBS` limit still controls links per batch.

## Why The Beta Uses One Process

Run one web process for this beta. Each Gunicorn worker or container would otherwise have its own private queue, and a progress request might reach the wrong one.

That process still uses a small worker pool, so it can read more than one page without opening unlimited browsers. Before adding more processes, move the queue to shared storage such as Redis and keep the current API response shape.

The included `gunicorn.conf.py` keeps one process and uses HTTP threads so health checks, progress requests, and downloads still work while scraping runs. During shutdown, JobLink stops accepting new work and cancels anything that has not started.

Restarting the app clears the queue. If that happens mid-batch, the page explains that the job is gone and the links can be submitted again.
