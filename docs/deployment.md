# Production Deployment

This phase packages the existing Flask and Playwright application for a small public beta. It does not change the product into a distributed service, and it deliberately keeps one application process while jobs remain in memory.

## Why Each Part Exists

### Application factory

`create_app()` gives every test or server process its own queue, capture buffer, rate-limit history, and log paths. Import-time global state is difficult to test and can leak state between app instances.

### Gunicorn

Flask's development server is useful locally but is not a production process manager. Gunicorn handles signals, worker lifetime, HTTP threads, timeouts, and graceful termination. The configuration uses one process because the current job store is in memory; four HTTP threads keep polling and health requests responsive while the separate scraper pool does browser work.

### Docker and Chromium

Playwright needs a browser binary plus Linux system libraries. The Docker build installs the exact dependencies from `requirements-prod.txt`, installs Chromium with Playwright, and runs the app as an unprivileged `joblink` user. This makes local, staging, and hosted builds use the same runtime instead of depending on whatever happens to be installed on a server.

### Bounded timeouts and shutdown

Browser navigation has a configurable timeout so slow or stalled sites do not occupy capacity forever. When Gunicorn receives a termination signal, JobLink stops accepting jobs, cancels queued links, and allows work already running to finish within the host's shutdown window.

### Health and readiness

- `GET /health` is a liveness check. A `200` means the Flask process can answer HTTP.
- `GET /ready` is a traffic check. It returns `503` when Chromium is unavailable or the queue is shutting down.

Keeping these checks separate prevents a deployment platform from routing users to a process that is alive but unable to scrape.

### Structured logging and request IDs

Production logs are one JSON object per line. They include time, severity, request ID, HTTP method, path, status, and duration. They intentionally exclude query strings, submitted URLs, workbook contents, request bodies, and extracted job fields. A returned `X-Request-ID` lets a user report a failure without exposing their tracker.

## Recommended First Host

Use a Docker web service on Render for the first public beta. Render can build the repository's Dockerfile, bind the service through its `PORT` environment variable, check `/ready`, issue TLS certificates, attach a custom domain, and roll back a deploy.

The included `render.yaml` selects the Standard instance: 2 GB RAM and 1 CPU at **$25 USD per month as of July 2026**. Chromium is memory-heavy, so the Free and Starter tiers' 512 MB RAM are useful only for a brief smoke test with `JOBLINK_SCRAPE_WORKERS=1`; they are not the recommended public configuration. Confirm current prices on [Render's pricing page](https://render.com/pricing) before creating the service.

## Production Start Command

The Docker image starts:

```text
gunicorn --config gunicorn.conf.py scraper.app:app
```

Gunicorn binds to `0.0.0.0:$PORT`. Do not add a second Gunicorn worker while the queue is stored in memory.

## Required Environment

| Variable | Required value or default | Reason |
| --- | --- | --- |
| `JOBLINK_ENV` | `production` | Enables secure production defaults. |
| `JOBLINK_SECRET_KEY` | Generated 32+ character secret | Protects Flask signing; startup fails for placeholders. |
| `JOBLINK_TRUST_PROXY_HOPS` | `1` on Render | Trusts exactly one hosting proxy for scheme and client address. |
| `JOBLINK_SCRAPE_WORKERS` | `2` | Caps simultaneous Chromium work. |
| `JOBLINK_MAX_PENDING_JOBS` | `25` | Bounds queued batches and memory use. |
| `JOBLINK_SCRAPE_PAGE_TIMEOUT_SECONDS` | `60` | Caps each browser navigation attempt. |
| `JOBLINK_CHROMIUM_DISABLE_DEV_SHM_USAGE` | `true` in the container | Avoids crashes caused by small container shared memory. |
| `JOBLINK_VERIFY_BROWSER_ON_STARTUP` | `true` | Keeps readiness false if Chromium was not installed. |
| `JOBLINK_JSON_LOGS` | `true` | Produces searchable structured logs. |
| `JOBLINK_LOG_LEVEL` | `INFO` | Controls application log detail. |

The Render blueprint generates `JOBLINK_SECRET_KEY`; never commit its resulting value.

## Local Container Check

Docker is required for this check:

```powershell
docker build -t joblink-tracker .
docker run --rm --init -p 10000:10000 `
  -e JOBLINK_SECRET_KEY="replace-with-a-random-32-character-value" `
  joblink-tracker
```

Then verify:

```powershell
Invoke-RestMethod http://127.0.0.1:10000/health
Invoke-RestMethod http://127.0.0.1:10000/ready
```

## Render Deployment

1. Merge the tested branch into `main`.
2. In Render, create a new Blueprint and select this repository.
3. Confirm the Docker web service and Standard plan from `render.yaml`.
4. Let Render generate `JOBLINK_SECRET_KEY`.
5. Wait for the Docker build and `/ready` health check to pass.
6. Open the generated `onrender.com` URL and test one job, one Excel download, and one uploaded tracker copy.
7. Review logs and confirm that full job URLs and workbook values are absent.

Render expects public services to bind to `0.0.0.0:$PORT` and can build directly from a Dockerfile. See the official [web service](https://render.com/docs/web-services), [Docker](https://render.com/docs/docker), and [health check](https://render.com/docs/health-checks) documentation.

## Rollback

If a deploy fails its build or readiness check, Render leaves the previous deployment serving traffic. If a successful deploy later behaves incorrectly:

1. Open the service's Deploys page.
2. Select the last known-good deploy.
3. Choose **Rollback**.
4. Verify `/health`, `/ready`, scraping, and Excel output.
5. Revert the faulty Git commit and deploy the corrected `main` branch.

Do not rely on rollback to recover in-memory jobs. Users must resubmit jobs that were running during a restart. See [Render's rollback documentation](https://render.com/docs/rollbacks).

## Custom Domain

After the generated Render URL is stable:

1. Add the domain in the service's **Settings > Custom Domains** section.
2. Add the DNS records Render provides at the domain registrar.
3. Wait for Render's managed TLS certificate to become active.
4. Test HTTPS, uploads, downloads, and request headers on the custom domain.

Keep the default Render subdomain enabled until the custom domain passes these checks.

## Scaling Later

The next scaling boundary is a shared queue and result store such as Redis. Only after that change should Gunicorn use multiple processes or Render use multiple instances. Authentication, abuse controls, and durable feedback storage should also be reviewed before promoting the private beta to unrestricted public access.
