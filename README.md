# JobLink Tracker

[![Release: v0.1 private beta](https://img.shields.io/badge/release-v0.1%20private%20beta-F26B4B?style=flat-square)](docs/desktop_beta.md)
[![Platform: Windows x64](https://img.shields.io/badge/platform-Windows%20x64-0078D4?style=flat-square&logo=windows11&logoColor=white)](docs/desktop_beta.md)
[![Desktop build](https://github.com/lyjz9/joblink-tracker/actions/workflows/build-windows-desktop.yml/badge.svg?branch=main)](https://github.com/lyjz9/joblink-tracker/actions/workflows/build-windows-desktop.yml)
[![Python: 3.11 or 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](#setup)
[![Excel: XLSX and XLSM](https://img.shields.io/badge/excel-XLSX%20%7C%20XLSM-217346?style=flat-square&logo=microsoftexcel&logoColor=white)](#excel-workflow)
[![Privacy: local first](https://img.shields.io/badge/privacy-local--first-0F766E?style=flat-square)](docs/privacy.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-6D5BD0?style=flat-square)](LICENSE)

JobLink Tracker is a local Python + Excel workflow I built for the part of job searching that quietly becomes exhausting: copying the same posting details into a spreadsheet over and over.

Paste in job links from company career pages or job boards, and the tool pulls out the details people usually track by hand: company, job title, location, work type, salary, and source. From there, you can review anything uncertain and save the cleaned rows into an Excel tracker.

It is especially meant for students, new grads, and anyone applying to enough roles that the tracking work starts becoming its own little job.

> Status: v0.1 private beta. A portable Windows build is available through the GitHub Actions build workflow, so testers can run JobLink without Python, PowerShell, Docker, or a hosting subscription.

## Known Limitations

[![Best input: employer and ATS pages](https://img.shields.io/badge/best%20input-employer%20%2B%20ATS%20pages-2F855A?style=flat-square)](docs/known_limitations.md)
[![Review: editable before export](https://img.shields.io/badge/review-editable%20before%20export-D97706?style=flat-square)](#private-desktop-beta)
[![Blocked pages: capture or manual entry](https://img.shields.io/badge/blocked%20pages-capture%20%7C%20manual%20entry-B91C1C?style=flat-square)](#browser-capture-for-blocked-sites)

JobLink Tracker is a helper, not a perfect scraper. Company career pages and applicant-tracking-system links usually work best. Some job boards, login-only pages, Cloudflare checks, human verification pages, private APIs, and JavaScript-heavy pages may block scraping or return incomplete fields.

Rows marked for review should be checked manually before they are added to a real application tracker. Salary, work type, and location are especially important to verify because different websites format these fields differently.

See [docs/known_limitations.md](docs/known_limitations.md) for more detail.


## Why I Built This

When you are applying to a lot of jobs, the tracking part can quietly turn into its own chore. Every posting has a company name, title, location, salary note, link, and follow-up date to copy somewhere. It is easy to lose time, make small mistakes, or stop tracking things clearly.

JobLink Tracker is my attempt to make that process less annoying. It does not try to replace your judgment. It handles some of the repetitive copying, then lets you review and edit everything before saving.

## Features

- Pull company, job title, location, salary, and work type from job posting links.
- Save results in an Excel-friendly application tracker format.
- Process pasted links as a bounded background batch with live progress and cancellation.
- Flag rows that may need a manual review with confidence and source reliability labels.
- Save problem rows locally for later scraper debugging.
- Help reduce repetitive copy-and-paste work during a job search.

## How It Works

1. Paste job posting URLs into the web beta, command line, or Excel input sheet.
2. JobLink Tracker opens each posting and looks for useful job details.
3. Review anything marked for manual review, especially when a site blocks automation or the result looks incomplete.
4. Save the cleaned rows to an Excel tracker.

## Current Tracker Columns

```text
Date Applied, Company, Job Title, Job link, Status, Location, Work Type, Salary Range, Follow-up, Source
```

## Setup

[![Runtime: Python 3.11 or 3.12](https://img.shields.io/badge/runtime-Python%203.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white)](#setup)
[![Install: requirements.txt](https://img.shields.io/badge/install-requirements.txt-475569?style=flat-square)](requirements.txt)
[![Browser: Chromium required](https://img.shields.io/badge/browser-Chromium%20required-4285F4?style=flat-square&logo=googlechrome&logoColor=white)](https://playwright.dev/python/docs/browsers)

JobLink Tracker is currently tested with Python 3.11 and 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

If Python 3.12 is not installed, Python 3.11 also works. On macOS or Linux, use `python3` instead of `py -3.12` if needed.

Copy `.env.example` to `.env` only when you need to change local defaults. Public deployment must set `JOBLINK_ENV=production` and provide a long, random `JOBLINK_SECRET_KEY` through the hosting provider's environment settings.

The background-job queue is intentionally in memory for the local/private beta. Run one Flask application process so job creation and polling reach the same queue. See [docs/background_jobs.md](docs/background_jobs.md) before changing server workers or deploying publicly.

For the no-subscription Windows package, build workflow, tester instructions, local data path, and release checks, see [docs/desktop_beta.md](docs/desktop_beta.md). Current paid and free hosting tradeoffs are recorded in [docs/deployment.md](docs/deployment.md).

## Usage

More examples are available in [docs/usage_examples.md](docs/usage_examples.md).
For common setup and scraping issues, see [docs/troubleshooting.md](docs/troubleshooting.md).

To test one job link directly:

```powershell
python test_scraper.py "https://example.com/job-posting-url"
```

To run the local web app:

```powershell
python scraper\app.py
```

Then open:

```text
http://127.0.0.1:5000
```

To test the API endpoint:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/scrape -Method Post -ContentType "application/json" -Body '{"url":"https://example.com/job-posting-url"}'
```

## Excel Workflow

[![Starter file: blank tracker](https://img.shields.io/badge/starter%20file-blank%20tracker-217346?style=flat-square&logo=microsoftexcel&logoColor=white)](templates/joblink_tracker_template.xlsx)
[![Formats: XLSX and XLSM](https://img.shields.io/badge/formats-XLSX%20%7C%20XLSM-16803A?style=flat-square)](#excel-workflow)
[![Workflow: update existing tracker](https://img.shields.io/badge/workflow-update%20existing%20tracker-0F766E?style=flat-square)](export/workbook_appender.py)
[![Macros: optional](https://img.shields.io/badge/macros-optional-6D5BD0?style=flat-square)](VBA/README.md)

You can start from the blank tracker template: [templates/joblink_tracker_template.xlsx](templates/joblink_tracker_template.xlsx).

If you want to use the Excel workflow manually, create a macro-enabled workbook with these sheets:

- `Applications`
- `Input`

Paste the headers from `excel_layout.csv` into the `Applications` sheet. In the `Input` sheet, add these headers:

```text
Job Link, Source, Notes, Process Status, Processed At, Error Message
```

Import `VBA/JobTracker.bas` using `Developer > Visual Basic > File > Import File`. If you want a button in the workbook, assign it to the `ProcessInputLinks` macro.

If you use the blank `.xlsx` template with VBA macros, save a personal copy as an Excel macro-enabled workbook (`.xlsm`) before importing the macro module.

You can also test the same workflow without a button by passing the path to your own workbook:

```powershell
python process_excel_links.py "path\to\your\Job_Application_Tracker.xlsm"
```

For a workbook in the current folder:

```powershell
python process_excel_links.py ".\Job_Application_Tracker.xlsm"
```

## Private Desktop Beta

[![Distribution: portable ZIP](https://img.shields.io/badge/distribution-portable%20ZIP-F26B4B?style=flat-square)](docs/desktop_beta.md)
[![Browser: Chromium bundled](https://img.shields.io/badge/browser-Chromium%20bundled-4285F4?style=flat-square&logo=googlechrome&logoColor=white)](packaging/joblink_tracker.spec)
[![Tester setup: no Python required](https://img.shields.io/badge/tester%20setup-no%20Python%20required-0F766E?style=flat-square)](docs/desktop_beta.md)

The portable Windows build lets testers double-click `JobLink Tracker.exe` without installing Python. It starts the same local interface and includes the compatible Chromium browser used by the scraper. See [docs/desktop_beta.md](docs/desktop_beta.md) for build and download instructions.

Developers who already have the project environment can still double-click `Open_JobLink_Beta.vbs` during local development.

- The browser opens at `http://127.0.0.1:5050`.
- Choose the date applied, paste up to 20 job links, select `Extract jobs`, edit any result cells, and download the results to Excel.
- `Clear links` only clears the pasted links. Use row checkboxes, `Clear selected`, or a row remove button to remove results.
- To add results to an existing tracker, select `Choose tracker`, pick an `.xlsx` or `.xlsm` file, then select `Update tracker`. Close the workbook in Excel first so the app can save the updated file cleanly.
- Rows marked `Review` show the exact reason, confidence, and source reliability. Retry the row or edit the remaining fields manually.
- The flag button on a result row saves that problem row to `logs/user_reported_issues.jsonl` so scraping issues can be debugged later.
- If a job board exposes an employer/company application link, JobLink shows it as `Employer link`; that link is usually better than the repost.
- If a site blocks automated access, open the job page yourself and use the Chrome capture extension in `browser_extension/joblink_capture`.

This beta runs locally on the tester's computer. Closing the desktop control window stops the local server.

## Browser Capture For Blocked Sites

[![Extension: Chrome MV3](https://img.shields.io/badge/extension-Chrome%20MV3-4285F4?style=flat-square&logo=googlechrome&logoColor=white)](browser_extension/joblink_capture/README.md)
[![Capture: full loaded page](https://img.shields.io/badge/capture-full%20loaded%20page-D97706?style=flat-square)](browser_extension/joblink_capture/manifest.json)
[![Handoff: localhost only](https://img.shields.io/badge/handoff-localhost%20only-0F766E?style=flat-square)](docs/privacy.md)

Some sites, including a few job boards with human checks or login walls, may block direct scraping. JobLink Tracker includes a small Chrome extension for pages that you can open manually.

1. Start JobLink Beta first.
2. In Chrome, open `chrome://extensions`.
3. Turn on `Developer mode`.
4. Select `Load unpacked`.
5. Choose the `browser_extension/joblink_capture` folder from this project.
6. Open the blocked job page and finish any human check if the site asks.
7. Click `JobLink Capture` from Chrome's extension menu, then select `Capture full job page`.
8. Return to JobLink Tracker and select `Load captured jobs`.

Browser capture is still a helper, not a guarantee. Review captured results before saving them to a tracker.

## Testing Notes

- Start with company career pages when possible. They usually contain cleaner job data than reposts on aggregator sites.
- Some sites block automation, require login, or hide job details behind private APIs, so results will not be perfect for every link. Use browser capture for pages that you can open yourself.
- Monster search pages and many Monster job-detail links are not reliable scraper inputs. If Monster opens or links to the employer/company job page, use that employer link instead.
- Source reliability labels mean: `Good` usually has clean structured data, `Okay` may need review, and `Limited` often blocks scraping or needs browser capture.
- Captured rows may show suggested values under fields; selecting one replaces the current value.
- Source should be a readable label such as Indeed, LinkedIn, Glassdoor, Greenhouse, or Company Website.
- Work Type should be Remote, Hybrid, Onsite, or n/a. If the posting does not explicitly say the work type, use n/a.
- Salary should show n/a when no trustworthy salary is found.

## Privacy

The local beta keeps diagnostic data on this computer. Hosted mode disables browser capture by default, hides internal logs, redacts full URLs from automatic diagnostics, and removes temporary workbook files after returning the download.

See [docs/privacy.md](docs/privacy.md) for the local and hosted data-handling details. Do not commit personal trackers, generated exports, logs, screenshots, or notes containing private application information.

## Project Structure

- `scraper/app.py` composes the Flask app and keeps the existing web and Excel routes.
- `scraper/job_queue.py` owns bounded execution, cancellation, and result expiry.
- `scraper/job_routes.py` exposes the background-job API.
- `scraper/capture_parser.py` parses pages sent by the local Chrome capture extension.
- `scraper/result_quality.py` assigns review issues, confidence, and reliability labels.
- `export/` contains new-workbook export and existing-workbook update logic.
- `desktop_launcher.py` starts and stops the one-click Windows beta.
- `packaging/joblink_tracker.spec` bundles Python, project assets, and Chromium with PyInstaller.
- `.github/workflows/build-windows-desktop.yml` creates the downloadable Windows ZIP.
- `Dockerfile` and `gunicorn.conf.py` define the single-process hosted runtime.

## Roadmap

- Make salary extraction more reliable, especially hourly pay, yearly ranges, and LinkedIn base-pay text.
- Clean up location results when pages include extra words like posting status, job category, or repeated page text.
- Improve work type detection so Remote, Hybrid, Onsite, and n/a are not guessed too aggressively.
- Handle expired, login-only, or blocked postings more clearly instead of returning confusing fields.
- Improve source labels for school career sites, reposts, and company career pages.
- Add a small set of real test links that cover the tricky cases found during testing.
- Add screenshots or a short demo once the main workflow feels stable.
- Collect private beta feedback before adding a full installer or paid code signing.

## Contributing

Feedback, issues, and pull requests are welcome. This project is still early, so even small notes are useful.

Helpful contributions include parser fixes for specific job boards, sample links for testing, clearer setup docs, and better error messages for blocked sites.

If you report a scraping issue, include:

- The job posting URL.
- What field was wrong or missing.
- The output you expected.

## License

MIT
