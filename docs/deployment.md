# Free Beta Deployment

JobLink Tracker is prepared to run as a free Hugging Face Docker Space. This is the recommended first hosted beta because the free CPU Basic hardware has enough memory for Chromium, and testers only need a web link.

The deployment remains deliberately small: one Flask process, one browser scraping worker, an in-memory job queue, and temporary files. It is suitable for a limited beta, not unrestricted high-traffic use.

## Why These Pieces Exist

### Docker and Chromium

Playwright needs a compatible Chromium binary and Linux system libraries. The Docker build installs both, then runs JobLink as the unprivileged `joblink` user with the user ID Hugging Face expects.

### Gunicorn

Flask's development server is for local work. Gunicorn handles production HTTP threads, timeouts, termination signals, and graceful shutdown. It still uses one process because the current queue and results are stored in memory.

### Bounded background work

The free container defaults to one browser worker and at most ten pending batches. This keeps a few users from starting enough Chromium sessions to exhaust the shared beta instance.

### Health checks

- `GET /health` confirms that Flask can answer HTTP.
- `GET /ready` confirms that Chromium is installed and the queue is accepting work.

The container health check uses the host-provided `PORT` value and calls `/ready`, so a live but unusable scraper is not treated as healthy.

### GitHub sync

`.github/workflows/deploy-huggingface.yml` uses Hugging Face's official sync action. After the one-time account setup, a change merged to `main` is copied to the Space automatically. A manual **Run workflow** button is also available in GitHub Actions.

## Free Plan Limits

Hugging Face currently lists CPU Basic as free with 2 vCPU, 16 GB RAM, and 50 GB of non-persistent disk. Free Spaces sleep after extended inactivity, currently about 48 hours, and a new visitor wakes them again. Check the official [Spaces overview](https://huggingface.co/docs/hub/main/spaces-overview) and [sleep behavior](https://huggingface.co/docs/hub/spaces-gpus) before publishing in case these terms change.

There is no hosting charge while the Space stays on **CPU Basic**. Do not select upgraded hardware if the goal is a zero-cost beta.

Important beta limitations:

- The first visitor after sleep may wait for the Space to wake.
- Running jobs and queued results disappear during a restart or sleep cycle.
- Logs and reported issues are stored on non-persistent disk and may disappear.
- A public Space exposes both the app and its source code. The GitHub repository is already public.
- Browser capture remains local-only; hosted mode disables it.

## One-Time Setup Without A Terminal

### 1. Create the Space

1. Sign in at [Hugging Face](https://huggingface.co/).
2. Open **Spaces**, then choose **Create new Space**.
3. Use a name such as `joblink-tracker`.
4. Choose **Docker** as the SDK and **Blank** as the Docker template.
5. Choose **Public** visibility and keep **CPU Basic - Free** selected.
6. Create the Space.

Hugging Face Docker Spaces use port `7860` by default. The repository's Dockerfile and Gunicorn configuration already use that port.

### 2. Add Space Settings

Open the Space's **Settings** page.

Add this **Secret**:

| Name | Value |
| --- | --- |
| `JOBLINK_SECRET_KEY` | A random value at least 32 characters long. A password manager can generate one. |

Add this **Variable**:

| Name | Value | Reason |
| --- | --- | --- |
| `JOBLINK_TRUST_PROXY_HOPS` | `1` | Lets Flask read the original HTTPS request and client address through the hosting proxy. |

The Docker image already sets production mode, one scraper worker, ten pending jobs, JSON logs, Chromium shared-memory protection, and port `7860`. Do not put `JOBLINK_SECRET_KEY` in GitHub files or a normal variable.

### 3. Connect GitHub To The Space

1. In Hugging Face, open **Settings > Access Tokens**.
2. Create a fine-grained token with write access to this Space.
3. In the GitHub repository, open **Settings > Secrets and variables > Actions**.
4. Under **Variables**, add `HF_SPACE_ID` with `your-hugging-face-name/joblink-tracker`.
5. Under **Secrets**, add `HF_TOKEN` with the Hugging Face token.

The workflow reads those values without printing or committing the token. Hugging Face documents the same GitHub sync approach in [Managing Spaces with GitHub Actions](https://huggingface.co/docs/hub/spaces-github-actions).

### 4. Deploy

1. Merge the tested `local` branch into `main`.
2. Open the GitHub repository's **Actions** tab.
3. Select **Deploy free beta**.
4. Wait for the sync job to finish.
5. Open the Space and wait for its Docker build to finish.

Every later push to `main` repeats the sync. The workflow is skipped until `HF_SPACE_ID` is configured, so adding it to the repository does not publish anything unexpectedly.

## First Release Check

Verify these before sharing the Space URL:

1. Open `/health` and confirm the response status is `200`.
2. Open `/ready` and confirm the response status is `200` and the browser check is ready.
3. Scrape one current company career-page link.
4. Confirm company, title, location, work type, salary, source, and original link.
5. Download a new tracker and open it in Excel.
6. Upload the blank template, add one reviewed result, and open the updated workbook.
7. Submit a test feedback report without personal information.
8. Check Space logs and confirm that full job URLs and workbook values are absent.

If `/ready` returns `503`, open the Space logs first. The readiness response identifies whether Chromium is missing or the queue is shutting down.

## Local Container Check

Docker is optional for local development but useful before a public release:

```powershell
docker build -t joblink-tracker .
docker run --rm --init -p 7860:7860 `
  -e JOBLINK_SECRET_KEY="replace-with-a-random-32-character-value" `
  joblink-tracker
```

Then verify:

```powershell
Invoke-RestMethod http://127.0.0.1:7860/health
Invoke-RestMethod http://127.0.0.1:7860/ready
```

## Privacy

Hosted mode does not permanently save uploaded workbooks. Exports use temporary files, automatic diagnostics redact full job URLs, and browser capture is disabled. Users should still avoid uploading trackers containing unrelated sensitive information. See [privacy.md](privacy.md) for the full policy.

The hosting platform may retain infrastructure logs according to its own policy. The app should not be presented as storage for private documents or account credentials.

## Rollback

If a new release breaks the beta:

1. Revert the faulty commit on GitHub.
2. Merge the revert into `main`.
3. Wait for **Deploy free beta** and the Space rebuild to finish.
4. Recheck `/health`, `/ready`, scraping, and Excel output.

In-memory jobs cannot be recovered after a rollback or restart. Testers must resubmit anything that was running.

## Scaling Later

Do not add more Gunicorn processes while jobs live in memory. A shared queue and result store, stronger abuse controls, durable issue storage, and authentication should come before a larger public launch. A paid host is an optional later decision, not a requirement for this beta.
