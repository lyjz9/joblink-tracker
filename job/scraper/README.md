Scraper details

- `parse_job_from_html(url)` returns a dict with keys: company, job_title, location, salary, description, skills, source
- `parse_job_with_browser(url)` is the stronger default for real job links. It uses a headless browser, structured job schema, ATS-specific patterns, and company-page fallbacks. It returns tracker-ready keys including date_applied, company, job_title, job_link, location, work_type, salary, skills, source, description, and ai_note.
- Add job-board API clients in `scraper.py` and call them from `app.py` when appropriate.
