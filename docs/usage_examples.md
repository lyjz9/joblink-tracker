# Usage Examples

## Test One Job Link

```powershell
python test_scraper.py "https://example.com/job-posting-url"
```

The output prints tracker-ready fields such as company, job title, location, work type, salary, and source.

Latest smoke test run:

```text
Command:
python test_scraper.py "https://careers-girlscouts.icims.com/jobs/2221/quality-control-analyst%2c-customer-support/job"

Result:
Company: Girl Scouts of the USA
Job Title: Quality Control Analyst, Customer Support
Location: United States
Work Type: Remote
Salary: $66,000 - $80,000
Source: iCIMS
Status: SUCCESS
```

## Run The Local Web Beta

```powershell
python scraper\app.py
```

Then open:

```text
http://127.0.0.1:5000
```

On Windows, you can also double-click `Open_JobLink_Beta.vbs` to start the private beta at `http://127.0.0.1:5050`.

## Test The API Endpoint

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/scrape -Method Post -ContentType "application/json" -Body '{"url":"https://example.com/job-posting-url"}'
```

## Export Jobs To Excel

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:5000/export -Method Post -ContentType "application/json" -Body '[{"company":"ACME","job_title":"Engineer","job_link":"https://example.com/job"}]' -OutFile jobs.xlsx
```

## Process A Copied Tracker Workbook

Use a copied workbook for testing, not your real personal tracker. You can start from `templates/joblink_tracker_template.xlsx`, then save your own working copy.

```powershell
python process_excel_links.py "path\to\copied_tracker.xlsm"
```
