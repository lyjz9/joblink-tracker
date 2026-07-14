# Hosted Deployment Notes

JobLink can run in a container, but free hosting is a rough fit for a browser-based scraper. Chromium needs more memory and CPU than a small static site or basic Flask app.

Hosting plans change, so check the current [Hugging Face pricing](https://huggingface.co/pricing) before creating a Docker Space. Docker support may require a paid account even when a basic CPU tier is listed as free.

Render also changes its limits over time. Compare the current [Render pricing](https://render.com/pricing) and [free service limits](https://render.com/docs/free) with Playwright's memory and outbound-traffic needs before relying on it.

The repo keeps `Dockerfile`, `requirements-prod.txt`, and `gunicorn.conf.py` for future self-hosting or paid hosting. None of them are needed for the Windows desktop app.

For a beta that does not require a subscription, use the [Windows desktop build](desktop_beta.md).
