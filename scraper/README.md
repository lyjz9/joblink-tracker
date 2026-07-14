# Scraper Details

JobLink tries the browser scraper first and falls back to a lighter HTML parser when needed.

- `parse_job_with_browser(url)` handles real job pages. It checks structured job data, common ATS layouts, and company-page patterns before falling back to visible page text.
- `parse_job_from_html(url)` is the lighter fallback. It can use page metadata and descriptions, but it has less context than the browser scraper.
- Both parsers return the fields used by the tracker: `date_applied`, `company`, `job_title`, `job_link`, `status`, `location`, `work_type`, `salary`, `follow_up`, and `source`.

Add a job-board API client only when the site offers a stable public endpoint and the integration makes the result more reliable.
