# Privacy

JobLink Tracker is designed to process job links and Excel trackers without permanently retaining a user's application workbook.

## Local mode

The local beta runs on the user's own computer. Browser captures, feedback, and reported extraction problems are written only to the local `logs/` folder. These files are ignored by Git.

Local mode may keep full job-posting URLs in local diagnostic logs because those links help improve website-specific extraction patterns.

## Hosted mode

Hosted mode is enabled with `JOBLINK_ENV=production`.

- Browser capture is disabled by default. The Chrome extension remains a local-only feature for the first public release.
- Internal extraction logs cannot be downloaded through a public endpoint.
- Automatic diagnostic logs store the job domain and a one-way URL hash instead of the complete URL.
- A user-reported problem stores bounded job fields. Full posting links are redacted unless the operator explicitly enables `JOBLINK_STORE_FULL_URLS` and discloses that policy.
- Uploaded `.xlsx` and `.xlsm` files are opened from the request, processed in a temporary directory, returned as a download, and removed from the working directory before the response is sent.
- Generated Excel exports are created in a temporary directory and returned from memory. They are not kept in `exports/`.
- Browser results remain in the user's browser storage so a refresh does not immediately erase their work. Clearing site data removes that browser copy.

JobLink Tracker does not need names, email addresses, passwords, payment information, or account credentials to extract a public job posting.

## User responsibility

Users should review extracted fields before adding them to a tracker. They should avoid uploading workbooks containing unrelated sensitive information.

