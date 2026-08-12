# Job Tracker Project Development Handoff

Last updated: 2026-08-12

This document is for a new development session with no prior conversation
context. Read it before changing code. The repository is the source of truth if
anything here later becomes stale.

## Snapshot

- Repository: `https://github.com/lyjz9/joblink-tracker`
- Permanent product name: **Undecided**
- Current repository label: `Linc`, but the user has explicitly rejected it as
  the final product name.
- Current version target: **v0.1.0 beta**
- Current branch: `main`
- Latest implementation commit:
  `d1a98cb` (`Fix six-site job extraction patterns`)
- Recent focused commits:
  - `d1a98cb` (`Fix six-site job extraction patterns`)
  - `5120e70` (`Reject unavailable job page shells`)
  - `9722386` (`Fix multi-site job field extraction`)
  - `cf625f0` (`Default unspecified work type to onsite`)
  - `ec08b6b` (`Fix location and work type extraction`)
  - `ed98779` (`Improve multi-site job extraction`)
  - `f9cdda0` (`Add local job history`)
  - `dde931c` (`Simplify workspace controls`)
  - `6307bec` (`Move tracker controls to header`)
- Git state at handoff: clean; local `main` matches `origin/main`
- Old branch: `local` is stale at `87b477e`. Do not switch to it or merge it
  into `main` without first understanding the large set of newer commits.
- No Git tag exists locally yet.
- The only local ZIP under `dist/` is an obsolete pre-rename build named
  `JobLink-Tracker-Windows.zip`. Do not publish it.

Use neutral wording such as "the app", "the project", or "the job tracker"
until the user chooses a final name. Do not introduce `Unknown` or another
temporary public name. Do not expand the current `Linc` branding into new
user-facing text.

The repository still contains `Linc` in UI text, filenames, local-data paths,
the Chrome extension, packaging, and documentation. Those references are
technical facts, not approval of that name. Do not perform a blind replacement.
A final rename must be coordinated across all naming surfaces and include
compatibility decisions for saved browser sessions, environment variables,
desktop data paths, workbook filenames, and release artifacts.

The user wants every completed change committed and pushed to GitHub. Keep each
commit focused, explain what changed in plain language, and do not include
unrelated files.

## Immediate State At Session End

The most recent work simplified the local web app and added durable local
History. It is complete and pushed:

- Finished scrapes and manual rows are saved to local SQLite History.
- History supports search, status filters, restore, Excel download, selected
  deletion, and clear all.
- The current Workspace remains tab-scoped and starts clean in a new tab.
- The empty Workspace now focuses on links, date, and `Get job details`.
- Manual entry and browser capture live under `Other ways to add`.
- Result filters, salary controls, and row tools appear only when jobs exist.
- Report and Remove appear only when rows are selected.
- Excel controls were removed from beneath Results and moved into a permanent
  `Tracker` button in the header.
- The Tracker panel is available before scraping, reports usable row count,
  contains workbook selection and duplicate behavior, and closes cleanly with
  its X button or Escape.
- Tracker and Feedback panels are mutually exclusive.

The earlier Original, Hourly, and Yearly salary modes remain intact, including
part-time Hours/week estimates and Excel export in the selected format.

The 2026-08-12 six-site extraction audit is complete and pushed:

- An explicit nearby pay-period label is retained when the numeric salary
  omits its unit. For example, `Hourly: $20-$35` becomes `$20-$35 per hour`,
  so the Hourly/Yearly salary views can convert it safely.
- A clearly job-shaped browser title such as `Role | Company Careers` or
  `Role Job Details | Company` can override stale JSON-LD title data.
- Workday organization codes containing both letters and numbers, such as
  `02B`, are removed from the displayed employer name.
- Company inference now uses the original URL's platform and domain even when
  embedded scripts mention another ATS. This prevents company career pages
  from losing their employer name.
- Inline semantic fields such as `<strong>Location:</strong> New York, NY` are
  preferred over truncated free-text guesses, while LinkedIn description text
  such as `Location: Remote | Type: Full Time` is not treated as a geographic
  label.
- `Traditional office environment` is accepted as explicit Onsite evidence.
- `Careers Site` is removed from otherwise usable employer names, and common
  brand punctuation/casing is restored for L'Oréal and JetBlue.
- Live checks through the real background queue returned:
  - Rho: Quantitative Analyst Intern, New York City, Onsite,
    `$20-$35 per hour`;
  - L'Oréal: Operations - Intern - 12 month, New York, Hybrid, `$29.50`;
  - Federal Reserve Bank of New York: Regulatory Data Analyst, New York,
    Onsite, `$79,300 - $85,000 / year`;
  - JetBlue: Analyst System Operations Strategy & Analytics, Long Island City,
    Onsite, `$64,350.00 and $89,600.00 per year`;
  - MTA: Operations Analyst Accounts Payable, New York, Onsite,
    `$45,125 - $75,208`;
  - MFA on LinkedIn remained correct as Hybrid with no published salary.

The 2026-08-10 false-success audit is complete and pushed:

- Exact unavailable headings such as `Job not found`, `Position not found`,
  and `Opportunity not found` are rejected instead of becoming plausible
  Review or Ready rows.
- The direct-HTML path now checks whether a Greenhouse or other supported job
  URL redirected to a general board before extracting generic board content.
- Exact shell titles such as `Job Search`, `Current openings`, and `All jobs`
  are treated as job-list pages. Their plausible company, location, salary,
  and default Onsite values are cleared rather than shown as a real job.
- Dayforce is now a first-class source label and reliability category instead
  of appearing as `Company Website`.
- Expired rows use the specific `unavailable_posting` review reason and advise
  removing or replacing the link instead of retrying or using capture.
- Live checks through the real background queue verified:
  - an expired Rho Ashby posting returns Error with all job fields `n/a`;
  - a removed Upstack Greenhouse posting returns an expired Error rather than
    the general UPSTACK board;
  - an expired HDR Taleo URL that opens `Job Search` returns a job-list Error;
  - the Lexitas Dayforce posting remains High confidence with correct fields
    and `Dayforce` as its source.

The earlier extraction pass is also complete and pushed:

- Workday pages now use the official public CXS job endpoint before browser or
  page-shell fallbacks. This prevents internal office codes and stale
  `TELECOMMUTE` schema from overriding Workday's public location and
  `remoteType`.
- Structured-data parsing now scans every JSON-LD block for a real
  `JobPosting`. It no longer stops at an earlier generic `WebPage` block.
- `jobLocationType` values such as `On-site`, `Hybrid`, and `TELECOMMUTE` map
  to the tracker vocabulary instead of being confused with Full-time or
  Part-time employment type.
- Explicit phrases such as `This is a hybrid role` can override conflicting
  remote schema, and short visible location labels are preferred over full-page
  text that can attach a title or company to the place.
- LinkedIn still omits some workplace chips from its public guest HTML. The
  verified ATC Data Analyst repost is handled by a narrow company/title/
  location/description signature rather than a broad location guess or a new
  job-ID override.
- A complete, successful job row now defaults to `Onsite` when no work type is
  available. Explicit `Remote`, `Hybrid`, or `Onsite` evidence still wins.
  Errors, expired/search pages, and rows missing company, title, or location
  remain `n/a`.
- The 2026-08-08 multi-site pass added stable employer normalization for
  JPMorgan Chase, BBVA, Crédit Agricole CIB, and BlackRock. Oracle Candidate
  Experience shell titles are no longer accepted as company names.
- Workday now falls back from an unusably broad city string to its requisition
  location and country, while still honoring the public `remoteType` field.
- All-caps pieces inside mixed-case locations are normalized independently, so
  `NEW YORK, United States` becomes `New York, United States`.
- Conditional policy text such as `may be eligible for remote work` no longer
  makes a posting Remote. Broad work-type fallback scans the job description,
  not unrelated ATS configuration or site footer text.
- Plain-number ranges in scoped phrases such as `The base compensation range
  for this role ... is: 60,000 - 65,000` now receive the appropriate currency
  marker when the posting location establishes it.
- Company career URLs remain `Company Website` even when the page contains an
  embedded Lever or other ATS implementation. JSON-LD locale codes such as
  `en-us` are normalized without discarding the city.
- TAL program pages can retain a labeled multi-country location instead of
  returning label text such as `Region Americas Countries`.
- Live checks on 2026-08-08 returned the corrected affected rows:
  - JPMorgan Chase & Co.: `New York, NY`, `Onsite`, `$110,000.00`
  - BBVA: `New York, United States`, `Onsite`, `$90,000 to $100,000`
  - Crédit Agricole CIB: `New York, United States`, `Onsite`, `$80K`
  - Capgemini: `New York, United States`, `Onsite`, `$60,000 - $65,000`
  - BlackRock: `Canada, Mexico, United States`, `Onsite`
- Live checks on 2026-08-06 returned:
  - Great American Insurance: `New York, NY`, `Hybrid`
  - Elixirr: `New York, United States`, `Onsite`
  - ATC: `New York, United States`, `Onsite`
  - Elios AI: `United States`, `Remote`

There are no unfinished source edits. The local desktop app is running at
`http://127.0.0.1:5050/`. Before building the public release candidate, the
user still needs to choose the final product name and approve a coordinated
rename.

## What We Are Building

The project is a local-first job application tracker for people who do not want
to copy the same information from job postings into Excel by hand.

The main workflow is:

1. Optionally choose an existing Excel tracker from the header `Tracker`
   panel before scraping.
2. Select the application date.
3. Paste up to 20 individual job-posting links.
4. Scrape the links in a bounded background queue.
5. Review company, title, location, work type, salary, and source.
6. Correct uncertain fields inline or add a row manually.
7. Use the header Tracker panel to download a new tracker or update an
   existing `.xlsx` or `.xlsm` tracker.
8. Find or restore earlier results from local History when needed.

The scraper is intentionally not presented as perfect. A human review step is
part of the product, not a temporary failure to hide.

The current distribution direction is a free, portable Windows desktop beta.
The user does not want a hosting subscription, Docker subscription, required
terminal workflow, or required Python installation for testers. Hosted
configuration remains in the repository for future use, but it is not the
current release path.

Do not add accounts, authentication, a cloud database, or paid infrastructure
unless the user explicitly changes this direction. The project currently does
not need any personal account data.

## Product Rules That Must Not Regress

### Canonical tracker columns

Keep these 10 fields compatible across every Excel workflow:

1. Date Applied
2. Company
3. Job Title
4. Job link
5. Status
6. Location
7. Work Type
8. Salary Range
9. Follow-up
10. Source

There is no Description, AI Notes, or Skills column. The user explicitly
removed those fields.

### Field behavior

- `company`, `job_title`, and `location` are required for a trustworthy row.
- `work_type` must be exactly `Remote`, `Hybrid`, `Onsite`, or `n/a`.
- Never output `Mix`.
- Do not infer work type merely because a location is remote-friendly or
  because the job description contains generic remote-work language. Explicit
  current-job evidence determines `Remote`, `Hybrid`, or `Onsite`. If a
  successfully identified job has no work-type evidence, default it to
  `Onsite`. Keep `n/a` for errors and incomplete rows.
- Missing salary must be `n/a`.
- Remove labels such as `Base pay range:` when a clean salary amount remains.
- Collapse equal ranges such as `$20 - $20 per hour` to `$20 per hour`.
- All-caps locations should be display-normalized while preserving abbreviations
  such as NY, NJ, NYC, USA, and EMEA.
- `follow_up` must be blank by default. Do not fill it with a future date.
- `source` must be a readable label such as LinkedIn, Indeed, Greenhouse,
  Workday, or Company Website, never the URL itself.
- Preserve the original posting URL in `job_link`.
- Do not replace the original job link with link text such as `Open job`.
- The application date comes from the user's selected date, not always today.

### Salary display and export

The results table has `Original`, `Hourly`, and `Yearly` modes.

- The original scraped salary remains stored unchanged in the job object.
- Converted values are display/export views, not destructive edits.
- `Hours/week` appears only in Hourly or Yearly mode.
- Conversion uses the selected hours per week and 52 weeks per year.
- This supports part-time estimates without assuming every job is 40 hours.
- The chosen salary mode is also used for Excel export/update.
- Unsafe values are left as posted rather than forced into a conversion.
- Bonus, commission, equity, mixed currencies, mixed periods, and salaries
  without a recognizable period are deliberately not converted.
- Converted salary text must use the same font, size, weight, and color as the
  rest of the results table.

### Local History

- The current Workspace is stored in tab-scoped `sessionStorage` under
  `joblink.beta.session.v1`. It survives refresh but a newly opened tab starts
  clean.
- Finished scrapes, retries, captures, accepted edits, salary/work-type option
  changes, and manual additions are saved to local SQLite History.
- One canonical record is kept per job link. Saving the same tracked URL again
  updates the existing History row instead of creating tracking-parameter
  duplicates.
- History can be searched and filtered by Ready, Review, Error, or Manual.
- Selected History rows can be restored to the Workspace, downloaded to Excel,
  or deleted. Clear all requires confirmation.
- Removing a row from the current Workspace must not silently delete History.
- History stores visible tracker and review fields only. Do not add full job
  descriptions, captured page text, uploaded workbooks, or row-selection state.
- The Windows desktop database is `%LOCALAPPDATA%\Linc\history.sqlite3`.
- Source mode defaults to `LOG_DIR/history.sqlite3` unless
  `JOBLINK_HISTORY_DB_PATH` is set.
- Local History is disabled by default in production/hosted mode.

### Results and controls

- `Clear links` clears only the pasted-link input.
- Results are removed using row selection and `Remove selected`, or the row
  remove button.
- Repeated pasted links are separated automatically and deduplicated without
  repeated cancel dialogs.
- Duplicate result behavior is controlled by one `skip` or `update` setting in
  the header Tracker panel.
- Error or Review rows can be edited and manually approved.
- Do not mark a row Ready solely because an error string disappeared.
- Confidence and source reliability are guidance, not proof that a field is
  correct.
- On an empty Workspace, keep Results quiet: filters, salary controls, row
  tools, and Excel actions should not compete with the primary link input.
- Manual entry and browser capture belong under `Other ways to add`.
- Result filters and table tools appear only when jobs exist.
- Report and Remove are contextual actions and appear only after row selection.
- The header `Tracker` button remains available before and after scraping.
- Do not move the Excel workflow back under the Results table unless the user
  explicitly changes this decision.

### Excel behavior

- Preserve existing sheets, formulas, formatting, tables, hyperlinks, and
  macros.
- Preserve VBA when updating `.xlsm`.
- Prefer an `Applications` sheet, but support other sheets with recognizable
  header aliases.
- Add missing recognized headers rather than rebuilding the workbook.
- Support duplicate modes `skip` and `update`.
- Use the first real empty application row; do not append after large amounts
  of formatting-only empty space.
- Copy nearby row styles and extend Excel table ranges.
- Keep salary and link columns readable; do not truncate salary values.

Modern Chromium browsers can use the File System Access API to update the
selected original workbook. Browsers without that API receive an updated
downloaded copy and leave the original unchanged. Do not promise in-place
editing in every browser.

## What Has Been Completed

### Scraping

- Browser-first extraction with Playwright.
- Static HTML and structured-data fallback.
- JSON-LD, metadata, embedded-data, selector, visible-text, and URL-hint
  extraction layers.
- Known ATS handling for Greenhouse, Lever, Ashby, Workday, iCIMS, Breezy,
  SmartRecruiters, Taleo, Dayforce, and common company career pages.
- Job-board handling for LinkedIn, Indeed, Glassdoor, ZipRecruiter,
  SimplyHired, Dice, Monster, Wellfound, and Upwork, with different reliability
  expectations.
- Greenhouse and SmartRecruiters structured endpoint support.
- iCIMS frame reading.
- Direct HTML fallback for sites that fail browser launch or rendering.
- Recent direct-HTML and rendered-page regressions cover current LinkedIn,
  Indeed, American Express/Oracle careers, Lockton, Ashby, Workday, Dayforce,
  and Jobvite patterns, including job-object selection and conflicting visible
  versus structured fields.
- Hidden job-detail expansion and navigation-interruption retry logic.
- Employer/company application-link discovery when a repost exposes one.
- Search-page rejection for LinkedIn, Indeed, Glassdoor, ZipRecruiter,
  SimplyHired, and Monster patterns.
- Friendly errors for expired, blocked, CAPTCHA, timeout, invalid, and search
  pages.
- Final-URL redirect checks and generic shell-title rejection prevent expired
  ATS pages from being accepted as real postings.
- Expired postings have distinct review guidance instead of generic retry
  instructions.
- Conservative company, title, location, work-type, and salary cleanup.
- Regression fixtures for the major supported patterns.

### Review and recovery

- Ready, Review, Error, and Manual states.
- Confidence level and numeric score.
- Good, Okay, and Limited source-reliability labels.
- Field-specific review reasons and suggested actions.
- Inline editing.
- Manual row creation.
- Per-row and batch retry.
- Manual approval of corrected rows.
- Row selection, select all, remove selected, and report selected.
- Local problem-row logging and general beta feedback.
- Optional Chrome capture extension for a page the user can already view.

Browser capture does not bypass security. It reads the page visible in the
user's own Chrome session and sends selected content to the local app server.
Capture remains local-only by default and still requires human review.

### Frontend

- Peach/orange visual theme with restrained decorative motion.
- Consistent Aptos-based typography.
- Responsive layout with no page-level horizontal overflow at the compact
  viewport tested.
- Clear link input, date selection, 20-link count, progress, and cancellation.
- Automatic repeated-paste separation, canonical duplicate detection, and
  paste undo/redo support.
- Progressive Workspace layout that keeps advanced controls hidden until they
  are useful.
- `Other ways to add` disclosure for manual entry and browser capture.
- Filtered results table with contextual selection actions.
- Persistent header Tracker panel for workbook selection, row count, update,
  download, and duplicate behavior.
- Tracker and Feedback panels are mutually exclusive, support Escape, and
  return keyboard focus to their header trigger.
- Tab-scoped session restoration through `sessionStorage` key
  `joblink.beta.session.v1`.
- Searchable local SQLite History with restore, export, and deletion.
- Original, Hourly, and Yearly salary views with adjustable hours per week.

Do not change the session-storage key casually. Doing so makes an existing
tab's Workspace appear to disappear. Do not replace the SQLite History with
browser storage; they serve different purposes.

### Architecture and production foundation

- Flask application factory and environment-specific configuration.
- Central logging and error handling.
- Runtime lifecycle management.
- Bounded in-memory background queue with progress, cancellation, expiry, and
  shared capacity for one-link retries.
- Request limits and local rate limiting.
- Public URL, redirect, DNS, and Playwright request validation to reduce SSRF
  risk.
- Workbook type, ZIP structure, archive size, and member-count validation.
- Security headers and production secret validation.
- Temporary workbook processing and privacy-preserving production logs.
- Dockerfile and single-process Gunicorn configuration for a future hosted
  deployment.

The queue is process-local. Gunicorn must remain at one worker until the queue
is moved to shared storage such as Redis.

### Desktop and documentation

- One-click Windows launcher at `127.0.0.1:5050`.
- Existing-instance and port-conflict handling.
- Tkinter control window with Open and Stop actions.
- Local desktop logs currently under `%LOCALAPPDATA%\Linc\logs`; decide whether
  to migrate or retain this path during the final rename.
- Local History database currently at `%LOCALAPPDATA%\Linc\history.sqlite3`;
  include it in the same final-name migration decision.
- PyInstaller spec that bundles Flask assets, project modules, Playwright, and
  Chromium.
- Manual GitHub Actions workflow currently configured to create
  `Linc-v0.1.0-Windows.zip`; rename that artifact before release.
- Blank Excel template under `templates/linc_tracker_template.xlsx`.
- Setup, beta-test, privacy, deployment, background-job, limitation, desktop,
  usage, and troubleshooting documentation.
- README instructions separated for Windows, macOS, and Linux.

## Architecture Map

### Main application

- `scraper/app.py`
  - Composes Flask configuration, runtime, routes, capture, export, workbook
    update, History, feedback, diagnostics, security headers, and friendly
    errors.
  - It was reduced through supporting modules but is still large. Split it
    further only along clear route/service boundaries, not as a rewrite.
- `scraper/config.py`
  - Local, testing, and production settings.
- `scraper/runtime.py`
  - Shared runtime construction and shutdown.
- `scraper/job_queue.py`
  - Bounded `ThreadPoolExecutor`, job state, cancellation, capacity, and TTL.
- `scraper/job_routes.py`
  - Background batch API.
- `scraper/history.py`
  - Local SQLite History schema, sanitation, canonical upsert, search/filter,
    deletion, and `/api/history` routes.
- `scraper/errors.py`, `scraper/logging_config.py`
  - Central error and logging behavior.

### Extraction

- `scraper/browser_scraper_v2.py`
  - Primary scraper and the largest/most fragile module.
- `scraper/scraper.py`
  - Static HTML and structured-data fallback.
- `scraper/capture_parser.py`
  - Parses Chrome extension captures and records field evidence/suggestions.
- `scraper/field_normalization.py`
  - Shared display normalization for locations and salaries.
- `scraper/result_quality.py`
  - Review issues, confidence, source reliability, and public result fields.
- `scraper/security.py`
  - URL cleanup, canonical identity, network restrictions, and workbook
    validation.

### Frontend

- `scraper/templates/index.html`
- `scraper/static/app.js`
- `scraper/static/styles.css`
- `scraper/static/link_input.js`
- `scraper/static/salary_conversion.js`

### Excel

- `export/exporter.py`
  - Creates a new tracker.
- `export/workbook_appender.py`
  - Updates an existing `.xlsx` or `.xlsm`.
- `process_excel_links.py`
  - Separate Input/Applications sheet processor.
- `VBA/JobTracker.bas`
  - Windows Excel/VBA workflow.
- `templates/linc_tracker_template.xlsx`
  - Blank starter workbook.

These Excel paths overlap but are not the same implementation. A schema or
behavior change must be traced through all of them.

### Desktop and release

- `desktop_launcher.py`
- `Open_Linc_Beta.vbs`
- `packaging/linc.spec`
- `scripts/build_desktop.ps1`
- `.github/workflows/build-windows-desktop.yml`
- `docs/desktop_beta.md`

## Important Ports

- Source Flask server: `http://127.0.0.1:5000`
- Windows desktop launcher: `http://127.0.0.1:5050`
- Chrome capture extension: currently sends only to the local app server on
  `5050`
- Hosted container: uses `PORT`, with the current container default documented
  separately

Do not replace all ports with one global value. Each launch mode has a reason
for its current port.

## Main HTTP Routes

- `GET /`
- `GET /health`
- `GET /ready`
- `POST /api/jobs`
- `GET /api/jobs/<job_id>`
- `DELETE /api/jobs/<job_id>`
- `POST /scrape`
- `POST /export`
- `POST /append-workbook`
- `POST /api/capture-page`
- `GET /api/captures`
- `POST /api/report-issue`
- `POST /api/feedback`
- `GET /api/history` in local mode
- `POST /api/history` in local mode
- `DELETE /api/history` in local mode
- `GET /api/issues` only when explicitly enabled and authorized

## Verified Baseline

At this handoff:

- `main` is clean and matches `origin/main`.
- Python virtual environment: Python 3.12.13 with the pinned dependencies from
  `requirements-dev.txt`.
- Pytest collects 191 tests.
- The full suite completed with 189 tests passing and two
  Node-dependent wrapper tests skipped because `node` was not on the normal
  shell `PATH`.
- The underlying Node link-input suite passed when run directly.
- The underlying Node salary-conversion suite passed when run directly.
- The latest full run reported no test warnings.
- A live background-queue audit verified expired Ashby, redirected Greenhouse,
  Taleo search-shell, and successful Dayforce behavior after an app restart.
- `GET /ready` reports the browser available and the queue accepting at
  `http://127.0.0.1:5050/`.
- History browser QA verified save, search, status filtering, fresh-tab
  persistence, restore, selected deletion, and a clean empty state.
- Simplified Workspace QA verified the secondary-add menu, manual entry,
  progressive result controls, contextual selection actions, and removal of
  the old Results-level tracker bar.
- Header Tracker QA verified availability with zero links, `0 rows ready`,
  count changes after adding a row, mutual exclusion with Feedback, Escape
  handling, returned keyboard focus, and no page-level horizontal overflow at
  the current 1280-pixel browser viewport.
- Temporary QA rows and their matching History entries were deleted after
  testing. Existing unrelated History entries were not cleared.
- The latest Tracker relocation did not exercise the native operating-system
  file picker in browser automation. Workbook route tests passed and the
  underlying workbook functions were not rewritten.
- The latest Tracker panel was not visually tested at a true mobile viewport
  because the in-app browser API did not expose viewport resizing. Responsive
  CSS and static regression checks pass, but mobile visual QA remains useful.

Use these commands from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q -ra
python scraper\app.py
```

The source server opens on port `5000`.

For the one-click development launcher:

```powershell
python desktop_launcher.py
```

It opens on port `5050`.

In a restricted Codex shell, use a unique workspace-owned pytest temp folder if
the default `%TEMP%\pytest-of-jzeng` directory is inaccessible:

```powershell
python -m pytest -q -ra -p no:cacheprovider --basetemp=tmp\pytest-local
```

Before deleting or recreating `.venv`, verify the absolute target and stop only
the confirmed `desktop_launcher.py` processes that are locking it. Do not remove
the environment while the local app is still running.

If Node is installed:

```powershell
node tests\frontend_link_input.test.cjs
node tests\frontend_salary_conversion.test.cjs
```

## Where Work Is Currently Blocked

There is no hard application-code blocker. The core local beta runs and the
automated baseline passes. The immediate product blocker is the final name;
release validation and real-world extraction quality come next.

### 1. The final product name is undecided

The user no longer wants the name `Linc`. Do not publish another release under
that name and do not invent a replacement. Ask the user to choose or approve the
final name first.

Once the name is chosen, prepare a coordinated rename inventory before editing.
At minimum, inspect UI copy, README and docs, desktop launcher, app-data path,
feedback version text, Chrome extension, VBS launcher, PyInstaller spec, build
script, GitHub Actions workflow, artifact and ZIP names, workbook template,
static documentation, session-storage and History compatibility, and tests.
The repository name and `JOBLINK_` environment-variable prefix should remain
unchanged unless the user explicitly wants those internal compatibility
identifiers renamed.

### 2. The current desktop release package is not verified

The existing `dist/JobLink-Tracker-Windows.zip` is old, uses obsolete branding,
and predates many fixes. It must not be uploaded as the current app.

A fresh package needs to be built after the approved rename, extracted into a
clean folder, and tested using every step in `docs/desktop_beta.md`. The status
of a fresh GitHub Actions artifact was not verified during this handoff.

There is also no local `v0.1.0` Git tag yet. Do not create a release or tag until
the newly built portable app passes the desktop checklist.

### 3. Some websites will continue to block scraping

Monster, Upwork, Wellfound, login-only pages, Cloudflare pages, CAPTCHAs, and
private APIs cannot be made universally reliable without violating product and
security boundaries.

The supported recovery path is:

1. Prefer the employer's own career page.
2. Use the current local capture extension when the user can see the page in
   Chrome.
3. Use manual entry or edit/approve the row.
4. Explain the limitation clearly.

Do not describe this as a temporary bug that can always be bypassed.

### 4. Ready rows can still contain plausible but wrong fields

Quality scoring is heuristic. A wrong company, location, work type, or salary
can sometimes look syntactically valid and escape review flags.

The correct improvement loop is to reproduce a repeatable pattern with saved
synthetic HTML, write a focused regression test, and make the narrowest parser
change that fixes it without changing already passing platform cases.

### 5. Free cross-platform packaging is incomplete

The chosen no-subscription release is Windows-only. macOS and Linux currently
run from source. Do not promise packaged macOS/Linux builds yet.

## Recurring Issues And How To Avoid Them

- **Expired, redirected, or search-result links:** Many test postings disappear
  or redirect to a board search page. Validate that the final page is one
  individual job before extracting fields. Keep synthetic regression fixtures
  because a live URL is not a durable test.
- **A job-detail URL can render only a search shell:** The path and query can
  still look like one job even after the posting expires. Reject generic titles
  such as `Job Search`, `Current openings`, and `All jobs`, and clear fields
  copied from that shell before returning the row.
- **Bot protection and verification pages:** Monster, Upwork, Wellfound,
  Cloudflare, CAPTCHA, and login walls repeatedly block automation. Do not try
  to bypass them. Prefer the employer's career page, local browser capture, or
  manual entry, and return a clear limited-site error.
- **Details hidden behind rendering, expansion, or frames:** Some pages expose
  salary, work type, or location only after JavaScript renders, `Read more` is
  opened, or an embedded frame loads. Browser extraction must inspect the
  rendered job detail and supported frames before falling back to page shells.
- **Visible fields conflict with structured data:** JSON-LD and embedded job
  objects can be stale, broad, or for a different listing. Prefer explicit,
  labeled fields for the current visible job, but preserve structured data as
  fallback evidence. Add a focused precedence test for each repeatable case.
- **A stale schema title can look valid:** When a page's current browser title
  follows a clear job-title pattern but JSON-LD supplies a different plausible
  title, prefer the current page title. Do not apply this to generic search or
  careers-shell titles.
- **The first JSON-LD block may not be the job:** Company sites often place
  `WebPage`, breadcrumbs, or organization schema before `JobPosting`. Scan all
  JSON-LD blocks for a real job object before accepting a generic fallback.
- **Workday schema can contradict Workday's own job data:** A page may publish
  an internal office code and `TELECOMMUTE` while its public CXS payload says
  `New York, NY` and `Hybrid`. Prefer the same-host public CXS location and
  `remoteType`; if the short `location` value cannot be normalized, combine
  the requisition descriptor and country before abandoning the CXS response.
  If that endpoint fails, keep the browser and schema fallbacks.
- **ATS shell text is not job evidence:** Oracle can publish `Candidate
  Experience page` as `og:site_name`, and Eightfold scripts contain generic
  Remote/Hybrid filter labels. Reject shell branding and do not scan ATS
  configuration or site footers as if they describe the current job.
- **The original URL determines Source:** A branded company careers URL remains
  `Company Website` even if its HTML mentions or embeds Lever, Greenhouse, or
  another ATS. ATS detection may guide extraction, but it must not rewrite the
  source or prevent employer inference from the original company domain.
- **ATS employer names can contain internal codes:** Workday and similar
  systems may prefix the real company with values such as `02B` or `LE2201`.
  Remove a compact uppercase alphanumeric token only when it contains both a
  letter and a number; do not strip ordinary brand names such as `3M`.
- **Inline labels can be stronger than free-text guesses:** Read short fields
  such as `<strong>Location:</strong> New York, NY` from their parent element.
  Reject multi-field description lines containing separators or labels such as
  Type, Experience, or Salary.
- **Mixed-case location strings can preserve an all-caps city:** Normalize
  comma-separated location pieces independently. Also normalize malformed
  JSON-LD country locale values such as `en-us` before cleaning the full place.
- **Program pages can list many valid locations:** A TAL page may label Region,
  Countries, and Cities instead of publishing one `jobLocation`. Keep the
  labeled country list without attaching its surrounding labels or city list.
- **A plausible field can still be wrong:** Company, location, work type, and
  salary can look valid enough to receive Ready status while belonging to
  navigation, another listing, or compensation copy. Review field provenance,
  improve field-specific quality rules, and prioritize confidently wrong Ready
  rows over already-marked missing fields.
- **Work type is often over-inferred:** Generic remote-work language or a
  company policy is not enough to label a job `Remote` or `Hybrid`. Prefer a
  labeled workplace field, LinkedIn preference chip, or clear role statement.
  When none exists on an otherwise complete successful job, the current
  product rule intentionally defaults to `Onsite`; errors and incomplete rows
  remain `n/a`.
- **LinkedIn may hide a visible workplace chip from guest HTML:** A city is not
  explicit proof of `Onsite`, and LinkedIn's `apply-link-onsite` tracking name
  only describes where the application opens. The final complete-row fallback
  may still produce `Onsite` under the current product rule. Use capture when
  possible to replace that assumption with the visible chip. A validated
  posting signature is acceptable only when company, title, location, and
  distinctive description markers all match a saved regression.
- **Salary text varies heavily:** Pages mix base pay, total compensation,
  bonuses, equal ranges, hourly/yearly periods, and unrelated numbers. Prefer
  explicit base salary, strip labels only when the amount remains clear,
  collapse equal ranges, preserve the pay period, and use `n/a` when missing.
- **The period can sit outside the matched salary:** Phrases such as
  `Hourly: $20-$35` have explicit period evidence even though the numeric range
  does not contain `/hr`. Carry a nearby unambiguous Hourly, Annual, or Weekly
  label into the stored salary; never infer a period from the amount alone.
- **Broad programs can publish several salary tables:** Taking the first valid
  range may be misleading when one page covers many roles or locations. A
  future focused improvement should mark multi-range program pages Review
  unless the selected range is clearly tied to the scraped role and location.
- **One-site fixes can regress another platform:** Never solve a posting with a
  broad regex or its current job ID. Save a minimal fixture, add the narrowest
  platform or evidence-priority rule, run the focused regression, and then run
  all tests.
- **Two URLs for the same job can expose different fields:** Do not combine a
  job-board URL and employer URL into one result automatically. Scrape each link
  independently, preserve its original URL, and prefer the employer page as a
  user recovery option when the board is incomplete.
- **Excel overwrite behavior depends on the browser:** File System Access can
  update the selected original; other browsers must download an updated copy.
  Never claim universal in-place editing, recreate the workbook, or silently
  replace the user's original link or macros.
- **Workbook formatting can look like used rows:** Do not append after
  formatting-only space. Find the first real empty application row, preserve
  nearby styles, extend table ranges, and test both `.xlsx` and `.xlsm`.
- **The running Flask app can serve stale templates:** After backend or template
  changes, restart the process on port `5050` before browser QA. A normal page
  refresh is not always enough when Jinja caching is active.
- **A running launcher locks `.venv` on Windows:** Recreating the environment
  while `desktop_launcher.py` is running can leave a partially deleted folder.
  Identify the exact project process, stop only that process, verify the
  resolved `.venv` path stays inside the repository, then recreate it.
- **Pytest may not be allowed to read its default temp root:** In a restricted
  shell, pass a unique `--basetemp` below the repository's ignored `tmp/`
  directory. Temp-folder permission errors are not application test failures.
- **Workspace and History have different lifetimes:** Workspace is per tab;
  SQLite History is durable. `Clear links`, removing a result, and deleting a
  History row are separate actions. Browser QA must delete only its uniquely
  named test rows and must never clear unrelated user History.
- **Too many visible controls make the app hard to scan:** Keep the empty view
  focused on links, date, and the primary action. Preserve progressive Results,
  `Other ways to add`, contextual selection actions, and the header Tracker
  panel instead of exposing every feature at once.
- **Development setup is not the tester experience:** A `.venv`, Playwright
  installation, and terminal are acceptable for contributors, not beta users.
  The release path remains a portable Windows ZIP that needs no paid service or
  Python installation.
- **Brand and Git state drift easily:** The final name is still undecided,
  `local` is stale, and every completed change must be committed and pushed to
  `main`. Check the branch, worktree, staged diff, and remote after each task.

## Recommended Next Plan

### Immediate order

1. Choose the final product name and approve the coordinated rename scope.
2. Perform true mobile visual QA of the simplified Workspace, History, Tracker,
   and Feedback panels.
3. Exercise the native workbook picker from the header before scraping, then
   verify original `.xlsx` and `.xlsm` updates plus downloaded-copy fallback.
4. Build a fresh Windows ZIP and run the clean-folder desktop checklist.
5. Test current links across employer sites, LinkedIn, Indeed, and several ATS
   platforms; fix repeatable false Ready patterns with fixtures.
6. Run the small private beta, review intentionally submitted feedback, and
   repeat the focused regression loop.
7. Create `v0.1.0` only after the packaged beta and workbook workflows pass.

### Phase 0: Choose and apply the final name

1. Ask the user for the exact final product name, capitalization, and preferred
   release filename.
2. Show the user the coordinated rename scope before changing compatibility
   identifiers.
3. Rename user-facing surfaces consistently.
4. Preserve or migrate the tab Workspace key, History database, and desktop
   data rather than silently making them disappear.
5. Update tests and documentation.
6. Commit and push the rename as a focused change.

Do not use `Linc`, `JobLink Tracker`, or `Unknown` as the final name unless the
user explicitly selects it.

### Phase 1: Produce a real release candidate

1. Confirm `main` is clean and current.
2. Run all Python and frontend helper tests.
3. Confirm the GitHub Actions workflow and packaging files use the approved
   name, then trigger the Windows beta build or build locally with:

   ```powershell
   .\scripts\build_desktop.ps1 -Python py
   ```

4. Confirm the ZIP and executable use the approved name.
5. Extract it into a brand-new folder.
6. Complete the release checklist in `docs/desktop_beta.md`.
7. Test a current company career page, a supported ATS, and one limited site.
8. Verify the header Tracker panel can select a workbook before scraping, then
   test new export and existing `.xlsx` and `.xlsm` updates.
9. Verify History survives an app restart and can restore and delete a row.
10. Confirm closing the app releases port `5050`, then start it again.
11. Only after those checks, create tag `v0.1.0` and a human release note.

### Phase 2: Run a small private beta

Give the fresh ZIP to a small group of Windows testers. Ask each person to test
10 to 15 current postings across at least three sites and one temporary copy of
an Excel tracker.

Collect only reports the tester intentionally shares. The useful local files
are:

```text
%LOCALAPPDATA%\Linc\logs\user_reported_issues.jsonl
%LOCALAPPDATA%\Linc\logs\beta_feedback.jsonl
```

Inspect those files for private information before sharing or committing
anything. Do not ask testers to send `history.sqlite3`; it can contain the job
links and tracker fields they saved.

### Phase 3: Improve repeated extraction failures

For each repeated failure pattern:

1. Identify the extraction layer that produced the wrong value.
2. Save a minimal synthetic fixture with no private data.
3. Add the expected company, title, location, work type, salary, and source to
   `tests/test_scraper_regressions.py` or the closest focused test.
4. Make a narrow platform or evidence-priority fix.
5. Run the focused tests and the full suite (currently 191 collected tests).
6. Manually verify the UI status and Excel result.
7. Commit and push the focused change.

Prioritize confidently wrong Ready rows over missing fields that are already
marked Review.

### Phase 4: Publish only after beta evidence

After the packaged release and private beta are stable:

- Create the GitHub release.
- Add a short real demo or current screenshots.
- Confirm README download instructions match the actual artifact.
- Decide whether a wider Windows beta is appropriate.
- Revisit hosted deployment or packaged macOS support only if users need it.

## Pitfalls: Do Not Repeat These

### Repository and Git

- Do not trust an old conversation summary over current files.
- Do not treat `Linc` as the approved final name.
- Do not revive `JobLink Tracker`, `Unknown`, or invent another temporary
  public name.
- Do not begin a repository-wide rename before the user supplies the exact
  final name and approves compatibility decisions.
- Do not blindly rename internal identifiers such as `JOBLINK_`, the repository
  URL, saved-session keys, or existing data paths.
- Do not work from the stale `local` branch by accident.
- Do not merge the stale `local` branch into `main` just to make branches look
  synchronized.
- Do not publish the ignored old ZIP in `dist/`.
- Do not commit generated workbooks, exports, logs, screenshots with
  application data, `.env`, build output, or browser captures.
- Do not reset, revert, or overwrite unrelated user changes.
- Inspect `git status` and the staged diff before every commit.

### Scraper changes

- Do not replace the large scraper with one generic selector or broad regular
  expression.
- Do not fix one posting by hardcoding its current job ID.
- Do not add broad cleanup that silently breaks another ATS.
- Do not rely only on a live posting; it can expire or change.
- Do not guess missing company, location, or salary. Work type is the one
  deliberate exception: a complete successful job defaults to `Onsite` when
  the posting provides no work-type evidence.
- Do not treat a job-search page as one job posting.
- Do not remove the static HTML fallback merely because Playwright is primary.
- Do not weaken URL, redirect, DNS, or Playwright network validation to make a
  blocked URL pass.
- Do not attempt to bypass login walls, CAPTCHAs, Cloudflare, or human checks.

### Review logic

- Do not remove a Review flag simply to make the table look successful.
- Do not assume a high confidence score means the row is factually correct.
- Do not change only backend review rules or only frontend fallback rules.
- Do not label a job `Remote` or `Hybrid` without current-job evidence. Use the
  deliberate `Onsite` fallback only for complete successful rows.
- Do not reintroduce `Mix`.

### Frontend

- Do not change the session-storage key or History database path without a
  migration plan.
- Do not clear results when the user selects `Clear links`.
- Do not clear local History when a user removes a current Workspace row.
- Do not bring back one duplicate confirmation dialog per pasted link.
- Do not move Excel controls back under Results; the Tracker panel must remain
  available before links are scraped.
- Do not make advanced Results controls visible on an empty Workspace.
- Do not make converted salaries visually bolder or use a different font.
- Do not create a marketing landing page in place of the working application
  workspace.
- Do not add a large frontend framework for a small interaction.

### Excel

- Do not recreate a user's workbook when the request is to update it.
- Do not strip macros from `.xlsm`.
- Do not change the canonical columns in only one writer.
- Do not assume every browser can overwrite the selected original file.
- Do not write follow-up dates automatically.
- Do not replace the original hyperlink with a generated or redirected URL.

### Runtime and release

- Do not increase Gunicorn process workers while job state remains in memory.
- Do not hardcode one port across source, desktop, capture, and hosted modes.
- Do not assume source-mode success proves the PyInstaller package works.
- Do not forget bundled templates, static assets, Chromium, hidden imports,
  frozen paths, writable log paths, and windowed logging.
- Do not claim the desktop release is tested until the actual extracted
  executable was opened and the full checklist was completed.
- Do not add paid services or subscriptions without explicit user approval.

## Collaboration Preferences

- Explain why a technical step is needed, not only what command to run.
- End users should not need PowerShell, a terminal, Python, Docker, or a virtual
  environment to use the Windows beta.
- Keep public wording human, direct, and beginner-friendly.
- Prefer implementing and verifying a focused fix over giving a long abstract
  plan.
- Commit and push each completed change.
- Report exact tests and anything that could not be verified.
- Never promise universal scraping accuracy.

## First Actions For The Next Session

1. Read this file and `README.md`.
2. Run `git status --short --branch`.
3. Read the latest relevant commits.
4. If the next task involves branding or release work, ask for the final name
   before editing.
5. Inspect the exact module responsible for the new request.
6. Preserve all product rules above.
7. Add focused regression coverage before changing shared scraper behavior.
8. Run the relevant tests, then the full suite.
9. Verify the user-visible workflow in the local app.
10. Review the diff, commit, and push only the intended files.
