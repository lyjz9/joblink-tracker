Scraper details

- `parse_job_from_html(url)` is the lightweight fallback parser. It may use page descriptions internally.
- `parse_job_with_browser(url)` is the stronger default for real job links. It uses a headless browser, structured job schema, ATS-specific patterns, and company-page fallbacks. It returns tracker-ready keys only: date_applied, company, job_title, job_link, status, location, work_type, salary, follow_up, and source.
- Add job-board API clients in `scraper.py` and call them from `app.py` when appropriate.
