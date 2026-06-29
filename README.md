Job Tracker - Excel VBA Template + Python Scraper

Overview
- Excel template to store and track job applications.
- Python Flask scraper to extract job details from company career pages and job boards.
- VBA macros can call the local Python server and populate a worksheet row from a job URL.

What's included
- `VBA/JobTracker.bas` - VBA module with macros to call the local server.
- `scraper/app.py` - Flask app exposing `/scrape` and `/export` endpoints.
- `scraper/browser_scraper_v2.py` - browser-backed scraper for JavaScript-heavy pages and company websites.
- `scraper/scraper.py` - HTML parsing helpers and fallback extraction.
- `export/exporter.py` - creates a `.xlsx` from job records matching the tracker columns.
- `excel_layout.csv` - plain CSV header row for manual setup if needed.
- `process_excel_links.py` - reads pending links from Excel and appends scraped jobs to the tracker.
- `requirements.txt` - Python package list.

Quick Start

1. Create a Python 3.11 environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

2. Test one job link directly:

```powershell
python test_scraper.py "https://example.com/job-posting-url"
```

3. Run the local scraper server:

```powershell
python scraper\app.py
```

4. Test the server endpoint from another PowerShell window:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/scrape -Method Post -ContentType "application/json" -Body '{"url":"https://example.com/job-posting-url"}'
```

Excel Setup
- Create a workbook with an `Applications` sheet and paste the headers from `excel_layout.csv` into row 1.
- Save it as a macro-enabled workbook: `File > Save As > Excel Macro-Enabled Workbook (*.xlsm)`.
- Import `VBA/JobTracker.bas`: `Developer > Visual Basic > File > Import File`.
- If Excel asks about macros, choose Enable Content for this workbook.
- Select a cell in the `Job link` column and run `FetchJobDetailsForActiveRow`.
- To process multiple pasted links, select those cells in the `Job link` column and run `FetchJobDetailsForSelection`.

Excel Batch Setup (Recommended)

1. Create sheets named `Input` and `Applications`.
2. Add the headers shown in `excel_layout.csv` to `Applications`, and add `Job Link`, `Source`, `Notes`, `Process Status`, `Processed At`, and `Error Message` to `Input`.
3. Import `VBA/JobTracker.bas` using `Developer > Visual Basic > File > Import File`.
4. Add a button on the Input sheet and assign the `ProcessInputLinks` macro.
5. Paste one job link per row under `Job Link`. Leave `Process Status` blank or enter `Pending`.
6. Click `Process Links`. The macro runs the scraper quietly in the background, processes every pending link, and saves the workbook. No PowerShell window or scraper server is required.
7. New jobs appear in `Applications`; each input row shows `Done`, `Needs Manual Review`, `Duplicate`, or `Error`.

You can test the same workflow without a button:

```powershell
python process_excel_links.py "C:\Users\jzeng\Documents\job\outputs\Job_Application_Tracker.xlsm"
```

Testing Notes
- Start with company career pages when possible. They usually contain better structured job data than reposts on aggregator sites.
- If a field is wrong or missing, copy the test output and the URL. That gives enough detail to tune the scraper for that website pattern.
- Some sites block automation, require login, or hide job details behind private APIs. Those cases may need a site-specific fallback.
- Source should be a readable label such as Indeed, LinkedIn, Glassdoor, Greenhouse, or Company Website.
- Work Type should be Remote, Hybrid, Onsite, or n/a. If the posting does not explicitly say the work type, use n/a.
- Salary should show n/a when no trustworthy salary is found.

Current Tracker Columns
- Date Applied
- Company
- Job Title
- Job link
- Status
- Location
- Work Type
- Salary Range
- Follow-up
- Source

Private Web Beta

- Double-click `Open_JobLink_Beta.vbs` to start the private beta without PowerShell.
- The browser opens at `http://127.0.0.1:5050`.
- Choose the date applied, paste up to 20 job links, select `Extract jobs`, edit any result cells, and download the results to Excel.
- `Clear links` only clears the pasted links. Use the row checkbox plus `Clear selected`, or the row remove button, to remove results.
- To add results to an existing tracker, select `Choose tracker`, pick an `.xlsx` or `.xlsm` file, then select `Update tracker`. In Chrome or Edge, the app can save into the selected workbook after browser permission; close the workbook in Excel first. If direct save is not available, the app downloads an updated copy instead. The original job URL stays visible in the link column.
- Rows marked `Review` have missing or suspicious fields. Use the retry button on the row or `Retry review` to try extraction again, then edit any remaining fields manually.
- The local beta is available only on this computer. Public sharing requires a hosted deployment.
