FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    JOBLINK_ENV=production \
    JOBLINK_LOG_DIR=/app/logs \
    JOBLINK_CHROMIUM_DISABLE_DEV_SHM_USAGE=true \
    HOME=/home/joblink \
    PORT=10000

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-prod.txt ./
RUN pip install -r requirements-prod.txt && \
    python -m playwright install --with-deps chromium && \
    chmod -R a+rX /ms-playwright

RUN useradd --create-home --uid 10001 joblink && \
    mkdir -p /app/logs && \
    chown -R joblink:joblink /app

COPY --chown=joblink:joblink . .

USER joblink

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/ready', timeout=3)"

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["gunicorn", "--config", "gunicorn.conf.py", "scraper.app:app"]
