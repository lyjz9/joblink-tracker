# Privacy

JobLink is built to work with job links and Excel trackers without keeping a permanent copy of an uploaded workbook.

## Local mode

The local beta runs on your computer. Browser captures, feedback, and reported extraction problems are written to the local `logs/` folder, which Git ignores.

Local diagnostic logs may include full job-posting URLs because the exact link helps reproduce site-specific scraper problems.

## Hosted mode

Hosted mode is enabled with `JOBLINK_ENV=production`.

- Browser capture is off by default. The Chrome extension is local-only for the first public release.
- Public endpoints cannot download internal extraction logs.
- Automatic diagnostics keep the job domain and a one-way URL hash instead of the full link.
- A reported problem includes only a limited set of job fields. Full links stay redacted unless the operator turns on `JOBLINK_STORE_FULL_URLS` and clearly discloses it.
- Uploaded `.xlsx` and `.xlsm` files are handled in a temporary directory, returned as a download, and removed before the response finishes.
- New Excel exports are created temporarily and returned from memory. They are not left in `exports/`.
- Results stay in browser storage so a refresh does not erase them. Clearing site data removes that local copy.

JobLink does not need your name, email address, password, payment information, or account credentials to read a public job posting.

## User responsibility

Review the extracted fields before saving them, and do not upload a workbook that contains unrelated sensitive information.
