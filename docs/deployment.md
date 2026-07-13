# Hosted Deployment Notes

JobLink Tracker can run in a container, but a reliable hosted scraper is not currently the zero-cost beta path.

Hugging Face's current pricing lists hosting Docker Spaces as a PRO feature. Its CPU Basic hardware can be free, but a free hardware label does not remove the account feature requirement shown during Docker Space creation. See the official [Hugging Face pricing page](https://huggingface.co/pricing).

Render offers a free web service, but it currently provides 512 MB RAM and 0.1 CPU, sleeps after 15 minutes of inactivity, and can suspend services that generate unusually high outbound traffic. Those limits are a poor fit for Playwright Chromium and multi-link scraping. See the official [Render pricing](https://render.com/pricing) and [free service limits](https://render.com/docs/free).

The repository keeps `Dockerfile`, `requirements-prod.txt`, and `gunicorn.conf.py` as a future paid-host or self-hosting option. They are not required for the Windows desktop beta.

For the no-subscription distribution path, use [desktop_beta.md](desktop_beta.md).
