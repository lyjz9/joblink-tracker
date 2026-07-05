# Scraper Details

[![Component: scraper](https://img.shields.io/badge/component-scraper-2563eb)](app.py)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB)](../requirements.txt)
[![Playwright](https://img.shields.io/badge/browser-Playwright-2f855a)](browser_scraper_v2.py)
[![BeautifulSoup](https://img.shields.io/badge/parser-BeautifulSoup-6b7280)](scraper.py)
[![Flask endpoint](https://img.shields.io/badge/API-Flask-000000)](app.py)
[![Requests fallback](https://img.shields.io/badge/fallback-requests-6b7280)](scraper.py)
[![ATS pages](https://img.shields.io/badge/targets-ATS%20pages-2563eb)](browser_scraper_v2.py)

- `parse_job_from_html(url)` is the lightweight fallback parser. It may use page descriptions internally.
- `parse_job_with_browser(url)` is the stronger default for real job links. It uses a headless browser, structured job schema, ATS-specific patterns, and company-page fallbacks. It returns tracker-ready keys only: date_applied, company, job_title, job_link, status, location, work_type, salary, follow_up, and source.
- Add job-board API clients in `scraper.py` and call them from `app.py` when appropriate.
