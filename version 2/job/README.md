Job Tracker - Excel VBA Template + Python Scraper

Overview
- Excel template to store and track job applications.
- Python Flask scraper to extract job details from company career pages and job boards.
- VBA macros can call the local Python server and populate a worksheet row from a job URL.

What's included
- `outputs/job_tracker_template.xlsx` - ready-to-open Excel tracker template with columns already split.
- `VBA/JobTracker.bas` - VBA module with macros to call the local server.
- `scraper/app.py` - Flask app exposing `/scrape` and `/export` endpoints.
- `scraper/browser_scraper_v2.py` - browser-backed scraper for JavaScript-heavy pages and company websites.
- `scraper/scraper.py` - HTML parsing helpers and fallback extraction.
- `export/exporter.py` - creates a `.xlsx` from job records matching the tracker columns.
- `excel_layout.csv` - plain CSV header row for manual setup if needed.
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
- Open `outputs/job_tracker_template.xlsx`.
- Save it as a macro-enabled workbook: `File > Save As > Excel Macro-Enabled Workbook (*.xlsm)`.
- Import `VBA/JobTracker.bas`: `Developer > Visual Basic > File > Import File`.
- If Excel asks about macros, choose Enable Content for this workbook.
- Select a cell in the `Job link` column and run `FetchJobDetailsForActiveRow`.
- To process multiple pasted links, select those cells in the `Job link` column and run `FetchJobDetailsForSelection`.

Testing Notes
- Start with company career pages when possible. They usually contain better structured job data than reposts on aggregator sites.
- If a field is wrong or missing, copy the test output and the URL. That gives enough detail to tune the scraper for that website pattern.
- Some sites block automation, require login, or hide job details behind private APIs. Those cases may need a site-specific fallback.

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
