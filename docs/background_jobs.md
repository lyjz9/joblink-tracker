# Background Scraping Jobs

JobLink submits pasted links as a small background batch instead of keeping one browser request open for every link. The browser creates a job, polls for progress, and adds each completed result to the editable table.

## API

- `POST /api/jobs` accepts `urls` and an optional `date_applied`, then returns `202 Accepted`, an opaque job ID, and a polling URL.
- `GET /api/jobs/<job_id>` returns job status, counts, and per-link results.
- `DELETE /api/jobs/<job_id>` requests cancellation. A page already being scraped is allowed to finish; links that have not started are cancelled.
- `POST /scrape` remains available for single-row retries and the existing Excel/VBA workflow. It shares the same scraper capacity limit.

Jobs are kept only in process memory and are removed after `JOBLINK_JOB_TTL_SECONDS`. Uploaded workbooks are not part of the job payload or job store.

## Limits

| Environment variable | Default | Purpose |
| --- | ---: | --- |
| `JOBLINK_SCRAPE_WORKERS` | `2` | Maximum concurrent browser-backed scrapes; capped at 4. |
| `JOBLINK_MAX_PENDING_JOBS` | `25` | Maximum queued or running batches. |
| `JOBLINK_JOB_TTL_SECONDS` | `1800` | How long completed and cancelled results remain pollable. |
| `JOBLINK_SCRAPE_CAPACITY_WAIT_SECONDS` | `2` | How long a synchronous retry waits for scraper capacity. |
| `JOBLINK_RATE_LIMIT_JOB_CREATE` | `10` | Batch submissions allowed per rate-limit window and client. |

The existing `JOBLINK_MAX_JOBS` limit still controls links per batch.

## Deployment Constraint

Use one web application process for this beta. Multiple Gunicorn workers or multiple containers would each create a separate in-memory job store, so a polling request could miss the process that accepted the job.

The queue uses bounded worker threads inside that one process, so one process does not mean unlimited or serial-only scraping. Before horizontally scaling the app, replace the in-memory job manager with a shared durable backend such as Redis while preserving the current API response shape.

After an application restart, in-progress and retained jobs are lost. The frontend reports the missing job clearly and users can submit the links again.
