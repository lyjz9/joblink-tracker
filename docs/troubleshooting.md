# Troubleshooting

## Playwright Browser Is Missing

Run:

```powershell
python -m playwright install chromium
```

## A Job Board Blocks Scraping

Use a direct company career page when possible. If you can open the blocked page yourself, use the Chrome extension in `browser_extension/joblink_capture`, then load the captured job in the web beta.

## Monster Does Not Work

Use the employer/company job page that Monster opens or links to. Monster search pages and many Monster job-detail pages are intentionally treated as limited inputs.

## Excel Tracker Will Not Update

Close the workbook in Excel before selecting `Update tracker`. If the browser cannot save over the selected workbook, JobLink downloads an updated copy instead.

## A Row Says Review

Review means one or more fields are missing, suspicious, low-confidence, or blocked by the source site. Check the review reason, edit the row, retry extraction, or save the problem row with the flag button.

## Browser Capture Looks Wrong

Make sure the full job posting is visible before capture. Finish any human check first, scroll enough for the page to load, then capture again. Captured rows may include suggested values under fields; select the best one or edit manually.
