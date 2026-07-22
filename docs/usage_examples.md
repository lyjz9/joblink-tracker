# Usage Examples

## Test One Job Link

```powershell
python test_scraper.py "https://example.com/job-posting-url"
```

The command prints the fields that will go into the tracker, including company, title, location, work type, salary, and source.

Example result:

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

## Start The Local App

```powershell
python scraper\app.py
```

Open this address after the server starts:

```text
http://127.0.0.1:5000
```

On Windows, double-click `Open_Linc_Beta.vbs` to start the local beta at `http://127.0.0.1:5050` without typing a command.

## Test The API Endpoint

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/scrape -Method Post -ContentType "application/json" -Body '{"url":"https://example.com/job-posting-url"}'
```

## Export Jobs To Excel

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:5000/export -Method Post -ContentType "application/json" -Body '[{"company":"ACME","job_title":"Engineer","job_link":"https://example.com/job"}]' -OutFile jobs.xlsx
```

## Update A Test Workbook

Test with the ready-made file at `templates/joblink_tracker_template.xlsx` or a copy of your own tracker. Keep your personal workbook untouched until you are comfortable with the result.

```powershell
python process_excel_links.py "path\to\copied_tracker.xlsm"
```
