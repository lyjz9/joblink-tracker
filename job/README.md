Job Tracker — Excel VBA template + Python scraper/exporter

Overview
- Excel template (VBA) to store and track job applications.
- Python Flask scraper to extract job details from HTML pages and job-board APIs.
- VBA macros call the local Python server to fetch job details for a URL and populate the worksheet.

What's included
- `VBA/JobTracker.bas` — VBA module with macros to call the local server.
- `scraper/app.py` — Flask app exposing `/scrape` and `/export` endpoints.
- `scraper/scraper.py` — HTML parsing helpers and job-board API stubs.
- `export/exporter.py` — create a `.xlsx` from job records (matching the Excel columns).
- `excel_layout.csv` — CSV with table headers you can paste into Excel to create the tracker.
- `requirements.txt` and `.gitignore`.

Quick start
1) Python server (scraper):

- Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

- Run the scraper server (default port 5000):

```bash
python scraper\app.py
```

2) Excel side (VBA)
- Open Excel and create a new workbook.
- Import the `VBA/JobTracker.bas` module into the workbook (Developer > Visual Basic > File > Import File...).
- Paste the header row from `excel_layout.csv` into the sheet (Row 1).
- Save the workbook as a Macro-Enabled Workbook (`.xlsm`).
- Ensure macros are enabled and set the `BASE_SERVER_URL` constant in the VBA module if your server uses a different host/port.
- Select a cell in the `Job link` column and run the `FetchJobDetailsForActiveRow` macro to populate columns for that row.
- To process several pasted links at once, select the pasted cells in the `Job link` column and run `FetchJobDetailsForSelection`.

Notes and next steps
- The VBA JSON parsing included is a simple helper; for robust JSON support we recommend installing the VBA-JSON library (https://github.com/VBA-tools/VBA-JSON) and switching to `ParseJson` for responses.
- The scraper uses a layered extraction flow: schema.org/JSON-LD first, common applicant-tracking systems next (Greenhouse, Lever, Workday, Ashby, SmartRecruiters, and similar pages), then company-site selectors and conservative text fallbacks.
- No scraper can guarantee perfect results on every website because some sites block automation, require login, or render data behind private APIs. The response includes an `AI Note` when important fields are still missing.
- The `/export` endpoint will create an `.xlsx` matching the Excel headers and return the filename. You can extend the VBA macros to call `/export` if desired.

Security
- The VBA macros call a local HTTP endpoint. Only run trusted code and keep the server local or behind authentication for private data.

License
- MIT
