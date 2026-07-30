# Job Tracker Project Development Handoff

Last updated: 2026-07-30

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
- Application baseline before this handoff:
  `686b646` (`Polish salary display controls`)
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

The last development task was salary presentation. It is complete and pushed:

- Users can switch the results between Original, Hourly, and Yearly.
- Part-time estimates use an adjustable Hours/week value.
- Hours/week is hidden in Original mode.
- The original scraped salary is preserved.
- The selected format is used when writing Excel rows.
- Converted and original salaries now use the same table typography.

There are no unfinished source edits from that task. Before building the public
release candidate, the user needs to choose the final product name and approve a
coordinated rename.

## What We Are Building

The project is a local-first job application tracker for people who do not want
to copy the same information from job postings into Excel by hand.

The main workflow is:

1. Select the application date.
2. Paste up to 20 individual job-posting links.
3. Scrape the links in a bounded background queue.
4. Review company, title, location, work type, salary, and source.
5. Correct uncertain fields inline or add a row manually.
6. Download a new Excel tracker or update an existing `.xlsx` or `.xlsm`
   tracker.

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
  because the job description contains generic remote-work language. Use an
  explicit posting signal; otherwise use `n/a`.
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

### Results and controls

- `Clear links` clears only the pasted-link input.
- Results are removed using row selection and `Remove selected`, or the row
  remove button.
- Repeated pasted links are separated automatically and deduplicated without
  repeated cancel dialogs.
- Duplicate result behavior is controlled by one `skip` or `update` setting.
- Error or Review rows can be edited and manually approved.
- Do not mark a row Ready solely because an error string disappeared.
- Confidence and source reliability are guidance, not proof that a field is
  correct.

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
- Hidden job-detail expansion and navigation-interruption retry logic.
- Employer/company application-link discovery when a repost exposes one.
- Search-page rejection for LinkedIn, Indeed, Glassdoor, ZipRecruiter,
  SimplyHired, and Monster patterns.
- Friendly errors for expired, blocked, CAPTCHA, timeout, invalid, and search
  pages.
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
- Filtered results table and responsive action groups.
- Separate controls for links, results, manual add, retry, Excel, issue
  reporting, and feedback.
- Session restoration through browser local storage key
  `joblink.beta.session.v1`.
- Original, Hourly, and Yearly salary views with adjustable hours per week.

Do not change the local-storage key casually. Doing so makes existing sessions
appear to disappear.

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
    update, feedback, diagnostics, security headers, and friendly errors.
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
- `GET /api/issues` only when explicitly enabled and authorized

## Verified Baseline

At this handoff:

- `main` is clean and matches `origin/main`.
- Python virtual environment: Python 3.12.10.
- Pytest collects 132 tests.
- `python -m pytest -q -ra` completed with 130 tests passing and two
  Node-dependent wrapper tests skipped because `node` was not on the normal
  shell `PATH`.
- The underlying Node link-input suite passed when run directly.
- The underlying Node salary-conversion suite passed when run directly.
- The only test warnings are two OpenPyXL deprecation warnings about
  `datetime.utcnow()`.
- The most recent live UI check verified Original, Hourly, and Yearly salary
  modes, a 24-hour part-time setting, matching salary/table typography, no
  browser console errors, and no page overflow at a 317-pixel viewport.

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

In a restricted Codex shell, `.venv\Scripts\python.exe` may appear unable to
launch even though the environment is healthy. Request the appropriate command
approval before deleting or recreating the environment. It was verified outside
that boundary at this handoff.

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
static documentation, local-storage compatibility, and tests. The repository
name and `JOBLINK_` environment-variable prefix should remain unchanged unless
the user explicitly wants those internal compatibility identifiers renamed.

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

## Recommended Next Plan

### Phase 0: Choose and apply the final name

1. Ask the user for the exact final product name, capitalization, and preferred
   release filename.
2. Show the user the coordinated rename scope before changing compatibility
   identifiers.
3. Rename user-facing surfaces consistently.
4. Preserve or migrate existing browser sessions and desktop data rather than
   silently making them disappear.
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
8. Test new workbook export and existing `.xlsx` and `.xlsm` updates.
9. Confirm closing the app releases port `5050`, then start it again.
10. Only after those checks, create tag `v0.1.0` and a human release note.

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
anything.

### Phase 3: Improve repeated extraction failures

For each repeated failure pattern:

1. Identify the extraction layer that produced the wrong value.
2. Save a minimal synthetic fixture with no private data.
3. Add the expected company, title, location, work type, salary, and source to
   `tests/test_scraper_regressions.py` or the closest focused test.
4. Make a narrow platform or evidence-priority fix.
5. Run the focused tests and all 132 collected tests.
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
- Do not guess missing company, location, work type, or salary.
- Do not treat a job-search page as one job posting.
- Do not remove the static HTML fallback merely because Playwright is primary.
- Do not weaken URL, redirect, DNS, or Playwright network validation to make a
  blocked URL pass.
- Do not attempt to bypass login walls, CAPTCHAs, Cloudflare, or human checks.

### Review logic

- Do not remove a Review flag simply to make the table look successful.
- Do not assume a high confidence score means the row is factually correct.
- Do not change only backend review rules or only frontend fallback rules.
- Do not output a work type unless the evidence is explicit.
- Do not reintroduce `Mix`.

### Frontend

- Do not change the local-storage key without a migration plan.
- Do not clear results when the user selects `Clear links`.
- Do not bring back one duplicate confirmation dialog per pasted link.
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
